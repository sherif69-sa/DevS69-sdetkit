# Team rollout playbook

## What this page is for
A compact week-1 rollout plan for teams adopting SDETKit in a real repository.

**Primary outcome:** your team can run the canonical local path, review the same artifacts in a consistent order, and carry that flow into one CI lane.

## Week 1 rollout plan

### 1. Establish the runtime baseline
- Confirm Python 3.10+ is available on team machines and CI runners.
- Use an isolated environment (`venv` or `pipx`) to avoid system-Python drift.
- Verify install and command discovery before rollout decisions.

### 2. Prove the canonical path locally
Run the same artifact-producing commands the team will later mirror in CI:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

Treat this as a confidence baseline, not a guarantee that every gate is green on day 1.

### 3. Agree on artifact review order
Use a shared triage order so reviews stay fast and consistent:

- `build/release-preflight.json`
- `build/gate-fast.json`
- raw logs only after artifact triage

### 4. Introduce one CI lane
- Start with one lane, usually a PR fast-gate, instead of full policy rollout.
- Keep CI commands as close as possible to local commands.
- Preserve JSON artifacts for every run so reviewers have durable evidence.

### 5. Define team review expectations
- Name who reads gate artifacts in PRs.
- Name who decides blocked/not blocked when signals conflict.
- Require PR and release decisions to reference artifact evidence, not only screenshots or log snippets.

### 6. Define support and escalation hygiene
- Standardize which artifacts to attach when asking for help.
- Route install/runtime issues to the install and troubleshooting docs first.
- Route docs clarity issues to docs issues or PRs.
- Route release-confidence interpretation disputes to the team’s agreed reviewers.

## What good adoption looks like
- Runtime baseline confirmed (Python 3.10+, isolated environment).
- Canonical local path runs and produces expected artifacts.
- One CI lane is active and preserving artifacts.
- Artifact review order is documented and followed.
- Support and escalation expectations are documented for the team.

## Related pages
- [Install](install.md)
- [Quickstart (copy-paste)](quickstart-copy-paste.md)
- [Adopt in your repository](adoption.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)
- [Team adoption checklist](team-adoption-checklist.md)
- [Why SDETKit for teams](why-sdetkit-for-teams.md)
- [Support](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/SUPPORT.md)
