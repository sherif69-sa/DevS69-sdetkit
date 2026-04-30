# Live-adoption product proof

SDETKit is backed by committed UTF-8 live-adoption product proof evidence.

## Proof identity

| Field | Value |
|---|---|
| Repository head | `4031d142ce57985b542f0aaf1298637309ab0318` |
| Public evidence contract | `live-adoption-product-proof-summary.json` |
| Decision | `SHIP with known STRICT_FINDINGS` |
| Blocking failures | `0` |
| Known strict finding | `legacy-noargs` compatibility behavior only |

## Proven strengths

| Layer | Proof |
|---|---|
| First-proof lane | `FIRST_PROOF_DECISION=SHIP`, health `100` |
| Core gates | gate fast, release dry-run, and doctor passed |
| Review front door | `json` and `operator-json` emit valid JSON with findings rc |
| Package proof | build, twine check, wheel install, CLI smoke, import smoke |
| Fixture proof | inspect/project/compare/patch/agent/serve/apiget shapes passed |
| Docs proof | curated front-door docs commands passed |
| Full repo analysis | command surface `SHIP`, blocking failures `0` |

## Evidence location

The committed evidence files live in:

```text
docs/artifacts/live-adoption/product-proof-post-1072/
```

Key files:

```text
live-adoption-product-proof-summary.json
repo-full-analysis-summary.md
docs-core-proof-summary.md
fixture-surface-proof-summary.md
docs-example-proof-summary.md
```

The compressed raw bundle is retained as local evidence and can be published separately as a release or Actions artifact. It is not committed because repo audit requires committed docs artifacts to be UTF-8 text.

The remaining `STRICT_FINDINGS` result is intentionally scoped to `legacy-noargs`; it is not a blocking product failure.
