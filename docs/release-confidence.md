# Release confidence with SDETKit

**Use this page if:** you want the product-level model for deterministic release decisions.

**For execution details:**
- First run commands: [First run quickstart](ready-to-use.md)
- Team rollout: [Adoption](adoption.md)
- CI implementation: [Recommended CI flow](recommended-ci-flow.md)
- Artifact interpretation: [CI artifact walkthrough](ci-artifact-walkthrough.md)

## Core idea

Use one repeatable command path to answer:

**"Is this repository ready to ship?"**

## Core commands

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

For policy enforcement and evidence artifacts in CI, continue with the CI lane pages.

## Why teams adopt this model

- Deterministic gate outcomes instead of subjective interpretation.
- Structured evidence for release approvals and audits.
- Same command language across local runs and CI.

## Related pages by lane

- Beginner lane: [install.md](install.md), [ready-to-use.md](ready-to-use.md)
- Team lane: [adoption.md](adoption.md), [team-rollout-scenario.md](team-rollout-scenario.md)
- CI lane: [recommended-ci-flow.md](recommended-ci-flow.md), [ci-contract.md](ci-contract.md)
- Comparison lane: [sdetkit-vs-ad-hoc.md](sdetkit-vs-ad-hoc.md)
