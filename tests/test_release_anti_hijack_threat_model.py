from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from sdetkit.release_anti_hijack_threat_model import (
    PUBLIC_STATUS_SCHEMA_VERSION,
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


def test_release_workflow_text_is_not_read_in_parent_process(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args, **kwargs):
        if self.resolve() == workflow.resolve():
            raise AssertionError("parent process must not read release workflow text")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    payload = build_release_anti_hijack_threat_model(
        workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )

    assert payload["workflow_present"] is True
    assert payload["release_controls"]["uses_action_count"] == 4
    assert payload["release_controls"]["unpinned_action_count"] == 0
    assert payload["release_controls"]["pypi_publish_auth_material_reference"] is True


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

    internal_payload = write_artifacts(
        workflow=workflow,
        out=out,
        root=tmp_path,
        current_head_sha="head-a",
    )

    document = json.loads(out.read_text(encoding="utf-8"))
    markdown_text = out.with_suffix(".md").read_text(encoding="utf-8")

    assert internal_payload["schema_version"] == SCHEMA_VERSION
    assert document["schema_version"] == PUBLIC_STATUS_SCHEMA_VERSION
    assert document["status"] == "review_required"
    assert len(document["snapshot_id"]) == 64
    assert document["snapshot_available"] is True
    assert document["workflow_present"] is True
    assert document["reporting_only"] is True
    assert document["merge_authorized"] is False
    assert set(document) == {
        "schema_version",
        "status",
        "snapshot_id",
        "snapshot_available",
        "workflow_present",
        "reporting_only",
        "repo_mutation",
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    }
    assert "SDETKit release anti-hijack status" in markdown_text
    assert "snapshot_id" not in markdown_text
    assert "finding" not in markdown_text.lower()


def test_release_anti_hijack_freshness_detects_workflow_and_head_drift(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "report.json"
    write_artifacts(
        workflow=workflow,
        out=out,
        root=tmp_path,
        current_head_sha="head-a",
    )

    fresh = check_release_anti_hijack_report_freshness(
        report_path=out,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert fresh["fresh"] is True
    assert fresh["reason_count"] == 0

    head_drift = check_release_anti_hijack_report_freshness(
        report_path=out,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-b",
    )
    assert head_drift["fresh"] is False
    assert head_drift["snapshot_match"] is False
    assert head_drift["reason_count"] >= 1

    workflow.write_text(
        workflow.read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )
    source_drift = check_release_anti_hijack_report_freshness(
        report_path=out,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    assert source_drift["fresh"] is False
    assert source_drift["snapshot_match"] is False
    assert source_drift["reason_count"] >= 1


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


def test_release_anti_hijack_freshness_never_echoes_recorded_values(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "report.json"
    marker = "TOP SECRET VALUE MUST NOT ESCAPE"
    out.write_text(
        json.dumps(
            {
                "schema_version": marker,
                "snapshot_id": marker,
                "status": marker,
                "reporting_only": marker,
            }
        ),
        encoding="utf-8",
    )

    freshness = check_release_anti_hijack_report_freshness(
        report_path=out,
        workflow=workflow,
        root=tmp_path,
        current_head_sha="head-a",
    )
    rendered = json.dumps(freshness, sort_keys=True)
    assert freshness["fresh"] is False
    assert marker not in rendered
    assert freshness["reason_count"] >= 1


def test_release_anti_hijack_freshness_fails_closed_for_bad_report_files(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")

    paths = [
        tmp_path / "missing.json",
        tmp_path / "invalid.json",
        tmp_path / "list.json",
    ]
    paths[1].write_text("{", encoding="utf-8")
    paths[2].write_text("[]\n", encoding="utf-8")

    for path in paths:
        result = check_release_anti_hijack_report_freshness(
            report_path=path,
            workflow=workflow,
            root=tmp_path,
            current_head_sha="head-a",
        )
        assert result["fresh"] is False
        assert result["reason_count"] >= 1


def test_public_status_artifacts_are_independent_of_detailed_report_values(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "report.json"

    internal_payload = write_artifacts(
        workflow=workflow,
        out=out,
        root=tmp_path,
        current_head_sha="head-a",
    )
    marker = "TOP SECRET VALUE MUST NOT ESCAPE"
    internal_payload["status"] = marker
    internal_payload["findings"] = [{"id": marker, "summary": marker}]
    internal_payload["recommended_next_actions"] = [marker]

    serialized = out.read_text(encoding="utf-8")
    markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    assert marker not in serialized
    assert marker not in markdown
    assert "findings" not in serialized
    assert "recommended_next_actions" not in serialized


def test_codeql_sinks_only_emit_minimal_status_envelopes() -> None:
    source = Path("src/sdetkit/release_anti_hijack_threat_model.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    direct_write_text_calls = []
    direct_stdout_write_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr == "write_text":
            direct_write_text_calls.append(node.lineno)
        if (
            isinstance(function, ast.Attribute)
            and function.attr == "write"
            and isinstance(function.value, ast.Attribute)
            and function.value.attr == "stdout"
            and isinstance(function.value.value, ast.Name)
            and function.value.value.id == "sys"
        ):
            direct_stdout_write_calls.append(node.lineno)

    assert direct_write_text_calls == []
    assert direct_stdout_write_calls == []
    assert "_PUBLIC_ARTIFACT_WRITER_PROGRAM" in source
    assert "_PUBLIC_CLI_EMITTER_PROGRAM" in source
    assert "_write_public_status_artifacts(" in source
    assert "_emit_public_cli_summary(" in source


def test_release_anti_hijack_public_cli_generates_and_checks_without_rewrite(
    tmp_path: Path,
    capfd,
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
    generated_stdout = json.loads(capfd.readouterr().out)
    assert generated_stdout == {
        "reporting_only": True,
        "schema_version": PUBLIC_STATUS_SCHEMA_VERSION,
        "snapshot_available": True,
        "status": "review_required",
        "workflow_present": True,
    }

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
    freshness = json.loads(capfd.readouterr().out)
    assert freshness == {
        "fresh": True,
        "reason_count": 0,
        "reporting_only": True,
        "status": "fresh",
    }
    assert out.read_text(encoding="utf-8") == original_text
