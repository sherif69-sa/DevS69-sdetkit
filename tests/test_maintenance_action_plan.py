import json

from sdetkit import maintenance_action_plan as plan


def _eligibility_payload():
    return {
        "schema_version": "sdetkit.maintenance.recommendation_eligibility.v1",
        "ok": True,
        "next_gate": "MAINTAINER_REVIEW",
        "diagnostic_only": True,
        "automation_allowed": False,
        "items": [
            {
                "rank": 1,
                "eligibility": "REVIEW_REQUIRED",
                "automation_readiness": "REVIEW_FIRST",
                "source": "maintenance_action",
                "title": "Run pytest -q",
                "memory_lookup_key": "maintenance-action:tests_check:run-tests",
                "proof_needed": "Attach passing test output.",
                "required_gate": "Attach review proof before considering automation policy changes.",
            },
            {
                "rank": 2,
                "eligibility": "DEFERRED",
                "automation_readiness": "CANDIDATE_LATER",
                "source": "safe_fix_rollup",
                "title": "Observe ruff safe-fix stability",
                "memory_lookup_key": "safe-fix:ruff",
                "proof_needed": "Require repeated successful runs.",
                "required_gate": "Continue observing repeated successful evidence.",
            },
            {
                "rank": 3,
                "eligibility": "ELIGIBLE_PENDING_POLICY",
                "automation_readiness": "AUTOMATION_READY",
                "source": "safe_fix_rollup",
                "title": "Safe fix appears stable",
                "memory_lookup_key": "safe-fix:ready",
                "proof_needed": "Open policy PR.",
                "required_gate": "Require an explicit policy PR before enabling automation.",
            },
        ],
    }


def test_build_action_plan_keeps_automation_off_and_marks_future_candidates():
    payload = plan.build_action_plan(_eligibility_payload())

    assert payload["schema_version"] == "sdetkit.maintenance.action_plan.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["auto_fix_enabled"] is False
    assert payload["source_next_gate"] == "MAINTAINER_REVIEW"
    assert payload["action_count"] == 3
    assert payload["future_auto_fix_candidate_count"] == 2

    by_key = {item["memory_lookup_key"]: item for item in payload["actions"]}
    assert by_key["maintenance-action:tests_check:run-tests"]["future_auto_fix_candidate"] is False
    assert by_key["safe-fix:ruff"]["future_auto_fix_candidate"] is True
    assert by_key["safe-fix:ready"]["future_auto_fix_candidate"] is True


def test_blocked_item_has_blocked_auto_fix_reason():
    payload = plan.build_action_plan(
        {
            "next_gate": "BLOCKED_REVIEW",
            "items": [
                {
                    "rank": 1,
                    "eligibility": "BLOCKED",
                    "automation_readiness": "NOT_ELIGIBLE",
                    "title": "Release blocker",
                    "source": "maintenance",
                    "memory_lookup_key": "maintenance:lint",
                    "required_gate": "Resolve the release blocker.",
                }
            ],
        }
    )

    item = payload["actions"][0]
    assert payload["future_auto_fix_candidate_count"] == 0
    assert item["future_auto_fix_candidate"] is False
    assert item["auto_fix_blocker"] == "Blocked by release or explicit non-eligibility gate."


def test_render_markdown_is_comment_ready():
    payload = plan.build_action_plan(_eligibility_payload())

    rendered = plan.render_markdown(payload)

    assert "# Maintenance action plan" in rendered
    assert "auto-fix enabled: **False**" in rendered
    assert "future auto-fix candidates: **2**" in rendered
    assert "What to do next" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    source = tmp_path / "eligibility.json"
    out_json = tmp_path / "action-plan.json"
    out_md = tmp_path / "action-plan.md"
    source.write_text(json.dumps(_eligibility_payload()), encoding="utf-8")

    rc = plan.main(
        [
            "--eligibility-json",
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
    assert payload["future_auto_fix_candidate_count"] == 2
    assert "Maintenance action plan" in out_md.read_text(encoding="utf-8")
