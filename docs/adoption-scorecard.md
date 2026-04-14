# Adoption scorecard

This scorecard gives one compact maturity snapshot from existing governance artifacts.

## v2 model (weighted + graded)

Scorecard v2 keeps backward-compatible top-level fields (`score`, `band`, `dimensions`) and adds graded/weighted details:

- **onboarding**: artifact freshness + canonical pass signal
- **release**: current release gate + trend over N runs
- **ops**: legacy density + reduction trend vs baseline
- **quality**: canonical drift guard + test signal

`dimensions` remains a legacy compatibility view (`0..25`).
`graded_dimensions` is the v2 score (`0..100`) per dimension with explicit `weights`.

## Generate scorecard

```bash
python scripts/adoption_scorecard.py --format json
```

Validate v2 contract:

```bash
python scripts/check_adoption_scorecard_v2_contract.py --format json
```

Default inputs:

- `.sdetkit/out/golden-path-health.json`
- `.sdetkit/out/canonical-path-drift.json`
- `.sdetkit/out/legacy-command-analyzer.json`

Optional trend/signal inputs:

- `--release-history <json>` with `{"series": [...]}` scores
- `--legacy-baseline <json>` previous legacy analyzer output
- `--test-signal <json>` with `pass_rate` (`0..1` or `0..100`)

Default output:

- `.sdetkit/out/adoption-scorecard.json`

## Output contract (v2)

- `schema_version`
- `score`
- `band` (`early`, `developing`, `strong`, `excellent`)
- `dimensions` (`onboarding`, `quality`, `release`, `ops`) compatibility view (`0..25`)
- `graded_dimensions` (`onboarding`, `quality`, `release`, `ops`) v2 graded view (`0..100`)
- `weights` normalized weighting map
- `signals` per-dimension input signal breakdown
