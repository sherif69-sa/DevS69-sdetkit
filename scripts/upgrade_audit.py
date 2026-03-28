#!/usr/bin/env python3
"""Audit dependency manifests and report upgrade planning signals."""

from sdetkit.upgrade_audit import main

if __name__ == "main_":
    raise SystemExit(main())
