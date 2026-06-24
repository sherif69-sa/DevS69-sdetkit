from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sdetkit import _legacy_cli
from sdetkit.artifact_contract_index import build_index
from sdetkit.release_readiness_evidence_package import (
    DEFAULT_OUT,
    SCHEMA_VERSION,
    build_release_readiness_evidence_package,
    check_release_readiness_evidence_freshness,
    main,
    release_readiness_evidence_input_provenance,
    render_release_readiness_evidence_markdown,
    write_release_readiness_evidence_package,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _seed_release_repo(root: Path) -> str:
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
        (
            "# Release-readiness evidence handoff\n\n"
            "Blocked when release evidence cannot identify source artifacts.\n"
        ),
        encoding="utf-8",
    )
    (root / "docs/artifact-reference.md").write_text(
        ("# Artifact reference\n\nRelease preflight artifacts are reporting-only.\n"),
        encoding="utf-8",
    )

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "SDETKit Tests")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed release surfaces")
    return _git(root, "rev-parse", "HEAD")


def _write_trusted_pr_quality_handoff(
    root: Path,
    *,
    head_sha: str,
    review_state: str = "ready",
    first_blocker: str = "none",
    next_action: str = "review_and_decide",
    required_checks: str = "clear",
    security_posture: str = "clear",
    merge_posture: str = ("automated_proof_complete_human_decision_required"),
    malformed_summary: bool = False,
) -> tuple[Path, Path]:
    summary = root / "pr-review-summary.md"
    manifest = root / "manifest.json"

    rows = [
        ("Review state", review_state),
        ("First blocker", first_blocker),
        ("Next action", next_action),
        ("Required checks", required_checks),
        ("Security posture", security_posture),
        ("Merge posture", merge_posture),
    ]
    if malformed_summary:
        rows = rows[:-1]

    summary_lines = [
        "# PR Quality Review Summary",
        "",
        "## Contributor decision",
        "",
        "| Item | Value |",
        "|---|---|",
        *[f"| {label} | `{value}` |" for label, value in rows],
        "",
        "## Adaptive review details",
        "",
        "<details><summary>Evidence</summary></details>",
        "",
    ]
    summary.write_text(
        "\n".join(summary_lines),
        encoding="utf-8",
    )
    summary_bytes = summary.read_bytes()

    empty_digest = hashlib.sha256(b"").hexdigest()
    manifest_payload = {
        "schema_version": ("sdetkit.pr_quality_publisher_handoff.v1"),
        "repository": "example/repo",
        "event_name": "pull_request",
        "pr_number": 1,
        "head_sha": head_sha,
        "source_workflow_name": "PR Quality Comment",
        "source_workflow_run_id": 101,
        "source_workflow_run_attempt": 1,
        "authority_boundary": {
            "reporting_only": True,
            "patch_application_allowed": False,
            "security_dismissal_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
        "files": [
            {
                "path": "payload/pr-comment-body.md",
                "size_bytes": 0,
                "sha256": empty_digest,
            },
            {
                "path": "payload/pr-comment-metadata.json",
                "size_bytes": 0,
                "sha256": empty_digest,
            },
            {
                "path": "payload/pr-review-summary.md",
                "size_bytes": len(summary_bytes),
                "sha256": hashlib.sha256(summary_bytes).hexdigest(),
            },
        ],
    }
    manifest.write_text(
        json.dumps(
            manifest_payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary, manifest


def test_release_readiness_evidence_package_reports_release_surfaces(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)

    payload = build_release_readiness_evidence_package(
        tmp_path,
        generated_at="2026-06-23T00:00:00Z",
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "ready_for_human_release_review"
    assert payload["report_status"] == "passed"
    assert payload["reporting_only"] is True
    assert payload["review_first"] is True
    assert payload["repo_mutation"] is False
    assert payload["issue_mutation_allowed"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["security_dismissal_allowed"] is False
    assert payload["safe_to_publish"] is False
    assert payload["release_authorized"] is False
    assert payload["publish_authorized"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert payload["next_allowed_action"] == "human_release_review"

    assert payload["generated_at"] == "2026-06-23T00:00:00Z"
    assert payload["current_head_sha"] == head
    assert payload["source_issue_numbers"] == []
    assert payload["source_run_ids"] == []
    assert set(payload["input_digests"]) == {
        "Makefile",
        ".github/workflows/release.yml",
        "docs/release-readiness-evidence-handoff.md",
        "docs/artifact-reference.md",
    }
    provenance = payload["input_provenance"]
    assert provenance["generator_schema_version"] == SCHEMA_VERSION
    assert provenance["generated_from_head_sha"] == head
    assert provenance["digest_algorithm"] == "sha256"

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


def test_release_readiness_evidence_input_provenance_is_deterministic(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)

    first = release_readiness_evidence_input_provenance(
        repo_root=tmp_path,
        current_head_sha=head,
        generated_at="2026-06-23T00:00:00Z",
    )
    second = release_readiness_evidence_input_provenance(
        repo_root=tmp_path,
        current_head_sha=head,
        generated_at="2026-06-23T01:00:00Z",
    )

    assert first["input_digest"] == second["input_digest"]
    assert first["input_digests"] == second["input_digests"]
    assert first["generated_at"] != second["generated_at"]


def test_release_readiness_evidence_markdown_stays_reporting_only(
    tmp_path: Path,
) -> None:
    _seed_release_repo(tmp_path)

    payload = build_release_readiness_evidence_package(tmp_path)
    markdown = render_release_readiness_evidence_markdown(payload)

    assert "# Release-readiness evidence package" in markdown
    assert "ready_for_human_release_review" in markdown
    assert "current_head_sha:" in markdown
    assert "## Input provenance" in markdown
    assert "safe_to_publish: `false`" in markdown
    assert "release_authorized: `false`" in markdown
    assert "python -m twine check dist/*" in markdown
    assert "does not authorize release" in markdown
    assert "semantic_equivalence_claim: `false`" in markdown


def test_write_and_freshness_round_trip(tmp_path: Path) -> None:
    head = _seed_release_repo(tmp_path)
    out_json = tmp_path / DEFAULT_OUT
    out_md = out_json.with_suffix(".md")

    payload = write_release_readiness_evidence_package(
        tmp_path,
        out_json,
        out_md,
        generated_at="2026-06-23T00:00:00Z",
    )

    assert out_json.is_file()
    assert out_md.is_file()
    loaded = json.loads(out_json.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == payload["schema_version"]
    assert loaded["current_head_sha"] == head
    assert "Release-readiness evidence package" in out_md.read_text(encoding="utf-8")

    freshness = check_release_readiness_evidence_freshness(
        repo_root=tmp_path,
        report_path=out_json,
    )
    assert freshness["status"] == "fresh"
    assert freshness["fresh"] is True
    assert freshness["reasons"] == []
    assert freshness["current_head_sha"] == head


def test_freshness_detects_input_change_and_missing_report(
    tmp_path: Path,
) -> None:
    _seed_release_repo(tmp_path)
    out_json = tmp_path / DEFAULT_OUT
    write_release_readiness_evidence_package(tmp_path, out_json)

    makefile = tmp_path / "Makefile"
    makefile.write_text(
        makefile.read_text(encoding="utf-8") + "\nrelease-note:\n\t@true\n",
        encoding="utf-8",
    )

    stale = check_release_readiness_evidence_freshness(
        repo_root=tmp_path,
        report_path=out_json,
    )
    assert stale["status"] == "stale"
    assert stale["fresh"] is False
    assert "input_digest_mismatch" in stale["reasons"]
    assert "input_digests_mismatch" in stale["reasons"]

    missing = check_release_readiness_evidence_freshness(
        repo_root=tmp_path,
        report_path=tmp_path / "missing.json",
    )
    assert missing["status"] == "stale"
    assert missing["fresh"] is False
    assert "report_missing" in missing["reasons"]


def test_release_readiness_evidence_package_cli_and_freshness(
    tmp_path: Path,
    capsys,
) -> None:
    _seed_release_repo(tmp_path)
    out_json = tmp_path / "package.json"
    out_md = tmp_path / "package.md"

    rc = main(
        [
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == SCHEMA_VERSION
    assert output["status"] == "ready_for_human_release_review"

    rc = main(
        [
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--check-freshness",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    freshness = json.loads(capsys.readouterr().out)
    assert freshness["fresh"] is True


def test_root_cli_routes_release_readiness_evidence_package(
    tmp_path: Path,
    capsys,
) -> None:
    _seed_release_repo(tmp_path)
    out_json = tmp_path / "root-package.json"
    out_md = tmp_path / "root-package.md"

    rc = _legacy_cli.main(
        [
            "release-readiness-evidence-package",
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == SCHEMA_VERSION
    assert out_json.is_file()
    assert out_md.is_file()


def test_artifact_contract_registers_release_readiness_evidence_package() -> None:
    entries = {item["id"]: item for item in build_index()["artifacts"]}
    entry = entries["release-readiness-evidence-package-json"]

    assert entry["schema_version"] == SCHEMA_VERSION
    assert entry["path"] == DEFAULT_OUT
    assert {
        "generated_at",
        "current_head_sha",
        "input_digests",
        "input_provenance",
        "status",
        "evidence_items",
        "authority_boundary",
        "release_authorized",
        "publish_authorized",
        "merge_authorized",
    }.issubset(set(entry["required_fields"]))


def test_pr_quality_handoff_is_not_requested_by_default(
    tmp_path: Path,
) -> None:
    _seed_release_repo(tmp_path)

    payload = build_release_readiness_evidence_package(tmp_path)

    handoff = payload["pr_quality_handoff"]
    assert handoff["collection_status"] == "not_requested"
    assert handoff["available"] is False
    assert handoff["release_review_blocking"] is False
    assert handoff["reporting_only"] is True
    assert payload["status"] == "ready_for_human_release_review"
    assert "pr_quality_summary" not in payload["input_digests"]
    assert "pr_quality_handoff_manifest" not in payload["input_digests"]


def test_pr_quality_ready_handoff_is_collected_and_head_bound(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha=head,
    )

    payload = build_release_readiness_evidence_package(
        tmp_path,
        current_head_sha=head,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )

    handoff = payload["pr_quality_handoff"]
    assert handoff["collection_status"] == "collected"
    assert handoff["available"] is True
    assert handoff["head_sha"] == head
    assert handoff["head_matches"] is True
    assert handoff["review_state"] == "ready"
    assert handoff["first_blocker"] == "none"
    assert handoff["next_action"] == "review_and_decide"
    assert handoff["required_checks"] == "clear"
    assert handoff["security_posture"] == "clear"
    assert handoff["release_review_blocking"] is False
    assert handoff["safe_to_publish"] is False
    assert handoff["release_authorized"] is False
    assert handoff["publish_authorized"] is False
    assert handoff["merge_authorized"] is False
    assert payload["status"] == "ready_for_human_release_review"
    assert payload["safe_to_publish"] is False
    assert payload["release_authorized"] is False
    assert payload["publish_authorized"] is False
    assert payload["merge_authorized"] is False
    assert {
        "pr_quality_summary",
        "pr_quality_handoff_manifest",
    }.issubset(payload["input_digests"])


def test_pr_quality_blocked_handoff_requires_release_review(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha=head,
        review_state="blocked",
        first_blocker="Code scanning alerts remain",
        next_action="fix_security_findings",
        security_posture="2 current alert(s)",
        merge_posture="do_not_merge_until_blocker_resolved",
    )

    payload = build_release_readiness_evidence_package(
        tmp_path,
        current_head_sha=head,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )

    handoff = payload["pr_quality_handoff"]
    assert handoff["collection_status"] == "collected"
    assert handoff["review_state"] == "blocked"
    assert handoff["release_review_blocking"] is True
    assert payload["status"] == "review_required"
    assert payload["report_status"] == "passed"
    assert payload["next_allowed_action"] == "human_release_review"


def test_pr_quality_stale_head_is_review_required(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha="different-head",
    )

    payload = build_release_readiness_evidence_package(
        tmp_path,
        current_head_sha=head,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )

    handoff = payload["pr_quality_handoff"]
    assert handoff["collection_status"] == "stale"
    assert handoff["head_matches"] is False
    assert handoff["release_review_blocking"] is True
    assert payload["status"] == "review_required"


def test_pr_quality_digest_mismatch_is_review_required(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha=head,
    )
    summary.write_text(
        summary.read_text(encoding="utf-8") + "\ntampered\n",
        encoding="utf-8",
    )

    payload = build_release_readiness_evidence_package(
        tmp_path,
        current_head_sha=head,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )

    handoff = payload["pr_quality_handoff"]
    assert handoff["collection_status"] == "digest_mismatch"
    assert handoff["release_review_blocking"] is True
    assert payload["status"] == "review_required"


def test_pr_quality_malformed_summary_is_review_required(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha=head,
        malformed_summary=True,
    )

    payload = build_release_readiness_evidence_package(
        tmp_path,
        current_head_sha=head,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )

    handoff = payload["pr_quality_handoff"]
    assert handoff["collection_status"] == "malformed"
    assert handoff["release_review_blocking"] is True
    assert payload["status"] == "review_required"


def test_pr_quality_missing_pair_is_review_required(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, _manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha=head,
    )

    payload = build_release_readiness_evidence_package(
        tmp_path,
        current_head_sha=head,
        pr_quality_summary=summary,
    )

    handoff = payload["pr_quality_handoff"]
    assert handoff["collection_status"] == "missing"
    assert handoff["release_review_blocking"] is True
    assert payload["status"] == "review_required"


def test_pr_quality_inputs_participate_in_freshness(
    tmp_path: Path,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha=head,
    )
    out_json = tmp_path / DEFAULT_OUT

    write_release_readiness_evidence_package(
        tmp_path,
        out_json,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )

    fresh = check_release_readiness_evidence_freshness(
        repo_root=tmp_path,
        report_path=out_json,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )
    assert fresh["fresh"] is True

    summary.write_text(
        summary.read_text(encoding="utf-8") + "\nchanged\n",
        encoding="utf-8",
    )
    stale = check_release_readiness_evidence_freshness(
        repo_root=tmp_path,
        report_path=out_json,
        pr_quality_summary=summary,
        pr_quality_handoff_manifest=manifest,
    )
    assert stale["fresh"] is False
    assert "input_digest_mismatch" in stale["reasons"]


def test_pr_quality_handoff_cli_and_root_cli_forwarding(
    tmp_path: Path,
    capsys,
) -> None:
    head = _seed_release_repo(tmp_path)
    summary, manifest = _write_trusted_pr_quality_handoff(
        tmp_path,
        head_sha=head,
    )

    module_json = tmp_path / "module-package.json"
    module_md = tmp_path / "module-package.md"
    rc = main(
        [
            "--root",
            str(tmp_path),
            "--out-json",
            str(module_json),
            "--out-md",
            str(module_md),
            "--pr-quality-summary",
            str(summary),
            "--pr-quality-handoff-manifest",
            str(manifest),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    module_payload = json.loads(capsys.readouterr().out)
    assert module_payload["pr_quality_handoff"]["collection_status"] == "collected"
    assert "## PR Quality handoff" in module_md.read_text(encoding="utf-8")

    root_json = tmp_path / "root-package-with-pr.json"
    root_md = tmp_path / "root-package-with-pr.md"
    rc = _legacy_cli.main(
        [
            "release-readiness-evidence-package",
            "--root",
            str(tmp_path),
            "--out-json",
            str(root_json),
            "--out-md",
            str(root_md),
            "--pr-quality-summary",
            str(summary),
            "--pr-quality-handoff-manifest",
            str(manifest),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    root_payload = json.loads(capsys.readouterr().out)
    assert root_payload["pr_quality_handoff"]["collection_status"] == "collected"
    assert root_json.is_file()
    assert root_md.is_file()
