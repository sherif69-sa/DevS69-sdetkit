# Top-tier reporting troubleshooting

Use this page when `make top-tier-reporting` fails or emitted artifacts look inconsistent.

## 1) Missing input sample file

**Symptom**
- Error like: `missing source artifact` or input file not found.

**Check**
```bash
ls docs/artifacts/portfolio-input-sample-*.jsonl
```

**Fix**
- Ensure `DATE_TAG` matches an existing input sample file.
- Example:
```bash
make top-tier-reporting DATE_TAG=2026-04-17
```

## 2) KPI contract check fails

**Symptom**
- `check_kpi_weekly_contract.py` returns non-zero.

**Check**
```bash
python scripts/check_kpi_weekly_contract.py \
  --schema docs/kpi-schema.v1.json \
  --payload docs/artifacts/kpi-weekly-from-portfolio-2026-04-17.json
```

**Fix**
- Rebuild KPI payload from portfolio artifact:
```bash
python scripts/build_kpi_weekly_snapshot.py \
  --portfolio-scorecard docs/artifacts/portfolio-scorecard-sample-2026-04-17.json \
  --out docs/artifacts/kpi-weekly-from-portfolio-2026-04-17.json \
  --week-ending 2026-04-17 \
  --program-status green \
  --rollback-count 0
```

## 3) Cross-artifact consistency check fails

**Symptom**
- `check_top_tier_reporting_contract.py` mismatch for onboarding rate / failed release rate.

**Check**
```bash
python scripts/check_top_tier_reporting_contract.py \
  --portfolio-scorecard docs/artifacts/portfolio-scorecard-sample-2026-04-17.json \
  --kpi-weekly docs/artifacts/kpi-weekly-from-portfolio-2026-04-17.json
```

**Fix**
- Regenerate both artifacts from the same input window via `make top-tier-reporting`.

## 4) Bundle manifest integrity check fails

**Symptom**
- `check_top_tier_bundle_manifest.py` reports SHA mismatch.

**Check**
```bash
python scripts/check_top_tier_bundle_manifest.py \
  --manifest docs/artifacts/top-tier-bundle-manifest-2026-04-17.json
```

**Fix**
- Rebuild bundle and regenerate manifest/check files:
```bash
make top-tier-reporting DATE_TAG=2026-04-17 WINDOW_START=2026-04-11 WINDOW_END=2026-04-17 GENERATED_AT=2026-04-17T10:00:00Z
```

## 5) CI workflow fails but local run passes

**Symptom**
- `.github/workflows/top-tier-reporting-sample.yml` fails while local run is green.

**Check**
```bash
python -m pytest -q \
  tests/test_top_tier_reporting_makefile.py \
  tests/test_top_tier_reporting_workflow.py
```

**Fix**
- Confirm workflow still runs `make top-tier-reporting`.
- Confirm workflow artifact upload list includes all expected files.
- Confirm your branch includes all newly-added scripts and tests.
