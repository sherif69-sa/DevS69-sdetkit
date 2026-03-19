#!/usr/bin/env python3
"""Audit dependency manifests and report upgrade planning signals."""

from __future__ import annotations

from sdetkit import upgrade_audit as _upgrade_audit

globals().update(_upgrade_audit.__dict__)
main = _upgrade_audit.main


if __name__ == "__main__":
    raise SystemExit(main())
