# Evidence circuit review pack

This pack is the reviewer-facing landing page for the completed evidence circuit.
Use it when a maintainer needs to move from a PR Quality dashboard to the
supporting Runtime Proof, ProtectedVerifier, artifact, and release-readiness
documents.

This pack is documentation-only. It does not authorize automation, patch
application, security dismissal, merge, or semantic-equivalence claims.

## Open this pack when

Use this page when:

- a PR Quality dashboard references evidence from the completed circuit;
- a Runtime Proof bundle includes benchmark or authority evidence;
- a reviewer needs a compact path through the artifact source map;
- release-readiness notes need to cite evidence without expanding authority;
- a maintainer needs to distinguish reviewable evidence from approval.

## Review path

Follow this path before making a PR or release-readiness decision:

1. Open [Dashboard and reporting polish](dashboard-reporting-polish.md).
2. Open [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map).
3. Open [Evidence graph summary](evidence-graph-summary.md).
4. Open [Operator evidence review guide](operator-evidence-review-guide.md).
5. Open [Release-readiness evidence handoff](release-readiness-evidence-handoff.md).
6. Confirm that all authority boundaries remain denied.

## Decision matrix

| Situation | First doc | Safe outcome |
| --- | --- | --- |
| Reviewer needs a dashboard reading order | Dashboard and reporting polish | Continue human review |
| Reviewer needs artifact paths | Artifact reference source map | Inspect artifacts before deciding |
| Reviewer needs circuit context | Evidence graph summary | Confirm source and stop condition |
| Reviewer sees authority fields | Operator evidence review guide | Block if authority expands |
| Reviewer prepares release notes | Release-readiness evidence handoff | Cite evidence without granting authority |

## Required authority checks

Before accepting any dashboard or artifact summary, confirm:

- patch application remains denied;
- security dismissal remains denied;
- merge authorization remains denied;
- semantic-equivalence claims remain absent;
- semantic-equivalence proof remains absent;
- missing evidence is marked as not collected;
- final decision remains with the human reviewer.

## Finished-document checklist

The documentation bundle is complete when these surfaces agree:

- docs index links the review pack and dashboard polish guide;
- roadmap points to the dashboard/reporting and release-readiness handoff;
- artifact reference maps evidence-circuit artifacts to review actions;
- evidence graph summary links to the dashboard and review pack;
- operator guide explains authority-boundary review;
- CI artifact walkthrough points reviewers back to this pack;
- release-readiness handoff keeps evidence reporting-only.

## Non-goals

This pack does not add a new evidence consumer. It does not create a release
gate. It does not replace PR review. It does not authorize automated fixes,
dismissals, merges, or semantic-equivalence claims.
