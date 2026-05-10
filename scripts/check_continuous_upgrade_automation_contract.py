#!/usr/bin/env python3
from __future__ import annotations

import argparse

from continuous_upgrade_cycle_contract_lib import run_cycle_contract_check

CYCLE = 9


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Cycle 9 continuous upgrade contract")
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-evidence", action="store_true")
    ns = parser.parse_args()
    return run_cycle_contract_check(CYCLE, root=ns.root, skip_evidence=bool(ns.skip_evidence))


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
