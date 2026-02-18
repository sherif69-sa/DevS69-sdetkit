from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_existing = os.environ.get("PYTHONPATH", "")
if _existing:
    if str(_SRC) not in _existing.split(os.pathsep):
        os.environ["PYTHONPATH"] = f"{_SRC}{os.pathsep}{_existing}"
else:
    os.environ["PYTHONPATH"] = str(_SRC)
