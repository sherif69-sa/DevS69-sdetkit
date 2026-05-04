# Mission Control

Mission Control is the canonical release-confidence evidence bundle for SDETKit.

Use it when you want one deterministic operator-facing starting point before running the deeper gates, diagnostics, review, and readiness commands.

```bash
python -m sdetkit mission-control run --out-dir build/mission-control
```

The command writes:

```text
build/mission-control/mission-control.json
build/mission-control/mission-control.md
```

The JSON bundle contains the schema version, repository identity, decision, risk band, workflow steps, findings, artifact index, and recommended next actions.

```bash
python -m sdetkit mission-control summarize --bundle build/mission-control/mission-control.json
```

The first Mission Control release is intentionally lightweight. It creates a stable evidence contract and points operators to the existing public release-confidence surfaces:

```text
gate fast
gate release
doctor
review
readiness
```

The release-room step is listed as a planned future public surface so the bundle can represent the full operator path before that command is promoted.

## Executable mode

Use `--execute` when you want Mission Control to run the lightweight public gates and capture their stdout/stderr as bundle artifacts.

```bash
python -m sdetkit mission-control run --execute --out-dir build/mission-control
```

By default executable mode runs:

```text
gate fast
doctor
readiness
```

Use `--include-release` when the stricter release gate should also be executed and archived:

```bash
python -m sdetkit mission-control run --execute --include-release --out-dir build/mission-control
```

When an executed step fails, the bundle records the failing return code, keeps the step output files, sets `ok` to false, and returns `NO_SHIP`.

## Run ledger

Each run appends a compact JSONL record to the local Mission Control ledger:

```text
.sdetkit/runs/mission-control-runs.jsonl
```

The ledger keeps the run id, timestamp, repository, branch, commit, mode, decision, risk band, step counts, and artifact directory. Use it to track release-confidence history without needing a remote service.

Use `--ledger-path` when you want the ledger somewhere else:

```bash
python -m sdetkit mission-control run --ledger-path build/mission-control-runs.jsonl
```

Use `--no-ledger` for one-off smoke runs that should not append history:

```bash
python -m sdetkit mission-control run --execute --no-ledger
```

## History summary

Use `history` to summarize a Mission Control JSONL run ledger without starting a server or database.

```bash
python -m sdetkit mission-control history --ledger .sdetkit/runs/mission-control-runs.jsonl
```

The text summary reports run counts, decision counts, the latest decision and risk band, failed-run rate, and the most common failed step when matching bundle artifacts are still available.

Use JSON output for automation:

```bash
python -m sdetkit mission-control history --ledger .sdetkit/runs/mission-control-runs.jsonl --format json
```

## Report brief

Use `report` to turn a Mission Control bundle into a Markdown release brief.

```bash
python -m sdetkit mission-control report   --bundle build/mission-control/mission-control.json   --out build/mission-control/report.md
```

Add `--history` to include ledger trend context in the same brief:

```bash
python -m sdetkit mission-control report   --bundle build/mission-control/mission-control.json   --history .sdetkit/runs/mission-control-runs.jsonl   --out build/mission-control/report.md
```

The report includes the executive decision, risk band, execution counts, step outcomes, findings, history summary, next actions, and artifact paths.

## Doctor Cortex

Mission Control can collect the public Doctor Cortex summaries during a run:

```bash
python -m sdetkit mission-control run --doctor-cortex --out-dir build/mission-control
```

The bundle records a `doctor_cortex` summary with diagnosis status, diagnosis count, prescription status, and prescription count. It also writes public-safe Doctor Cortex JSON artifacts in the Mission Control output directory.

Mission Control stores only summary fields in the main bundle. Raw doctor evidence and raw fix text remain outside the Mission Control bundle.

## Doctor Cortex trend

Doctor Cortex trend can summarize diagnosis and prescription counts across a Mission Control ledger:

```bash
python -m sdetkit.mission_control_cortex_trend \
  --ledger-path .sdetkit/runs/mission-control-runs.jsonl \
  --format md \
  --out build/doctor-cortex-trend.md
```

The trend report is summary-only and redacts ledger and artifact paths.

CLI and file output are public projections: they omit run ids, timestamps, ledger paths, artifact paths, and sample rows while keeping counts, statuses, and trend direction.
