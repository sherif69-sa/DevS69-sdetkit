# Operational maturity v2 rollout

This page is the practical rollout guide for the maturity-v2 additions.

## New commands

```bash
python scripts/legacy_burndown.py --format json
python scripts/adoption_scorecard.py --format json
python scripts/check_adoption_scorecard_v2_contract.py --format json
python scripts/check_observability_v2_contract.py --format json
```

## CI wiring (`ci.sh`)

`ci.sh` now executes a maturity-v2 flow in both `quick` and `all` modes:

1. generate legacy analyzer JSON
2. generate burn-down JSON/MD/CSV
3. generate scorecard v2 JSON
4. validate scorecard v2 contract

## Environment knobs

Observability freshness thresholds:

- global: `SDETKIT_OBSERVABILITY_STALE_SECONDS`
- per artifact: `SDETKIT_OBSERVABILITY_STALE_<ARTIFACT_KEY>_SECONDS`

## Compatibility

- Existing stable CLI/API routes are unchanged.
- New contracts/fields are additive and can be gradually adopted.
