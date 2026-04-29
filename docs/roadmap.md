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
- Weekly adapter smoke issue/artifact is maintained by `.github/workflows/adapter-smoke-bot.yml`.
- Weekly repo optimization control-loop issue is maintained by `.github/workflows/repo-optimization-bot.yml`.
- Weekly docs experience radar issue/artifact is maintained by `.github/workflows/docs-experience-bot.yml`.
- Weekly runtime fast-follow watchlist issue/artifact is maintained by `.github/workflows/runtime-watchlist-bot.yml`.
- Weekly release readiness radar issue/artifact is maintained by `.github/workflows/release-readiness-radar-bot.yml`.
- Monthly workflow governance audit issue/artifact is maintained by `.github/workflows/workflow-governance-bot.yml`.
- Security triage should include Dependabot, Code Scanning, Secret Scanning, Dependency Audit, SBOM freshness, dependency review posture, security-configuration visibility, and Actions workflow status review.
- At least one open enhancement intake issue should exist and be labeled with `enhancement` plus a `priority:*` label.

## Enhancement tracking policy

When an enhancement is identified from customer or user feedback:

1. Create/confirm an issue labeled `enhancement`.
2. Add one priority label: `priority:high`, `priority:medium`, or `priority:low`.
3. Link the enhancement issue or PR back to this roadmap page and the main `ROADMAP.md` where appropriate.

## Current enhancement candidate from maintenance intake (April 2026)

- **User pain point:** The open issue queue is dominated by GHAS tracker issues, but maintainers lack a single documented triage lane that maps each tracker type to a concrete remediation action and expected PR artifact.
- **Acceptance criteria:**
  1. Roadmap guidance explicitly maps each open GHAS tracker type (weekly digest, SLA tracker, campaign planner, and hotspots) to a remediation action.
  2. Each remediation action defines a concrete output artifact (issue comment update, linked remediation PR, or deferred command-center note).
  3. The command-center issue remains the parent coordination lane for all weekly tracker follow-up.
- **Expected impact:** Faster weekly triage, fewer orphaned tracker issues, and clearer auditability between automated GHAS signals and code changes.

### GHAS tracker-to-action mapping

- **GHAS weekly digest** → verify alert deltas and workflow freshness; capture disposition in the rolling command-center issue.
- **GHAS alert SLA tracker** → prioritize 14+ day alerts into an owned remediation batch; link resulting PRs.
- **GHAS campaign planner** → group aged alerts into campaign slices and record owner + expected completion window.
- **GHAS CodeQL hotspots** → batch-fix the top rule/path hotspot and re-run the planner to validate backlog reduction.

## Continuous maintenance hardening loop

The maintenance system now produces ten recurring artifacts:

- A date-scoped checklist issue for security and baseline operations.
- A date-scoped weak-spot report issue that auto-detects workflow failures/staleness and maintenance hygiene drift, then proposes concrete follow-up actions.
- A date-scoped GHAS digest issue that summarizes code scanning, Dependabot, secret scanning, and security workflow freshness.
- A date-scoped GHAS campaign planner issue that groups GHAS backlog slices by age/severity and calls out Copilot Autofix opportunities plus push-protection follow-up.
- A date-scoped GHAS CodeQL hotspot issue that groups the code-scanning queue by rule and path so fixes can be batched.
- A monthly GHAS configuration audit issue that verifies the repo's workflow/config coverage and attached security-configuration context.
- A date-scoped dependency radar issue that highlights validation-linked upgrade candidates and a runtime fast-follow watchlist.
- A date-scoped adapter smoke issue that keeps optional notification channels and integration-adapter quickstarts healthy.
- A date-scoped docs experience radar issue that keeps flagship docs, nav coverage, and search discoverability reviewable.
- A date-scoped runtime fast-follow watchlist that keeps hot-path runtime-core packages on a tighter maintenance loop.
- A date-scoped release readiness radar issue that joins doctor output, release assets, and publish-workflow coverage.
- A monthly workflow governance audit issue that keeps workflow permissions, SHA pinning, and manual recovery visible.

This creates a repeatable maintenance loop: **detect weak spots → summarize GHAS risk → prioritize upgrade and docs work → confirm release posture → track implementation in issues/PRs → repeat weekly**.
