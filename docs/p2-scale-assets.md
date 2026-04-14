# P2 scale assets

These assets operationalize the P2 backlog from the CTO full-package plan.

## Integration adapter for portfolio consumers

- Script: `scripts/build_portfolio_scorecard.py`
- Input: normalized records (JSON list or JSONL)
- Output: aggregated scorecard JSON for dashboard/export consumers

Example:

```bash
python scripts/build_portfolio_scorecard.py \
  --in docs/artifacts/top-tier-benchmark-pack/release-trend-benchmark-sample.jsonl \
  --out build/portfolio-scorecard.json
```

## Benchmark dataset for release trend analysis

- Dataset: `docs/artifacts/top-tier-benchmark-pack/release-trend-benchmark-sample.jsonl`
- Example output: `docs/artifacts/top-tier-benchmark-pack/portfolio-scorecard-sample.json`

## Partner-ready implementation pack

- Pack doc: `docs/artifacts/top-tier-partner-implementation-pack/partner-implementation-pack.md`
- Includes discovery worksheet scope, pilot plan expectations, and handoff criteria.
