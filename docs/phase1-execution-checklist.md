# Phase 1 execution checklist and closeout cleanup

Use this checklist to execute and close Phase 1 before moving to later phases.

## Run order

1. `make phase1-baseline`
2. `python scripts/phase1_status_report.py --format json --out build/phase1-baseline/phase1-status.json`
3. `make phase1-next`
4. `make phase1-ops-snapshot`
5. `make phase1-dashboard`
6. `make phase1-weekly-pack`
7. `make phase1-control-loop`
8. `python scripts/check_phase1_baseline_summary_contract.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json --require-logs`
9. `python scripts/phase1_completion_gate.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json`

Or run the full closeout path in one command:

- `make phase1-complete`

## Phase 1 definition of done (DoD)

Required checks must be green in the baseline summary:

- `doctor`
- `enterprise_contracts`
- `primary_docs_map`

Allowlisted non-blocking checks (can fail temporarily during hardening):

- `ruff`
- `pytest`

The completion gate enforces this policy by default.
Optional checks (`ruff`, `pytest`) are tracked and reported, but are non-blocking for Phase 1 closeout by default.

`make phase1-status` prints what is accomplished and what is not yet complete.
`make phase1-next` emits required actions when blockers exist, and advisory actions when closeout is complete.

## After Phase 1 completes: cleanup the plan

Immediately simplify the phased plan so execution stays focused:

1. Mark Phase 1 status as complete in your weekly status notes.
2. Archive outdated Phase 1 TODO bullets that are no longer actionable.
3. Keep only Phase 2+ next actions in the operator daily checklist.
4. Keep baseline artifacts for audit history; do not delete run evidence.

## Suggested evidence bundle for phase closeout

- `build/phase1-baseline/phase1-baseline-summary.json`
- `build/phase1-baseline/phase1-baseline-summary.md`
- completion-gate JSON output
- key remediation notes (if any)
