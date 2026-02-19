# Enterprise + regulated workflow

A governance-first landing page for organizations that need deterministic quality, policy evidence, and compliance-safe release controls.

## Who this is for

- Regulated engineering organizations with compliance, audit, or legal controls.
- Platform and quality teams supporting multiple repositories and business units.
- Security and GRC stakeholders needing repeatable evidence and change traceability.

## 15-minute enterprise baseline

Use this sequence to establish an enterprise guardrail baseline:

```bash
python -m sdetkit repo audit . --profile enterprise --format json
python -m sdetkit security report --format text
python -m sdetkit policy snapshot --output .sdetkit/day13-policy-snapshot.json
python -m pytest -q tests/test_enterprise_use_case.py tests/test_cli_help_lists_subcommands.py
python scripts/check_day13_enterprise_use_case_contract.py
```

## Governance operating cadence

1. Run `repo audit --profile enterprise` at the start of each sprint and before release freeze.
2. Run `security --strict` and `policy` for every release candidate.
3. Publish signed artifacts from these checks into your long-term evidence store.

## Compliance evidence controls

- **Separation of duties:** require review ownership split between platform and service teams.
- **Artifact retention:** archive JSON/markdown outputs for traceability and audit requests.
- **Policy drift detection:** fail PR checks when controls deviate from approved baselines.

## CI compliance lane recipe

Use this workflow to enforce Day 13 enterprise contract checks on every PR:

```yaml
name: enterprise-compliance-lane
on:
  pull_request:
  workflow_dispatch:

jobs:
  enterprise-compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit enterprise-use-case --format json --strict
      - run: python -m sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict
      - run: python scripts/check_day13_enterprise_use_case_contract.py
```

## KPI and control dashboard

Track these outcomes weekly:

- Policy violations by severity and mean time to resolution.
- Audit readiness score across repositories.
- Compliance check pass rate in PRs.
- Percentage of releases with complete evidence bundles.

## Automated evidence bundle

Generate and persist command outputs in one pass:

```bash
python -m sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict
```

This writes a structured `day13-execution-summary.json` and one per-command log file for audit-ready handoff.

## Rollout model across business units

1. Pilot with one regulated service and one shared platform repository.
2. Expand to all critical repositories with a policy baseline and CI lane.
3. Standardize quarterly audits using generated Day 13 artifacts.
