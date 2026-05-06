import json

from sdetkit import maintenance_action_categories as categories


def _action_plan_payload():
    return {
        "schema_version": "sdetkit.maintenance.action_plan.v1",
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "actions": [
            {
                "rank": 1,
                "signal": "Run ruff check",
                "source": "safe_fix_rollup",
                "memory_lookup_key": "safe-fix:ruff",
                "eligibility": "DEFERRED",
                "automation_readiness": "CANDIDATE_LATER",
                "proof_needed": "Require repeated successful runs.",
            },
            {
                "rank": 2,
                "signal": "Run pytest -q",
                "source": "maintenance_action",
                "memory_lookup_key": "maintenance-action:tests_check:run-tests",
                "eligibility": "REVIEW_REQUIRED",
                "automation_readiness": "REVIEW_FIRST",
                "proof_needed": "Attach passing test output.",
            },
            {
                "rank": 3,
                "signal": "Fix Python runtime compatibility",
                "source": "maintenance_action",
                "memory_lookup_key": "diagnosis:PYTHON_RUNTIME_COMPATIBILITY:runtime",
                "diagnosis_class": "PYTHON_RUNTIME_COMPATIBILITY",
                "eligibility": "REVIEW_REQUIRED",
                "automation_readiness": "REVIEW_FIRST",
            },
            {
                "rank": 4,
                "signal": "Sync branch before push",
                "source": "git",
                "memory_lookup_key": "diagnosis:GIT_BRANCH_DIVERGED:git",
                "diagnosis_class": "GIT_BRANCH_DIVERGED",
                "eligibility": "REVIEW_REQUIRED",
                "automation_readiness": "REVIEW_FIRST",
            },
            {
                "rank": 5,
                "signal": "Safe format drift appears stable",
                "source": "safe_fix_rollup",
                "memory_lookup_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT:formatting",
                "diagnosis_class": "PRE_COMMIT_FORMAT_DRIFT",
                "eligibility": "ELIGIBLE_PENDING_POLICY",
                "automation_readiness": "AUTOMATION_READY",
            },
        ],
    }


def test_build_action_categories_keeps_diagnostic_only_and_maps_classes():
    payload = categories.build_action_categories(_action_plan_payload())

    assert payload["schema_version"] == "sdetkit.maintenance.action_categories.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["item_count"] == 5

    by_key = {item["memory_lookup_key"]: item for item in payload["items"]}

    ruff = by_key["safe-fix:ruff"]
    assert ruff["diagnosis_class"] == "RUFF_FIXABLE_LINT"
    assert ruff["category"] == "lint"
    assert ruff["risk_level"] == "low"
    assert ruff["safe_fix_route"] == "candidate_later"
    assert ruff["review_required"] is False

    tests = by_key["maintenance-action:tests_check:run-tests"]
    assert tests["diagnosis_class"] == "PRODUCT_LOGIC_FAILURE"
    assert tests["category"] == "product_logic"
    assert tests["safe_fix_route"] == "review_first"
    assert tests["review_required"] is True

    runtime = by_key["diagnosis:PYTHON_RUNTIME_COMPATIBILITY:runtime"]
    assert runtime["category"] == "runtime"
    assert runtime["risk_level"] == "high"
    assert runtime["review_required"] is True

    git = by_key["diagnosis:GIT_BRANCH_DIVERGED:git"]
    assert git["safe_fix_route"] == "command_guidance"
    assert git["review_required"] is True

    policy = by_key["diagnosis:PRE_COMMIT_FORMAT_DRIFT:formatting"]
    assert policy["safe_fix_route"] == "policy_required"
    assert policy["review_required"] is False


def test_counts_are_deterministic():
    payload = categories.build_action_categories(_action_plan_payload())

    assert payload["counts_by_category"] == {
        "formatting": 1,
        "git_workflow": 1,
        "lint": 1,
        "product_logic": 1,
        "runtime": 1,
    }
    assert payload["counts_by_route"] == {
        "candidate_later": 1,
        "command_guidance": 1,
        "policy_required": 1,
        "review_first": 2,
    }


def test_unknown_action_is_review_first():
    payload = categories.build_action_categories(
        {
            "actions": [
                {
                    "rank": 1,
                    "signal": "Unexpected maintenance signal",
                    "memory_lookup_key": "unknown:signal",
                }
            ]
        }
    )

    item = payload["items"][0]
    assert item["diagnosis_class"] == "UNKNOWN_REVIEW_REQUIRED"
    assert item["category"] == "unknown"
    assert item["safe_fix_route"] == "review_first"
    assert item["review_required"] is True


def test_render_markdown_is_comment_ready():
    payload = categories.build_action_categories(_action_plan_payload())
    rendered = categories.render_markdown(payload)

    assert "# Maintenance action categories" in rendered
    assert "automation allowed: **False**" in rendered
    assert "Category mix" in rendered
    assert "Classified actions" in rendered
    assert "PYTHON_RUNTIME_COMPATIBILITY" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    source = tmp_path / "action-plan.json"
    out_json = tmp_path / "categories.json"
    out_md = tmp_path / "categories.md"
    source.write_text(json.dumps(_action_plan_payload()), encoding="utf-8")

    rc = categories.main(
        [
            "--action-plan-json",
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
    assert payload["schema_version"] == "sdetkit.maintenance.action_categories.v1"
    assert payload["automation_allowed"] is False
    assert "Maintenance action categories" in out_md.read_text(encoding="utf-8")
