# Evidence graph summary

This page summarizes the completed evidence circuit as a human-readable source
map. It explains where evidence enters, which surface carries it forward, and
what a reviewer should inspect before making a decision.

This is a documentation summary only. It does not add a new recursive consumer
to the evidence circuit.

## Summary

The completed evidence graph connects these review surfaces:

```text
FailureVectorEngine
  -> SafetyGate
  -> TrajectoryStore
  -> RepoMemory
  -> ProtectedVerifier
  -> PR Quality
  -> Runtime Proof
  -> ReplayableBenchmarkHarness
  -> Runtime Proof
  -> ProtectedVerifier
  -> PR Quality
  -> Runtime Proof
  -> ProtectedVerifier
```

The graph is useful because it gives maintainers a stable source map for
evidence review. It is not an automation authority graph.

## Source map

| Surface | Evidence role | Human review use |
| --- | --- | --- |
| FailureVectorEngine | Normalizes failure signals into a reviewable contract | Check whether the failure is structured and explainable |
| SafetyGate | Consumes failure evidence and preserves safe decision boundaries | Check whether the gate remains review-first |
| TrajectoryStore | Records evidence as durable history | Check whether evidence survives as history without mutation authority |
| RepoMemory | Summarizes recorded evidence for later review | Check whether memory reports evidence without granting authority |
| ProtectedVerifier | Blocks authority-expanding evidence | Check whether patch, dismissal, merge, and semantic authority remain denied |
| PR Quality | Presents maintainer-facing evidence | Check whether evidence is visible in the PR review surface |
| Runtime Proof | Bundles runtime evidence artifacts | Check whether proof artifacts preserve denied authority fields |
| ReplayableBenchmarkHarness | Replays evidence paths through benchmark scenarios | Check whether replay supports review without authorizing action |

## Review-only authority boundary

The graph preserves a reporting-only authority boundary.

Reviewers should treat the following as denied unless a separate reviewed policy
path explicitly authorizes otherwise:

- automatic patch application
- automatic security dismissal
- merge authorization
- semantic-equivalence claims
- semantic-equivalence proof

Evidence may explain risk. Evidence may point to a likely next investigation.
Evidence may justify asking for changes. Evidence must not become automatic
approval.

## Evidence graph reading order

Use this order when reviewing a PR or runtime artifact that includes evidence
from the circuit:

1. Start with the PR Quality summary because it is the maintainer-facing surface.
2. Open Runtime Proof artifacts when the summary references runtime evidence.
3. Inspect ProtectedVerifier when authority boundaries matter.
4. Use RepoMemory and TrajectoryStore evidence when historical context matters.
5. Use benchmark replay evidence when the same contract should be proven across
   replay scenarios.
6. Return to the PR decision only after confirming the authority boundary.

## Clean graph condition

A clean evidence graph has these properties:

- evidence sources are named;
- collection status is visible;
- missing evidence is explicit;
- authority-expanding fields are absent or blocked;
- patch application remains denied;
- security dismissal remains denied;
- merge authorization remains denied;
- semantic equivalence remains unclaimed;
- the final decision remains with a human reviewer.

## Blocked graph condition

A graph should be treated as blocked when any surface attempts to convert
evidence into authority.

Examples:

- Runtime Proof says merge is authorized.
- PR Quality implies automatic approval.
- ProtectedVerifier observes expanded authority fields.
- benchmark replay evidence claims semantic equivalence.
- a generated artifact suggests automatic patch application or security
  dismissal.

The correct response is investigation, not merge.

## Relationship to the architecture checkpoint

The architecture checkpoint records that the propagation loop stops at #1761.
This page adds a reviewer-facing map of that completed circuit.

Future work should extend product usability around this graph, such as
dashboards, source maps, artifact indexes, and release-readiness packaging. It
should not add another recursive consumer of the same benchmark replay evidence
without a distinct product surface.

## Related docs

- [Evidence circuit architecture checkpoint](evidence-circuit-architecture-checkpoint.md)
- [Operator evidence review guide](operator-evidence-review-guide.md)
- [Artifact reference and generated sample map](artifact-reference.md#evidence-circuit-artifact-source-map)
- [Investigation operator guide](investigation-operator-guide.md)
