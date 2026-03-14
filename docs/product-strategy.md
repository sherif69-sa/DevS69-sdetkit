# Product Strategy: Make SDETKit a Real Tool

## Primary wedge

**SDETKit v1 focus:** become a **Release Confidence Engine** for SDET and DevOps teams.

### Problem
Teams often run quality, security, and release checks in disconnected tools, which creates
unclear ship/no-ship decisions and weak auditability.

### Outcome
Given a repository, SDETKit should produce deterministic evidence that answers:

- Is this build safe to ship now?
- If not, what failed and why?
- What artifact can be shared with engineering leadership?

## Hero workflow (ship-ready lane)

Use this sequence as the default v1 story:

```bash
bash ci.sh quick --skip-docs
bash quality.sh cov
python -m sdetkit security check --root . --baseline tools/security.baseline.json --format json
python -m sdetkit gate release
```

## 30-impact execution plan

### Week 1 — positioning + onboarding

- Keep one primary persona in all docs: SDET/DevOps release owner.
- Add one single-page quickstart for the hero workflow.
- Define 3 measurable success metrics.

### Week 2 — product UX hardening

- Add opinionated command presets (`quick`, `safe`, `release`) in docs and CLI help.
- Reduce decision points in first-run experience.
- Validate deterministic outputs and exit codes in tests.

### Week 3 — proof of value

- Publish two example scenarios (startup team + platform team).
- Include expected outputs and pass/fail interpretation.
- Add one reproducible release evidence artifact example.

### Week 4 — trust and adoption

- Add release narrative template tied to generated evidence.
- Document CI/CD integration copy-paste snippets by role.
- Prepare v1 scope freeze criteria and non-goals.

## Success metrics

- **Time to first successful release lane:** under 10 minutes from install.
- **Deterministic rerun consistency:** same inputs produce same pass/fail outputs.
- **Adoption signal:** repeated weekly usage of the hero workflow in target repos.

## What we will not optimize yet

- Broad feature expansion outside release-confidence scope.
- Persona-specific deep customization before core workflow stability.
- Complex integrations that reduce determinism or increase setup friction.
