# Operational workflow runbook

Use this runbook to execute the live Phase 1 workflow and produce operational artifacts.

## One-command execution

Run the complete operational workflow:

- `make operations-workflow`

This command runs the execution lane, validates the flow contract, computes the gate decision, and writes the executive report.

## Run order

1. `make operations-baseline`
2. `python scripts/phase1_status_report.py --format json --out build/phase1-baseline/phase1-status.json`
3. `make operations-next-action`
4. `make operations-snapshot`
5. `make operations-dashboard`
6. `make operations-weekly-pack`
7. `make operations-control-loop`
8. `python scripts/check_phase1_baseline_summary_contract.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json --require-logs`
9. `python scripts/phase1_completion_gate.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json`

Or run the full closeout path in one command:

- `make operations-complete`

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

`make operations-status` prints what is accomplished and what is not yet complete.
`make operations-next-action` emits required actions when blockers exist, and advisory actions when closeout is complete.

## Workflow retention policy

The repository keeps the Phase 1 workflow and its execution artifacts as the source of truth.

1. Keep baseline artifacts for audit history; do not delete run evidence.
2. Keep `make operations-status` and `make operations-next-action` as the operational source of truth.
3. Treat non-blocking checks (`ruff`, `pytest`) as advisory remediation until stabilized.

## Suggested evidence bundle for phase closeout

- `build/phase1-baseline/phase1-baseline-summary.json`
- `build/phase1-baseline/phase1-baseline-summary.md`
- completion-gate JSON output
- key remediation notes (if any)
