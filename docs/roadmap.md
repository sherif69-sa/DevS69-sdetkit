# Roadmap

This page tracks current direction and links to deeper planning artifacts.

## Current release baseline

- **Latest stable release:** `v1.0.1`
- **Primary focus:** strong quality gates, safe repository automation, and enterprise-ready policy/security defaults.

## Recently delivered

- CI gate runs `sdetkit doctor --all` and `sdetkit repo check --profile enterprise` on every PR.
- GitHub Actions hardened by pinning to commit SHAs.
- Dependency lockfiles added to improve deterministic builds.
- Repo init/apply made more robust for non-UTF-8 preset template files.

## Next planning views

- Product-level roadmap and milestones: [ROADMAP.md](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/ROADMAP.md)
- Release-by-release record: [CHANGELOG.md](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CHANGELOG.md)
- Governance and policy direction: [Governance & org packs](governance-and-org-packs.md)

!!! tip "Want to help shape priorities?"
    Open an issue or PR with your use case, expected workflow, and acceptance criteria so roadmap updates are actionable.
