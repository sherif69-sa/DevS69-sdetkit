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
