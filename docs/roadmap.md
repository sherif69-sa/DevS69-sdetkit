# Roadmap

See the repo roadmap in `docs/roadmap/product-roadmap.md` for product and release direction.

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
3. Link the enhancement issue or PR back to this roadmap page and the main `docs/roadmap/product-roadmap.md` where appropriate.

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

## Current enhancement candidate from maintenance intake (June 2026)

- **Source issue:** #1786
- **User pain point:** A successful but malformed GitHub API response can be reported as an authoritative zero in the maintenance command center, allowing queue or security decisions to proceed from invalid evidence.
- **Acceptance criteria:**
  1. Valid empty collections continue to render an authoritative zero.
  2. Successful malformed list payloads and malformed workflow-run envelopes render unavailable or unknown instead of zero.
  3. Queue actions never proceed from an explicit `available=false` collection state.
  4. Focused regression tests cover the six collection-integrity findings while preserving the existing pagination fallback.
- **Expected impact:** More trustworthy maintenance queue decisions and a clear distinction between authoritative zero, unavailable collection state, and malformed API evidence.

## Developer workflow program: Contributor Review and Delivery Workflow

This program connects contributor preparation, PR evidence, the canonical review model, trusted publication, human review, post-merge verification, and release-readiness handoff without expanding automation authority.

### Active roadmap action

```text
action:
  id=pr-review-state
  lane=Developer workflow
  title=Normalize PR Quality decision states
  priority=P1
  risk=medium
  value=Give contributors one truthful verdict, one blocker, and one next action across every review surface.
  status=in_progress
```

**Acceptance criteria**

1. The canonical review state is one of `waiting`, `blocked`, `review`, `ready`, `stale`, or `invalid`.
2. A `ready` review has no blocker and does not recommend rerunning proof.
3. Required-check counts match the required-check names shown to contributors.
4. The review summary, step summary, dashboard, and artifact manifest consume the same state and next action.
5. Contradictory evidence produces `invalid` rather than a green verdict.
6. The read-only evidence workflow and trusted publisher topology remain unchanged.

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

## Evidence circuit checkpoint

The evidence propagation chain from #1748 through #1761 is documented in [Evidence circuit architecture checkpoint](evidence-circuit-architecture-checkpoint.md). Future work should treat that chain as complete and move toward architecture, operator review, dashboard, or release-readiness slices rather than adding another recursive consumer.
The operator review flow for this completed circuit is documented in [Operator evidence review guide](operator-evidence-review-guide.md).
The reviewer-facing source map for this completed circuit is documented in [Evidence graph summary](evidence-graph-summary.md).
The artifact navigation layer for this circuit is documented in [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map).
The dashboard/reporting review layer for this circuit is documented in [Dashboard and reporting polish](dashboard-reporting-polish.md).

## Evidence circuit documentation bundle

The completed #1748 through #1761 evidence circuit now has a bundled
reviewer path:

- [Evidence circuit architecture checkpoint](evidence-circuit-architecture-checkpoint.md)
- [Operator evidence review guide](operator-evidence-review-guide.md)
- [Evidence graph summary](evidence-graph-summary.md)
- [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map)
- [Dashboard and reporting polish](dashboard-reporting-polish.md)
- [Evidence circuit review pack](evidence-circuit-review-pack.md)
- [Release-readiness evidence handoff](release-readiness-evidence-handoff.md)

The next roadmap slice should move from documentation completion to a concrete
product surface, artifact generation improvement, dashboard UI improvement, or
release-readiness packaging task.
