import json

from sdetkit import maintenance_priority_rollup as rollup


def _maintenance_report():
    return {
        "checks": {
            "lint_check": {
                "ok": False,
                "summary": "ruff failed",
                "actions": [{"id": "lint-fix", "title": "Run ruff check --fix"}],
            },
            "doctor_check": {
                "ok": True,
                "summary": "doctor score 95%",
                "actions": [{"id": "doctor-review", "title": "Review doctor hints"}],
            },
        }
    }


def _annotation_report():
    return {
        "annotation_hygiene": {
            "findings": [
                {
                    "id": "github_actions_node20_deprecation",
                    "severity": "warning",
                    "job": "submit-pypi",
                    "title": "GitHub Actions Node.js 20 runtime deprecation",
                    "evidence": "Node.js 20 actions are deprecated.",
                    "recommendation": "Update the action or test Node 24.",
                },
                {
                    "id": "github_actions_missing_python_version",
                    "severity": "notice",
                    "job": "submit-pypi",
                    "title": "GitHub Actions setup-python version is implicit",
                    "evidence": "The python-version input is not set.",
                    "recommendation": "Pin an explicit python-version.",
                },
            ]
        }
    }


def _safe_fix_rollup():
    return {
        "groups": [
            {
                "fix_type": "ruff_fixable_lint",
                "code": "RUFF_FIXABLE_LINT",
                "remediation_attempts": 2,
                "remediation_successes": 1,
                "commit_pushes": 1,
                "latest_remediation_status": "failed",
            },
            {
                "fix_type": "format_only",
                "code": "PRE_COMMIT_FORMAT_DRIFT",
                "remediation_attempts": 3,
                "remediation_successes": 3,
                "commit_pushes": 0,
                "latest_remediation_status": "success",
            },
        ]
    }


def test_build_priority_rollup_ranks_maintenance_failures_first():
    payload = rollup.build_priority_rollup(
        maintenance_report=_maintenance_report(),
        annotation_report=_annotation_report(),
        safe_fix_rollup=_safe_fix_rollup(),
    )

    assert payload["schema_version"] == "sdetkit.maintenance.priority_rollup.v1"
    assert payload["ok"] is False
    assert payload["priority_queue"][0]["priority"] == 1
    assert payload["priority_queue"][0]["source"] == "maintenance"
    assert "lint_check" in payload["priority_queue"][0]["title"]
    assert payload["counts_by_source"]["annotation_hygiene"] == 2
    assert payload["counts_by_source"]["safe_fix_rollup"] == 2


def test_build_priority_rollup_includes_top_action_and_limits_queue():
    payload = rollup.build_priority_rollup(
        maintenance_report=_maintenance_report(),
        annotation_report=_annotation_report(),
        safe_fix_rollup=_safe_fix_rollup(),
        limit=3,
    )

    assert payload["queue_count"] == 3
    assert (
        payload["top_action"]
        == "Review maintenance check `lint_check` and run its suggested action."
    )
    assert [item["rank"] for item in payload["priority_queue"]] == [1, 2, 3]


def test_render_markdown_outputs_comment_ready_table():
    payload = rollup.build_priority_rollup(
        maintenance_report=_maintenance_report(),
        annotation_report=_annotation_report(),
    )

    rendered = rollup.render_markdown(payload)

    assert "# Maintenance priority rollup" in rendered
    assert "| Rank | P | Source | Severity | Title | Action |" in rendered
    assert "GitHub Actions Node.js 20 runtime deprecation" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    maintenance_path = tmp_path / "maintenance.json"
    annotation_path = tmp_path / "annotation.json"
    safe_fix_path = tmp_path / "safe-fix.json"
    out_json = tmp_path / "priority.json"
    out_md = tmp_path / "priority.md"

    maintenance_path.write_text(json.dumps(_maintenance_report()), encoding="utf-8")
    annotation_path.write_text(json.dumps(_annotation_report()), encoding="utf-8")
    safe_fix_path.write_text(json.dumps(_safe_fix_rollup()), encoding="utf-8")

    rc = rollup.main(
        [
            "--maintenance-json",
            str(maintenance_path),
            "--annotation-report-json",
            str(annotation_path),
            "--safe-fix-rollup-json",
            str(safe_fix_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--limit",
            "5",
        ]
    )

    assert rc == 1
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["queue_count"] == 5
    assert "Maintenance priority rollup" in out_md.read_text(encoding="utf-8")


def test_empty_rollup_is_ok_and_has_no_actions():
    payload = rollup.build_priority_rollup()

    assert payload["ok"] is True
    assert payload["queue_count"] == 0
    assert payload["top_action"] == ""
    assert "No prioritized maintenance follow-ups" in rollup.render_markdown(payload)
