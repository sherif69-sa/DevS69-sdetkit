import json

from sdetkit import maintenance_recommendations as recs


def _memory_context():
    return {
        "decision": "BLOCK_RELEASE",
        "ok": False,
        "release_blocking": True,
        "decisions": [
            {
                "rank": 1,
                "decision": "BLOCK_RELEASE",
                "source": "maintenance",
                "severity": "error",
                "title": "Maintenance check failed: lint_check",
                "memory_lookup_key": "maintenance:lint_check",
                "release_risk": "high",
                "automation_risk": "high",
            },
            {
                "rank": 2,
                "decision": "TRACK_ONLY",
                "source": "annotation_hygiene",
                "severity": "warning",
                "title": "GitHub Actions Node.js 20 runtime deprecation",
                "memory_lookup_key": "annotation:node20:submit-pypi",
                "automation_risk": "high",
                "release_risk": "low",
                "history_context": {
                    "matched": True,
                    "seen_count": 3,
                    "policy_hint": "Escalate recurrence review if the same non-green decision keeps appearing.",
                },
                "annotation_context": {
                    "matched": True,
                    "job": "submit-pypi",
                    "policy_hint": "Track as workflow hygiene unless repeated history later shows release impact.",
                },
            },
            {
                "rank": 3,
                "decision": "REVIEW_REQUIRED",
                "source": "safe_fix_rollup",
                "severity": "warning",
                "title": "Safe fix needs review: ruff_fixable_lint",
                "memory_lookup_key": "safe-fix:ruff_fixable_lint:RUFF_FIXABLE_LINT",
                "automation_risk": "high",
                "safe_fix_context": {
                    "matched": True,
                    "remediation_attempts": 3,
                    "remediation_successes": 2,
                    "policy_hint": "Keep REVIEW_REQUIRED until safe-fix outcomes are consistently successful.",
                },
            },
        ],
    }


def test_build_recommendations_turns_memory_context_into_next_actions():
    payload = recs.build_recommendations(_memory_context())

    assert payload["schema_version"] == "sdetkit.maintenance.recommendations.v1"
    assert payload["decision"] == "BLOCK_RELEASE"
    assert payload["release_blocking"] is True
    assert payload["automation_allowed"] is False
    assert payload["recommendation_count"] == 3
    assert payload["top_recommendation"] == "BLOCK_RELEASE_REVIEW"

    by_key = {item["memory_lookup_key"]: item for item in payload["recommendations"]}
    assert by_key["maintenance:lint_check"]["automation_readiness"] == "NOT_ELIGIBLE"
    assert (
        by_key["annotation:node20:submit-pypi"]["recommendation"]
        == "OPEN_WORKFLOW_HYGIENE_FOLLOWUP"
    )
    assert by_key["annotation:node20:submit-pypi"]["observed_seen_count"] == 3
    assert (
        by_key["safe-fix:ruff_fixable_lint:RUFF_FIXABLE_LINT"]["recommendation"]
        == "REVIEW_SAFE_FIX_OUTCOMES"
    )


def test_build_recommendations_tracks_single_annotation_without_escalating():
    payload = recs.build_recommendations(
        {
            "decision": "TRACK_ONLY",
            "release_blocking": False,
            "decisions": [
                {
                    "rank": 1,
                    "decision": "TRACK_ONLY",
                    "source": "annotation_hygiene",
                    "title": "GitHub Actions setup-python version is implicit",
                    "memory_lookup_key": "annotation:python-version:submit-pypi",
                    "history_context": {"seen_count": 1},
                }
            ],
        }
    )

    item = payload["recommendations"][0]
    assert payload["release_blocking"] is False
    assert item["recommendation"] == "TRACK_WORKFLOW_HYGIENE"
    assert item["automation_readiness"] == "OBSERVE_ONLY"
    assert item["automation_eligible"] is False


def test_build_recommendations_emits_no_action_for_empty_nonblocking_context():
    payload = recs.build_recommendations(
        {"decision": "NO_ACTION", "release_blocking": False, "decisions": []}
    )

    assert payload["recommendation_count"] == 1
    assert payload["top_recommendation"] == "NO_ACTION_REQUIRED"
    assert (
        payload["recommendations"][0]["recommended_next_action"]
        == "No maintenance action is required."
    )


def test_render_markdown_is_comment_ready():
    payload = recs.build_recommendations(_memory_context())

    rendered = recs.render_markdown(payload)

    assert "# Adaptive maintenance recommendations" in rendered
    assert "BLOCK_RELEASE_REVIEW" in rendered
    assert "Why now / proof needed" in rendered
    assert "OPEN_WORKFLOW_HYGIENE_FOLLOWUP" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    memory_path = tmp_path / "memory.json"
    out_json = tmp_path / "recommendations.json"
    out_md = tmp_path / "recommendations.md"
    memory_path.write_text(json.dumps(_memory_context()), encoding="utf-8")

    rc = recs.main(
        [
            "--memory-context-json",
            str(memory_path),
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
    assert payload["top_recommendation"] == "BLOCK_RELEASE_REVIEW"
    assert "Adaptive maintenance recommendations" in out_md.read_text(encoding="utf-8")


def test_cli_returns_zero_for_nonblocking_recommendations(tmp_path):
    memory_path = tmp_path / "memory.json"
    memory_path.write_text(
        json.dumps({"decision": "TRACK_ONLY", "release_blocking": False, "decisions": []}),
        encoding="utf-8",
    )

    rc = recs.main(["--memory-context-json", str(memory_path)])

    assert rc == 0
