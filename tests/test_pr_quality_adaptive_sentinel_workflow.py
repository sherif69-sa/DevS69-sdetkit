from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")
QUALITY_LOG = "/".join(("build", "pr-quality", "failure-intelligence", "quality.log"))


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pr_quality_workflow_runs_adaptive_sentinel_after_failure_bundle() -> None:
    text = _workflow_text()

    assert "Build adaptive failure intelligence bundle" in text
    assert "Run adaptive sentinel scan" in text
    assert text.index("Build adaptive failure intelligence bundle") < text.index(
        "Run adaptive sentinel scan"
    )
    assert "python -m sdetkit adaptive sentinel scan" in text
    assert "--out-dir build/sdetkit/sentinel" in text
    assert "--no-fail" in text


def test_pr_quality_workflow_passes_sentinel_control_room_to_adaptive_renderer() -> None:
    text = _workflow_text()

    assert "python -m sdetkit.pr_quality_evidence_narrative" in text
    assert "--sentinel-control-room build/sdetkit/sentinel/control-room.json" in text
    assert "--evidence-graph build/sdetkit/evidence-graph/evidence-graph.json" in text
    assert "--changed-files build/pr-quality/changed-files.txt" in text
    assert "sentinel_state=" not in text
    assert "append_sentinel_summary" not in text


def test_pr_quality_workflow_uploads_adaptive_sentinel_artifacts() -> None:
    text = _workflow_text()

    assert "Upload adaptive sentinel artifacts" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "name: pr-quality-adaptive-sentinel" in text
    assert "build/sdetkit/sentinel/" in text
    assert ".sdetkit/adaptive-sentinel/" in text


def test_pr_quality_workflow_builds_evidence_graph_from_sentinel_control_room() -> None:
    text = _workflow_text()

    assert "Build PR evidence graph" in text
    assert "python -m sdetkit.evidence_graph" in text
    assert "--sentinel-control-room build/sdetkit/sentinel/control-room.json" in text
    assert "--out-dir build/sdetkit/evidence-graph" in text
    assert "--evidence-graph build/sdetkit/evidence-graph/evidence-graph.json" in text


def test_pr_quality_workflow_uploads_evidence_graph_artifacts() -> None:
    text = _workflow_text()

    assert "build/sdetkit/evidence-graph/" in text


def test_pr_quality_workflow_delegates_comment_body_to_adaptive_renderer() -> None:
    text = _workflow_text()

    assert "python -m sdetkit.pr_quality_evidence_narrative" in text
    assert text.count(f"--quality-log {QUALITY_LOG}") == 2
    assert "--quality-outcome" in text
    assert "--changed-files build/pr-quality/changed-files.txt" in text
    assert "--json-out build/pr-quality/pr-evidence-narrative.json" in text
    assert "write_evidence_graph_summary" not in text
    assert "append_evidence_graph_summary" not in text


def test_pr_quality_routes_generated_quality_log_out_of_sentinel_git_surface() -> None:
    text = _workflow_text()
    quality = text[
        text.index("- name: Run quality gate") : text.index(
            "- name: Build adaptive failure intelligence bundle"
        )
    ]
    sentinel = text[
        text.index("- name: Run adaptive sentinel scan") : text.index(
            "- name: Collect security review evidence"
        )
    ]

    assert f"tee {QUALITY_LOG}" in quality
    assert "tee quality.log" not in quality
    assert "python -m sdetkit adaptive sentinel scan" in sentinel
    assert "build/" in Path(".gitignore").read_text(encoding="utf-8").splitlines()
