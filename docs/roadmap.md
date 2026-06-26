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

### Completed roadmap action

```text
action:
  id=pr-review-state
  lane=Developer workflow
  title=Normalize PR Quality decision states
  priority=P1
  risk=medium
  value=Give contributors one truthful verdict, one blocker, and one next action across every review surface.
  status=done
```

**Closure evidence**

- PRs `#1861` and `#1862` are merged.
- The post-merge closure audit passed with `150` focused tests.
- CodeQL alerts `#1428` through `#1432` are fixed without dismissal.
- The six-state canonical review contract and reporting-only authority boundary remain intact.

### Completed roadmap action

```text
action:
  id=pr-review-summary
  lane=Developer workflow
  title=Publish a contributor-first PR Quality summary
  priority=P1
  risk=medium
  value=Put the contributor decision, blocker, next action, required checks, security posture, and merge posture before internal diagnostics.
  status=done
```

**Closure evidence**

- PR `#1863` is merged at `80db8844915069c7771dab3714cabdabfab2fe9e`.
- The post-merge closure audit passed with `154` focused tests.
- The contributor panel contains six canonical rows.
- Ready-state failure language is absent from the primary panel.
- Product-artifact navigation has one trusted publisher owner.
- PR Quality publisher and evidence workflow files remain unchanged.

### Completed roadmap action

```text
action:
  id=pr-release-handoff
  lane=Release readiness
  title=Bind trusted PR Quality decisions into release-readiness evidence
  priority=P1
  risk=medium
  value=Carry the exact head-bound contributor review decision into one reporting-only release-readiness packet.
  status=done
```

**Closure evidence**

- PR `#1868` is merged at `8ccc7705aa6215163d020db96fb2fc3258450b00`.
- The post-merge closure audit passed with `183` focused tests.
- Local targeted security findings are zero.
- GHAS current review threads are zero; six superseded threads are outdated.
- The release package schema remains additive `v2`.
- PR Quality publisher, evidence, and release workflow files remain unchanged.

### Completed roadmap action

```text
action:
  id=pr-post-merge-proof
  lane=Release readiness
  title=Productize post-merge verification evidence
  priority=P1
  risk=medium
  value=Turn repeated external closure scripts into one deterministic, reporting-only repo-native evidence product.
  status=done
```

**Closure evidence**

- PR `#1872` is merged at `08f20f2b10ed10fe6bef2b325ab3a34c24a84925`.
- Corrective PR `#1873` is merged at `82d6bed21361bc0e8e748fa59795aca3cf4478a1`.
- Repo-native post-merge verification returned `verified` with exact merge containment.
- The closure run passed `28` targeted tests, mypy across `482` source files, pre-commit, and `proof-after-format`.
- Local security reported informational findings separately with zero blocking, warning, or error findings.
- PR Quality publisher, evidence, and release workflow files remain unchanged.

### Completed roadmap action

```text
action:
  id=release-evidence-recipes
  lane=Docs and operator experience
  title=Publish release-evidence recipes and sanitized proof samples
  priority=P2
  risk=low
  status=done
```

Closure evidence:

- PR `#1874` is merged at `c93c360ae99470c33788b95ea3305bb38dcc74b1`.
- The curated release-evidence recipes, sanitized proof samples, navigation, and focused drift contracts are present on `main`.
- The selection-correction audit classified `diagnostic-job-local-runner` as already implemented and selected the next unfinished reliability-spine action.

### Completed roadmap action

```text
action:
  id=exact-failure-extraction-safe-remediation
  lane=Repo-native diagnosis and remediation control
  title=Harden exact-failure extraction and safe-remediation visibility in the SDET Quality Gate PR comment
  priority=P1
  risk=medium
  value=Give contributors one canonical, confidence-scored first failure and a truthful remediation eligibility decision without expanding automation authority.
  status=done
```

**Closure evidence**

- PR `#1875` was squash-merged from head `ccf07bf17a5c06515db2eb05ec2e3b0fa2937066` at accepted-main commit `17876b2c481930161132fec028828813e5e6004c`.
- The trusted SDET Quality Gate reported `ready`, no first blocker, clear required checks, and clear security posture.
- The post-merge closure audit verified squash tree identity, exact eight-file scope, and unchanged protected workflows.
- Accepted-main proof passed `205` focused tests, scoped pre-commit, and `proof-after-format` with a clean isolated worktree.
- Automation, patch application, security dismissal, merge authorization, and semantic-equivalence authority remain denied.

**Selection correction**

- The PatchScorer to ProtectedVerifier candidate handoff is already implemented by `pr_quality_candidate_visibility`; it must not be duplicated.
- ProtectedVerifier review-first evidence propagation and verified network isolation already exist.
- The first explicit unfinished, non-authority-expanding gap is PR Quality workflow visibility for Git-grounded proof profiles beyond the current narrow Ruff profile.

### Completed roadmap action

```text
action:
  id=git-proof-profile-visibility
  lane=Protected proof and reviewer evidence
  title=Expand Git-grounded PR Quality proof visibility beyond the narrow Ruff profile
  priority=P1
  risk=medium
  value=Expose multiple existing allowlisted current-head proof profiles as reporting-only reviewer evidence without claiming semantic equivalence or expanding automation authority.
  status=done
```

**Closure evidence**

- PR Quality already executes the allowlisted `ruff_src_tests` and `pre_commit_all` profiles against the same exact Git-derived base/head inventory.
- The runtime-proof summary now retains a bounded, sanitized result for each executed profile instead of collapsing evidence into counts only.
- The contributor-facing PR Quality report shows each profile ID, canonical command, status, exit code, timeout state, workspace-mutation state, runtime-guard status, inventory-claim match, Git-inventory verification, network-boundary status, wrapping state, and review-first disposition.
- Missing, incomplete, failed, timed-out, mutated, inventory-mismatched, or authority-expanding profile evidence remains review-first.
- The runtime projection remains additive under the existing schema and grants no automation, patch application, security dismissal, merge, or semantic-equivalence authority.
- The PR Quality producer and trusted publisher workflows remain unchanged.

### Roadmap selection status

```text
roadmap_state:
  patch_ready_action=none
  next_recommended_pr=none
  automation_expansion_allowed=false
  merge_authority_expansion_allowed=false
```

The remaining partially aligned reliability-spine gaps require unavailable semantic-equivalence,
external-filesystem-containment, process-escape-prevention, or explicit human authority evidence.
They are capability/review blockers, not safe patch-ready roadmap work, and must not be converted
into implementation PRs without new evidence.


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
