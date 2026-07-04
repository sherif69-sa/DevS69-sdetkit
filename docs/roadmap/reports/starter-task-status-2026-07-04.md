# Starter task status checkpoint — 2026-07-04

This checkpoint records merged starter-sized reliability tasks so maintainers can
see which contributor-facing roadmap items have moved from open starter work to
accepted mainline evidence.

## Completed starter tasks

| Issue | PR | Area | Mainline result |
| --- | --- | --- | --- |
| #1943 | #1999 | JavaScript proof commands | Package-manager-aware JavaScript test command recommendation is merged. |
| #1947 | #2000 | Go security surface | Explicit `govulncheck` evidence detection and review-first security proof recommendation are merged. |
| #1938 | #2001 | Vitest fixture coverage | Saved Vitest failure-log fixture coverage is merged. |

## Maintainer notes

- These tasks were intentionally small and reviewable.
- Each merged slice preserved review-first authority boundaries.
- No merged slice grants automation, patch application, merge authorization, or
  semantic-equivalence authority.
- The next suitable starter work should remain one issue per PR and avoid broad
  runtime rewrites.

## Suggested next review queue

The remaining roadmap candidates should be selected only when the implementation
surface is small enough to patch safely and prove with focused tests:

- #1944 — GitLab CI proof-command extraction.
- #1945 — Jenkins declarative-pipeline proof-command extraction.
- #1948 — JavaScript package-security command discovery.
- #1946 — cargo-audit security-surface discovery.

If a candidate requires a large full-file rewrite or parser architecture change,
prefer opening a narrower preparatory issue before implementation.
