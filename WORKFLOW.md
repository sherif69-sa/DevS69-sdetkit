# Single-Operator Workflow (SDETKit)

This file is a focused operating guide for running this repository without context overload.

## Purpose

Use a strict tiered workflow so daily work stays centered on ship/no-ship confidence, while advanced and legacy surfaces remain opt-in.

Primary outcome: **know if a change is ready to ship**.

---

## Zero-friction startup (run this first)

```bash
python scripts/start_session.py --size small
```

Use `--run` when you want to execute the selected profile immediately:

```bash
python scripts/start_session.py --size <small|medium|large> --run
```

---

## Tier 1 — Daily / PR lane (default)

Run these first, in order:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

If a gate fails:
1. Inspect JSON artifacts first (`failed_steps`, `ok`, profile payloads).
2. Use raw logs only after artifact triage.

### Tier 1 ownership files

- `src/sdetkit/gate.py`
- `src/sdetkit/doctor.py`
- `src/sdetkit/cli.py`

---

## Tier 2 — Weekly health lane (scheduled)

Run once per week:

```bash
PYTHONPATH=src pytest -q
bash quality.sh cov
ruff check .
mutmut results
```

Track these 4 metrics weekly:
- test pass rate
- branch coverage
- lint violations
- mutation survivors

---

## Tier 3 — Release-day / advanced lane (opt-in)

Use only when needed:

- `python -m sdetkit review . --no-workspace --format operator-json`
- `python -m sdetkit kits list`

---

## Default ignore list (to reduce context switching)

Do **not** explore these unless the task explicitly needs them:

- hidden/legacy closeout lanes (`*-closeout`, transition-era commands)
- broad advanced families (`ops`, `agent`, deep playbook families)
- archive/history-heavy docs

---

## Quick run checklist

1. Run Tier 1 in order.
2. If failing, triage artifacts first.
3. Escalate to Tier 3 only when Tier 1 diagnosis is insufficient.
4. Run Tier 2 on weekly cadence.
---

## PR clean policy (every PR)

Before opening a PR, run a size-based profile so checks are right-sized but always clean:

```bash
python scripts/pr_clean.py --size small
python scripts/pr_clean.py --size medium
python scripts/pr_clean.py --size large
```

Execute checks for your chosen profile:

```bash
python scripts/pr_clean.py --size <small|medium|large> --run
```

Report artifact:

```bash
cat .sdetkit/pr-clean-report.json
```

Profile intent:
- **small**: ruff + format + gate fast
- **medium**: small + full pytest + gate release + review
- **large**: medium + doctor + coverage + review




## Security + quality + review guard

Run this before opening bigger PRs to enforce a single combined guardrail:

```bash
python scripts/security_quality_review_guard.py
python scripts/security_quality_review_guard.py --run
```


## Interactive error triage assistant

When CI/local failures happen frequently, pipe logs to the assistant for concrete remediation steps:

```bash
python scripts/review_error_assistant.py --format text < ci-fail.log
python scripts/review_error_assistant.py --format json < ci-fail.log
```
