from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adoption_learning_report_dashboard


def _report_payload(
    *,
    candidates: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    rows = (
        candidates
        if candidates is not None
        else [
            {
                "rank": 1,
                "classification": "weak_proof_command_mapping",
                "priority": "P1",
                "ranking_score": 130,
                "next_pr_title": (
                    "feat(adoption): strengthen proof-command mapping "
                    "from real-world matrix evidence"
                ),
                "observed_in_repos": ["repo-a", "repo-b", "repo-c"],
                "frequency_across_matrix": 3,
                "owner_files": ["src/sdetkit/adoption_proof_recommendations.py"],
                "reason_from_real_repo": ("weak_proof_command_mapping appeared in 3 repos."),
                "proof_needed": ["python -m pytest -q tests/test_adoption_surface.py -o addopts="],
                "review_first": True,
                "safe_to_patch": False,
                "recommended_next_action": ("Open one focused PR after human review."),
            },
            {
                "rank": 2,
                "classification": "artifact_path_gap",
                "priority": "P2",
                "ranking_score": 50,
                "next_pr_title": ("feat(adoption): improve artifact path detection"),
                "observed_in_repos": ["repo-d"],
                "frequency_across_matrix": 1,
                "owner_files": ["src/sdetkit/adoption_repo_topology.py"],
                "reason_from_real_repo": "artifact_path_gap appeared in 1 repo.",
                "proof_needed": [],
                "review_first": True,
                "safe_to_patch": False,
                "recommended_next_action": ("Open one focused PR after human review."),
            },
        ]
    )
    return {
        "schema_version": "sdetkit.adoption_learning_report.v1",
        "source_matrix": "/tmp/adoption-real-world-matrix.json",
        "source_matrix_schema_version": ("sdetkit.adoption_real_world_learning_matrix.v1"),
        "source_matrix_status": "review_required",
        "source_repo_count": 4,
        "candidate_count": len(rows),
        "top_candidate": rows[0] if rows else None,
        "prioritized_upgrade_candidates": rows,
        "repo_memory_profile": {
            "connected": False,
            "path": "",
            "schema_version": "",
            "profile_status": "not_provided",
            "memory_mode": "",
            "review_first": True,
            "authoritative_for_adoption_report": False,
            "authority_boundary": {
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            },
        },
        "operator_summary": {
            "status": "review_first_learning_report_generated",
            "next_action": (
                rows[0]["next_pr_title"]
                if rows
                else "No upgrade candidates found in the source matrix."
            ),
        },
        "rules": {
            "source_matrix_only": True,
            "repo_memory_profile_read": False,
            "repo_memory_profile_authoritative": False,
            "target_repos_read": False,
            "install_dependencies": False,
            "target_tests_executed": False,
            "target_repo_mutation": False,
            "target_pr_or_issue_opened": False,
            "endorsement_claim": False,
            "review_first": True,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _write_report(
    path: Path,
    *,
    payload: dict[str, object] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload or _report_payload(), indent=2),
        encoding="utf-8",
    )
    return path


def test_dashboard_builds_read_only_candidate_summary(
    tmp_path: Path,
) -> None:
    report = _write_report(tmp_path / "adoption-learning-report.json")
    before = report.read_bytes()
    out = tmp_path / "dashboard.html"

    payload = adoption_learning_report_dashboard.build_dashboard(
        report,
        out_path=out,
    )

    assert payload["schema_version"] == ("sdetkit.adoption_learning_report_dashboard.v1")
    assert payload["status"] == "ready"
    assert payload["report_exists"] is True
    assert payload["source_report_schema_version"] == ("sdetkit.adoption_learning_report.v1")
    assert payload["source_repo_count"] == 4
    assert payload["candidate_count"] == 2
    assert payload["top_candidate"]["classification"] == ("weak_proof_command_mapping")
    assert payload["local_only"] is True
    assert payload["read_only"] is True
    assert report.read_bytes() == before

    boundary = payload["decision_boundary"]
    assert all(value is False for value in boundary.values())


def test_dashboard_renders_static_escaped_html(
    tmp_path: Path,
) -> None:
    candidate = {
        "rank": 1,
        "classification": "review_first_unknown",
        "priority": "P2",
        "ranking_score": 10,
        "next_pr_title": "<script>alert('x')</script>",
        "observed_in_repos": ["repo-<one>"],
        "frequency_across_matrix": 1,
        "owner_files": ["src/<unsafe>.py"],
        "reason_from_real_repo": "<img src=x onerror=alert(1)>",
        "proof_needed": ["pytest <unsafe>"],
        "review_first": True,
        "safe_to_patch": False,
        "recommended_next_action": "Review <manually>.",
    }
    report = _write_report(
        tmp_path / "adoption-learning-report.json",
        payload=_report_payload(candidates=[candidate]),
    )
    out = tmp_path / "dashboard.html"

    rc = adoption_learning_report_dashboard.main(
        [
            "--report-path",
            str(report),
            "--format",
            "html",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Adoption learning report dashboard" in text
    assert "Static, local-only, read-only" in text
    assert "&lt;script&gt;" in text
    assert "&lt;img src=x onerror=alert(1)&gt;" in text
    assert "<script>" not in text
    assert "safe to patch</dt><dd>false" in text.lower()
    assert "merge_authorized</strong>: false" in text


def test_dashboard_writes_deterministic_json(
    tmp_path: Path,
) -> None:
    report = _write_report(tmp_path / "adoption-learning-report.json")
    before = report.read_bytes()
    first = tmp_path / "dashboard-1.json"
    second = tmp_path / "dashboard-2.json"

    for out in (first, second):
        rc = adoption_learning_report_dashboard.main(
            [
                "--report-path",
                str(report),
                "--format",
                "json",
                "--out",
                str(out),
            ]
        )
        assert rc == 0

    assert first.read_bytes() == second.read_bytes()
    assert report.read_bytes() == before

    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 2
    assert payload["decision_boundary"]["automation_allowed"] is False
    assert payload["decision_boundary"]["merge_authorized"] is False


def test_dashboard_renders_valid_empty_report(
    tmp_path: Path,
) -> None:
    report = _write_report(
        tmp_path / "adoption-learning-report.json",
        payload=_report_payload(candidates=[]),
    )
    out = tmp_path / "dashboard.html"

    rc = adoption_learning_report_dashboard.main(
        [
            "--report-path",
            str(report),
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "No upgrade candidates" in text

    payload = adoption_learning_report_dashboard.build_dashboard(
        report,
        out_path=out,
    )
    assert payload["status"] == "empty"
    assert payload["candidate_count"] == 0
    assert payload["top_candidate"] is None


def test_dashboard_rejects_missing_or_malformed_report(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "dashboard.html"

    rc = adoption_learning_report_dashboard.main(
        [
            "--report-path",
            str(tmp_path / "missing.json"),
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "error=" in capsys.readouterr().err

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    rc = adoption_learning_report_dashboard.main(
        [
            "--report-path",
            str(malformed),
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "error=" in capsys.readouterr().err


def test_dashboard_rejects_unknown_schema_or_inconsistent_count(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "dashboard.json"

    unknown = _report_payload()
    unknown["schema_version"] = "sdetkit.adoption_learning_report.v999"
    unknown_path = _write_report(
        tmp_path / "unknown.json",
        payload=unknown,
    )

    rc = adoption_learning_report_dashboard.main(
        [
            "--report-path",
            str(unknown_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "unsupported adoption learning report schema" in (capsys.readouterr().err)

    inconsistent = _report_payload()
    inconsistent["candidate_count"] = 99
    inconsistent_path = _write_report(
        tmp_path / "inconsistent.json",
        payload=inconsistent,
    )

    rc = adoption_learning_report_dashboard.main(
        [
            "--report-path",
            str(inconsistent_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "candidate_count does not match" in capsys.readouterr().err
