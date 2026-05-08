from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_remediation_policy
from sdetkit.cli import main as top_level_main


def _safe_plan(file_count: int = 2) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "source_status": "needs_fix",
        "source_code": "RUFF_FIXABLE_LINT",
        "safe_to_auto_fix": True,
        "fix_type": "ruff_fixable_lint",
        "requires_human_review": False,
        "affected_files": [f"tests/test_{index}.py" for index in range(file_count)],
        "proof_commands": [
            "PYTHONPATH=src python -m ruff check tests/test_0.py",
            "PYTHONPATH=src python -m pytest -q <targeted-tests>",
        ],
    }


def _patch_plan() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive.patch_plan.v1",
        "status": "review_required",
        "source_status": "needs_fix",
        "source_code": "UNKNOWN_REVIEW_REQUIRED",
        "safe_to_auto_fix": False,
        "dry_run_only": True,
        "requires_human_review": True,
        "affected_files": ["pyproject.toml"],
        "proof_commands": ["python -m pip install -r requirements-test.txt -e ."],
    }


def test_remediation_policy_approves_narrow_safe_fix() -> None:
    payload = adaptive_remediation_policy.evaluate_policy(
        adaptive_remediation_policy.default_policy(), _safe_plan()
    )

    assert payload["schema_version"] == "sdetkit.adaptive.remediation_policy.result.v1"
    assert payload["ok"] is True
    assert payload["recommendation"] == "APPROVE"
    assert payload["plan_kind"] == "safe_fix"
    assert payload["finding_count"] == 0


def test_remediation_policy_rejects_unsafe_policy_expansion() -> None:
    policy = {
        **adaptive_remediation_policy.default_policy(),
        "allowed_safe_fix_types": ["format_only", "review_required"],
        "allow_review_required_auto_fix": True,
    }

    payload = adaptive_remediation_policy.evaluate_policy(policy, _safe_plan())

    assert payload["ok"] is False
    assert payload["recommendation"] == "REJECT_POLICY"
    assert {row["code"] for row in payload["findings"]} >= {
        "POLICY_UNSAFE_FIX_TYPE_ALLOWED",
        "POLICY_REVIEW_REQUIRED_AUTO_FIX_ENABLED",
    }


def test_remediation_policy_rejects_unknown_auto_fix_even_if_policy_tries_to_allow_it() -> None:
    policy = adaptive_remediation_policy.default_policy()
    plan = {
        **_safe_plan(),
        "source_code": "UNKNOWN_REVIEW_REQUIRED",
        "fix_type": "format_only",
    }

    payload = adaptive_remediation_policy.evaluate_policy(policy, plan)

    assert payload["ok"] is False
    assert payload["recommendation"] == "REJECT_PLAN"
    assert payload["findings"][0]["code"] == "PLAN_SOURCE_CODE_BLOCKED_FOR_AUTO_FIX"


def test_remediation_policy_rejects_changed_file_scope_over_limit() -> None:
    policy = {**adaptive_remediation_policy.default_policy(), "max_changed_files": 1}

    payload = adaptive_remediation_policy.evaluate_policy(policy, _safe_plan(file_count=3))

    assert payload["ok"] is False
    assert payload["recommendation"] == "REJECT_PLAN"
    assert payload["findings"][0]["code"] == "PLAN_CHANGED_FILE_SCOPE_EXCEEDED"


def test_remediation_policy_accepts_review_only_patch_plan() -> None:
    payload = adaptive_remediation_policy.evaluate_policy(
        adaptive_remediation_policy.default_policy(), _patch_plan()
    )

    assert payload["ok"] is True
    assert payload["recommendation"] == "APPROVE"
    assert payload["plan_kind"] == "assisted_patch_plan"
    assert payload["safe_to_auto_fix"] is False


def test_remediation_policy_cli_and_top_level_passthrough(tmp_path: Path) -> None:
    policy = tmp_path / "policy.json"
    plan = tmp_path / "safe-plan.json"
    out = tmp_path / "result.json"
    policy.write_text(json.dumps(adaptive_remediation_policy.default_policy()), encoding="utf-8")
    plan.write_text(json.dumps(_safe_plan()), encoding="utf-8")

    rc = top_level_main(
        [
            "adaptive",
            "remediation-policy",
            "validate",
            str(plan),
            "--policy",
            str(policy),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["recommendation"] == "APPROVE"


def test_remediation_policy_template_writes_default(tmp_path: Path) -> None:
    out = tmp_path / "policy.json"

    rc = adaptive_remediation_policy.main(["template", "--format", "json", "--out", str(out)])

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.adaptive.remediation_policy.v1"
    assert payload["allow_review_required_auto_fix"] is False
