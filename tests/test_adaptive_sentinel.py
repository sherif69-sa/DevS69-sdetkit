from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sdetkit import adaptive_sentinel, cli

UNKNOWN_REVIEW_REQUIRED = "UNKNOWN" + "_REVIEW" + "_REQUIRED"


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _failure_bundle(root: Path, *, clear: bool = False) -> Path:
    return _write_json(
        root / "build/sdetkit/failure-intelligence/failure-intelligence-bundle.json",
        {
            "schema_version": "sdetkit.adaptive.failure_bundle.v1",
            "status": "clear" if clear else "needs_fix",
            "primary_diagnosis_code": "" if clear else UNKNOWN_REVIEW_REQUIRED,
            "diagnosis_count": 0 if clear else 1,
            "review_first": False if clear else True,
            "safe_to_auto_fix": False,
            "artifacts": {
                "operator_brief_markdown": (
                    root / "build/sdetkit/failure-intelligence/operator-brief.md"
                ).as_posix(),
            },
        },
    )


def test_sentinel_scan_flags_review_first_failure_bundle(tmp_path: Path) -> None:
    _failure_bundle(tmp_path)

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=True)

    assert payload["schema_version"] == "sdetkit.adaptive.sentinel.v1"
    assert payload["state"] == "critical"
    assert payload["ok"] is False
    assert payload["finding_count"] >= 1
    finding = payload["findings"][0]
    assert finding["source"] == "adaptive_failure_bundle"
    assert "review-first" in finding["summary"]
    joined = "\n".join(payload["recommendations"])
    assert "investigate failure" in joined
    assert "doctor --diagnose --failure-bundle" in joined
    assert (tmp_path / "build/sdetkit/sentinel/sentinel.json").exists()
    assert (tmp_path / "build/sdetkit/sentinel/sentinel.md").exists()
    assert (tmp_path / ".sdetkit/adaptive-sentinel/events.jsonl").exists()


def test_sentinel_scan_clear_bundle_is_healthy(tmp_path: Path) -> None:
    _failure_bundle(tmp_path, clear=True)

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    assert payload["state"] == "healthy"
    assert payload["ok"] is True
    assert payload["findings"][0]["source"] == "adaptive_failure_bundle"
    assert "status=clear" in payload["findings"][0]["evidence"]


def test_sentinel_cli_route_and_help(tmp_path: Path, capsys) -> None:
    _failure_bundle(tmp_path)

    rc = cli.main(
        [
            "adaptive",
            "sentinel",
            "scan",
            "--root",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "sentinel"),
            "--format",
            "json",
            "--no-fail",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "critical"

    try:
        cli.main(["adaptive", "sentinel", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    help_out = capsys.readouterr().out
    assert "scan" in help_out
    assert "watch" in help_out


def test_sentinel_watch_writes_repeated_events(tmp_path: Path, capsys) -> None:
    _failure_bundle(tmp_path)
    event_log = tmp_path / "events.jsonl"

    rc = adaptive_sentinel.main(
        [
            "watch",
            "--root",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "sentinel"),
            "--event-log",
            str(event_log),
            "--interval-seconds",
            "0",
            "--iterations",
            "2",
            "--format",
            "json",
            "--no-fail",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "critical"
    assert len(event_log.read_text(encoding="utf-8").splitlines()) == 2


def test_sentinel_render_markdown_contains_boundary(tmp_path: Path) -> None:
    _failure_bundle(tmp_path)
    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    rendered = adaptive_sentinel.render_markdown(payload)

    assert "# Adaptive Sentinel" in rendered
    assert "Recommended next commands" in rendered
    assert "read-only" in rendered


def test_sentinel_trend_memory_escalates_recurring_unknown_review(tmp_path: Path) -> None:
    _failure_bundle(tmp_path)
    event_log = tmp_path / ".sdetkit/adaptive-sentinel/events.jsonl"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event_log.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adaptive.sentinel.event.v1",
                "created_at_utc": "2026-05-01T00:00:00Z",
                "state": "critical",
                "finding_count": 1,
                "finding_fingerprints": [
                    {
                        "fingerprint": (
                            "adaptive_failure_bundle|primary=UNKNOWN_REVIEW_REQUIRED|"
                            "Adaptive failure bundle signal"
                        ),
                        "source": "adaptive_failure_bundle",
                        "state": "critical",
                        "title": "Adaptive failure bundle signal",
                        "evidence_key": "primary=UNKNOWN_REVIEW_REQUIRED",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=True)

    trend = payload["trend_memory"]
    assert payload["trend_state"] == "critical"
    assert payload["threat_score"] >= 90
    assert trend["trend_state"] == "critical"
    assert trend["escalated_finding_count"] == 1
    assert trend["escalated_findings"][0]["reason"] == "persistent_unknown_review_required"
    assert trend["escalated_findings"][0]["recurrence_count"] == 2
    assert (tmp_path / "build/sdetkit/sentinel/trend-memory.json").exists()
    assert (tmp_path / "build/sdetkit/sentinel/trend-memory.md").exists()


def test_sentinel_trend_memory_marks_three_time_recurring_quality_failure(
    tmp_path: Path,
) -> None:
    quality = tmp_path / ".sdetkit/out/quality-verdict.json"
    quality.parent.mkdir(parents=True, exist_ok=True)
    quality.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.final-verdict.v2",
                "blocking_failures": "coverage",
                "merge_release_recommendation": "do-not-merge",
            }
        ),
        encoding="utf-8",
    )
    event_log = tmp_path / ".sdetkit/adaptive-sentinel/events.jsonl"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    prior_event = {
        "schema_version": "sdetkit.adaptive.sentinel.event.v1",
        "state": "warning",
        "finding_fingerprints": [
            {
                "fingerprint": "quality_verdict|blocking_failures=coverage|Quality verdict signal",
                "source": "quality_verdict",
                "state": "warning",
                "title": "Quality verdict signal",
                "evidence_key": "blocking_failures=coverage",
            }
        ],
    }
    event_log.write_text(
        json.dumps(prior_event) + "\n" + json.dumps(prior_event) + "\n",
        encoding="utf-8",
    )

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    trend = payload["trend_memory"]
    assert trend["trend_state"] == "critical"
    assert trend["top_recurring_findings"][0]["reason"] == "quality_regression_loop"
    assert trend["top_recurring_findings"][0]["recurrence_count"] == 3
    assert payload["threat_score"] >= 90


def test_sentinel_trend_memory_clear_scan_has_zero_threat_score(tmp_path: Path) -> None:
    _failure_bundle(tmp_path, clear=True)

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    assert payload["state"] == "healthy"
    assert payload["trend_state"] == "healthy"
    assert payload["threat_score"] == 0
    assert payload["trend_memory"]["recurring_finding_count"] == 0


def test_sentinel_markdown_includes_trend_memory_section(tmp_path: Path) -> None:
    _failure_bundle(tmp_path)
    event_log = tmp_path / ".sdetkit/adaptive-sentinel/events.jsonl"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event_log.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adaptive.sentinel.event.v1",
                "state": "critical",
                "finding_fingerprints": [
                    {
                        "fingerprint": (
                            "adaptive_failure_bundle|primary=UNKNOWN_REVIEW_REQUIRED|"
                            "Adaptive failure bundle signal"
                        ),
                        "source": "adaptive_failure_bundle",
                        "state": "critical",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    rendered = adaptive_sentinel.render_markdown(payload)

    assert "## Trend memory" in rendered
    assert "persistent_unknown_review_required" in rendered
    assert "threat score" in rendered


def _init_git_repo(root: Path) -> None:
    subprocess.run(
        ["git", "init"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_sentinel_flags_protected_workflow_change(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/security.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Security\non: workflow_dispatch\n", encoding="utf-8")

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    protected = payload["protected_surface_changes"]
    assert protected[0]["path"] == ".github/workflows/security.yml"
    assert protected[0]["surface"] == "workflow_automation"
    assert protected[0]["risk_band"] == "critical"
    assert payload["state"] == "warning"
    assert any(item["source"] == "protected_surface_changes" for item in payload["findings"])
    assert any("pre_commit" in command for command in payload["recommendations"])


def test_sentinel_flags_dependency_contract_change(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    (tmp_path / "constraints-ci.txt").write_text("pytest==8.0.0\n", encoding="utf-8")

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    protected = payload["protected_surface_changes"]
    assert protected[0]["path"] == "constraints-ci.txt"
    assert protected[0]["surface"] == "dependency_contract"
    assert payload["state"] == "warning"
    assert any(
        "pip install -c constraints-ci.txt" in command for command in payload["recommendations"]
    )


def test_sentinel_does_not_classify_normal_docs_as_protected_surface(
    tmp_path: Path,
) -> None:
    _init_git_repo(tmp_path)
    docs = tmp_path / "docs/operator-note.md"
    docs.parent.mkdir(parents=True)
    docs.write_text("# note\n", encoding="utf-8")

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)

    assert payload["protected_surface_changes"] == []
    assert not any(item["source"] == "protected_surface_changes" for item in payload["findings"])


def test_sentinel_markdown_lists_protected_surface_changes(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/quality.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Quality\non: workflow_dispatch\n", encoding="utf-8")

    payload = adaptive_sentinel.build_sentinel_scan(root=tmp_path, write=False)
    rendered = adaptive_sentinel.render_markdown(payload)

    assert "## Protected surface changes" in rendered
    assert ".github/workflows/quality.yml" in rendered
    assert "workflow_automation" in rendered
