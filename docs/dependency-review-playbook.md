# Dependency review playbook

Use this playbook when reviewing dependency and GitHub Actions update pull requests. It keeps dependency maintenance fast without treating a green check as broader proof than the changed surface supports.

## Review goal

Dependency PRs should answer four questions before merge:

1. What changed?
2. Which runtime, documentation, security, or workflow surface can be affected?
3. Which exact-head checks proved the affected surface?
4. Does the change require a human follow-up PR after the bot update merges?

Bot-authored version bumps should remain bot-authored. Human follow-up work belongs in separate reviewable PRs.

## Dependency PR triage

| Changed surface | Minimum evidence to inspect |
| --- | --- |
| `requirements*.txt` | package build, wheel install, dependency audit, OSV/security, full CI |
| `.github/workflows/*.yml` | workflow governance, branch protection, security, PR Quality, full CI |
| documentation toolchain | docs build, link integrity, package install, full CI |
| runtime dependency | focused tests for the affected runtime path plus full CI |
| security scanner dependency | security workflow, OSV, dependency review, SARIF upload path when applicable |

When the PR changes more than one surface, use the strongest applicable set.

## Exact-head checklist

Before merge, inspect:

- PR number and exact head SHA.
- changed files.
- dependency names and versions.
- required statuses: `ci` and `maintenance-autopilot`.
- security and dependency review results.
- package and wheel-smoke evidence when Python dependencies changed.
- workflow governance evidence when GitHub Actions changed.

Never reuse proof from an older head after a rebase, Dependabot refresh, or `main` movement.

## Human follow-up candidates

Create a separate human-authored PR when a dependency update reveals work beyond the version bump:

- documentation for a new dependency review pattern;
- a regression test for a dependency behavior that matters to SDETKit;
- a workflow guard that prevents unsafe future dependency changes;
- a contributor checklist that explains how to validate the changed surface;
- removal of stale notes after the dependency makes them obsolete.

These follow-up PRs can include human co-authorship when the contributors actually helped design or review the change.

## Authority boundary

Dependency review is reporting and validation work only. It does not authorize patch application, security dismissal, merge approval, or semantic-equivalence claims.
