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
