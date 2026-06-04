# Operational readiness hardening

Lane closes Baseline by hardening top entry pages, removing stale guidance, and publishing a deterministic completion report lane.

## Why Lane exists

- Preserve trust by ensuring README + docs index + strategy pages are mutually consistent.
- Close stale docs gaps before Lane phase wrap and handoff.
- Produce a reviewable hardening artifact pack for maintainers.

## Hardening scope

- README entry-page checks and command-lane verification.
- Docs index discoverability checks for Lane integration/report pages.
- Strategy alignment checks against `docs/top-10-github-strategy.md` Lane objective.
- Stale marker scans across top entry pages and recent integration docs.

## Lane command lane

```bash
python -m sdetkit baseline-hardening --format json --strict
python -m sdetkit baseline-hardening --emit-pack-dir docs/artifacts/baseline-hardening-pack --format json --strict
python -m sdetkit baseline-hardening --execute --evidence-dir docs/artifacts/baseline-hardening-pack/evidence --format json --strict
python scripts/check_baseline_hardening_contract.py
```

## Scoring model

Lane weighted score (0-100):

- Docs contract and command-lane completeness: 35 points.
- Entry-page discoverability + strategy alignment: 35 points.
- Stale marker elimination in top pages: 20 points.
- Artifact/report wiring for baseline completion report: 10 points.

## Entry page polish checklist

- README includes Lane section and command lane.
- Docs index links both integration guide and Lane report.
- Top-10 strategy includes Lane hardening objective.
- No stale placeholder markers in top entry pages.

## Evidence mode

`--execute` runs deterministic checks and captures command logs in `--evidence-dir`.
