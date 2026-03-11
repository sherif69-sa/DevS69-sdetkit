# Adopt SDETKit in your repository (canonical)

**Use this page if:** you are introducing SDETKit to a team-owned repository and need a staged rollout plan.

**Not this page:**
- First solo run: [First run quickstart](ready-to-use.md)
- CI workflow templates and branch policies: [Recommended CI flow (canonical)](recommended-ci-flow.md)
- Artifact interpretation details: [CI artifact walkthrough (canonical)](ci-artifact-walkthrough.md)

## Adoption objective

Move from local confidence checks to repeatable team gates with machine-readable release evidence.

## Stage 0 — install and verify in target repo

Use [Install](install.md), then verify:

```bash
python -m sdetkit --help
python -m sdetkit gate --help
```

## Stage 1 — local proof in the team repo

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

This is a signal-producing gate, not a guaranteed-green onboarding command.

## Stage 2 — baseline release confidence

```bash
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

Add security budgets once the team has agreement on thresholds:

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
```

## Stage 3 — CI rollout (handoff)

Use [Recommended CI flow](recommended-ci-flow.md) as the canonical CI rollout source. It defines:

- PR fast-gate baseline
- main/release stricter gates
- artifact upload conventions
- progressive tightening without all-at-once friction

## Team operating model

- PR lane: keep `gate fast` always on.
- main/release lane: enforce agreed security budgets and release gates.
- triage: use artifact-first flow via [CI artifact walkthrough](ci-artifact-walkthrough.md).

## If onboarding fails

Use these in order:

1. [First-failure triage](first-failure-triage.md)
2. [Adoption troubleshooting](adoption-troubleshooting.md)
3. [Remediation cookbook](remediation-cookbook.md)

## Related rollout pages

- [Team rollout scenario](team-rollout-scenario.md)
- [Example adoption flow](example-adoption-flow.md)
- [Adoption examples](adoption-examples.md)
- [Choose your path](choose-your-path.md)
