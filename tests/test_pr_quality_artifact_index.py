from __future__ import annotations

import base64
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from sdetkit.pr_quality_artifact_index import (
    refresh_pr_quality_artifact_index,
)


class _PayloadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inside = False
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        self.inside = tag == "script" and attributes.get("id") == "evidenceData"

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.inside = False

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.parts.append(data)


def _model() -> dict:
    return {
        "schema_version": "sdetkit.pr_quality.review_model.v2",
        "decision": {
            "review_state": "ready",
            "status": "green",
            "merge_assessment": ("automated_proof_complete_human_decision_required"),
            "next_action": "review_and_decide",
            "risk_surface": "diagnostic_engine",
        },
        "authority_boundary": {
            "boundary_mode": "reporting_only",
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
        "artifact_index": [
            {
                "path": "pr-review-dashboard.html",
                "kind": "html",
                "title": "Detailed review",
            },
            {
                "path": "pr-review-summary.md",
                "kind": "markdown",
                "title": "Review summary",
            },
            {
                "path": "pr-review-model.json",
                "kind": "json",
                "title": "Review model",
            },
            {
                "path": "pr-review-artifacts-manifest.json",
                "kind": "json",
                "title": "Artifact manifest",
            },
            {
                "path": "pr-comment-body.md",
                "kind": "markdown",
                "title": "Comment body",
            },
        ],
        "live_evidence": {
            "schema_version": "sdetkit.pr_quality.live_evidence.v1",
            "snapshot_status": "complete",
            "generated_at_utc": "2026-06-26T08:00:00+00:00",
            "provenance": {
                "pr_number": 1883,
                "head_sha": "head-sha",
                "workflow_run_id": "123",
                "head_binding_status": "verified",
                "artifact_entrypoint": "pr-quality/index.html",
                "artifacts_url": ("https://github.com/example/repo/actions/runs/123#artifacts"),
            },
            "authority_boundary": {
                "boundary_mode": "reporting_only",
                "patch_automation": False,
                "security_dismissal": False,
                "merge_authorization": False,
                "semantic_equivalence_claim": False,
            },
            "facts": [],
            "lineage": [],
        },
    }


def _payload(html: str) -> dict:
    parser = _PayloadParser()
    parser.feed(html)
    return json.loads("".join(parser.parts))


def test_refresh_embeds_final_files_byte_for_byte(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "pr-review-model.json"
    summary_path = tmp_path / "pr-review-summary.md"
    html_path = tmp_path / "pr-review-dashboard.html"
    manifest_path = tmp_path / "pr-review-artifacts-manifest.json"
    comment_path = tmp_path / "pr-comment-body.md"
    out = tmp_path / "index.html"

    model_path.write_text(
        json.dumps(_model(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text("# Final summary\n", encoding="utf-8")
    html_path.write_text(
        "<!doctype html><title>Final review</title>\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        '{"status":"final"}\n',
        encoding="utf-8",
    )
    comment_path.write_text(
        "# Initial body\n\n## Final appendix\n",
        encoding="utf-8",
    )

    result = refresh_pr_quality_artifact_index(
        review_model_path=model_path,
        review_summary_path=summary_path,
        review_html_path=html_path,
        review_manifest_path=manifest_path,
        comment_body_path=comment_path,
        out=out,
    )

    assert result["status"] == "passed"
    assert result["embedded_artifact_count"] == 5
    assert result["embedded_artifact_mismatch_count"] == 0
    assert result["relative_artifact_link_count"] == 0

    rendered = out.read_text(encoding="utf-8")
    payload = _payload(rendered)
    embedded = payload["embedded_artifacts"]

    expected = {
        "pr-review-dashboard.html": html_path.read_bytes(),
        "pr-review-summary.md": summary_path.read_bytes(),
        "pr-review-model.json": model_path.read_bytes(),
        "pr-review-artifacts-manifest.json": manifest_path.read_bytes(),
        "pr-comment-body.md": comment_path.read_bytes(),
    }
    for artifact_path, expected_bytes in expected.items():
        actual = base64.b64decode(
            embedded[artifact_path]["content_base64"],
            validate=True,
        )
        assert actual == expected_bytes

    assert "## Final appendix" not in rendered
    assert 'href="pr-comment-body.md"' not in rendered
    assert 'data-open-artifact="pr-comment-body.md"' in rendered


def test_refresh_fails_closed_when_final_file_is_missing(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "pr-review-model.json"
    model_path.write_text(
        json.dumps(_model()),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="required artifact file is missing",
    ):
        refresh_pr_quality_artifact_index(
            review_model_path=model_path,
            review_summary_path=tmp_path / "missing-summary.md",
            review_html_path=tmp_path / "missing-dashboard.html",
            review_manifest_path=tmp_path / "missing-manifest.json",
            comment_body_path=tmp_path / "missing-comment.md",
            out=tmp_path / "index.html",
        )
