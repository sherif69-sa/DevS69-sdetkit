# Current product delta

SDETKit's repository evolves faster than its published package. This page separates released behavior from capabilities that exist only on `main` so operators do not mistake repository documentation for installed-wheel proof.

Contract: [`docs/contracts/current-product-delta.v1.json`](contracts/current-product-delta.v1.json)

## Release truth

| Surface | Current truth |
|---|---|
| Published package | `sdetkit==1.0.3` |
| Published release date | 2026-04-18 |
| Current repository direction | 1.1.0 release-candidate preparation |
| Release status | `main_ahead_of_published_package` |

The installation command in the README intentionally pins the latest published package. Capabilities marked **main-only** below are not claimed to be available from that wheel until a later release is built, verified, and published.

## Stable released front door

The stable first path remains:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

These commands express the primary product outcome: determine whether a change is ready to ship and retain machine-readable evidence.

## Main-only capability groups

### Diagnostic failure model — advanced supported

- FailureVector extraction and normalized failure contracts.
- Review-first SafetyGate decisions.
- DiagnosticJob and execution-plan handoffs.

These capabilities are intended for operator diagnosis. Candidate status does not authorize patch application, merge, security dismissal, or semantic-equivalence claims.

### Verification and benchmarking — experimental incubator

- Isolated proof execution.
- Protected verifier decisions.
- Patch scoring and anti-cheat checks.
- Replayable remediation benchmark scorecards.

These surfaces remain qualification inputs for the next release. They are not described as autonomous remediation authority.

### Trajectory and repository memory — experimental incubator

- Trajectory storage.
- Repository memory.
- Diagnostic learning and pattern insights.

These surfaces retain evidence and repeated failure patterns. They do not independently prove a diagnosis or repair.

### External adoption intelligence — advanced supported

- Read-only repository surface discovery.
- Proof recommendation generation.
- External integration evidence bundles.
- Public repository trial-matrix reporting.

External-repository commands remain read-only by default. Recommended proof commands are operator guidance, not commands SDETKit is authorized to run automatically.

## 1.1.0 release blockers

The next release is blocked until all of the following are proven:

1. The changelog accounts for the product delta since 1.0.3.
2. The exact release-candidate wheel passes clean-room installation and canonical-command smoke tests on Python 3.10, 3.11, and 3.12.
3. Live-adoption evidence is refreshed at the release-candidate SHA.
4. Workflow and operator-surface consolidation is complete enough for maintainers and adopters to identify the canonical path.
5. PyPI publication uses reviewed Trusted Publishing configuration instead of a long-lived upload token.

## Authority boundary

The release-delta contract must preserve:

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

Changing any of those values requires a separate security- and verifier-reviewed policy change. This release-truth document cannot authorize it.
