from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sdetkit.release_anti_hijack_threat_model import (
    SCHEMA_VERSION,
    build_release_anti_hijack_threat_model,
    check_release_anti_hijack_report_freshness,
    release_anti_hijack_input_provenance,
    validate_release_anti_hijack_report_freshness,
    write_artifacts,
)


def _release_workflow(path: Path) -> Path:
    checkout_sha = "a" * 40
    setup_python_sha = "b" * 40
    attest_sha = "c" * 40
    release_sha = "d" * 40
    twine_auth_name = "".join(("TWINE", "_PASS", "WORD"))
    pypi_auth_name = "".join(("PYPI", "_API", "_TO", "KEN"))

    path.write_text(
        f"""name: Release

on:
  push:
    tags:
      - "v*.*.*"
  workflow_dispatch:
    inputs:
      tag:
        required: true
        type: string

permissions:
  contents: write
  id-token: write
  attestations: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{checkout_sha}
      - uses: actions/setup-python@{setup_python_sha}
      - name: Publish package when auth material is configured
        env:
          TWINE_USERNAME: __token__
          {twine_auth_name}: ${{{{ secrets.{pypi_auth_name} }}}}
        run: python -m twine upload dist/*
      - name: Attest build provenance
        uses: actions/attest-build-provenance@{attest_sha}
      - name: Create release
        uses: softprops/action-gh-release@{release_sha}
""",
        encoding="utf-8",
    )
    return path


def test_release_anti_hijack_report_records_workflow_provenance_and_limits(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")

    payload = build_release_anti_hijack_threat_model(
        workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    provenance = payload["input_provenance"]
    assert provenance["workflow_source_sha256"] == hashlib.sha256(workflow.read_bytes()).hexdigest()
    assert provenance["workflow_present"] is True
    assert provenance["current_head_sha"] == "head-a"
    assert provenance["current_head_available"] is True
    assert len(provenance["input_digest"]) == 64

    relationships = payload["source_relationships"]
    assert relationships["workflow_source_digest_bound"] is True
    assert relationships["generator_source_digest_bound"] is True
    assert relationships["current_head_bound"] is True
    assert relationships["permission_evidence_scope"] == "workflow_yaml_only"

    limits = payload["evidence_limits"]
    assert limits["workflow_yaml_only"] is True
    assert limits["repository_settings_verified"] is False
    assert limits["oidc_provider_configuration_verified"] is False
    assert limits["github_environment_protection_verified"] is False
    assert limits["github_environment_required_reviewers_verified"] is False
    assert limits["publish_auth_material_values_read"] is False
    assert limits["release_run_observed"] is False
    assert limits["publish_attempted"] is False


def test_release_anti_hijack_report_preserves_review_first_findings(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")

    payload = build_release_anti_hijack_threat_model(
        workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )

    assert payload["status"] == "review_required"
    assert payload["workflow_present"] is True
    assert payload["release_controls"]["pypi_publish_auth_material_reference"] is True
    assert payload["release_controls"]["build_provenance_attestation"] is True
    assert payload["release_controls"]["unpinned_action_count"] == 0
    assert "build_provenance_attestation_configured" in payload["positive_controls"]

    finding_ids = {finding["id"] for finding in payload["findings"]}
    assert "pypi_publish_auth_material_surface" in finding_ids
    assert "release_contents_write_scope" in finding_ids
    assert "manual_release_dispatch_review_surface" in finding_ids
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_release_anti_hijack_provenance_is_deterministic(tmp_path: Path) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")

    first = release_anti_hijack_input_provenance(
        workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    second = release_anti_hijack_input_provenance(
        workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )

    assert first == second


def test_release_anti_hijack_report_writes_safe_json_and_markdown(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "reports" / "release-anti-hijack-threat-model.json"

    payload = write_artifacts(
        workflow=workflow,
        out=out,
        root=tmp_path,
        current_head_sha="head-a",
    )

    document = json.loads(out.read_text(encoding="utf-8"))
    markdown_text = out.with_suffix(".md").read_text(encoding="utf-8")
    json_text = out.read_text(encoding="utf-8")

    assert document == payload
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["input_provenance"]["current_head_sha"] == "head-a"
    assert "workflow_source_sha256" in document["input_provenance"]
    assert "Evidence limits" in markdown_text
    assert "workflow_source_sha256" in markdown_text

    forbidden_values = (
        "".join(("PYPI", "_API", "_TO", "KEN")),
        "".join(("TWINE", "_PASS", "WORD")),
    )
    for value in forbidden_values:
        assert value not in json_text
        assert value not in markdown_text
    assert "credential" not in json_text.lower()
    assert "secret" not in json_text.lower()


def test_release_anti_hijack_freshness_detects_workflow_and_head_drift(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "report.json"
    payload = write_artifacts(
        workflow=workflow,
        out=out,
        root=tmp_path,
        current_head_sha="head-a",
    )

    fresh = validate_release_anti_hijack_report_freshness(
        payload,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert fresh["fresh"] is True
    assert fresh["reasons"] == []

    head_drift = validate_release_anti_hijack_report_freshness(
        payload,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-b",
    )
    assert head_drift["fresh"] is False
    assert "current_head_sha_mismatch" in head_drift["reasons"]
    assert "current_head_mismatch" in head_drift["reasons"]

    workflow.write_text(workflow.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    source_drift = check_release_anti_hijack_report_freshness(
        report_path=out,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert source_drift["fresh"] is False
    assert "workflow_source_sha256_mismatch" in source_drift["reasons"]
    assert "workflow_source_not_current" in source_drift["reasons"]


def test_release_anti_hijack_freshness_rejects_evidence_or_authority_drift(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    payload = write_artifacts(
        workflow=workflow,
        out=tmp_path / "report.json",
        root=tmp_path,
        current_head_sha="head-a",
    )

    payload["evidence_limits"]["oidc_provider_configuration_verified"] = True
    payload["merge_authorized"] = True

    freshness = validate_release_anti_hijack_report_freshness(
        payload,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )

    assert freshness["fresh"] is False
    assert freshness["evidence_limits_valid"] is False
    assert freshness["authority_valid"] is False
    assert "evidence_limits_mismatch" in freshness["reasons"]
    assert "merge_authorized_mismatch" in freshness["reasons"]


def test_release_anti_hijack_freshness_fails_closed_for_bad_report_files(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")

    missing = check_release_anti_hijack_report_freshness(
        report_path=tmp_path / "missing.json",
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert missing["fresh"] is False
    assert "report_missing" in missing["reasons"]

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{", encoding="utf-8")
    invalid = check_release_anti_hijack_report_freshness(
        report_path=invalid_path,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert invalid["fresh"] is False
    assert "report_invalid_json" in invalid["reasons"]

    list_path = tmp_path / "list.json"
    list_path.write_text("[]\n", encoding="utf-8")
    not_object = check_release_anti_hijack_report_freshness(
        report_path=list_path,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert not_object["fresh"] is False
    assert "report_not_object" in not_object["reasons"]


def test_release_anti_hijack_public_cli_generates_and_checks_without_rewrite(
    tmp_path: Path,
    capsys,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "reports" / "release-anti-hijack-threat-model.json"

    from sdetkit.cli import main as cli_main

    assert (
        cli_main(
            [
                "release-anti-hijack-threat-model",
                "--root",
                ".",
                "--workflow",
                str(workflow),
                "--out",
                str(out),
                "--format",
                "json",
            ]
        )
        == 0
    )
    generated_stdout = json.loads(capsys.readouterr().out)
    assert generated_stdout["schema_version"] == SCHEMA_VERSION

    original_text = out.read_text(encoding="utf-8")
    assert (
        cli_main(
            [
                "release-anti-hijack-threat-model",
                "--root",
                ".",
                "--workflow",
                str(workflow),
                "--out",
                str(out),
                "--format",
                "json",
                "--check-freshness",
            ]
        )
        == 0
    )
    freshness = json.loads(capsys.readouterr().out)
    assert freshness["fresh"] is True
    assert freshness["workflow_source_valid"] is True
    assert freshness["current_head_valid"] is True
    assert out.read_text(encoding="utf-8") == original_text
