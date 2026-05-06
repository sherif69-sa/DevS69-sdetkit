import json

from sdetkit import maintenance_recommendation_eligibility as eligibility


def _recommendations_payload():
    return {
        "schema_version": "sdetkit.maintenance.recommendations.v1",
        "ok": True,
        "decision": "REVIEW_REQUIRED",
        "release_blocking": False,
        "automation_allowed": False,
        "recommendations": [
            {
                "rank": 1,
                "recommendation": "MANUAL_REVIEW_REQUIRED",
                "decision": "REVIEW_REQUIRED",
                "source": "maintenance_action",
                "title": "Run pytest -q",
                "memory_lookup_key": "maintenance-action:tests_check:run-tests",
                "automation_readiness": "REVIEW_FIRST",
                "automation_allowed": False,
                "automation_eligible": False,
                "proof_needed": "Attach passing test output.",
            },
            {
                "rank": 2,
                "recommendation": "OBSERVE_SAFE_FIX_STABILITY",
                "decision": "TRACK_ONLY",
                "source": "safe_fix_rollup",
                "title": "Observe safe fix stability",
                "memory_lookup_key": "safe-fix:ruff",
                "automation_readiness": "CANDIDATE_LATER",
                "automation_allowed": False,
                "automation_eligible": False,
                "proof_needed": "Require repeated successful runs.",
            },
        ],
    }


def test_build_eligibility_report_classifies_review_and_deferred_items():
    payload = eligibility.build_eligibility_report(_recommendations_payload())

    assert payload["schema_version"] == "sdetkit.maintenance.recommendation_eligibility.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["next_gate"] == "MAINTAINER_REVIEW"
    assert payload["counts_by_eligibility"] == {"DEFERRED": 1, "REVIEW_REQUIRED": 1}

    by_key = {item["memory_lookup_key"]: item for item in payload["items"]}
    assert by_key["maintenance-action:tests_check:run-tests"]["eligibility"] == "REVIEW_REQUIRED"
    assert by_key["safe-fix:ruff"]["eligibility"] == "DEFERRED"


def test_build_eligibility_report_blocks_release_review_items():
    payload = eligibility.build_eligibility_report(
        {
            "decision": "BLOCK_RELEASE",
            "release_blocking": True,
            "recommendations": [
                {
                    "rank": 1,
                    "recommendation": "BLOCK_RELEASE_REVIEW",
                    "decision": "BLOCK_RELEASE",
                    "source": "maintenance",
                    "memory_lookup_key": "maintenance:lint",
                    "automation_readiness": "NOT_ELIGIBLE",
                }
            ],
        }
    )

    assert payload["next_gate"] == "BLOCKED_REVIEW"
    assert payload["counts_by_eligibility"] == {"BLOCKED": 1}
    assert payload["items"][0]["required_gate"] == (
        "Resolve or explicitly review the release-blocking signal first."
    )


def test_ready_signals_still_require_policy_pr_and_do_not_enable_automation():
    payload = eligibility.build_eligibility_report(
        {
            "decision": "TRACK_ONLY",
            "release_blocking": False,
            "automation_allowed": True,
            "recommendations": [
                {
                    "rank": 1,
                    "recommendation": "OBSERVE_SAFE_FIX_STABILITY",
                    "decision": "TRACK_ONLY",
                    "source": "safe_fix_rollup",
                    "memory_lookup_key": "safe-fix:ready",
                    "automation_readiness": "AUTOMATION_READY",
                    "automation_allowed": True,
                    "automation_eligible": True,
                }
            ],
        }
    )

    assert payload["automation_allowed"] is False
    assert payload["diagnostic_only"] is True
    assert payload["next_gate"] == "POLICY_PR_REQUIRED"
    assert payload["items"][0]["eligibility"] == "ELIGIBLE_PENDING_POLICY"


def test_render_markdown_is_comment_ready():
    payload = eligibility.build_eligibility_report(_recommendations_payload())

    rendered = eligibility.render_markdown(payload)

    assert "# Maintenance recommendation eligibility" in rendered
    assert "diagnostic only" in rendered
    assert "MAINTAINER_REVIEW" in rendered
    assert "Why blocked, deferred, or review-first" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    source = tmp_path / "recommendations.json"
    out_json = tmp_path / "eligibility.json"
    out_md = tmp_path / "eligibility.md"
    source.write_text(json.dumps(_recommendations_payload()), encoding="utf-8")

    rc = eligibility.main(
        [
            "--recommendations-json",
            str(source),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "md",
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["next_gate"] == "MAINTAINER_REVIEW"
    assert "Maintenance recommendation eligibility" in out_md.read_text(encoding="utf-8")
