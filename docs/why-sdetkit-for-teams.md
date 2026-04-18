# Why SDETKit for teams

SDETKit exists to answer one expensive question with less ambiguity:

**"Is this change safe to ship right now?"**

For many teams, that decision is spread across shell scripts, CI snippets, raw logs, and human interpretation. That works until release pressure increases and teams need repeatable evidence they can trust.

SDETKit provides a deterministic release-confidence path that turns this into a consistent contract:

- one repeatable local-to-CI command flow
- machine-readable evidence artifacts
- explicit `ship` / `no-ship` decision inputs

## What problem SDETKit solves

Without a common release-confidence path, teams often face:

- inconsistent checks between local runs and CI
- slow triage through logs instead of clear artifacts
- go/no-go decisions based on tribal knowledge
- hard-to-audit release decisions

SDETKit standardizes that decision surface so teams can review release readiness from stable JSON artifacts, not scattered tooling output.

## Why not just separate tools and scripts?

Separate tools are still valuable, but orchestration usually becomes the fragile part:

- each repository wires tools differently
- output formats vary and drift over time
- CI and local commands diverge
- evidence is harder to compare from run to run

SDETKit is the thin confidence layer above those checks. It focuses on deterministic outcome contracts and artifact-driven triage, so teams can make consistent release calls under time pressure.

## Why deterministic, artifact-driven decisions help teams

Deterministic artifacts improve release operations because they make decisions:

- **repeatable**: same path, same evidence contract
- **reviewable**: machine-readable output for PRs and release reviews
- **automatable**: CI systems can gate on structured fields
- **auditable**: teams can trace why a release was blocked or approved

## Who it is for / not for

**Best fit**
- Teams that want explicit ship/no-ship evidence.
- Engineering orgs that need one path from local runs to CI gates.
- Repositories that want stable machine-readable release artifacts.

**Probably not a fit (yet)**
- Teams that only need lightweight ad hoc checks.
- Repos where release governance and evidence contracts are unnecessary.

## How to start (canonical path)

Install and run the canonical path:

```bash
python -m pip install sdetkit==1.0.3
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

Then inspect `build/release-preflight.json` first, and use `failed_steps` to find the first deterministic remediation target.
