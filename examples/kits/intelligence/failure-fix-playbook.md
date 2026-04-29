# Failure Fix Playbook

Use this flow to start fixing failures from `failure-action-plan.json`.

## 1) Pick the top-ranked issue
- Open `examples/kits/intelligence/failure-action-plan.json`.
- Start with the lowest `rank` value (highest priority).

## 2) Reproduce the issue
- Run the `reproduce_command` for the selected action.
- Capture logs and any stack traces.

## 3) Implement fix safely
- Keep changes scoped to the component mapped by the failing test.
- Add/adjust test coverage for the identified bug path.
- For payment/network issues, enforce idempotency and bounded retries.

## 4) Verify resolution
- Run `verify_command` at least 3 times.
- Mark item complete only when all runs pass and no new regressions appear.

## 5) Update status
- Change `status` in the action item (`planned` -> `in_progress` -> `blocked`/`done`).
- Add short notes in commit message referencing `issue_id`.

## Suggested immediate order
1. `ISSUE-001` (`P1`) - API retry timeout stabilization.
2. `ISSUE-002` (`P2`) - checkout connection reset hardening.

## 6) Run the unified autofix workflow
Use the automation script to execute all planned failure reproductions and emit one combined report:

```bash
python scripts/failure_autofix_workflow.py --max-actions 5
```

The report is written to:
- `examples/kits/intelligence/failure-autofix-report.json`

Use this report to:
- identify failing reproductions quickly,
- map each issue to likely code areas,
- apply targeted autofix suggestions,
- and re-run security/verification gates before merge.
