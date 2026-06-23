# Operator evidence review guide

Use this guide when reviewing evidence produced by the completed evidence
circuit from #1748 through #1761.

The goal is to help a human reviewer understand what to inspect, where the
evidence came from, and which authority boundaries must remain denied.

This guide is not an automation policy. It does not authorize patch
application, security dismissal, merge, or semantic-equivalence claims.

## When to use this guide

Use this guide when a PR, maintenance run, or runtime proof artifact includes
evidence from one or more of these surfaces:

- FailureVectorEngine
- SafetyGate
- TrajectoryStore
- RepoMemory
- ProtectedVerifier
- PR Quality
- Runtime Proof
- ReplayableBenchmarkHarness

Start with the evidence-circuit checkpoint when you need the architecture
overview, then use this page for the human review flow.

## Fast review flow

1. Confirm the evidence source.
2. Confirm the evidence status is collected or intentionally not collected.
3. Check whether any authority-expanding fields were observed.
4. Confirm every authority boundary remains denied.
5. Review the human-facing summary in PR Quality, Runtime Proof, or
   ProtectedVerifier.
6. Decide whether more investigation is needed before merge review continues.

The reviewer may use the evidence to ask for changes, request more proof, or
document risk. The reviewer must not treat the evidence as automatic approval.

## Evidence source map

| Source | What to inspect | Reviewer question |
| --- | --- | --- |
| FailureVectorEngine | Normalized failure contract | Is the failure signal structured enough to review? |
| SafetyGate | Contract and safety decision evidence | Did the gate preserve review-first behavior? |
| TrajectoryStore | Durable recorded evidence | Is the evidence retained without mutation authority? |
| RepoMemory | Profile and consumed contract evidence | Did memory summarize evidence without creating authority? |
| ProtectedVerifier | Runtime, RepoMemory, and benchmark evidence | Did verifier block authority expansion? |
| PR Quality | Reviewer-facing summary and action report | Is the evidence visible to maintainers? |
| Runtime Proof | Runtime proof artifact bundle | Does the proof show denied authority fields? |
| ReplayableBenchmarkHarness | Replay evidence | Does replay support review without authorizing action? |

## Authority checks

Every review should confirm these fields remain false or denied:

- `automation_allowed`
- `patch_application_allowed`
- `security_dismissal_allowed`
- `merge_authorized`
- `semantic_equivalence_claim`
- `semantic_equivalence_proven`

If any evidence source attempts to set one of these as true, treat it as
blocking review evidence. The correct response is to keep the PR review-first
and investigate the source of the authority expansion.

## How to read ProtectedVerifier evidence

ProtectedVerifier is the final review guard for the completed circuit. It may
summarize evidence from RepoMemory, Runtime Proof, PR Quality, and benchmark
replay.

The important reviewer checks are:

- `expanded_authority_fields` is empty or explicitly flagged.
- patch application remains denied.
- security dismissal remains denied.
- merge authorization remains denied.
- semantic equivalence remains unclaimed.
- the markdown summary explains the evidence without granting action authority.

A clean ProtectedVerifier result means the evidence is reviewable. It does not
mean the PR is automatically safe to merge.

## How to read PR Quality evidence

PR Quality is the maintainer-facing surface. It should make evidence easier to
read without changing the decision authority.

The important reviewer checks are:

- PR Quality includes the relevant ProtectedVerifier or benchmark replay
  evidence.
- the action report remains review-first.
- stale or blocked security findings are not dismissed automatically.
- the summary does not imply merge authorization.
- proof commands are visible and reproducible.

PR Quality may help prioritize a review, but it must not replace the reviewer.

## How to read Runtime Proof evidence

Runtime Proof is the artifact bundle showing what was observed during the
proof flow.

The important reviewer checks are:

- collected evidence is labeled with status and counts.
- missing evidence is explicit rather than silently ignored.
- benchmark replay evidence remains reporting-only.
- authority fields remain denied.
- proof output is tied to the reviewed branch and commit.

Runtime Proof may make the evidence portable. It does not make the evidence
self-authorizing.

## Review outcomes

Use one of these outcomes when summarizing the evidence:

| Outcome | Meaning | Next action |
| --- | --- | --- |
| Reviewable | Evidence is present and authority remains denied | Continue normal human review |
| Needs investigation | Evidence is incomplete, inconsistent, or unclear | Request focused proof or investigation |
| Blocked by authority expansion | Evidence attempted to grant automation, dismissal, merge, or semantic authority | Block until the source is corrected |
| Not collected | Evidence is absent but explicitly marked not collected | Decide whether the slice requires it |

## Stop condition reminder

The evidence propagation loop stops at #1761.

Do not add another consumer of the same benchmark replay evidence unless there
is a new product surface or a concrete missing review artifact. Prefer review
guides, source maps, dashboards, release-readiness packaging, or operator
usability improvements.

## Minimal reviewer checklist

Before accepting a PR that uses this evidence circuit, verify:

- the branch proof was run on the reviewed commit;
- PR Quality, Runtime Proof, or ProtectedVerifier exposes the relevant
  evidence;
- no evidence source grants patch application;
- no evidence source grants security dismissal;
- no evidence source grants merge authorization;
- no evidence source claims semantic equivalence;
- the final decision remains human-reviewed.

## Related source map

Use [Evidence graph summary](evidence-graph-summary.md) when you need a compact source map of the completed evidence circuit before reading individual PR Quality, Runtime Proof, or ProtectedVerifier artifacts.

## Documentation bundle handoff

For complete reviewer navigation, pair this guide with:

- [Evidence circuit review pack](evidence-circuit-review-pack.md)
- [Dashboard and reporting polish](dashboard-reporting-polish.md)
- [Release-readiness evidence handoff](release-readiness-evidence-handoff.md)

The handoff remains review-first and reporting-only.

## Operator onboarding evidence flow

Use the local operator onboarding evidence flow when a maintainer needs one
reviewer-facing map of the operator path:

```bash
python -m sdetkit.operator_onboarding_evidence_flow \
  --root . \
  --out-json build/sdetkit/operator-onboarding-evidence-flow/flow.json \
  --out-md build/sdetkit/operator-onboarding-evidence-flow/flow.md \
  --format text
```

The flow maps the operator onramp dry run, first-proof collection,
onboarding-next action plan, onboarding wizard, operator brief, operator
evidence loop, and onramp verification. It is reporting-only and does not
authorize remediation, patch application, merge, security dismissal, or
semantic-equivalence claims.

## Review the maintenance queue rollup

Use the maintenance queue rollup when a maintainer needs one review-first ordering of the issue queue, automation-health evidence, and security-followup dispositions.

Generate the rollup from the three accepted source artifacts:

```bash
python -m sdetkit maintenance-queue-rollup \
  --issue-queue-json build/sdetkit/issue-queue-classifier.json \
  --automation-health-json build/sdetkit/automation-health.json \
  --security-followup-json build/sdetkit/security-followup-disposition.json \
  --out build/sdetkit/maintenance-queue-rollup.json \
  --format text
```

The command always writes the JSON artifact. `--format text` prints a compact operator summary; `--format json` prints the same artifact payload to standard output.

Before relying on an existing classifier, automation-health, or rollup artifact, run the same command with `--check-freshness`. The check is read-only and fails closed when the report is missing, malformed, bound to another Git head, generated from different issue/input bytes, uses unsupported input schemas, or records different source run IDs.

Read these top-level fields first:

- `schema_version`
- `status`
- `source_issue_count`
- `queue_item_count`
- `review_required_count`
- `close_candidate_count`
- `primary_issue`
- `recommended_next_action`
- `queue_items`
- `input_artifacts`
- `automation_allowed`
- `merge_authorized`
- `semantic_equivalence_proven`

The status values mean:

- `review required`: one or more queue items require human review;
- `ready with proof`: queue items exist, but none currently require review;
- `empty`: no valid queue items were produced.

Queue items requiring review are ordered before other items. Within that boundary, higher `rank_score` values are ordered first, followed by the lower issue number when scores are equal.

For each queue item, inspect:

- `issue_number`
- `title`
- `lane`
- `classification`
- `rank_score`
- `review_required`
- `close_candidate`
- `security_disposition`
- `automation_health_state`
- `recommended_action`

`primary_issue` identifies the first item in the review ordering. It is a prioritization signal, not authorization to edit, close, dismiss, or merge anything. Likewise, `close_candidate=true` is context for human review and never performs issue mutation.

The rollup preserves these boundaries at the top level and on every queue item:

```text
automation_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

The artifact is registered as `maintenance-queue-rollup-json` at `build/sdetkit/maintenance-queue-rollup.json` with schema `sdetkit.maintenance.queue.rollup.v2`. The dashboard accepts both legacy v1 and current v2 rollups. The artifact is local and reporting-only; it does not apply patches, mutate issues, dismiss security findings, or make a merge decision.

## Review the maintenance queue rollup dashboard

Use the dashboard after generating a valid `maintenance-queue-rollup.json` artifact. It provides a static local view of queue ordering, review-required items, close-candidate context, lane counts, and denied authority fields.

Generate the HTML dashboard with the installed console command:

```bash
sdetkit-maintenance-queue-rollup-dashboard \
  --rollup-path build/sdetkit/maintenance-queue-rollup.json \
  --format html \
  --out build/sdetkit/maintenance-queue-rollup-dashboard.html
```

The equivalent module fallback is:

```bash
python -m sdetkit.maintenance_queue_rollup_dashboard \
  --rollup-path build/sdetkit/maintenance-queue-rollup.json \
  --format html \
  --out build/sdetkit/maintenance-queue-rollup-dashboard.html
```

Generate the deterministic JSON projection with:

```bash
sdetkit-maintenance-queue-rollup-dashboard \
  --rollup-path build/sdetkit/maintenance-queue-rollup.json \
  --format json \
  --out build/sdetkit/maintenance-queue-rollup-dashboard.json
```

The dashboard accepts legacy `sdetkit.maintenance.queue.rollup.v1` and current `sdetkit.maintenance.queue.rollup.v2` source artifacts. It validates `queue_item_count`, `review_required_count`, `close_candidate_count`, and `primary_issue` against the ordered `queue_items` before writing output. Missing, malformed, unsupported, inconsistent, or authority-expanding input returns exit code `2`; successful rendering returns `0`.

Read these dashboard fields first:

- `schema_version`
- `status`
- `rollup_path`
- `rollup_exists`
- `source_rollup_schema_version`
- `source_rollup_status`
- `source_issue_count`
- `queue_item_count`
- `review_required_count`
- `close_candidate_count`
- `primary_issue`
- `recommended_next_action`
- `lane_counts`
- `input_artifacts`
- `queue_items`
- `local_only`
- `read_only`
- `decision_boundary`

The dashboard status is `ready` when queue items are present and `empty` when the source rollup is valid but contains no items. The source rollup status remains separately visible in `source_rollup_status`.

The HTML output is static and escapes source-provided text. It contains no JavaScript, performs no network access, and does not modify the source rollup. The JSON output is deterministic for the same source artifact and command arguments.

Every dashboard decision-boundary field must remain false:

```text
current_pr_decision_input=false
automation_allowed=false
issue_mutation_allowed=false
security_dismissal_allowed=false
proof_commands_executed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

The dashboard schema is `sdetkit.maintenance_queue_rollup_dashboard.v1`. The default HTML path is `build/sdetkit/maintenance-queue-rollup-dashboard.html`; the recommended JSON path is `build/sdetkit/maintenance-queue-rollup-dashboard.json`.

This dashboard is a read-only review surface. `primary_issue`, `review_required`, and `close_candidate` are prioritization context only and never authorize issue mutation, security dismissal, patch application, proof execution, or merge. Dashboard JSON artifact-contract registration remains a separate follow-up.


## Product maturity radar projection trust

`product-maturity-radar` is a reporting-only projection. It does not become the
source of authority for workflow, adoption, remediation, release, diagnosis, or
queue claims.

Known dependency reports are discovered at their standard `build/sdetkit` paths.
Use repeated `--report-json <dependency-id>=<path>` arguments to override those
paths. Missing reports produce a current but partial projection. A report that
is present but malformed, schema-incompatible, authority-expanding, bound to a
different Git head, or missing deterministic provenance invalidates the
projection.

Run the same command with `--check-freshness` to compare an existing radar with
the current repository snapshot and dependency-report bytes. The check is
read-only and returns nonzero for stale or invalid evidence. It never rewrites
the radar, mutates issues, applies patches, dismisses security findings, or
authorizes merge.

## Cross-report consistency verdict

`cross-report-consistency` reads existing decision-report JSON artifacts and emits
one reporting-only verdict for schema, Git-head, freshness, and authority-boundary
agreement. It never regenerates dependency reports.

Discovery mode is the default. Missing report artifacts or legacy trust fields
produce a `partial` result, while present schema mismatches, foreign or conflicting
Git heads, stale or invalid dependencies, and explicit authority expansion produce
a `blocked` result. Use `--complete` only when the requested decision bundle must
contain every core report.

```bash
python -m sdetkit cross-report-consistency \
  --root . \
  --out build/sdetkit/cross-report-consistency.json \
  --format json

python -m sdetkit cross-report-consistency \
  --root . \
  --out build/sdetkit/cross-report-consistency.json \
  --check-freshness \
  --format text
```

The aggregate schema is `sdetkit.cross_report_consistency.v1`. The output binds to
the current Git head, generator bytes, artifact-contract index bytes, and every
known report path, including explicit missing markers. Recommendation text is not
reconciled in this first slice.

All authority fields remain non-authorizing: reporting only, no repository or
issue mutation, no patch application, no security dismissal, no merge authority,
and no semantic-equivalence claim.

## Report dependency graph and freshness dashboard

`report-dependency-graph` is a reporting-only projection over the canonical
`cross_report_consistency.REPORT_SPECS` registry. It also normalizes declared
Product Maturity Radar dependencies and dependency records embedded in present
reports. It does not replace the source reports or create a new authority
boundary.

The graph distinguishes producer schema from public artifact schema. This is
required for reports such as release anti-hijack, whose internal threat-model
schema and sanitized public-status schema are intentionally different.
Dependency edges state whether their expected schema refers to the producer or
the public artifact.

Use discovery mode for an inventory in which absent reports are partial. Use
`--complete` only when the supplied report bundle is expected to contain every
required report. In complete mode, missing or unmapped dependencies block the
graph. Directed cycles always block because they make freshness ordering
ambiguous.

```bash
python -m sdetkit report-dependency-graph \
  --root . \
  --out build/sdetkit/report-dependency-graph.json \
  --format text

python -m sdetkit report-dependency-graph \
  --root . \
  --out build/sdetkit/report-dependency-graph.json \
  --check-freshness \
  --format text

python -m sdetkit report-dependency-graph-dashboard \
  --graph-path build/sdetkit/report-dependency-graph.json \
  --format html \
  --out build/sdetkit/report-dependency-graph-dashboard.html
```

The dashboard is static, local-only, and read-only. It escapes report-provided
text, contains no JavaScript, and never regenerates source reports. Node states,
edge schema roles, cycles, unmapped dependencies, and source-head bindings are
review context only.

Every graph and dashboard authority field remains non-authorizing:

```text
reporting_only=true
repo_mutation=false
issue_mutation_allowed=false
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```
