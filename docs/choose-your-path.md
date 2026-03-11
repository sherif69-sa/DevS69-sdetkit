# Choose your path (30-second router)

**Use this page if:** you want to pick the right SDETKit lane quickly.

**Core promise:** deterministic release-confidence checks and evidence-backed shipping decisions.

## Pick one lane

| Situation | Start here | Next page |
| --- | --- | --- |
| First-time user, want immediate signal | `python -m sdetkit gate fast` | [First run quickstart (canonical)](ready-to-use.md) |
| Team standardization across repos | `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json` | [Adoption (canonical)](adoption.md) |
| CI policy rollout and artifact governance | PR fast gate + artifact upload | [Recommended CI flow (canonical)](recommended-ci-flow.md) |
| Need proof/comparison for stakeholders | Compare current ad hoc path vs deterministic gates | [SDETKit vs ad hoc (canonical)](sdetkit-vs-ad-hoc.md) |
| Need command/reference depth | Explore command families and boundaries | [Advanced/reference lane](cli.md) |

## Safe rollout sequence (default)

1. First-run lane
2. Team adoption lane
3. CI/automation lane
4. Advanced/extensions lane (only when needed)

Historical material is intentionally separate in [Archive and history](archive/index.md).
