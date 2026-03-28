# Cycle 29 — Phase-1 hardening

Cycle 29 closes Phase-1 by hardening top entry pages, removing stale guidance, and publishing a deterministic closeout lane.

## Why Cycle 29 exists

- Preserve trust by ensuring README + docs index + strategy pages are mutually consistent.
- Close stale docs gaps before Cycle 30 phase wrap and handoff.
- Produce a reviewable hardening artifact pack for maintainers.

## Hardening scope

- README entry-page checks and command-lane verification.
- Docs index discoverability checks for Cycle 29 integration/report pages.
- Strategy alignment checks against `docs/top-10-github-strategy.md` Cycle 29 objective.
- Stale marker scans across top entry pages and recent integration docs.

## Cycle 29 command lane

```bash
python -m sdetkit phase1-hardening --format json --strict
python -m sdetkit phase1-hardening --emit-pack-dir docs/artifacts/phase1-hardening-pack --format json --strict
python -m sdetkit phase1-hardening --execute --evidence-dir docs/artifacts/phase1-hardening-pack/evidence --format json --strict
python scripts/check_phase1_hardening_contract.py
```

## Scoring model

Cycle 29 weighted score (0-100):

- Docs contract and command-lane completeness: 35 points.
- Entry-page discoverability + strategy alignment: 35 points.
- Stale marker elimination in top pages: 20 points.
- Artifact/report wiring for Phase-1 closeout: 10 points.

## Entry page polish checklist

- README includes Cycle 29 section and command lane.
- Docs index links both integration guide and Cycle 29 report.
- Top-10 strategy includes Cycle 29 hardening objective.
- No stale placeholder markers in top entry pages.

## Evidence mode

`--execute` runs deterministic checks and captures command logs in `--evidence-dir`.
