import json

from sdetkit import github_actions_annotation_hygiene_report as report

ANNOTATIONS = """submit-pypi
Node.js 20 actions are deprecated. The following actions are running on Node.js 20 and may not work as expected: actions/component-detection-dependency-submission-action@374343effede691df3a5ffaf36b4e7acab919590.
submit-pypi
The `python-version` input is not set. The version of Python currently in `PATH` will be used.
"""


def _maintenance_payload():
    return {
        "ok": False,
        "checks": {
            "github_actions_annotation_hygiene": {
                "ok": False,
                "summary": "GitHub Actions annotation hygiene: 2 finding(s), 1 warning(s), 1 notice(s)",
                "details": {
                    "annotation_hygiene": {
                        "schema_version": "sdetkit.github_actions.annotation_hygiene.v1",
                        "ok": False,
                        "finding_count": 2,
                        "warning_count": 1,
                        "notice_count": 1,
                        "findings": [
                            {
                                "id": "github_actions_node20_deprecation",
                                "severity": "warning",
                                "job": "submit-pypi",
                                "action": "actions/component-detection-dependency-submission-action@abc",
                                "title": "GitHub Actions Node.js 20 runtime deprecation",
                                "evidence": "Node.js 20 actions are deprecated.",
                                "recommendation": "Update the action or test Node 24.",
                            },
                            {
                                "id": "github_actions_missing_python_version",
                                "severity": "notice",
                                "job": "submit-pypi",
                                "action": "",
                                "title": "GitHub Actions setup-python version is implicit",
                                "evidence": "The `python-version` input is not set.",
                                "recommendation": "Pin an explicit python-version.",
                            },
                        ],
                    }
                },
                "actions": [],
            }
        },
    }


def test_report_from_maintenance_json_rolls_up_findings(tmp_path):
    path = tmp_path / "maintenance.json"
    path.write_text(json.dumps(_maintenance_payload()), encoding="utf-8")

    payload = report.report_from_maintenance_json(path)

    assert payload["schema_version"] == "sdetkit.github_actions.annotation_hygiene_report.v1"
    assert payload["ok"] is False
    assert payload["source_type"] == "maintenance_json"
    assert payload["warning_count"] == 1
    assert payload["notice_count"] == 1
    assert payload["by_id"]["github_actions_node20_deprecation"] == 1
    assert payload["by_severity"]["warning"] == 1
    assert "Update the action" in payload["top_actions"][0]


def test_report_from_annotation_log_runs_analyzer(tmp_path):
    path = tmp_path / "annotations.txt"
    path.write_text(ANNOTATIONS, encoding="utf-8")

    payload = report.report_from_annotation_log(path)

    assert payload["source_type"] == "annotation_log"
    assert payload["warning_count"] == 1
    assert payload["notice_count"] == 1
    assert "github_actions_node20_deprecation" in payload["by_id"]


def test_render_markdown_is_comment_ready(tmp_path):
    path = tmp_path / "maintenance.json"
    path.write_text(json.dumps(_maintenance_payload()), encoding="utf-8")

    rendered = report.render_markdown(report.report_from_maintenance_json(path))

    assert "# GitHub Actions annotation hygiene report" in rendered
    assert "GitHub Actions Node.js 20 runtime deprecation" in rendered
    assert "Suggested next actions" in rendered
    assert "submit-pypi" in rendered


def test_cli_writes_json_and_markdown_from_maintenance_report(tmp_path):
    input_path = tmp_path / "maintenance.json"
    out_json = tmp_path / "annotation-hygiene-report.json"
    out_md = tmp_path / "annotation-hygiene-report.md"
    input_path.write_text(json.dumps(_maintenance_payload()), encoding="utf-8")

    rc = report.main(
        [
            "--maintenance-json",
            str(input_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 1
    assert json.loads(out_json.read_text(encoding="utf-8"))["warning_count"] == 1
    assert "GitHub Actions annotation hygiene report" in out_md.read_text(encoding="utf-8")


def test_cli_returns_zero_for_clean_annotation_log(tmp_path, capsys):
    input_path = tmp_path / "annotations.txt"
    input_path.write_text("all green\n", encoding="utf-8")

    rc = report.main(["--annotation-log", str(input_path), "--format", "md"])

    assert rc == 0
    assert "No GitHub Actions annotation hygiene findings" in capsys.readouterr().out
