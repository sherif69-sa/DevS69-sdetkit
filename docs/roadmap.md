# Roadmap

See the repo roadmap in `ROADMAP.md` for product and release direction.

## Security and maintenance operations cadence

To keep security and maintenance work visible and actionable, the repo runs an automated checklist and enhancement intake process:

- Weekly security checklist issue is maintained by `.github/workflows/security-maintenance-bot.yml`.
- Security triage should include Dependabot, Code Scanning, and Actions workflow status review.
- At least one open enhancement intake issue should exist and be labeled with `enhancement` plus a `priority:*` label.

## Enhancement tracking policy

When an enhancement is identified from customer or user feedback:

1. Create/confirm an issue labeled `enhancement`.
2. Add one priority label: `priority:high`, `priority:medium`, or `priority:low`.
3. Link the enhancement issue or PR back to this roadmap page and the main `ROADMAP.md` where appropriate.

## Current enhancement candidate from maintenance intake

- **User pain point:** Automated maintenance issues were being reused without a clear week marker, making it difficult to tell whether checklist items were still current.
- **Acceptance criteria:**
  1. Weekly maintenance issue includes a date stamp in the title.
  2. Previous weekly maintenance issues are automatically closed when a new week is created.
  3. The security/maintenance automation runs weekly (not daily) to match the issue intent.
- **Expected impact:** Cleaner issue triage, reduced stale maintenance noise, and clearer operational cadence for maintainers.

## Continuous maintenance hardening loop

The maintenance bot now produces two weekly artifacts:

- A date-scoped checklist issue for security and baseline operations.
- A date-scoped weak-spot report issue that auto-detects workflow failures/staleness and maintenance hygiene drift, then proposes concrete follow-up actions.

This creates a repeatable maintenance loop: **detect weak spots → suggest fixes → track implementation in issues/PRs → repeat weekly**.
