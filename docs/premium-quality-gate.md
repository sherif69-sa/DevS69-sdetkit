# Premium Quality Gate Guidelines

This guide defines the **premium bar** for contributions in this repository.

## Core principle

Every change should be:

1. **Correct** (tests prove behavior),
2. **Safe** (security + dependency checks),
3. **Maintainable** (readable code, docs, and changelog quality),
4. **Operationally clear** (CI output and PR comments are actionable).

## Required local checks before opening a PR

Run these from repo root:

```bash
python -m ruff format --check .
python -m pre_commit run -a
bash quality.sh cov
python -m build
python -m twine check dist/*
mkdocs build
```

## Coverage expectations

- The repository-wide gate is controlled by `COV_FAIL_UNDER`.
- For premium quality, prioritize adding tests in low-coverage modules before adding new features.
- If behavior changes, include at least one failing-path test and one happy-path test.

## PR checklist (premium)

- [ ] Clear summary of what changed and why.
- [ ] Risks/edge cases called out.
- [ ] Tests added/updated with meaningful assertions.
- [ ] Docs updated for user-facing behavior.
- [ ] Changelog updated when behavior changed.
- [ ] CI and quality gates green.

## Bot helpers available

The repository supports helper comment commands on PRs:

- `/doctor` — run doctor checks and return a report.
- `/check` — run validation checks.
- `/quality` — run full coverage gate (`bash quality.sh cov`) and report coverage.
- `/hint` — post premium guideline hints and high-impact next actions.

Use these commands to quickly diagnose PR quality issues and unblock reviews.

## One-command premium gate

Use `bash premium-gate.sh` locally and in CI. The gate is now a self-contained **five-head engine** with explicit phases and runtime telemetry:

1. **Head-1 Foundation & Quality** (`bash quality.sh`)
2. **Head-2 Source Truth & Style** (ruff format/lint)
3. **Head-3 Operational Confidence** (CI + doctor + maintenance + ops profile)
4. **Head-4 Security & Compliance** (SARIF scan + baseline-aware triage + evidence pack)
5. **Head-5 Intelligence Brain** (`python3 -m sdetkit.premium_gate_engine`)

The script emits:

- per-step logs under `.sdetkit/out/premium-gate.*.log`
- a machine ledger: `.sdetkit/out/premium-step-results.ndjson`
- a structured five-head index: `.sdetkit/out/premium-step-index.json`
- premium engine summary: `.sdetkit/out/premium-summary.json`

Useful flags:

- `--mode full|fast|engine-only`
- `--continue-on-error` (collect all failures in one run)
- `--engine-min-score <int>`
- `--out-dir <path>`
- `--ops-jobs <int>`

Examples:

```bash
bash premium-gate.sh --mode full
bash premium-gate.sh --mode full --continue-on-error
bash premium-gate.sh --mode fast --engine-min-score 75
bash premium-gate.sh --mode engine-only --out-dir .sdetkit/out
```


## Local insights API (editable guideline reference + commit learning)

The premium engine can now run a local API that stores guideline knowledge and per-commit learning in a SQLite database:

```bash
python3 -m sdetkit.premium_gate_engine \
  --out-dir .sdetkit/out \
  --db-path .sdetkit/out/premium-insights.db \
  --serve-api --host 127.0.0.1 --port 8799
```

Key endpoints:

- `GET /health`
- `GET /guidelines?active=1&limit=100`
- `POST /guidelines` (add/editable guideline references)
- `PUT /guidelines/{id}` (update guideline content)
- `GET /analyze` (collect current gate signals + persist a run snapshot)
- `POST /learn-commit` (record commit metadata for self-learning history)

For non-server runs, pass `--learn-db --learn-commit` so every premium gate execution appends the current run and commit context to the insights database.
