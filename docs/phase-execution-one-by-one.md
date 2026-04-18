# One-by-one phase execution (operator guide)

If you already completed planning for all 6 phases, execute only one phase at a time with this rule:

1. Finish current phase exit criteria.
2. Publish evidence artifacts.
3. Freeze phase status.
4. Start next phase kickoff.

## Current focus: Phase 1

Use this exact sequence for Phase 1 operations:

```bash
make phase-current
make phase1-baseline
make phase1-status
make phase1-next
make phase1-ops-snapshot
make phase1-dashboard
make phase1-weekly-pack
make phase1-control-loop
make phase1-run-all
make phase1-artifact-set
make phase1-telemetry
make phase1-finish-signal
make phase1-next-pass
make phase1-blocker-register
make phase1-do-it
make phase1-gate-phase2
make phase1-executive-report
make phase1-retire-plan
make phase1-complete
make phase1-closeout
```

If you want machine-readable output for automation:

```bash
make phase-current-json
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

For each phase closeout, record:

- Phase id and name
- Date
- Exit criteria pass/fail status
- Blocking risks
- Canonical artifacts produced
- Go/No-go decision for next phase

Keeping this format constant makes trend reporting and investor review easier.


## After Phase 1 is completed

Run `make phase1-closeout` to archive the previous strategic plan snapshot and remove Phase 1 from the active phase queue, then advance `current_phase` to Phase 2.

Use `make phase1-ops-snapshot` each week to publish:

- progress percent (accomplished vs remaining),
- hard blockers,
- ranked quality debt register,
- recommended next actions.


For one-command orchestration, run `make phase1-run-all` (or `python scripts/phase1_run_all.py --include-closeout`).


Use `make phase1-telemetry` after `phase1-run-all` to track run timing drift, pass-rate, and blocker categories over time.


Use `make phase1-artifact-set` to enforce that all Phase 1 JSON/Markdown artifacts exist before closeout.


Use `make phase1-finish-signal` to answer if Phase 1 is early / in_progress / near_finish / complete.


If you want to run the full evidence pipeline now, use `make phase1-do-it`.


Use `make phase1-next-pass` to generate a concise remediation card for the immediate next pass.


Use `make phase1-blocker-register` to produce a prioritized JSON/CSV blocker list for assignment tracking.


After Phase 1 is truly complete, run `make phase1-retire-plan` to archive Phase 1 planning state and keep flow-first operations as the repo default.


Use `make phase1-gate-phase2` to decide if Phase 2 can start, based on finish signal + artifact contract.


Use `make phase1-executive-report` to produce a one-page status for leadership handoff and phase decision meetings.
