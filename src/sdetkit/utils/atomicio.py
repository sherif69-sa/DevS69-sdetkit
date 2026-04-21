import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


def atomic_write_text(
    path: Path, text: str, before_replace: Callable[[Path, Path], None] | None = None
) -> None:
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

        if before_replace is not None:
            before_replace(tmp_path, path)

        os.replace(tmp_path, path)

        try:
            dir_fd = os.open(str(parent), os.O_DIRECTORY)
        except Exception:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as exc:
            # Best-effort cleanup: failure to remove temporary file is non-fatal.
            logging.debug("Failed to remove temporary file %s: %s", tmp_path, exc)


def atomic_write_bytes(
    path: Path, data: bytes, before_replace: Callable[[Path, Path], None] | None = None
) -> None:
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if before_replace is not None:
            before_replace(tmp_path, path)

        os.replace(tmp_path, path)

        try:
            dir_fd = os.open(str(parent), os.O_DIRECTORY)
        except Exception:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as exc:
            # Best-effort cleanup: failure to remove temporary file is non-fatal.
            logging.debug("Failed to remove temporary file %s: %s", tmp_path, exc)


def canonical_json_dumps(payload: Any, *, indent: int | None = 2) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=indent) + "\n"


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
