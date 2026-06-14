# Release-readiness evidence handoff

Use this page when evidence from PR Quality, Runtime Proof, ProtectedVerifier,
or the evidence graph needs to be summarized for release-readiness review.

The handoff is reporting-only. It packages evidence for humans; it does not
authorize release, merge, patch application, security dismissal, or
semantic-equivalence claims.

## Handoff inputs

A complete release-readiness handoff may reference:

- PR Quality Review Dashboard status;
- PR Quality Artifact Center inventory;
- Runtime Proof summary artifacts;
- ProtectedVerifier decision output;
- evidence graph summary;
- artifact source map;
- operator evidence review guide.

## Handoff template

Use this structure in release notes or command-center comments:

```markdown
### Evidence reviewed
- PR Quality dashboard:
- PR Quality artifact center:
- Runtime Proof summary:
- ProtectedVerifier decision:
- Evidence graph/source map:

### Authority boundary
- Patch application allowed: false
- Security dismissal allowed: false
- Merge authorization: false
- Semantic-equivalence claim: false
- Semantic-equivalence proof: false

### Human decision required
- Reviewer:
- Required proof:
- Remaining blocker:
```

## Review rules

Release-readiness language must stay factual:

- say evidence is present, absent, or not collected;
- say a blocker is reviewable or needs investigation;
- cite artifact names or docs;
- avoid saying evidence approves a merge;
- avoid saying replay proves semantic equivalence;
- avoid implying stale alerts can be dismissed automatically.

## Blocked handoff

A release-readiness handoff is blocked when:

- any artifact grants merge authorization;
- any report says patch application is automatic;
- any report says security dismissal is automatic;
- any replay evidence claims semantic equivalence;
- missing evidence is hidden;
- the human reviewer cannot identify the source artifact.

## Related docs

- [Evidence circuit review pack](evidence-circuit-review-pack.md)
- [Dashboard and reporting polish](dashboard-reporting-polish.md)
- [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map)
- [Evidence graph summary](evidence-graph-summary.md)
- [Operator evidence review guide](operator-evidence-review-guide.md)
