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

## Markdown rendering

The Markdown renderer produces these sections:

- Status
- Primary Finding
- Findings
- Safety Decision
- Roadmap Alignment
- Proof Commands

The goal is professional operator communication, not ASCII art or rough placeholder output.

## Initial usage

```python
from sdetkit.doctor_report import build_doctor_report_contract, render_doctor_report_markdown

contract = build_doctor_report_contract(doctor_payload)
markdown = render_doctor_report_markdown(contract)
```

## Follow-up work

A later PR should wire this contract into `python -m sdetkit doctor` output after the contract remains stable under focused tests.
