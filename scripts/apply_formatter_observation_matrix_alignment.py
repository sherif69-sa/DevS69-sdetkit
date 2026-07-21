from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"marker mismatch: {path}: {old[:60]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


path = ROOT / "docs/contracts/platform-capability-matrix.v1.json"
payload = json.loads(path.read_text(encoding="utf-8"))
payload["active_repository_gaps"] = [
    {
        "exit_criteria": "Retain one real digest-bound formatter proposal review with zero false authority.",
        "gap_id": "formatter_policy_proposal_reviewed_evidence",
        "priority": "P2",
        "review_first": True,
        "suggested_owner_files": [
            "docs/evidence/formatter-policy-proposal/reviewed-observations.v1.json",
            "docs/formatter-policy-proposal-observation.md",
            "tests/test_formatter_policy_proposal_observation.py",
        ],
        "title": "Retain one real reviewed formatter proposal observation",
    }
]
ids = {row["capability_id"] for row in payload["capabilities"]}
if "formatter_policy_proposal_observation" in ids:
    raise SystemExit("observation capability already present")
payload["capabilities"].append(
    {
        "authority": "reporting_only",
        "capability_id": "formatter_policy_proposal_observation",
        "owner_files": [
            "src/sdetkit/formatter_policy_proposal_observation.py",
            "docs/contracts/formatter-policy-proposal-observation.v1.json",
            "docs/formatter-policy-proposal-observation.md",
        ],
        "proof_tests": ["tests/test_formatter_policy_proposal_observation.py"],
        "status": "implemented_and_tested",
        "title": "Digest-bound formatter policy proposal observation",
    }
)
payload["capabilities"] = sorted(payload["capabilities"], key=lambda row: row["capability_id"])
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

TEST = "tests/test_platform_capability_matrix.py"
replace_once(
    TEST,
    '    "formatter_policy_proposal_eligibility",\n',
    '    "formatter_policy_proposal_eligibility",\n'
    '    "formatter_policy_proposal_observation",\n',
)
replace_once(
    TEST,
    '    assert {"formatter_policy_proposal_observation"} == set(gaps)\n',
    '    assert {"formatter_policy_proposal_reviewed_evidence"} == set(gaps)\n',
)
replace_once(
    TEST,
    '    assert "formatter_policy_proposal_eligibility" in capability_ids\n'
    '    assert payload["external_or_manual_blockers"] == []\n',
    '    assert "formatter_policy_proposal_eligibility" in capability_ids\n'
    '    assert "formatter_policy_proposal_observation" in capability_ids\n'
    '    assert payload["external_or_manual_blockers"] == []\n',
)
replace_once(
    TEST,
    '    assert "`formatter_policy_proposal_observation`" in roadmap\n'
    '    assert "Formatter policy proposal eligibility" in roadmap\n',
    '    assert "`formatter_policy_proposal_reviewed_evidence`" in roadmap\n'
    '    assert "Formatter policy proposal eligibility" in roadmap\n'
    '    assert "Formatter policy proposal observation" in roadmap\n'
    '    assert "formatter-policy-proposal-observation.json" in roadmap\n',
)

print("matrix_alignment=applied")
