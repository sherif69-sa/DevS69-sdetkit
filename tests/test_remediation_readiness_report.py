from __future__ import annotations

import json
from pathlib import Path

from sdetkit.remediation_readiness_report import (
    SCHEMA_VERSION,
    build_remediation_readiness_report,
    write_artifacts,
)


def test_remediation_readiness_report_is_verifier_backed_and_non_authorizing() -> None:
    payload = build_remediation_readiness_report(".")

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["report_status"] == "review_required"
    assert payload["blocking_gap_count"] == 0

    checks = payload["readiness_checks"]
    assert checks["policy_accepts_review_only_dry_run_plan"] is True
    assert checks["policy_accepts_narrow_safe_fix_candidate"] is True
    assert checks["protected_verifier_structural_check_passed"] is True
    assert checks["protected_verifier_keeps_semantic_equivalence_false"] is True
    assert checks["safety_gate_requires_local_repro_command"] is True

    safety_gate_policy = payload["safety_gate_policy"]
    assert safety_gate_policy["present"] is True
    assert safety_gate_policy["local_repro_command"] == "non_empty"
    assert safety_gate_policy["requires_local_repro_command"] is True

    contract_paths = {item["path"] for item in payload["contract_files"]}
    assert "src/sdetkit/safety_gate.py" in contract_paths
    assert "src/sdetkit/failure_vector.py" in contract_paths
    assert "docs/contracts/safety-gate-policy-matrix.v1.json" in contract_paths
    assert "docs/safety-gate-policy-matrix.md" in contract_paths

    verifier = payload["protected_verifier_result"]
    assert verifier["decision_status"] == "structurally_verified_candidate"
    assert verifier["structural_verification_passed"] is True
    assert verifier["semantic_equivalence_proven"] is False
    assert verifier["automation_allowed"] is False
    assert verifier["merge_authorized"] is False

    assert payload["rules"] == {
        "read_only": True,
        "dry_run_only": True,
        "verifier_backed": True,
        "patch_application_attempted": False,
        "target_repo_mutation": False,
        "review_first": True,
        "safe_to_patch": False,
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_remediation_readiness_report_blocks_unsafe_policy_expansion(tmp_path: Path) -> None:
    policy = tmp_path / "unsafe-policy.json"
    policy.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adaptive.remediation_policy.v1",
                "name": "unsafe-policy",
                "allowed_safe_fix_types": ["format_only", "review_required"],
                "max_changed_files": 8,
                "required_proof_outcomes": ["proof_passed"],
                "allow_review_required_auto_fix": True,
                "blocked_auto_source_codes": ["UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"],
            }
        ),
        encoding="utf-8",
    )

    payload = build_remediation_readiness_report(".", policy_path=policy)

    assert payload["report_status"] == "blocked"
    assert payload["blocking_gap_count"] >= 1
    assert payload["readiness_checks"]["policy_accepts_review_only_dry_run_plan"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False


def test_remediation_readiness_report_writes_json_and_markdown(tmp_path: Path) -> None:
    out = tmp_path / "reports" / "remediation-readiness-report.json"

    payload = write_artifacts(root=".", out=out)

    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()

    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == SCHEMA_VERSION
    assert persisted["blocking_gap_count"] == payload["blocking_gap_count"]

    rendered = markdown.read_text(encoding="utf-8")
    assert "# SDETKit remediation readiness report" in rendered
    assert "verifier_backed: true" in rendered
    assert "dry_run_only: true" in rendered
    assert "SafetyGate proof contract" in rendered
    assert "local_repro_command: non_empty" in rendered
    assert "semantic_equivalence_proven: false" in rendered
    assert "automation_allowed: false" in rendered


def test_remediation_readiness_report_public_cli_dispatch(tmp_path: Path, capsys) -> None:
    from sdetkit.cli import main as cli_main

    out = tmp_path / "reports" / "remediation-readiness-report.json"

    rc = cli_main(
        [
            "remediation-readiness-report",
            "--root",
            ".",
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "# SDETKit remediation readiness report" in stdout
    assert "verifier_backed: true" in stdout
    assert "dry_run_only: true" in stdout
    assert "automation_allowed: false" in stdout
    assert out.is_file()
    assert out.with_suffix(".md").is_file()


def test_remediation_readiness_report_stays_hidden_from_default_help() -> None:
    from sdetkit import cli

    default_help = cli._build_root_parser()[0].format_help()
    hidden_help = cli._build_root_parser(show_hidden_commands=True)[0].format_help()

    assert "remediation-readiness-report" not in default_help
    assert "remediation-readiness-report" in hidden_help
