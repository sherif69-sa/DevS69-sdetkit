# Doctor report contract

The Doctor report contract is the first focused upgrade for the Doctor feature. It turns standard Doctor output into a clean, review-first report that a maintainer can read quickly and a CI job can store as deterministic JSON.

## Purpose

Doctor should not be a placeholder status printer. It should explain repository health in practical operator language:

- what is wrong,
- why it matters,
- which roadmap lane is affected,
- what proof command should run next,
- and whether the finding must stay review-first.

The contract is intentionally advisory. It does not authorize automation, patch application, security dismissal, merge, or semantic-equivalence claims.

## Contract fields

```json
{
  "schema_version": "sdetkit.doctor_report.v1",
  "status": "green | review_required | blocked",
  "confidence": "low | medium | high",
  "summary": {},
  "primary_finding": {},
  "findings": [],
  "failure_vector_evidence": {},
  "safety_decision": {},
  "roadmap_alignment": {},
  "proof_commands": []
}
```

## Safety decision

Every Doctor report preserves the authority boundary:

```json
{
  "reporting_only": true,
  "review_first": true,
  "automation_allowed": false,
  "patch_application_allowed": false,
  "security_dismissal_allowed": false,
  "merge_authorized": false,
  "semantic_equivalence_claim": false
}
```

This keeps Doctor useful without making unsafe claims. Future remediation work can consume the report, but separate SafetyGate, verifier, proof, and trajectory records must still decide whether any action is allowed.

## Failure vector evidence

`build_doctor_report_contract()` accepts an optional `failure_vector_bundle` payload. This lets Doctor summarize existing `sdetkit.failure_vector.bundle.v1` evidence without parsing logs inside the Doctor report layer.

When evidence is supplied, the report includes:

- `failure_vector_count`
- counts by failure class and risk
- safe-fix candidate and review-first counts
- the highest-risk top failure signal
- the `failure_diagnosis` roadmap lane

Supplying failure-vector evidence can raise a green Doctor payload to `review_required`, because active failure vectors mean the repository still has unresolved diagnosis evidence. The report remains advisory and review-first.

## Markdown rendering

The Markdown renderer produces these sections:

- Status
- Primary Finding
- Findings
- Failure Vector Evidence
- Safety Decision
- Roadmap Alignment
- Proof Commands

The goal is professional operator communication, not ASCII art or rough placeholder output.

## Python usage

```python
from sdetkit.doctor_report import build_doctor_report_contract, render_doctor_report_markdown

contract = build_doctor_report_contract(doctor_payload)
markdown = render_doctor_report_markdown(contract)

contract_with_failure_vectors = build_doctor_report_contract(
    doctor_payload,
    failure_vector_bundle=failure_vector_bundle,
)
```

## CLI usage

The main `sdetkit` CLI can project standard Doctor output into the report contract without changing default Doctor behavior:

```bash
python -m sdetkit doctor --report-contract --format json
python -m sdetkit doctor --report-contract --format md --ci --out build/sdetkit/doctor-report.md
python -m sdetkit doctor --report-contract --failure-vector-bundle build/sdetkit/failure-vector.json
```

`--report-contract` uses the same Doctor checks and exit status, but renders the advisory report contract as JSON or Markdown. The mode keeps automation, patch application, and merge authorization false.

`--failure-vector-bundle` is only consumed by the report-contract route. It must point to a prebuilt `sdetkit.failure_vector.bundle.v1` JSON object. The CLI loads it as evidence and passes it to `build_doctor_report_contract(..., failure_vector_bundle=...)`.

## Artifact bundle

Use `--report-artifact-dir` when CI or an operator needs both machine-readable and human-readable report files in one deterministic directory:

```bash
python -m sdetkit doctor --report-contract --report-artifact-dir build/sdetkit
python -m sdetkit doctor --report-contract --failure-vector-bundle build/sdetkit/failure-vector.json --report-artifact-dir build/sdetkit
```

The artifact bundle writes:

- `doctor-report.json`
- `doctor-report.md`
- `doctor-report-manifest.json`

The manifest schema is `sdetkit.doctor_report_artifact_bundle.v1`. It records the report schema version, report status, output paths, and SHA-256 digests for the JSON and Markdown report files.
