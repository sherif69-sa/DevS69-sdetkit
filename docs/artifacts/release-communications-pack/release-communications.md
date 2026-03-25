# Release communications

**Headline:** This release is ready to communicate broadly with a stable quality posture.

## Release posture

- Release score: **96.56**
- Gate status: **pass**
- Readiness label: **ready**

## Highlights

- add GHAS alert SLA + metrics export bots, wire them into maintenance coverage checks, and refresh GHAS automation docs.
- add Name 86 launch readiness closeout lane command, docs, checks, and tests (`name86-launch-readiness-closeout`).
- upgrade audit: parse modern `pyproject.toml` `[dependency-groups]` declarations, including `{include-group = "..."}` expansions.
- Packaging: modernize license metadata.
- CI gate: run `sdetkit doctor --all` and `sdetkit repo check --profile enterprise` on every PR.
- Enterprise hardening: GitHub Actions pinned to commit SHAs.

## Risks and follow-ups

- Release posture is strong; proceed with release candidate tagging and notes preparation.

## Audience blurbs

- **Non Maintainers:** What changed: clearer quality gates, faster release confidence, and traceable evidence for audits.
- **Engineering:** Ship with confidence by tying release-readiness score to concrete checklist and evidence artifacts.
- **Support:** Use highlights + risks sections to pre-brief known changes and probable user questions.

## Narrative channels

- **Release Notes:** This release is ready to communicate broadly with a stable quality posture. Key highlights: add GHAS alert SLA + metrics export bots, wire them into maintenance coverage checks, and refresh GHAS automation docs.
- **Community Post:** Shipping update: stronger quality gates, clearer evidence, and a smoother adoption path for teams.
- **Internal Update:** Release communications pack is ready. Reuse the highlights/risks sections in weekly status and customer comms.

**Call to action:** Share this narrative in release notes, weekly updates, and community announcements.
