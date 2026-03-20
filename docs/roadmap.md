# Roadmap

See the repo roadmap in `ROADMAP.md` for product and release direction.

## Security and maintenance operations cadence

To keep security and maintenance work visible and actionable, the repo runs an automated checklist and enhancement intake process:

- Weekly security checklist issue is maintained by `.github/workflows/security-maintenance-bot.yml`.
- Weekly GHAS digest issue is maintained by `.github/workflows/ghas-review-bot.yml`.
- Weekly GHAS campaign planner issue is maintained by `.github/workflows/ghas-campaign-bot.yml`.
- Weekly GHAS alert SLA tracker issue is maintained by `.github/workflows/ghas-alert-sla-bot.yml`.
- Weekly GHAS metrics snapshot issue/artifact is maintained by `.github/workflows/ghas-metrics-export-bot.yml`.
- Weekly GHAS CodeQL hotspot issue/artifact is maintained by `.github/workflows/ghas-codeql-hotspots-bot.yml`.
- Monthly GHAS configuration audit issue is maintained by `.github/workflows/security-configuration-audit-bot.yml`.
- Weekly secret protection review issue is maintained by `.github/workflows/secret-protection-review-bot.yml`.
- Weekly dependency radar issue is maintained by `.github/workflows/dependency-radar-bot.yml`.
- Weekly repo optimization control-loop issue is maintained by `.github/workflows/repo-optimization-bot.yml`.
- Monthly workflow governance audit issue/artifact is maintained by `.github/workflows/workflow-governance-bot.yml`.
- Security triage should include Dependabot, Code Scanning, Secret Scanning, Dependency Audit, SBOM freshness, dependency review posture, security-configuration visibility, and Actions workflow status review.
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

The maintenance system now produces eight recurring artifacts:

- A date-scoped checklist issue for security and baseline operations.
- A date-scoped weak-spot report issue that auto-detects workflow failures/staleness and maintenance hygiene drift, then proposes concrete follow-up actions.
- A date-scoped GHAS digest issue that summarizes code scanning, Dependabot, secret scanning, and security workflow freshness.
- A date-scoped GHAS campaign planner issue that groups GHAS backlog slices by age/severity and calls out Copilot Autofix opportunities plus push-protection follow-up.
- A date-scoped GHAS CodeQL hotspot issue that groups the code-scanning queue by rule and path so fixes can be batched.
- A monthly GHAS configuration audit issue that verifies the repo's workflow/config coverage and attached security-configuration context.
- A date-scoped dependency radar issue that highlights validation-linked upgrade candidates and a runtime fast-follow watchlist.
- A monthly workflow governance audit issue that keeps workflow permissions, SHA pinning, and manual recovery visible.

This creates a repeatable maintenance loop: **detect weak spots → summarize GHAS risk → group campaign work → prioritize upgrade work → track implementation in issues/PRs → repeat weekly**.
