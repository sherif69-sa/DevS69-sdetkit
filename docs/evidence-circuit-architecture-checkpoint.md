# Evidence circuit architecture checkpoint

This checkpoint records the evidence circuit completed across #1748 through
#1761. The purpose is to stop the propagation chain here, document the
architecture, and keep future roadmap slices from becoming another
"consume the previous consumer" loop.

## Why this checkpoint exists

The recent roadmap work connected evidence across the core review surfaces:

1. FailureVectorEngine produces normalized failure evidence.
2. SafetyGate consumes the normalized failure evidence.
3. TrajectoryStore records the evidence as durable history.
4. RepoMemory consumes the recorded evidence.
5. ProtectedVerifier consumes RepoMemory evidence.
6. PR Quality surfaces ProtectedVerifier evidence.
7. Runtime proof artifacts consume PR Quality and ProtectedVerifier evidence.
8. Replayable benchmark evidence validates the evidence path.
9. Runtime Proof, PR Quality, and ProtectedVerifier consume the replay evidence
   without expanding authority.

The circuit is now complete enough to treat it as an architecture asset, not as
a reason to keep adding recursive consumers.

## Completed evidence path

| Slice | Surface | Evidence movement |
| --- | --- | --- |
| #1748 | FailureVectorEngine | Adds normalized failure-vector contract |
| #1749 | SafetyGate | Consumes failure-vector contract |
| #1750 | TrajectoryStore | Records contract evidence |
| #1751 | RepoMemory | Consumes recorded contract evidence |
| #1752 | ProtectedVerifier | Consumes RepoMemory contract evidence |
| #1753 | PR Quality | Surfaces ProtectedVerifier contract evidence |
| #1754 | Runtime Proof | Consumes ProtectedVerifier contract evidence |
| #1755 | ProtectedVerifier | Consumes Runtime Proof contract evidence |
| #1756 | ReplayableBenchmarkHarness | Replays Runtime Proof contract evidence |
| #1757 | Runtime Proof | Consumes benchmark replay evidence |
| #1758 | ProtectedVerifier | Consumes Runtime Proof benchmark replay evidence |
| #1759 | PR Quality | Consumes ProtectedVerifier benchmark replay evidence |
| #1760 | Runtime Proof | Consumes PR Quality verifier benchmark replay evidence |
| #1761 | ProtectedVerifier | Consumes Runtime Proof PR Quality benchmark replay evidence |

## Architecture boundary

The completed circuit is reporting-only.

It may collect, summarize, replay, compare, and display evidence. It must not
grant any of the following authority:

- automatic patch application
- automatic security dismissal
- merge authorization
- semantic-equivalence claims

Every consumer in the circuit must preserve these denied authorities even when
incoming evidence contains a field that attempts to expand authority.

## What the circuit proves

The circuit proves that evidence can move across the delivery-reliability
surfaces without becoming an action-authorizing control plane.

The intended use is:

- Help maintainers see why a patch is risky or reviewable.
- Preserve the path from failure signal to review artifact.
- Make repeated evidence visible across PR Quality, Runtime Proof, and
  ProtectedVerifier.
- Keep human review as the final decision point.

The circuit does not prove that a code change is semantically equivalent. It
does not authorize a merge. It does not apply patches. It does not dismiss
security findings.

## Stop condition

The propagation loop stops at #1761.

Future slices should not add another consumer of the same benchmark replay
evidence unless there is a new product surface or a concrete missing review
artifact. Prefer one of these next directions instead:

- architecture diagrams and docs navigation
- [evidence graph summary](evidence-graph-summary.md)
- [operator review guide](operator-evidence-review-guide.md)
- dashboard/reporting polish
- release-readiness packaging
- narrower usability improvements

## Post-checkpoint benchmark validation

Later diagnostic execution-plan and trajectory-handoff work adds a new contract
to the existing control plane, but it does not reopen the recursive consumer
chain. Replayable benchmark scenarios may validate the observed,
not-provided, and forged-authority outcomes for that contract.

This validation remains reporting-only:

- planned commands are evidence, not executable instructions;
- trajectory proof command arrays remain empty;
- benchmark output does not feed current PR decisions or RepoMemory;
- forged execution authority must fail before trajectory evidence is written.

## Review checklist for future slices

Before adding another evidence consumer, confirm all of the following:

- The new surface is distinct from the existing circuit.
- The evidence is not already visible in PR Quality, Runtime Proof, or
  ProtectedVerifier.
- The new slice improves operator review, not automation authority.
- The implementation preserves reporting-only behavior.
- The proof output still shows no patch application, no security dismissal, no
  merge authorization, and no semantic-equivalence claim.
