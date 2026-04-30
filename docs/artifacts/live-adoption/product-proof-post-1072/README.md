# DevS69 SDETKit live-adoption product proof

This directory contains committed UTF-8 live-adoption evidence for the post-#1072 product proof pass.

## Proof identity

| Field | Value |
|---|---|
| Repository head | `4031d142ce57985b542f0aaf1298637309ab0318` |
| Public evidence contract | `live-adoption-product-proof-summary.json` |
| Final classification | `SHIP with known STRICT_FINDINGS` |
| Blocking failures | `0` |
| Known strict finding | `legacy-noargs` compatibility behavior |

## Proven layers

| Layer | Evidence |
|---|---|
| Clean main proof | #1072 landed on `main` and review fix is present |
| Review front door | `review . --format json` and `operator-json` emit valid JSON with findings rc |
| First-proof lane | `FIRST_PROOF_DECISION=SHIP` |
| Health score | `100` |
| Core gates | gate fast, release dry-run, and doctor passed |
| Full repo analysis | artifact generation succeeded, command surface decision `SHIP`, blocking failures `0` |
| Fixture surface proof | fixture/shape probes passed |
| Docs front-door proof | curated docs-core command proof passed |
| Package proof | package build, twine check, wheel install, CLI smoke, and import smoke passed |

## Files

| File | Purpose |
|---|---|
| `live-adoption-product-proof-summary.json` | Curated public proof contract |
| `repo-full-analysis-summary.md` | Full repo analysis summary |
| `docs-core-proof-summary.md` | Curated docs front-door proof |
| `fixture-surface-proof-summary.md` | Fixture-backed surface proof |
| `docs-example-proof-summary.md` | Safe docs example scan proof |

## Binary bundle policy

The compressed raw proof bundle is intentionally not committed because repo audit treats committed docs artifacts as UTF-8 text.

Local bundle retained outside Git:

```text
build/live-adoption/devs69-sdetkit-product-proof-post-1072-20260430T100932Z.tar.gz
sha256: 454adf4f272f4bee405883342200827d9c680cebe894790650e8afeccb964e04
```

The remaining `STRICT_FINDINGS` result is intentionally scoped to `legacy-noargs`; it is not a blocking product failure.
