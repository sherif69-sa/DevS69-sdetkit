"""`utils.filelock.exclusive_lock`: one holder at a time, across processes."""

from __future__ import annotations

import multiprocessing as mp
import time
from pathlib import Path

import pytest

from sdetkit.utils.filelock import exclusive_lock


def _hold(lock: str, held: str, release: str) -> None:
    with exclusive_lock(Path(lock)):
        Path(held).touch()
        deadline = time.monotonic() + 20
        while not Path(release).exists() and time.monotonic() < deadline:
            time.sleep(0.01)


def test_a_second_holder_waits_and_then_times_out(tmp_path: Path) -> None:
    lock, held, release = tmp_path / "x.lock", tmp_path / "held", tmp_path / "release"
    holder = mp.get_context("spawn").Process(
        target=_hold, args=(str(lock), str(held), str(release))
    )
    holder.start()
    try:
        deadline = time.monotonic() + 30
        while not held.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert held.exists(), "the other process never took the lock"

        with pytest.raises(TimeoutError, match="could not lock"):
            with exclusive_lock(lock, timeout=0.2):
                pass
    finally:
        release.touch()
        holder.join(timeout=30)

    # Released: the lock can be taken again, and the lock file is reused.
    with exclusive_lock(lock, timeout=5):
        assert lock.exists()


def test_the_lock_is_released_when_the_block_raises(tmp_path: Path) -> None:
    lock = tmp_path / "nested" / "x.lock"

    with pytest.raises(RuntimeError):
        with exclusive_lock(lock):
            raise RuntimeError("boom")

    with exclusive_lock(lock, timeout=1):
        pass
