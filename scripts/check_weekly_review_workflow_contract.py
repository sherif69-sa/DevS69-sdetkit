"""Canonical contract checker entrypoint.

Legacy alias: scripts/check_weekly_review_workflow_contract.py
"""

from check_weekly_review_workflow_contract import main

if __name__ in {"__main__", "main_"}:
    raise SystemExit(main())
