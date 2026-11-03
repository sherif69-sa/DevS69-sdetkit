"""An exclusive lock on a sidecar file, for read-modify-write updates shared between processes.

Atomic writes keep a reader from seeing half a file; they do not stop two writers that read the
same old file from each dropping the other's change. Holding this lock across the read and the
write does.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def exclusive_lock(path: Path, *, timeout: float = 30.0, poll: float = 0.01) -> Iterator[None]:
    """Hold an exclusive lock on `path` (created if missing) for the `with` block."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while not _try_lock(fd):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"could not lock {path} within {timeout:g}s")
            time.sleep(poll)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
