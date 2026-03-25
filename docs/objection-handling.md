# FAQ and objections

Objection handling turns recurring adoption blockers into deterministic answers that teams can validate before launches.

## Who should run objection-handling

- Maintainers preparing public launch narratives and onboarding material.
- Developer advocates collecting recurring objections from discussions/issues.
- Platform leads deciding whether to standardize on sdetkit workflows.

## When to use sdetkit

Use sdetkit when you need deterministic, CLI-first quality and reliability workflows for CI and local checks.

- You want reproducible diagnostics and policy checks for contributors.
- You need artifact-driven evidence packs for leadership or compliance reviews.
- You want one command lane that scales from startup teams to regulated enterprise contexts.

## When not to use sdetkit

Avoid sdetkit as a first step if your team only needs one-off scripts and no governance evidence.

- You do not maintain a shared CI pipeline.
- You are not ready to enforce basic quality and security gates.
- You only need ad-hoc local checks without repeatability requirements.

## Top objections and responses

### Objection 1: "This looks heavy for small teams"

Response: start with `doctor`, `repo audit`, and `security gate` only. Expand to governance packs later.

### Objection 2: "We already have scripts"

Response: sdetkit provides deterministic contracts, evidence artifacts, and strict gates that ad-hoc scripts usually lack.

### Objection 3: "How do we prove this is production-ready?"

Response: run strict mode, emit an objection-handling pack, and attach execution logs as evidence in release reviews.

## Fast verification commands

```bash
python -m sdetkit objection-handling --format json --strict
python -m sdetkit objection-handling --emit-pack-dir docs/artifacts/objection-handling-pack --format json --strict
python -m sdetkit objection-handling --execute --evidence-dir docs/artifacts/objection-handling-pack/evidence --format json --strict
python scripts/check_objection_handling_contract.py
```

## Escalation and rollout policy

- If strict mode fails, pause launch messaging and assign owners for missing FAQ guidance.
- If objections repeat for two sprints, add dedicated docs links and command examples.
- Require objection-handling pack attachment in release-readiness review for external promotions.
