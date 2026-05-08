from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_fix_audit
from sdetkit.cli import main as top_level_main


def _patch_plan() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive.patch_plan.v1",
        "status": "review_required",
        "source_status": "needs_fix",
        "source_code": "UNKNOWN_REVIEW_REQUIRED",
        "safe_to_auto_fix": False,
        "dry_run_only": True,
        "requires_human_review": True,
        "reason": "Review-only patch plan.",
        "guardrails": {
            "automation_mutation_allowed": False,
            "post_fix_proof_required": True,
        },
        "affected_files": ["pyproject.toml"],
        "proof_commands": ["python -m pip install -r requirements-test.txt -e ."],
        "rollback_notes": ["Revert reviewed changes if proof fails."],
    }


def _safe_fix_plan() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "source_status": "needs_fix",
        "source_code": "PRE_COMMIT_FORMAT_DRIFT",
        "safe_to_auto_fix": True,
        "requires_human_review": False,
        "fix_type": "format_only",
        "reason": "Formatter drift is safe to plan.",
        "affected_files": ["tests/test_widget.py"],
        "proof_commands": ["PYTHONPATH=src python -m ruff format --check tests/test_widget.py"],
    }


def test_fix_audit_record_captures_patch_plan_guardrails() -> None:
    record = adaptive_fix_audit.build_audit_record(
        _patch_plan(), source_path="build/patch-plan.json", outcome="planned", note="triage"
    )

    assert record["schema_version"] == "sdetkit.adaptive.fix_audit.v1"
    assert record["plan_kind"] == "assisted_patch_plan"
    assert record["source_code"] == "UNKNOWN_REVIEW_REQUIRED"
    assert record["safe_to_auto_fix"] is False
    assert record["requires_human_review"] is True
    assert record["dry_run_only"] is True
    assert record["guardrails"]["automation_mutation_allowed"] is False
    assert record["proof_commands"] == ["python -m pip install -r requirements-test.txt -e ."]
    assert record["rollback_notes"] == ["Revert reviewed changes if proof fails."]


def test_fix_audit_record_and_summary_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "audit.jsonl"
    patch_path = tmp_path / "patch-plan.json"
    safe_path = tmp_path / "safe-fix.json"
    patch_path.write_text(json.dumps(_patch_plan()), encoding="utf-8")
    safe_path.write_text(json.dumps(_safe_fix_plan()), encoding="utf-8")

    patch_record = adaptive_fix_audit.record_from_file(patch_path, db, outcome="planned")
    safe_record = adaptive_fix_audit.record_from_file(safe_path, db, outcome="proof_passed")
    summary = adaptive_fix_audit.summarize_records(adaptive_fix_audit.read_records(db))

    assert patch_record["plan_kind"] == "assisted_patch_plan"
    assert safe_record["plan_kind"] == "safe_fix"
    assert summary["record_count"] == 2
    assert summary["outcomes"] == {"planned": 1, "proof_passed": 1}
    assert summary["plan_kinds"] == {"assisted_patch_plan": 1, "safe_fix": 1}
    assert summary["unsafe_mutation_attempt_count"] == 0
    assert summary["ok"] is True


def test_fix_audit_cli_and_top_level_passthrough(tmp_path: Path) -> None:
    db = tmp_path / "audit.jsonl"
    plan = tmp_path / "patch-plan.json"
    plan.write_text(json.dumps(_patch_plan()), encoding="utf-8")

    rc = top_level_main(
        [
            "adaptive",
            "fix-audit",
            "record",
            str(plan),
            "--db",
            str(db),
            "--outcome",
            "planned",
            "--format",
            "json",
        ]
    )
    assert rc == 0

    rc = top_level_main(["adaptive", "fix-audit", "summarize", "--db", str(db), "--format", "json"])
    assert rc == 0
    summary = adaptive_fix_audit.summarize_records(adaptive_fix_audit.read_records(db))
    assert summary["record_count"] == 1
    assert summary["top_source_codes"][0] == {"code": "UNKNOWN_REVIEW_REQUIRED", "count": 1}


def test_fix_audit_summary_flags_missing_post_fix_proof(tmp_path: Path) -> None:
    db = tmp_path / "audit.jsonl"
    plan = tmp_path / "patch-plan.json"
    plan.write_text(json.dumps(_patch_plan()), encoding="utf-8")
    adaptive_fix_audit.record_from_file(plan, db, outcome="planned")

    summary = adaptive_fix_audit.summarize_records(adaptive_fix_audit.read_records(db))

    assert summary["recommendation"] == "SHIP_WITH_CONTROLS"
    assert summary["missing_proof_count"] == 1
    assert summary["proof_failed_count"] == 0
    assert summary["next_owner_action"].startswith("Collect post-fix proof")


def test_fix_audit_summary_clears_missing_proof_after_terminal_outcome(tmp_path: Path) -> None:
    db = tmp_path / "audit.jsonl"
    plan = tmp_path / "patch-plan.json"
    plan.write_text(json.dumps(_patch_plan()), encoding="utf-8")
    adaptive_fix_audit.record_from_file(plan, db, outcome="planned")
    adaptive_fix_audit.record_from_file(plan, db, outcome="proof_passed")

    summary = adaptive_fix_audit.summarize_records(adaptive_fix_audit.read_records(db))

    assert summary["recommendation"] == "SHIP"
    assert summary["missing_proof_count"] == 0
    assert summary["proof_failed_count"] == 0
    assert summary["ok"] is True


def test_fix_audit_summary_blocks_release_on_failed_proof(tmp_path: Path) -> None:
    db = tmp_path / "audit.jsonl"
    plan = tmp_path / "patch-plan.json"
    plan.write_text(json.dumps(_patch_plan()), encoding="utf-8")
    adaptive_fix_audit.record_from_file(plan, db, outcome="planned")
    adaptive_fix_audit.record_from_file(plan, db, outcome="proof_failed")

    summary = adaptive_fix_audit.summarize_records(adaptive_fix_audit.read_records(db))

    assert summary["recommendation"] == "NO_SHIP"
    assert summary["missing_proof_count"] == 0
    assert summary["proof_failed_count"] == 1
    assert summary["ok"] is False
    assert summary["next_owner_action"].startswith("Block release signoff")
