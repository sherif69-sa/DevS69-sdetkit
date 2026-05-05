import json

from sdetkit import maintenance_policy_decisions as policy


def _priority_rollup():
    return {
        "schema_version": "sdetkit.maintenance.priority_rollup.v1",
        "ok": False,
        "priority_queue": [
            {
                "rank": 1,
                "priority": 1,
                "source": "maintenance",
                "severity": "error",
                "title": "Maintenance check failed: lint_check",
                "action": "Review maintenance check `lint_check` and run its suggested action.",
                "key": "maintenance:lint_check",
            },
            {
                "rank": 2,
                "priority": 2,
                "source": "annotation_hygiene",
                "severity": "warning",
                "title": "GitHub Actions Node.js 20 runtime deprecation",
                "action": "Update the action or test Node 24.",
                "key": "annotation:node20:submit-pypi",
            },
            {
                "rank": 3,
                "priority": 2,
                "source": "safe_fix_rollup",
                "severity": "warning",
                "title": "Safe fix needs review: ruff_fixable_lint",
                "action": "Review safe-fix outcomes before widening automation policy.",
                "key": "safe-fix:ruff_fixable_lint:RUFF_FIXABLE_LINT",
            },
            {
                "rank": 4,
                "priority": 4,
                "source": "annotation_hygiene",
                "severity": "notice",
                "title": "GitHub Actions setup-python version is implicit",
                "action": "Pin an explicit python-version.",
                "key": "annotation:python-version:submit-pypi",
            },
        ],
    }


def test_build_policy_decisions_blocks_release_for_priority_one_maintenance_failure():
    payload = policy.build_policy_decisions(_priority_rollup())

    assert payload["schema_version"] == "sdetkit.maintenance.policy_decisions.v1"
    assert payload["ok"] is False
    assert payload["decision"] == "BLOCK_RELEASE"
    assert payload["release_blocking"] is True
    assert payload["automation_allowed"] is False
    assert payload["adaptive_ready"] is True
    assert payload["decisions"][0]["decision"] == "BLOCK_RELEASE"
    assert payload["decisions"][0]["confidence"] == "high"
    assert payload["decisions"][0]["release_risk"] == "high"
    assert payload["decisions"][0]["observed_source"] == "maintenance"
    assert "source=maintenance" in payload["decisions"][0]["policy_basis"]
    assert payload["counts_by_decision"]["BLOCK_RELEASE"] == 1


def test_build_policy_decisions_maps_warning_and_safe_fix_policies():
    payload = policy.build_policy_decisions(_priority_rollup())
    by_title = {item["title"]: item for item in payload["decisions"]}

    node20 = by_title["GitHub Actions Node.js 20 runtime deprecation"]
    safe_fix = by_title["Safe fix needs review: ruff_fixable_lint"]
    python_version = by_title["GitHub Actions setup-python version is implicit"]

    assert node20["decision"] == "TRACK_ONLY"
    assert node20["automation_risk"] == "high"
    assert node20["release_risk"] == "low"
    assert "submit-pypi" in node20["adaptive_context"]
    assert "key=annotation:node20:submit-pypi" in node20["policy_basis"]

    assert safe_fix["decision"] == "REVIEW_REQUIRED"
    assert safe_fix["automation_risk"] == "high"
    assert "safe-fix outcome history" in safe_fix["adaptive_context"]

    assert python_version["decision"] == "TRACK_ONLY"


def test_build_policy_decisions_no_action_for_empty_rollup():
    payload = policy.build_policy_decisions({"priority_queue": []})

    assert payload["ok"] is True
    assert payload["decision"] == "NO_ACTION"
    assert payload["release_blocking"] is False
    assert payload["top_action"] == ""
    assert payload["top_adaptive_context"] == ""
    assert payload["adaptive_ready"] is True
    assert payload["decisions"] == []


def test_render_markdown_is_comment_ready():
    payload = policy.build_policy_decisions(_priority_rollup())

    rendered = policy.render_markdown(payload)

    assert "# Maintenance policy decisions" in rendered
    assert "overall decision: **BLOCK_RELEASE**" in rendered
    assert "| Rank | Decision | P | Source | Confidence | Risk | Title | Action |" in rendered
    assert "Adaptive context" in rendered
    assert "Safe fix needs review: ruff_fixable_lint" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    input_path = tmp_path / "priority.json"
    out_json = tmp_path / "policy.json"
    out_md = tmp_path / "policy.md"
    input_path.write_text(json.dumps(_priority_rollup()), encoding="utf-8")

    rc = policy.main(
        [
            "--priority-rollup-json",
            str(input_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "md",
        ]
    )

    assert rc == 1
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "BLOCK_RELEASE"
    assert "Maintenance policy decisions" in out_md.read_text(encoding="utf-8")


def test_cli_returns_zero_for_track_only_rollup(tmp_path):
    input_path = tmp_path / "priority.json"
    input_path.write_text(
        json.dumps(
            {
                "priority_queue": [
                    {
                        "rank": 1,
                        "priority": 4,
                        "source": "annotation_hygiene",
                        "severity": "notice",
                        "title": "GitHub Actions setup-python version is implicit",
                        "action": "Pin an explicit python-version.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rc = policy.main(["--priority-rollup-json", str(input_path)])

    assert rc == 0
