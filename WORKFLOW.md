# Single-Operator Workflow (SDETKit)

The maintained operator workflow lives in [`docs/project/operator-workflow.md`](docs/project/operator-workflow.md).

This root pointer is kept for compatibility with existing workflow-contract checks.

## Zero-friction startup (run this first)

```bash
python scripts/start_session.py --size <small|medium|large> --run
```

## Tier 1 — Daily / PR lane (default)

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

## Tier 2 — Weekly health lane (scheduled)

```bash
PYTHONPATH=src pytest -q
bash quality.sh cov
ruff check .
mutmut results
```

## Tier 3 — Release-day / advanced lane (opt-in)

```bash
python -m sdetkit review . --no-workspace --format operator-json
```

## Default ignore list (to reduce context switching)

Do not explore archive/history-heavy docs unless the task explicitly needs them.

## Quick run checklist

1. Run the Tier 1 gate path.
2. Inspect artifacts before raw logs.
3. Escalate only when the diagnostic lane needs more evidence.

## PR clean policy (every PR)

```bash
python scripts/pr_clean.py --size <small|medium|large> --run
cat .sdetkit/pr-clean-report.json
```

## Security + quality + review guard

```bash
python scripts/security_quality_review_guard.py --run
```

## Interactive error triage assistant

```bash
python scripts/review_error_assistant.py --format json < ci-fail.log
```
