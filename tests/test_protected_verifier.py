from __future__ import annotations

import json
from pathlib import Path

from sdetkit.protected_verifier import (
    CHANGED_FILE_INVENTORY_MISMATCH,
    OUTSIDE_SCORED_SCOPE,
    PATCH_SCORE_NOT_CANDIDATE,
    PROTECTED_PATH_CHANGED,
    REQUIRED_PROOF_FAILED,
    REQUIRED_PROOF_NOT_CAPTURED,
    SEMANTIC_EQUIVALENCE_NOT_PROVEN,
    main,
    verify_candidate,
)


def _candidate_score() -> dict:
    return {
        "patch_id": "format-patch",
        "diagnosis_id": "formatting-autopilot",
        "score": 100,
        "changed_files": ["src/sdetkit/example.py"],
        "allowed_files": ["src/sdetkit/example.py"],
        "proof_requirements": ["python -m pre_commit run -a"],
        "decision": {
            "status": "candidate_for_protected_verification",
            "candidate_for_protected_verification": True,
            "automation_allowed": False,
        },
    }


def _passing_evidence() -> dict:
    return {
        "changed_files": ["src/sdetkit/example.py"],
        "proof_results": [
            {
                "command": "python -m pre_commit run -a",
                "status": "passed",
                "exit_code": 0,
            }
        ],
    }


def test_verifier_structurally_verifies_candidate_but_does_not_authorize() -> None:
    payload = verify_candidate(
        patch_score=_candidate_score(),
        verification_evidence=_passing_evidence(),
    )

    decision = payload["decision"]
    assert decision["status"] == "structurally_verified_candidate"
    assert decision["structural_verification_passed"] is True
    assert decision["semantic_equivalence_proven"] is False
    assert decision["automation_allowed"] is False
    assert decision["merge_authorized"] is False
    assert payload["findings"] == [
        {
            "code": SEMANTIC_EQUIVALENCE_NOT_PROVEN,
            "message": (
                "This prototype verifies structural scope and captured proof results only; "
                "it does not prove semantic equivalence."
            ),
            "blocking": False,
            "files": [],
            "commands": [],
        }
    ]


def test_verifier_blocks_non_candidate_patch_score() -> None:
    score = _candidate_score()
    score["decision"] = {
        "status": "blocked_review_first",
        "candidate_for_protected_verification": False,
        "automation_allowed": False,
    }

    payload = verify_candidate(
        patch_score=score,
        verification_evidence=_passing_evidence(),
    )

    codes = {finding["code"] for finding in payload["findings"]}
    assert PATCH_SCORE_NOT_CANDIDATE in codes
    assert payload["decision"]["status"] == "blocked_review_first"
    assert payload["decision"]["structural_verification_passed"] is False


def test_verifier_blocks_file_inventory_drift_and_protected_paths() -> None:
    score = _candidate_score()
    score["changed_files"] = ["src/sdetkit/example.py", "tests/test_example.py"]
    score["allowed_files"] = ["src/sdetkit/example.py", "tests/test_example.py"]

    payload = verify_candidate(
        patch_score=score,
        verification_evidence={
            "changed_files": ["src/sdetkit/example.py", "tests/test_example.py"],
            "proof_results": _passing_evidence()["proof_results"],
        },
    )

    codes = {finding["code"] for finding in payload["findings"]}
    assert PROTECTED_PATH_CHANGED in codes
    assert payload["decision"]["status"] == "blocked_review_first"


def test_verifier_blocks_changed_file_mismatch_and_outside_scope() -> None:
    payload = verify_candidate(
        patch_score=_candidate_score(),
        verification_evidence={
            "changed_files": ["src/sdetkit/example.py", "src/sdetkit/unplanned.py"],
            "proof_results": _passing_evidence()["proof_results"],
        },
    )

    codes = {finding["code"] for finding in payload["findings"]}
    assert CHANGED_FILE_INVENTORY_MISMATCH in codes
    assert OUTSIDE_SCORED_SCOPE in codes
    assert payload["decision"]["status"] == "blocked_review_first"


def test_verifier_blocks_missing_and_failed_required_proof() -> None:
    missing = verify_candidate(
        patch_score=_candidate_score(),
        verification_evidence={"changed_files": ["src/sdetkit/example.py"], "proof_results": []},
    )
    assert REQUIRED_PROOF_NOT_CAPTURED in {finding["code"] for finding in missing["findings"]}

    failed = verify_candidate(
        patch_score=_candidate_score(),
        verification_evidence={
            "changed_files": ["src/sdetkit/example.py"],
            "proof_results": [
                {
                    "command": "python -m pre_commit run -a",
                    "status": "failed",
                    "exit_code": 1,
                }
            ],
        },
    )
    assert REQUIRED_PROOF_FAILED in {finding["code"] for finding in failed["findings"]}
    assert failed["decision"]["status"] == "blocked_review_first"


def test_verifier_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    score_path = tmp_path / "patch-score.json"
    evidence_path = tmp_path / "verification-evidence.json"
    out_dir = tmp_path / "protected-verifier"

    score_path.write_text(json.dumps(_candidate_score()), encoding="utf-8")
    evidence_path.write_text(json.dumps(_passing_evidence()), encoding="utf-8")

    rc = main(
        [
            "--patch-score",
            str(score_path),
            "--verification-evidence",
            str(evidence_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "protected-verifier-result.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "protected-verifier-result.md").read_text(encoding="utf-8")

    assert printed["decision"]["status"] == "structurally_verified_candidate"
    assert saved["decision"]["automation_allowed"] is False
    assert "# Protected verifier result" in markdown
    assert "does not prove semantic equivalence" in markdown
