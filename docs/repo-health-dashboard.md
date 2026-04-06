# Repo Health Dashboard

Use this page as a lightweight, repeatable checklist for weekly repository health reviews.

## Why this exists

A repo can feel "not good enough" even when quality tooling exists, because health signals are scattered.
This guide centralizes the minimum set of signals needed for steady improvement.

## Weekly command set

Run from repo root:

```bash
PYTHONPATH=src pytest -q
bash quality.sh cov
ruff check .
mutmut results
```

## Record these four metrics

1. **Test pass rate**
   - Source: `pytest` summary
   - Goal: maintain 100% pass on non-network test lane

2. **Branch coverage**
   - Source: `bash quality.sh cov`
   - Goal: trend upward or hold above agreed threshold

3. **Lint status**
   - Source: `ruff check .`
   - Goal: zero new violations

4. **Mutation survivors**
   - Source: `mutmut results`
   - Goal: reduce survivors in critical modules each week

## Suggested PR template snippet

Paste this into your PR description after running the weekly command set:

```text
Repo Health Snapshot
- Test pass rate: <value>
- Branch coverage: <value>
- Ruff violations: <value>
- Mutation survivors: <value>

Notes:
- <what improved>
- <what regressed>
- <next action>
```

## 30-day improvement rhythm

- **Week 1:** establish baseline and identify top 3 weak modules
- **Week 2:** add tests for weak branches and flaky behavior
- **Week 3:** kill high-impact mutation survivors
- **Week 4:** consolidate docs and remove stale repo artifacts

Consistency beats one-time cleanup. Track trends, not just snapshots.
