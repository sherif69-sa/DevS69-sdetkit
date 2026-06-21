from __future__ import annotations

import json
from pathlib import Path

from sdetkit.remediation_readiness_report import (
    SCHEMA_VERSION,
    build_remediation_readiness_report,
    check_remediation_readiness_report_freshness,
    remediation_readiness_input_provenance,
    validate_remediation_readiness_report_freshness,
    write_artifacts,
)


def test_remediation_readiness_report_is_verifier_backed_and_non_authorizing() -> None:
    payload = build_remediation_readiness_report(".")

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["report_status"] == "review_required"
    assert payload["blocking_gap_count"] == 0
    provenance = payload["input_provenance"]
    assert provenance["digest_algorithm"] == "sha256"
    assert len(provenance["input_digest"]) == 64
    assert provenance["generator_schema_version"] == SCHEMA_VERSION
    assert provenance["generator_source"] == "src/sdetkit/remediation_readiness_report.py"
    assert provenance["policy_path"] == "config/adaptive_remediation_policy.default.json"
    assert provenance["missing_input_count"] == 0

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
    assert "input_digest:" in rendered
    assert "digest_algorithm: `sha256`" in rendered
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


def test_remediation_readiness_input_digest_is_deterministic_and_root_independent(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    first_generator = first / "generator.py"
    second_generator = second / "generator.py"
    first_generator.write_text("generator-v1\n", encoding="utf-8")
    second_generator.write_text("generator-v1\n", encoding="utf-8")

    first_payload = remediation_readiness_input_provenance(
        first,
        generator_path=first_generator,
    )
    second_payload = remediation_readiness_input_provenance(
        second,
        generator_path=second_generator,
    )

    assert first_payload == second_payload
    assert first_payload["digest_algorithm"] == "sha256"
    assert len(first_payload["input_digest"]) == 64
    assert first_payload["generator_schema_version"] == SCHEMA_VERSION
    assert first_payload["missing_input_count"] > 0


def test_remediation_readiness_input_digest_changes_with_policy_or_generator(
    tmp_path: Path,
) -> None:
    generator = tmp_path / "generator.py"
    generator.write_text("generator-v1\n", encoding="utf-8")
    baseline = remediation_readiness_input_provenance(
        tmp_path,
        generator_path=generator,
    )

    policy = tmp_path / "config" / "adaptive_remediation_policy.default.json"
    policy.parent.mkdir(parents=True)
    policy.write_text('{"schema_version":"policy-v1"}\n', encoding="utf-8")
    policy_changed = remediation_readiness_input_provenance(
        tmp_path,
        generator_path=generator,
    )
    assert policy_changed["input_digest"] != baseline["input_digest"]

    policy.unlink()
    generator.write_text("generator-v2\n", encoding="utf-8")
    generator_changed = remediation_readiness_input_provenance(
        tmp_path,
        generator_path=generator,
    )
    assert generator_changed["input_digest"] != baseline["input_digest"]


def test_remediation_readiness_freshness_detects_matching_and_stale_reports(
    tmp_path: Path,
) -> None:
    out = tmp_path / "reports" / "remediation-readiness-report.json"
    write_artifacts(root=tmp_path, out=out)

    fresh = check_remediation_readiness_report_freshness(
        root=tmp_path,
        report_path=out,
    )
    assert fresh["status"] == "fresh"
    assert fresh["fresh"] is True
    assert fresh["schema_valid"] is True
    assert fresh["authority_valid"] is True
    assert fresh["reasons"] == []
    assert fresh["repo_mutation"] is False
    assert fresh["automation_allowed"] is False
    assert fresh["patch_application_allowed"] is False
    assert fresh["merge_authorized"] is False

    policy = tmp_path / "config" / "adaptive_remediation_policy.default.json"
    policy.parent.mkdir(parents=True)
    policy.write_text('{"schema_version":"policy-v1"}\n', encoding="utf-8")
    stale = check_remediation_readiness_report_freshness(
        root=tmp_path,
        report_path=out,
    )
    assert stale["status"] == "stale"
    assert stale["fresh"] is False
    assert "input_digest_mismatch" in stale["reasons"]


def test_remediation_readiness_freshness_rejects_schema_and_authority_drift(
    tmp_path: Path,
) -> None:
    payload = build_remediation_readiness_report(tmp_path)
    payload["schema_version"] = "sdetkit.remediation_readiness_report.v0"
    payload["patch_application_allowed"] = True
    payload["authority_boundary"]["merge_authorized"] = True
    payload["rules"]["safe_to_patch"] = True

    result = validate_remediation_readiness_report_freshness(tmp_path, payload)

    assert result["status"] == "stale"
    assert result["fresh"] is False
    assert result["schema_valid"] is False
    assert result["authority_valid"] is False
    assert "schema_version_mismatch" in result["reasons"]
    assert "patch_application_allowed_mismatch" in result["reasons"]
    assert "authority_boundary_merge_authorized_mismatch" in result["reasons"]
    assert "rules_safe_to_patch_mismatch" in result["reasons"]


def test_remediation_readiness_freshness_rejects_missing_invalid_and_non_object(
    tmp_path: Path,
) -> None:
    missing = check_remediation_readiness_report_freshness(
        root=tmp_path,
        report_path=tmp_path / "missing.json",
    )
    assert missing["fresh"] is False
    assert "report_missing" in missing["reasons"]

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{invalid", encoding="utf-8")
    invalid = check_remediation_readiness_report_freshness(
        root=tmp_path,
        report_path=invalid_path,
    )
    assert invalid["fresh"] is False
    assert "report_invalid_json" in invalid["reasons"]

    non_object_path = tmp_path / "non-object.json"
    non_object_path.write_text("[]\n", encoding="utf-8")
    non_object = check_remediation_readiness_report_freshness(
        root=tmp_path,
        report_path=non_object_path,
    )
    assert non_object["fresh"] is False
    assert "report_not_object" in non_object["reasons"]


def test_remediation_readiness_cli_checks_freshness_without_rewriting(
    tmp_path: Path,
    capsys,
) -> None:
    from sdetkit.cli import main as cli_main

    out = tmp_path / "reports" / "remediation-readiness-report.json"
    write_artifacts(root=tmp_path, out=out)
    original = out.read_text(encoding="utf-8")

    rc = cli_main(
        [
            "remediation-readiness-report",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--check-freshness",
            "--format",
            "text",
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "freshness_status=fresh" in stdout
    assert "schema_valid=true" in stdout
    assert "authority_valid=true" in stdout
    assert out.read_text(encoding="utf-8") == original

    policy = tmp_path / "config" / "adaptive_remediation_policy.default.json"
    policy.parent.mkdir(parents=True)
    policy.write_text('{"schema_version":"policy-v1"}\n', encoding="utf-8")
    rc = cli_main(
        [
            "remediation-readiness-report",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--check-freshness",
            "--format",
            "json",
        ]
    )
    assert rc == 1
    stale = json.loads(capsys.readouterr().out)
    assert stale["fresh"] is False
    assert out.read_text(encoding="utf-8") == original
