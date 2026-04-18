# Start here: deterministic release confidence

DevS69 SDETKit is a release-confidence CLI for deterministic ship/no-ship decisions with machine-readable evidence.

**Primary outcome:** move from local proof to CI using one repeatable path.

## Canonical first run (local -> CI)

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## What you get

```text
build/gate-fast.json
build/release-preflight.json
```

## Try it quickly

- [Start Here in 5 Minutes](start-here-5-minutes.md)
- [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
- [First run quickstart](ready-to-use.md)
- [Quickstart (copy-paste)](quickstart-copy-paste.md)

## Team rollout / CI

- [Adopt in your repository](adoption.md)
- [Team adoption checklist](team-adoption-checklist.md)
- [Operator essentials](operator-essentials.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)
- [Release confidence flow](release-confidence-flow.md)
- [First failure triage](first-failure-triage.md)
- [Phase-by-phase execution plan](phase-by-phase-execution-plan.md)

## Reference / advanced

- [CLI reference](cli.md)
- [Doctor checks](doctor.md)
- [Stability levels](stability-levels.md)
- [Versioning and support posture](versioning-and-support.md)
- [Integrations and extension boundary](integrations-and-extension-boundary.md)
- [Why SDETKit for teams](why-sdetkit-for-teams.md)
- [Use cases](use-cases.md)
- [Release confidence ROI](release-confidence-roi.md)
- [Repo health dashboard](repo-health-dashboard.md)

## Install and runtime notes

- Python 3.11+
- Prefer isolated environments
- `NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q`
