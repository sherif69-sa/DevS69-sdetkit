from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sdetkit import _legacy_cli
from sdetkit.artifact_contract_index import build_index
from sdetkit.first_proof_quality_evidence import (
    DEFAULT_OUT,
    SCHEMA_VERSION,
    build_first_proof_quality_evidence,
    check_first_proof_quality_freshness,
    main,
    write_first_proof_quality_evidence,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _seed_repo(root: Path, *, bind_head: bool = True) -> str:
    artifact_dir = root / "build/first-proof"
    artifact_dir.mkdir(parents=True)

    health = {
        "schema_version": "1.0.0",
        "score": 92,
        "decision": "GREEN",
        "reason_count": 0,
        "reasons": [],
    }
    dashboard = {
        "schema_version": "1.0.0",
        "decision": "SHIP",
        "health_score": 92,
        "health_decision": "GREEN",
        "execution_contract_ok": True,
        "followup_ready": True,
    }
    threshold = {
        "ok": True,
        "profile": "standard",
        "config": {"min_health_score": 85},
        "errors": [],
    }

    (artifact_dir / "health-score.json").write_text(
        json.dumps(health, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "dashboard.json").write_text(
        json.dumps(dashboard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "readiness-threshold.json").write_text(
        json.dumps(threshold, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "SDETKit Tests")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed first-proof artifacts")
    head = _git(root, "rev-parse", "HEAD")

    if bind_head:
        for filename in (
            "health-score.json",
            "dashboard.json",
            "readiness-threshold.json",
        ):
            path = artifact_dir / filename
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["current_head_sha"] = head
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    return head


def test_bundle_reports_consistent_current_sources(tmp_path: Path) -> None:
    head = _seed_repo(tmp_path)

    payload = build_first_proof_quality_evidence(
        repo_root=tmp_path,
        generated_at="2026-06-23T00:00:00Z",
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "ready_for_human_review"
    assert payload["current_head_sha"] == head
    assert payload["source_issue_numbers"] == [1843]
    assert payload["source_count"] == 3
    assert payload["source_state_counts"] == {"present": 3}
    assert payload["head_binding_counts"] == {"current": 3}
    assert payload["finding_counts"] == {
        "blocking": 0,
        "partial": 0,
        "advisory": 0,
    }
    assert payload["refresh_commands"] == [
        "make first-proof-health-score",
        "make first-proof-dashboard",
        "make first-proof-readiness-threshold",
    ]
    assert payload["reporting_only"] is True
    assert payload["repo_mutation"] is False
    assert payload["automation_allowed"] is False
    assert payload["merge_authorized"] is False


def test_bundle_reports_missing_and_legacy_unbound_sources(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path, bind_head=False)
    (tmp_path / "build/first-proof/readiness-threshold.json").unlink()

    payload = build_first_proof_quality_evidence(repo_root=tmp_path)

    assert payload["status"] == "review_required"
    assert payload["finding_counts"]["blocking"] == 0
    assert payload["finding_counts"]["partial"] == 1
    assert payload["finding_counts"]["advisory"] == 2
    finding_ids = {item["finding_id"] for item in payload["findings"]}
    assert "readiness_threshold_missing" in finding_ids
    assert "health_score_head_unbound" in finding_ids
    assert "dashboard_head_unbound" in finding_ids


def test_bundle_blocks_invalid_json_and_schema(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    artifact_dir = tmp_path / "build/first-proof"
    (artifact_dir / "health-score.json").write_text(
        "{invalid",
        encoding="utf-8",
    )
    dashboard = json.loads((artifact_dir / "dashboard.json").read_text(encoding="utf-8"))
    dashboard["schema_version"] = "9.9.9"
    (artifact_dir / "dashboard.json").write_text(
        json.dumps(dashboard),
        encoding="utf-8",
    )

    payload = build_first_proof_quality_evidence(repo_root=tmp_path)

    assert payload["status"] == "blocked"
    assert payload["finding_counts"]["blocking"] == 2
    finding_ids = {item["finding_id"] for item in payload["findings"]}
    assert "health_score_invalid_json" in finding_ids
    assert "dashboard_schema_mismatch" in finding_ids


def test_bundle_detects_cross_artifact_contradictions(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path)
    dashboard_path = tmp_path / "build/first-proof/dashboard.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    dashboard["health_score"] = 51
    dashboard["health_decision"] = "RED"
    dashboard_path.write_text(
        json.dumps(dashboard, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    payload = build_first_proof_quality_evidence(repo_root=tmp_path)

    assert payload["status"] == "blocked"
    finding_ids = {item["finding_id"] for item in payload["findings"]}
    assert "health_score_contradiction" in finding_ids
    assert "health_decision_contradiction" in finding_ids


def test_bundle_reports_failed_readiness_threshold(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path)
    threshold_path = tmp_path / "build/first-proof/readiness-threshold.json"
    threshold = json.loads(threshold_path.read_text(encoding="utf-8"))
    threshold["ok"] = False
    threshold["errors"] = ["health_score<85"]
    threshold_path.write_text(
        json.dumps(threshold, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    payload = build_first_proof_quality_evidence(repo_root=tmp_path)

    assert payload["status"] == "blocked"
    assert any(item["finding_id"] == "readiness_threshold_failed" for item in payload["findings"])


def test_write_and_freshness_round_trip(tmp_path: Path) -> None:
    head = _seed_repo(tmp_path)
    out = tmp_path / DEFAULT_OUT
    markdown = out.with_suffix(".md")

    payload = write_first_proof_quality_evidence(
        repo_root=tmp_path,
        out=out,
        markdown_out=markdown,
        generated_at="2026-06-23T00:00:00Z",
    )

    assert out.is_file()
    assert markdown.is_file()
    assert payload["current_head_sha"] == head
    assert "# First-proof quality evidence" in markdown.read_text(encoding="utf-8")

    freshness = check_first_proof_quality_freshness(
        repo_root=tmp_path,
        report_path=out,
    )
    assert freshness["fresh"] is True
    assert freshness["status"] == "fresh"
    assert freshness["reasons"] == []


def test_freshness_detects_source_artifact_change(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path)
    out = tmp_path / DEFAULT_OUT
    write_first_proof_quality_evidence(repo_root=tmp_path, out=out)

    health_path = tmp_path / "build/first-proof/health-score.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health["score"] = 91
    health_path.write_text(
        json.dumps(health, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    freshness = check_first_proof_quality_freshness(
        repo_root=tmp_path,
        report_path=out,
    )
    assert freshness["fresh"] is False
    assert freshness["status"] == "stale"
    assert "input_digest_mismatch" in freshness["reasons"]
    assert "input_digests_mismatch" in freshness["reasons"]


def test_module_and_root_cli(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    out = tmp_path / "bundle.json"
    markdown = tmp_path / "bundle.md"

    rc = main(
        [
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--markdown-out",
            str(markdown),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    module_payload = json.loads(capsys.readouterr().out)
    assert module_payload["schema_version"] == SCHEMA_VERSION

    root_out = tmp_path / "root-bundle.json"
    root_markdown = tmp_path / "root-bundle.md"
    rc = _legacy_cli.main(
        [
            "first-proof-quality-evidence",
            "--root",
            str(tmp_path),
            "--out",
            str(root_out),
            "--markdown-out",
            str(root_markdown),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    root_payload = json.loads(capsys.readouterr().out)
    assert root_payload["schema_version"] == SCHEMA_VERSION
    assert root_out.is_file()
    assert root_markdown.is_file()


def test_artifact_contract_registers_bundle() -> None:
    entries = {item["id"]: item for item in build_index()["artifacts"]}
    entry = entries["first-proof-quality-evidence-json"]

    assert entry["schema_version"] == SCHEMA_VERSION
    assert entry["path"] == DEFAULT_OUT.as_posix()
    assert {
        "generated_at",
        "current_head_sha",
        "input_digests",
        "input_provenance",
        "status",
        "sources",
        "findings",
        "finding_counts",
        "refresh_commands",
        "authority_boundary",
    }.issubset(set(entry["required_fields"]))
