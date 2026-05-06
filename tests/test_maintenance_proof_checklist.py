import json

from sdetkit import maintenance_proof_checklist as checklist


def _categories_payload():
    return {
        "schema_version": "sdetkit.maintenance.action_categories.v1",
        "ok": True,
        "diagnostic_only": True,
        "automation_allowed": False,
        "items": [
            {
                "rank": 1,
                "signal": "Run ruff check",
                "memory_lookup_key": "diagnosis:RUFF_FIXABLE_LINT:lint",
                "diagnosis_class": "RUFF_FIXABLE_LINT",
                "category": "lint",
                "risk_level": "low",
                "safe_fix_route": "candidate_later",
            },
            {
                "rank": 2,
                "signal": "Run pytest -q",
                "memory_lookup_key": "diagnosis:PRODUCT_LOGIC_FAILURE:tests",
                "diagnosis_class": "PRODUCT_LOGIC_FAILURE",
                "category": "product_logic",
                "risk_level": "high",
                "safe_fix_route": "review_first",
            },
            {
                "rank": 3,
                "signal": "Sync branch before push",
                "memory_lookup_key": "diagnosis:GIT_BRANCH_DIVERGED:git",
                "diagnosis_class": "GIT_BRANCH_DIVERGED",
                "category": "git_workflow",
                "risk_level": "medium",
                "safe_fix_route": "command_guidance",
                "proof_status": "complete",
                "proof_evidence": ["rebased and preflight passed"],
            },
            {
                "rank": 4,
                "signal": "Unknown maintenance signal",
                "memory_lookup_key": "diagnosis:UNKNOWN_REVIEW_REQUIRED:unknown",
                "diagnosis_class": "UNKNOWN_REVIEW_REQUIRED",
                "category": "unknown",
                "risk_level": "medium",
                "safe_fix_route": "review_first",
            },
        ],
    }


def test_build_proof_checklist_blocks_missing_proof_and_keeps_diagnostic_only():
    payload = checklist.build_proof_checklist(_categories_payload())

    assert payload["schema_version"] == "sdetkit.maintenance.proof_checklist.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["proof_item_count"] == 4
    assert payload["complete_count"] == 1
    assert payload["missing_count"] == 3

    by_key = {item["memory_lookup_key"]: item for item in payload["items"]}

    ruff = by_key["diagnosis:RUFF_FIXABLE_LINT:lint"]
    assert ruff["proof_status"] == "missing"
    assert ruff["can_progress_to_candidate"] is False
    assert ruff["blocking_reason"] == "Required proof has not been attached."
    assert "ruff check" in " ".join(ruff["proof_commands"]).lower()

    product = by_key["diagnosis:PRODUCT_LOGIC_FAILURE:tests"]
    assert product["required_artifacts"] == ["before/after focused pytest output"]
    assert product["can_progress_to_candidate"] is False

    git = by_key["diagnosis:GIT_BRANCH_DIVERGED:git"]
    assert git["proof_status"] == "complete"
    assert git["can_progress_to_candidate"] is True
    assert git["blocking_reason"] == ""


def test_unknown_diagnosis_gets_review_required_proof():
    payload = checklist.build_proof_checklist(
        {
            "items": [
                {
                    "rank": 1,
                    "signal": "Unclassified thing",
                    "memory_lookup_key": "unknown:signal",
                    "diagnosis_class": "NOT_A_REAL_CLASS",
                }
            ]
        }
    )

    item = payload["items"][0]
    assert item["diagnosis_class"] == "NOT_A_REAL_CLASS"
    assert item["required_artifacts"] == ["failure log", "review note"]
    assert item["proof_status"] == "missing"
    assert item["can_progress_to_candidate"] is False


def test_render_markdown_is_comment_ready():
    payload = checklist.build_proof_checklist(_categories_payload())
    rendered = checklist.render_markdown(payload)

    assert "# Maintenance proof checklist" in rendered
    assert "automation allowed: **False**" in rendered
    assert "missing proof: **3**" in rendered
    assert "Proof checklist" in rendered
    assert "Proof commands" in rendered
    assert "RUFF_FIXABLE_LINT" in rendered


def test_cli_writes_json_and_markdown(tmp_path):
    source = tmp_path / "categories.json"
    out_json = tmp_path / "proof-checklist.json"
    out_md = tmp_path / "proof-checklist.md"
    source.write_text(json.dumps(_categories_payload()), encoding="utf-8")

    rc = checklist.main(
        [
            "--action-categories-json",
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
    assert payload["schema_version"] == "sdetkit.maintenance.proof_checklist.v1"
    assert payload["missing_count"] == 3
    assert "Maintenance proof checklist" in out_md.read_text(encoding="utf-8")
