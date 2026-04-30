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
NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q
```

## Coverage expectations

- Coverage mode defaults are staged in `quality.sh`:
  - `COV_MODE=standard` → fail-under `85` (default),
  - `COV_MODE=strict` → fail-under `95` (merge/release truth),
  - `COV_MODE=legacy` → fail-under `80` (temporary compatibility lane).
- `COV_FAIL_UNDER` still overrides mode defaults when explicitly set.
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

### Five-head contract

The five-head engine is a deterministic product signal, not an external AI call. It summarizes release posture across five named heads:

| Head | Meaning |
|---|---|
| `quality` | test, lint, doctor, and validation pressure |
| `reliability` | repeatability, workflow health, and runtime confidence |
| `security` | security/audit posture and policy gate pressure |
| `evidence` | supporting versus conflicting evidence quality |
| `delivery` | priority queue heat and release-readiness pressure |

`review --format operator-json` emits the same contract under top-level `five_heads` with schema version `sdetkit.review.five-heads.v1`. The premium gate renders the same posture for operator-facing markdown and step-index outputs. Status values are intended for deterministic triage and should be treated as release signals, not as a replacement for the underlying evidence artifacts.


1. **Head-1 Foundation & Quality** (`bash quality.sh`)
2. **Head-2 Source Truth & Style** (ruff format/lint)
3. **Head-3 Operational Confidence** (CI + doctor + maintenance + integration topology contract + ops profile)
4. **Head-4 Security & Compliance** (SARIF scan + baseline-aware triage + evidence pack)
5. **Head-5 Intelligence Brain** (`python3 -m sdetkit.premium_gate_engine`)

The script emits:

- per-step logs under `.sdetkit/out/premium-gate.*.log`
- a machine ledger: `.sdetkit/out/premium-step-results.ndjson`
- a structured five-head index: `.sdetkit/out/premium-step-index.json`
- integration topology artifact: `.sdetkit/out/integration-topology.json`
- premium engine summary: `.sdetkit/out/premium-summary.json`
- smart remediation logs when the engine auto-runs repo scripts: `.sdetkit/out/premium-autofix.*.log`

Useful flags:

- `--mode full|fast|engine-only` (`fast` = smoke confidence only, `full` = pre-merge verification)
- `--continue-on-error` (collect all failures in one run)
- `--engine-min-score <int>`
- `--out-dir <path>`
- `--ops-jobs <int>`
- `--no-auto-run-scripts` to keep the engine in analysis-only mode
- `--script-catalog <path>` to load extra repo-specific remediation scripts
- `SDETKIT_PREMIUM_TOPOLOGY_PROFILE=<path>` to override the topology profile used by the Head-3 topology contract step

Examples:

```bash
bash quality.sh ci       # fast/smoke confidence while iterating
bash quality.sh verify   # full verification before merge
bash premium-gate.sh --mode full
bash premium-gate.sh --mode full --continue-on-error
bash premium-gate.sh --mode fast --engine-min-score 75
bash premium-gate.sh --mode full --no-auto-run-scripts
bash premium-gate.sh --mode engine-only --out-dir .sdetkit/out
```

## Smart remediation loop

Head-5 now does more than report problems:

- it applies the existing safe security auto-fixes,
- it selects repo-safe remediation scripts based on the current warning mix,
- it refreshes artifacts like `doctor.json`, `maintenance.json`, and `security-check.json`,
- and it records a pre/post score delta in `premium-summary.json`.

To use the smart script lane, you can automatically trigger:

- `sdetkit gate fast --fix-only` when doctor/style/quality drift is detected,
- `sdetkit doctor --json --out ...` to refresh doctor evidence after fixes,
- `sdetkit maintenance --mode full --fix --format json --out ...` for maintenance drift,
- and `tools/triage.py --mode security ... --tee ...` to rebuild the baseline-aware security artifact after security auto-fixes.

The engine can also ingest a repo-local JSON catalog at `.sdetkit/premium-remediation-scripts.json` (or a custom path passed via `--script-catalog` / `SDETKIT_PREMIUM_SCRIPT_CATALOG`). That lets maintainers register additional safe fix commands with trigger conditions such as failed steps, warning sources, and post-autofix follow-up runs without hard-coding every workflow into the engine.


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
