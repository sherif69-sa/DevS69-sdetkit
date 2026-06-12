from __future__ import annotations

import json
from pathlib import Path

from sdetkit.release_anti_hijack_threat_model import (
    SCHEMA_VERSION,
    build_release_anti_hijack_threat_model,
    write_artifacts,
)


def _release_workflow(path: Path) -> Path:
    checkout_sha = "a" * 40
    setup_python_sha = "b" * 40
    attest_sha = "c" * 40
    twine_env_name = "".join(("TWINE", "_PASS", "WORD"))
    pypi_credential_name = "".join(("PYPI", "_API", "_TO", "KEN"))

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
      - name: Publish package when credential is configured
        env:
          TWINE_USERNAME: __token__
          {twine_env_name}: ${{{{ secrets.{pypi_credential_name} }}}}
        run: python -m twine upload dist/*
      - name: Attest build provenance
        uses: actions/attest-build-provenance@{attest_sha}
""",
        encoding="utf-8",
    )
    return path


def test_release_anti_hijack_threat_model_reports_publish_credential_surface(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")

    payload = build_release_anti_hijack_threat_model(workflow)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "review_required"
    assert payload["workflow_present"] is True
    assert payload["release_controls"]["pypi_publish_credential_reference"] is True
    assert payload["release_controls"]["build_provenance_attestation"] is True
    assert payload["release_controls"]["unpinned_action_count"] == 0
    assert "build_provenance_attestation_configured" in payload["positive_controls"]

    finding_ids = {finding["id"] for finding in payload["findings"]}
    assert "pypi_publish_credential_surface" in finding_ids
    assert "release_contents_write_scope" in finding_ids
    assert "manual_release_dispatch_review_surface" in finding_ids

    assert payload["rules"]["workflow_read_only"] is True
    assert payload["rules"]["release_workflow_mutated"] is False
    assert payload["rules"]["publish_attempted"] is False
    assert payload["rules"]["pypi_trusted_publisher_verified"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_release_anti_hijack_threat_model_writes_json_and_markdown(
    tmp_path: Path,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "reports" / "release-anti-hijack-threat-model.json"

    payload = write_artifacts(workflow=workflow, out=out)

    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()
    json_text = out.read_text(encoding="utf-8")
    markdown_text = markdown.read_text(encoding="utf-8")
    assert "PYPI_API_TOKEN" not in json_text
    assert "TWINE_PASSWORD" not in json_text
    assert "credential" not in json_text.lower()
    assert "secret" not in json_text.lower()
    assert "PYPI_API_TOKEN" not in markdown_text
    assert "TWINE_PASSWORD" not in markdown_text
    assert "credential" not in markdown_text.lower()
    assert "secret" not in markdown_text.lower()

    document = json.loads(json_text)
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["finding_count"] == payload["finding_count"]

    finding_ids = {finding["id"] for finding in document["findings"]}
    assert "pypi_publish_auth_material_surface" in finding_ids
    assert "release_contents_write_scope" in finding_ids
    assert "manual_release_dispatch_review_surface" in finding_ids
    assert document["unverified_settings"]
    assert document["rules"]["release_workflow_mutated"] is False
    assert document["automation_allowed"] is False
    assert document["patch_application_allowed"] is False
    assert document["merge_authorized"] is False
    assert document["semantic_equivalence_proven"] is False

    assert "# SDETKit release anti-hijack threat model" in markdown.read_text(encoding="utf-8")
    assert payload["finding_count"] >= 1


def test_release_anti_hijack_threat_model_public_cli_dispatch(
    tmp_path: Path,
    capsys,
) -> None:
    workflow = _release_workflow(tmp_path / "release.yml")
    out = tmp_path / "reports" / "release-anti-hijack-threat-model.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "release-anti-hijack-threat-model",
            "--workflow",
            str(workflow),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert stdout == "Public release-risk report generated.\n"
    assert "PYPI_API_TOKEN" not in stdout
    assert "TWINE_PASSWORD" not in stdout
    assert "credential" not in stdout.lower()
    assert "secret" not in stdout.lower()
    assert out.is_file()
    assert out.with_suffix(".md").is_file()

    markdown_text = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "# SDETKit release anti-hijack threat model" in markdown_text
    assert "pypi_publish_auth_material_surface" in markdown_text
    assert "automation_allowed: false" in markdown_text
