"""Compatibility wrapper for historical `sdetkit.gate` imports."""

from sdetkit.gates import gate as _gate

globals().update({k: v for k, v in _gate.__dict__.items() if not k.startswith('__')})
