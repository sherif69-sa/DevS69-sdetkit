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

Use `bash premium-gate.sh` locally and in CI. It runs quality, explicit ruff checks, CI, doctor (ASCII + JSON), full maintenance checks, baseline-aware security triage, security SARIF export, control-plane ops, and evidence pack generation.

The script now also emits **real-time step recommendations**, writes per-step logs under `.sdetkit/out/`, and runs a top-level connector intelligence engine (`python3 -m sdetkit.premium_gate_engine --double-check --min-score 70 --auto-fix --fix-root .`) that unifies step logs, doctor, maintenance, and security triage artifacts into one scored control-plane summary with warnings, hotspot ranking, and prioritized recommendations.


## Premium operating visualization

<div align="center">
  <p><strong>From checks → learning DB → applied remediation</strong></p>
</div>

<table>
  <tr>
    <td><strong>Step</strong></td>
    <td><strong>Input</strong></td>
    <td><strong>Output</strong></td>
  </tr>
  <tr>
    <td>Analyze</td>
    <td>doctor / maintenance / security artifacts + step logs</td>
    <td>warnings, recommendations, score, hotspots</td>
  </tr>
  <tr>
    <td>Learn</td>
    <td>recommendations + commit metadata</td>
    <td><code>premium-insights.db</code> history and guideline rows</td>
  </tr>
  <tr>
    <td>Apply</td>
    <td>current warnings + active guidelines</td>
    <td>learned-guideline recommendations + manual fix plan actions</td>
  </tr>
</table>

Live visualization reference: <a href="https://sherif69-sa.github.io/DevS69-sdetkit/">https://sherif69-sa.github.io/DevS69-sdetkit/</a>

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
