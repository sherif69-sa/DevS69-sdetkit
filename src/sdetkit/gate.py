"""Expose gates implementation as `sdetkit.gate`."""

from __future__ import annotations

import sys

from sdetkit.gates import gate as _gate

sys.modules[__name__] = _gate
