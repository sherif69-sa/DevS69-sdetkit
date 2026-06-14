# Dashboard and reporting polish

Use this guide when reviewing PR Quality dashboards, artifact centers, Runtime
Proof summaries, or ProtectedVerifier output for the completed evidence circuit.

The goal is to make the reporting surfaces easier to read without changing
decision authority. This guide is documentation-only and reporting-only.

## Reporting surfaces

| Surface | Open when | Reviewer check |
| --- | --- | --- |
| PR Quality Review Dashboard | You need the fastest PR-facing summary | Confirm status, blocker, proof, artifact cards, and authority boundary |
| PR Quality Artifact Center | You need the artifact bundle map | Confirm expected artifact inventory and authority evidence sources |
| PR Quality Review Summary | You need markdown review context | Confirm the summary does not imply merge authorization |
| Runtime Proof artifacts | You need runtime or benchmark evidence | Confirm denied authority fields are preserved in JSON and markdown |
| ProtectedVerifier decision | Authority boundaries are disputed | Confirm expanded authority fields are absent or blocked |
| Evidence graph summary | You need the completed circuit source map | Confirm evidence flow and stop condition before reading artifacts |

## Dashboard reading order

1. Start with the PR Quality Review Dashboard.
2. Open the PR Quality Artifact Center when artifact completeness matters.
3. Open Runtime Proof summaries when runtime or benchmark evidence is referenced.
4. Open ProtectedVerifier output when the report mentions authority boundaries.
5. Use the Evidence graph summary to confirm where each evidence source belongs.
6. Return to the PR only after the authority boundary remains denied.

## Healthy dashboard signals

A healthy dashboard or reporting surface should show:

- the current PR status or review status;
- the primary blocker or an explicit no-blocker state;
- proof commands or proof artifacts to verify;
- artifact links or expected artifact inventory;
- authority boundary fields;
- reporting-only language;
- no automatic patch application;
- no automatic security dismissal;
- no merge authorization;
- no semantic-equivalence claim.

## Unhealthy dashboard signals

Treat a dashboard or report as blocked if it does any of these:

- claims a PR is safe to merge automatically;
- says a patch should be applied without a reviewed policy path;
- says stale GHAS or Code Scanning alerts can be dismissed automatically;
- claims semantic equivalence from replay evidence;
- hides missing evidence instead of marking it not collected;
- omits authority-boundary fields from a decision surface.

## Reporting polish rules

Dashboard and reporting changes should improve readability, navigation, or
artifact discoverability. They should not create a new evidence consumer unless
there is a distinct product surface and a concrete missing review artifact.

Acceptable polish examples:

- clearer dashboard section labels;
- links from docs to the correct artifact surface;
- explicit reading order for PR Quality, Runtime Proof, and ProtectedVerifier;
- clearer authority-boundary language;
- artifact inventory and source-map navigation.

Non-goals:

- automatic patch application;
- automatic security dismissal;
- automatic merge authorization;
- semantic-equivalence proof;
- another recursive consumer of the same benchmark replay evidence.

## Related docs

- [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map)
- [Evidence graph summary](evidence-graph-summary.md)
- [Operator evidence review guide](operator-evidence-review-guide.md)
- [Evidence circuit architecture checkpoint](evidence-circuit-architecture-checkpoint.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)

## Complete documentation bundle

Use this dashboard guide together with the full evidence review pack:

- [Evidence circuit review pack](evidence-circuit-review-pack.md)
- [Release-readiness evidence handoff](release-readiness-evidence-handoff.md)
- [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map)
- [Evidence graph summary](evidence-graph-summary.md)
- [Operator evidence review guide](operator-evidence-review-guide.md)

This bundle finishes the dashboard/reporting documentation layer for the
completed evidence circuit. Future work should move to product behavior,
artifact generation, dashboard UI polish, or release packaging rather than
adding another recursive documentation-only consumer.
