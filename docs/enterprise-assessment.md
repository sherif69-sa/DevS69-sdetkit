# Enterprise assessment (`sdetkit enterprise-assessment`)

`enterprise-assessment` provides a high-signal company-readiness assessment with a weighted score, operational metrics, and a prioritized boost plan.

## Why this command exists

Use this when leadership asks:
- what is already strong,
- what is blocking full-package release confidence,
- what to do next in strict priority order.

## Quick start

```bash
python -m sdetkit enterprise-assessment --format text
python -m sdetkit enterprise-assessment --format json
python -m sdetkit enterprise-assessment --format markdown
```

## Strict mode

```bash
python -m sdetkit enterprise-assessment --format json --strict
python -m sdetkit enterprise-assessment --format json --fail-on-risk-band medium
```

Strict mode exits non-zero until tier is `enterprise-ready`.
Risk-band policy can additionally fail builds when risk remains medium/high.

## Emit report pack

```bash
python -m sdetkit enterprise-assessment \
  --format json \
  --emit-pack-dir docs/artifacts/enterprise-assessment-pack
```

Artifacts:
- `enterprise-assessment-summary.json`
- `enterprise-assessment-report.md`

## Execute mode (recommended for full assessment runs)

```bash
python -m sdetkit enterprise-assessment \
  --format json \
  --execute \
  --evidence-dir docs/artifacts/enterprise-assessment-pack/evidence
```

`--execute` runs these commands and captures command-level pass/fail evidence:

- `python -m sdetkit doctor --format json`
- `python -m sdetkit production-readiness --format json`
- `python -m sdetkit release-readiness --format json`
- `python -m sdetkit enterprise-readiness --format json`

Evidence outputs:
- `enterprise-assessment-execution-summary.json`
- one per-command log (`01-doctor.log`, etc.)

## Baseline trend comparison

Use a previous summary artifact to compute score movement:

```bash
python -m sdetkit enterprise-assessment \
  --format json \
  --baseline-summary docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json
```

The output includes:
- `trend.status` (`improved`, `flat`, `declined`, `no-baseline`)
- `trend.score_delta`
- previous score when baseline is provided

## Production profile (recommended for release pipelines)

```bash
python -m sdetkit enterprise-assessment --format json --production-profile
```

`--production-profile` applies strong defaults:
- enables `--execute` and `--strict`,
- enables `--fail-on-risk-band medium`,
- emits pack to `docs/artifacts/enterprise-assessment-pack`,
- writes evidence logs to `docs/artifacts/enterprise-assessment-pack/evidence`.

Validate emitted summary contract:

```bash
python scripts/check_enterprise_assessment_contract.py \
  --summary docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json \
  --format json
```

## Scoring model

The command evaluates weighted checks across:

- canonical path clarity,
- release controls,
- security governance,
- quality automation,
- commercial packaging,
- operating model documentation.

It also emits:

- inventory metrics (`modules_count`, `tests_count`, `workflows_count`, `docs_markdown_count`),
- a priority boost plan from failed checks and scale-risk thresholds,
- an action board (`owner_team`, `response_sla_hours`, priority queue),
- an upgrade contract (`gate_decision`, `risk_score`, `risk_band`, `sla_review_hours`, top now/next actions),
- production metadata contract (`schema_version`, `generated_at_utc`, `contract_id`).
