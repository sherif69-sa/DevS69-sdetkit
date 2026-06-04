# Sequential execution operator guide

If you already completed planning for all 6 phases, execute only one phase at a time with this rule:

1. Finish current phase exit criteria.
2. Publish evidence artifacts.
3. Freeze phase status.
4. Start next phase kickoff.

## Current focus: baseline

Use this exact sequence for baseline operations:

```bash
make operations-current
make operations-baseline
make operations-status
make operations-next-action
make operations-snapshot
make operations-dashboard
make operations-weekly-pack
make operations-control-loop
make operations-run-all
make operations-artifact-set
make operations-telemetry
make operations-readiness-signal
make operations-remediation-plan
make operations-blocker-register
make operations-run
make operations-flow-contract
make operations-quality-gate
make operations-executive-report
make operations-cleanup-plan
make operations-complete
make operations-finalize
```

If you want machine-readable output for automation:

```bash
make operations-current-json
```

## Phase completion contract

Before promoting a phase from active to complete:

- Canonical truth lane artifacts exist and are readable.
- Exit criteria are all explicitly marked pass.
- Remaining work is moved to either:
  - the next phase backlog, or
  - an expansion options backlog.

## Weekly operating cadence (recommended)

- **Monday:** Plan (scope, KPI, risks)
- **Wednesday:** Build + validate checkpoint
- **Friday:** Operationalize + expand backlog + phase status update

## Phase gate decision record template

For each phase completion report, record:

- Phase id and name
- Date
- Exit criteria pass/fail status
- Blocking risks
- Canonical artifacts produced
- Go/No-go decision for next phase

Keeping this format constant makes trend reporting and investor review easier.


## After baseline is completed

Run `make operations-finalize` to archive the previous strategic plan snapshot and remove baseline from the active phase queue, then advance `current_phase` to release readiness.

Use `make operations-snapshot` each week to publish:

- progress percent (accomplished vs remaining),
- hard blockers,
- ranked quality debt register,
- recommended next actions.


For one-command orchestration, run `make operations-run-all` (or `python scripts/baseline_run_all.py --include-completion report`).


Use `make operations-telemetry` after `baseline-run-all` to track run timing drift, pass-rate, and blocker categories over time.


Use `make operations-artifact-set` to enforce that all baseline JSON/Markdown artifacts exist before completion report.


Use `make operations-readiness-signal` to answer if baseline is early / in_progress / near_finish / complete.


If you want to run the full evidence pipeline now, use `make operations-run`.


Use `make operations-remediation-plan` to generate a concise remediation card for the immediate next pass.


Use `make operations-blocker-register` to produce a prioritized JSON/CSV blocker list for assignment tracking.


After baseline is truly complete, run `make operations-cleanup-plan` to archive baseline planning state and keep flow-first operations as the repo default.


Use `make operations-quality-gate` to decide if release readiness can start, based on finish signal + artifact contract.


Use `make operations-executive-report` to produce a one-page status for leadership handoff and phase decision meetings.


Use `make operations-flow-contract` to ensure the documented command path and Makefile targets stay in sync.
