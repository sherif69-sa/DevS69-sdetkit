# Portfolio reporting recipe (multi-repo)

Use this recipe to aggregate release-confidence evidence across repositories into one portfolio-level view.

## Objective

Create a weekly board that answers:

1. Which repos are release-ready?
2. Where is risk trending up?
3. Which teams need intervention this week?

## Inputs

Per repository, collect:

- `build/gate-fast.json`
- `build/release-preflight.json`
- `build/doctor.json`
- repository metadata (team, service tier, lane)

## Output contract (versioned)

The scorecard output follows the portfolio aggregate contract:

- Schema reference: [`docs/portfolio-aggregation-schema.md`](portfolio-aggregation-schema.md)
- Script: `python scripts/build_portfolio_scorecard.py`

### Top-level required fields

- `schema_name`
- `schema_version`
- `generated_at`
- `window.start_date`
- `window.end_date`
- `totals`
- `repos`

### `repos[]` required fields (minimum)

- `repo_id`
- `risk_tier`
- `release_confidence_ok`
- `gate_fast_ok`
- `gate_release_ok`
- `doctor_ok`
- `evidence_window_end`

## Input record example (normalized)

```json
{
  "repo": "service-a",
  "team": "checkout",
  "lane": "scale",
  "timestamp": "2026-04-14T00:00:00Z",
  "gate_fast_ok": true,
  "gate_release_ok": true,
  "doctor_ok": true,
  "failed_steps_count": 0
}
```

## Build command

```bash
python scripts/build_portfolio_scorecard.py \
  --in docs/artifacts/portfolio-input.jsonl \
  --out docs/artifacts/portfolio-scorecard-2026-04-17.json \
  --schema-version 1.0.0 \
  --window-start 2026-04-11 \
  --window-end 2026-04-17
```

## Aggregation rules

Risk tier thresholds:

- `low`: all three checks pass and failed steps = 0
- `medium`: partial failure without release-gate hard failure
- `high`: release gate fails or repeated failures (`failed_steps_count >= 2`)

## Weekly portfolio scorecard template

| Repo | Team | Lane | Gate fast | Gate release | Doctor | Failed steps | Risk |
|---|---|---|---|---|---|---:|---|
| service-a | checkout | scale | ✅ | ✅ | ✅ | 0 | low |
| service-b | growth | startup | ✅ | ❌ | ✅ | 2 | high |

## Portfolio roll-up metrics

- `repo_count_total`
- `repo_count_reporting`
- `high_risk_repo_count`
- `medium_risk_repo_count`
- `low_risk_repo_count`
- `release_gate_failure_rate_percent`

## Operating notes

- Keep one schema version per quarter unless breaking changes are required.
- Use a strict reporting cutoff (e.g., Friday 17:00 UTC).
- Flag missing data as `unknown` instead of implicitly passing.
- Attach the generated scorecard JSON to weekly leadership reviews.

## Worked sample artifacts

- Input sample: [`docs/artifacts/portfolio-input-sample-2026-04-17.jsonl`](artifacts/portfolio-input-sample-2026-04-17.jsonl)
- Output sample: [`docs/artifacts/portfolio-scorecard-sample-2026-04-17.json`](artifacts/portfolio-scorecard-sample-2026-04-17.json)

Use these files as a template for weekly portfolio board generation and review.

For the full end-to-end sample pipeline, run `make top-tier-reporting`.

Direct orchestrator option:

```bash
python scripts/build_top_tier_reporting_bundle.py \
  --input docs/artifacts/portfolio-input-sample-2026-04-17.jsonl \
  --out-dir docs/artifacts/top-tier-bundle \
  --window-start 2026-04-11 \
  --window-end 2026-04-17 \
  --generated-at 2026-04-17T10:00:00Z \
  --manifest-out docs/artifacts/top-tier-bundle-manifest-2026-04-17.json
```

CI automation option: `.github/workflows/top-tier-reporting-sample.yml`.

Bundle manifest example: [`docs/artifacts/top-tier-bundle-manifest-2026-04-17.json`](artifacts/top-tier-bundle-manifest-2026-04-17.json).

Bundle manifest check example: [`docs/artifacts/top-tier-bundle-manifest-check-2026-04-17.json`](artifacts/top-tier-bundle-manifest-check-2026-04-17.json).


## Cross-artifact consistency check

After generating KPI and portfolio outputs, run:

```bash
python scripts/check_top_tier_reporting_contract.py \
  --portfolio-scorecard docs/artifacts/portfolio-scorecard-sample-2026-04-17.json \
  --kpi-weekly docs/artifacts/kpi-weekly-from-portfolio-2026-04-17.json \
  --out docs/artifacts/top-tier-contract-check-2026-04-17.json
```

This validates KPI values against portfolio totals and sample sizes.


## Promotion helper

To copy bundle outputs to canonical sample artifact names:

```bash
python scripts/promote_top_tier_bundle.py --bundle-dir docs/artifacts/top-tier-bundle --date-tag 2026-04-17
```
