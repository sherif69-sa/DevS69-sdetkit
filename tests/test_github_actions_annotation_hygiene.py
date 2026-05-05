import json

from sdetkit import github_actions_annotation_hygiene as hygiene

ANNOTATIONS = """submit-pypi
Node.js 20 actions are deprecated. The following actions are running on Node.js 20 and may not work as expected: actions/component-detection-dependency-submission-action@374343effede691df3a5ffaf36b4e7acab919590. Actions will be forced to run with Node.js 24 by default starting June 2nd, 2026.
submit-pypi
The `python-version` input is not set. The version of Python currently in `PATH` will be used.
Run actions/component-detection-dependency-submission-action@374343effede691df3a5ffaf36b4e7acab919590
/home/runner/work/repo/repo/component-detection scan --SourceDirectory . --DetectorsFilter PipReport
"""


def test_analyze_annotations_detects_node20_python_and_dependency_submission_source():
    payload = hygiene.analyze_annotations(ANNOTATIONS)

    assert payload["schema_version"] == "sdetkit.github_actions.annotation_hygiene.v1"
    assert payload["ok"] is False
    assert payload["warning_count"] == 1
    assert payload["notice_count"] == 1
    ids = {finding["id"] for finding in payload["findings"]}
    assert "github_actions_node20_deprecation" in ids
    assert "github_actions_missing_python_version" in ids
    assert "github_actions_dependency_submission_annotation_source" in ids


def test_node20_finding_extracts_action_and_job():
    payload = hygiene.analyze_annotations(ANNOTATIONS)
    finding = next(
        item for item in payload["findings"] if item["id"] == "github_actions_node20_deprecation"
    )

    assert finding["job"] == "submit-pypi"
    assert finding["action"].startswith("actions/component-detection-dependency-submission-action@")
    assert "Node.js 20" in finding["title"]


def test_render_markdown_includes_recommendations():
    rendered = hygiene.render_markdown(hygiene.analyze_annotations(ANNOTATIONS))

    assert "# GitHub Actions annotation hygiene" in rendered
    assert "GitHub Actions Node.js 20 runtime deprecation" in rendered
    assert "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" in rendered
    assert "Do not patch product code" in rendered


def test_cli_writes_json_and_returns_warning_status(tmp_path):
    log_path = tmp_path / "annotations.txt"
    out_path = tmp_path / "annotations.json"
    log_path.write_text(ANNOTATIONS, encoding="utf-8")

    rc = hygiene.main([str(log_path), "--format", "json", "--out", str(out_path)])

    assert rc == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["warning_count"] == 1


def test_cli_returns_zero_when_no_warnings(tmp_path, capsys):
    log_path = tmp_path / "annotations.txt"
    log_path.write_text("all green\n", encoding="utf-8")

    rc = hygiene.main([str(log_path), "--format", "md"])

    assert rc == 0
    assert "No GitHub Actions annotation hygiene findings" in capsys.readouterr().out
