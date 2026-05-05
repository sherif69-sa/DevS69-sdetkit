import json

from sdetkit import maintenance_policy_memory_context as memory


def _policy_decisions():
    return {
        "decision": "BLOCK_RELEASE",
        "ok": False,
        "release_blocking": True,
        "top_action": "Review maintenance check `lint_check`.",
        "decisions": [
            {
                "rank": 1,
                "decision": "BLOCK_RELEASE",
                "source": "maintenance",
                "title": "Maintenance check failed: lint_check",
                "memory_lookup_key": "maintenance:lint_check",
                "source_key": "maintenance:lint_check",
                "action": "Review maintenance check `lint_check`.",
            },
            {
                "rank": 2,
                "decision": "TRACK_ONLY",
                "source": "annotation_hygiene",
                "title": "GitHub Actions Node.js 20 runtime deprecation",
                "memory_lookup_key": "annotation:node20:submit-pypi",
                "source_key": "annotation:node20:submit-pypi",
                "action": "Update the action or test Node 24.",
            },
            {
                "rank": 3,
                "decision": "REVIEW_REQUIRED",
                "source": "safe_fix_rollup",
                "title": "Safe fix needs review: ruff_fixable_lint",
                "memory_lookup_key": "safe-fix:ruff_fixable_lint:RUFF_FIXABLE_LINT",
                "source_key": "safe-fix:ruff_fixable_lint:RUFF_FIXABLE_LINT",
                "action": "Review safe-fix outcomes before widening automation policy.",
            },
        ],
    }


def _safe_fix_rollup():
    return {
        "groups": [
            {
                "fix_type": "ruff_fixable_lint",
                "code": "RUFF_FIXABLE_LINT",
                "remediation_attempts": 3,
                "remediation_successes": 2,
                "commit_pushes": 1,
                "latest_remediation_status": "failed",
            }
        ]
    }


def _annotation_report():
    return {
        "annotation_hygiene": {
            "findings": [
                {
                    "id": "github_actions_node20_deprecation",
                    "severity": "warning",
                    "job": "submit-pypi",
                    "evidence": "Node.js 20 actions are deprecated.",
                    "recommendation": "Update the action or test Node 24.",
                }
            ]
        }
    }


def _history_records():
    return [
        {
            "decisions": [
                {
                    "decision": "BLOCK_RELEASE",
                    "memory_lookup_key": "maintenance:lint_check",
                    "title": "Maintenance check failed: lint_check",
                },
                {
                    "decision": "TRACK_ONLY",
                    "memory_lookup_key": "annotation:node20:submit-pypi",
                    "title": "GitHub Actions Node.js 20 runtime deprecation",
                },
            ]
        },
        {
            "decisions": [
                {
                    "decision": "TRACK_ONLY",
                    "memory_lookup_key": "annotation:node20:submit-pypi",
                    "title": "GitHub Actions Node.js 20 runtime deprecation",
                },
            ]
        },
        {
            "decisions": [
                {
                    "decision": "TRACK_ONLY",
                    "memory_lookup_key": "annotation:node20:submit-pypi",
                    "title": "GitHub Actions Node.js 20 runtime deprecation",
                },
            ]
        },
    ]


def test_build_policy_memory_context_enriches_annotation_and_safe_fix_decisions():
    payload = memory.build_policy_memory_context(
        _policy_decisions(),
        safe_fix_rollup=_safe_fix_rollup(),
        annotation_report=_annotation_report(),
        history_records=_history_records(),
    )

    assert payload["schema_version"] == "sdetkit.maintenance.policy_memory_context.v1"
    assert payload["decision"] == "BLOCK_RELEASE"
    assert payload["release_blocking"] is True
    assert payload["memory_aware"] is True
    assert payload["memory_enriched_count"] == 3
    assert payload["repeated_signal_count"] == 1

    by_key = {item["memory_lookup_key"]: item for item in payload["decisions"]}
    node20 = by_key["annotation:node20:submit-pypi"]
    safe_fix = by_key["safe-fix:ruff_fixable_lint:RUFF_FIXABLE_LINT"]

    assert node20["annotation_context"]["job"] == "submit-pypi"
    assert node20["history_context"]["seen_count"] == 3
    assert "Escalate recurrence review" in node20["history_context"]["policy_hint"]

    assert safe_fix["safe_fix_context"]["remediation_attempts"] == 3
    assert safe_fix["safe_fix_context"]["remediation_successes"] == 2
    assert "Keep REVIEW_REQUIRED" in safe_fix["safe_fix_context"]["policy_hint"]


def test_build_policy_memory_context_marks_first_observation_when_no_history():
    payload = memory.build_policy_memory_context(_policy_decisions())

    assert payload["memory_aware"] is True
    assert payload["memory_enriched_count"] == 0
    assert payload["repeated_signal_count"] == 0
    assert payload["decisions"][0]["history_context"]["matched"] is False
    assert "first observation" in payload["decisions"][0]["history_context"]["policy_hint"]


def test_render_markdown_shows_context_highlights():
    payload = memory.build_policy_memory_context(
        _policy_decisions(),
        safe_fix_rollup=_safe_fix_rollup(),
        annotation_report=_annotation_report(),
        history_records=_history_records(),
    )

    rendered = memory.render_markdown(payload)

    assert "# Maintenance policy memory context" in rendered
    assert "Context highlights" in rendered
    assert "annotation:node20:submit-pypi" in rendered
    assert "Safe-fix memory shows 2/3 remediation successes" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    policy_path = tmp_path / "policy.json"
    safe_fix_path = tmp_path / "safe-fix.json"
    annotation_path = tmp_path / "annotation.json"
    history_path = tmp_path / "history.jsonl"
    out_json = tmp_path / "memory-context.json"
    out_md = tmp_path / "memory-context.md"

    policy_path.write_text(json.dumps(_policy_decisions()), encoding="utf-8")
    safe_fix_path.write_text(json.dumps(_safe_fix_rollup()), encoding="utf-8")
    annotation_path.write_text(json.dumps(_annotation_report()), encoding="utf-8")
    history_path.write_text(
        "\n".join(json.dumps(item) for item in _history_records()) + "\n",
        encoding="utf-8",
    )

    rc = memory.main(
        [
            "--policy-decisions-json",
            str(policy_path),
            "--safe-fix-rollup-json",
            str(safe_fix_path),
            "--annotation-report-json",
            str(annotation_path),
            "--history-jsonl",
            str(history_path),
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
    assert payload["memory_enriched_count"] == 3
    assert "Maintenance policy memory context" in out_md.read_text(encoding="utf-8")


def test_cli_returns_zero_for_non_blocking_policy(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps({"decision": "TRACK_ONLY", "release_blocking": False, "decisions": []}),
        encoding="utf-8",
    )

    rc = memory.main(["--policy-decisions-json", str(policy_path)])

    assert rc == 0
