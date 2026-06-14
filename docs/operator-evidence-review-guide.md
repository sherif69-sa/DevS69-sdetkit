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
