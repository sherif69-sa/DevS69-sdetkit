from __future__ import annotations

import json
from pathlib import Path

from sdetkit.release_readiness_evidence_package import (
    SCHEMA_VERSION,
    build_release_readiness_evidence_package,
    main,
    render_release_readiness_evidence_markdown,
    write_release_readiness_evidence_package,
)


def _seed_release_repo(root: Path) -> None:
    (root / ".github/workflows").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "scripts").mkdir()

    (root / "pyproject.toml").write_text(
        """
[project.optional-dependencies]
packaging = ["build==1.5.0", "twine==6.2.0", "check-wheel-contents==0.6.3"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "Makefile").write_text(
        """
package-validate:
\tpython -m build
\tpython -m twine check dist/*
\tpython -m check_wheel_contents --ignore W009 dist/*.whl
\tpython -m pip install --force-reinstall dist/*.whl
\tsdetkit --help

release-preflight:
\tpython scripts/release_preflight.py

release-verify-plan:
\tpython scripts/release_verify_post_publish.py --plan
""".lstrip(),
        encoding="utf-8",
    )
    (root / ".github/workflows/release.yml").write_text(
        """
name: Release
permissions:
  contents: write
  id-token: write
  attestations: write
jobs:
  release:
    steps:
      - run: python scripts/release_preflight.py --tag v1.0.0 --format json --out build/release-preflight.json
      - run: python -m build
      - run: python -m twine check dist/*
      - run: python -m check_wheel_contents --ignore W009 dist/*.whl
      - run: python -m pip install --force-reinstall dist/*.whl && sdetkit --help
      - uses: actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        with:
          name: release-diagnostics
          path: build/release-preflight.json
""".lstrip(),
        encoding="utf-8",
    )
    (root / "docs/release-readiness-evidence-handoff.md").write_text(
        "# Release-readiness evidence handoff\n\nBlocked when release evidence cannot identify source artifacts.\n",
        encoding="utf-8",
    )
    (root / "docs/artifact-reference.md").write_text(
        "# Artifact reference\n\nRelease preflight artifacts are reporting-only.\n",
        encoding="utf-8",
    )


def test_release_readiness_evidence_package_reports_release_surfaces(tmp_path: Path) -> None:
    _seed_release_repo(tmp_path)

    payload = build_release_readiness_evidence_package(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "ready_for_human_release_review"
    assert payload["reporting_only"] is True
    assert payload["review_first"] is True
    assert payload["safe_to_publish"] is False
    assert payload["release_authorized"] is False
    assert payload["next_allowed_action"] == "human_release_review"

    boundary = payload["authority_boundary"]
    assert boundary["release_authorization"] is False
    assert boundary["publish_authorization"] is False
    assert boundary["merge_authorization"] is False
    assert boundary["patch_automation"] is False
    assert boundary["security_dismissal"] is False
    assert boundary["semantic_equivalence_claim"] is False

    item_ids = {item["id"] for item in payload["evidence_items"]}
    assert "package_build_command" in item_ids
    assert "twine_metadata_check" in item_ids
    assert "wheel_contents_check" in item_ids
    assert "wheel_smoke_install" in item_ids
    assert "release_preflight" in item_ids
    assert "release_provenance_attestation" in item_ids
    assert "release_diagnostics_upload" in item_ids
    assert "post_publish_or_rollback_plan" in item_ids

    assert payload["summary"]["missing_evidence_count"] == 0
    assert "make package-validate" in payload["proof_commands"]
    assert "automatic_publish" in payload["blocked_actions"]


def test_release_readiness_evidence_markdown_stays_reporting_only(tmp_path: Path) -> None:
    _seed_release_repo(tmp_path)

    payload = build_release_readiness_evidence_package(tmp_path)
    markdown = render_release_readiness_evidence_markdown(payload)

    assert "# Release-readiness evidence package" in markdown
    assert "ready_for_human_release_review" in markdown
    assert "safe_to_publish: `false`" in markdown
    assert "release_authorized: `false`" in markdown
    assert "python -m twine check dist/*" in markdown
    assert "does not authorize release" in markdown
    assert "semantic_equivalence_claim: `false`" in markdown


def test_write_release_readiness_evidence_package_outputs_json_and_markdown(tmp_path: Path) -> None:
    _seed_release_repo(tmp_path)
    out_json = tmp_path / "build/release-evidence/package.json"
    out_md = tmp_path / "build/release-evidence/package.md"

    payload = write_release_readiness_evidence_package(tmp_path, out_json, out_md)

    assert out_json.is_file()
    assert out_md.is_file()
    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == payload["schema_version"]
    assert "Release-readiness evidence package" in out_md.read_text(encoding="utf-8")


def test_release_readiness_evidence_package_cli(tmp_path: Path, capsys) -> None:
    _seed_release_repo(tmp_path)

    rc = main(
        [
            "--root",
            str(tmp_path),
            "--out-json",
            str(tmp_path / "package.json"),
            "--out-md",
            str(tmp_path / "package.md"),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == SCHEMA_VERSION
    assert output["status"] == "ready_for_human_release_review"
