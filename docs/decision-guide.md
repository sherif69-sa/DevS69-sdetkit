# Is SDETKit right for your repo? (Decision guide)

Use this page to make a fast fit decision.

Core promise: deterministic release-confidence checks and evidence-backed shipping decisions.

If you already decided to adopt, use [Start here](index.md) or [Choose your path](choose-your-path.md).

## 1) Good-fit profile

SDETKit is usually a good fit when at least one of these is true:

| Repo/team profile | Why SDETKit fits |
| --- | --- |
| Repo owner improving release confidence | You want deterministic go/no-go checks instead of ad hoc interpretation. |
| QA/SDET/reliability-minded team | You need repeatable checks plus evidence artifacts for triage and audits. |
| Team standardizing local + CI decisions | You want one command path and consistent outputs across environments. |
| Platform/release team with governance needs | You need evidence-backed release approvals with machine-readable outputs. |

Quick fit signal command (risk-based recommendation):

```bash
python scripts/recommend_sdetkit_fit.py --repo-size medium --team-size medium --release-frequency medium --change-failure-impact high --compliance-pressure medium --format json
```

Convert fit + latest gate decision into prioritized follow-up actions:

```bash
make adoption-followup
make adoption-followup-contract
python -m sdetkit adoption --format json
```

## 2) When SDETKit is probably *not* worth it

SDETKit may be unnecessary if:

- Your repo is very small/simple and release risk is low.
- You only want raw underlying tools and prefer fully custom orchestration.
- Your team is not ready to adopt a shared command path.

If these apply, run only the lightweight core lane first, then stop unless repeatability or evidence gaps appear.

## 3) Lightweight core path (recommended)

1. [Install (canonical)](install.md)
2. [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
3. `python -m sdetkit gate fast`
4. `python -m sdetkit gate release`
5. `python -m sdetkit doctor`
6. Validate artifact interpretation with [Evidence showcase](evidence-showcase.md)

## 4) Manual scattered workflow vs SDETKit workflow

| Dimension | Manual scattered workflow | SDETKit workflow |
| --- | --- | --- |
| Command execution | Multiple tools/scripts with operator-defined order | Core gate path with deterministic outcomes |
| Output consistency | Mixed formats and ad hoc interpretation | Structured evidence and report outputs |
| Release decision quality | Subjective and reviewer-dependent | Evidence-backed and repeatable |
| CI portability | Each repo reinvents wiring | Reusable adoption path and baseline |

SDETKit does **not** replace every underlying tool; it standardizes orchestration and interpretation for release-confidence decisions.

## 5) “Stop here” point

Stop after the lightweight path if:

- `gate fast` and `gate release` already meet confidence needs,
- doctor checks are healthy,
- and current evidence outputs satisfy release reviewers.

Then keep using the core commands and expand only if integration needs appear.

## 6) Route into one lane (avoid sprawl)

After confirming fit, choose exactly one lane:

- **Guided first run**: [ready-to-use.md](ready-to-use.md)
- **Team adoption**: [adoption.md](adoption.md)
- **CI rollout**: [recommended-ci-flow.md](recommended-ci-flow.md)
- **Advanced/reference** (only when needed): [cli.md](cli.md), [api.md](api.md), [plugins.md](plugins.md), [tool-server.md](tool-server.md)

Historical transition-era docs remain available under [Archive and history](archive/index.md).

## Next if you need more context (secondary)

- Compare value proposition vs scattered tooling: [sdetkit-vs-ad-hoc.md](sdetkit-vs-ad-hoc.md)
- Keep repo layout/rules clean during adoption: [repo-cleanup-plan.md](repo-cleanup-plan.md)
- Track longer-term repository posture: [repo-health-dashboard.md](repo-health-dashboard.md)
