from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_patch_plan
from sdetkit.cli import main as top_level_main


def _diagnosis(
    code: str = "UNKNOWN_REVIEW_REQUIRED", confidence: str = "medium"
) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive.diagnosis.v1",
        "status": "needs_fix",
        "confidence": confidence,
        "diagnosis_count": 1,
        "diagnoses": [
            {
                "code": code,
                "title": "Failure needs human review",
                "severity": "high",
                "confidence": confidence,
                "evidence": [
                    "candidate_scenarios=PACKAGE_INSTALL_FAILURE,CACHE_ARTIFACT_POISONING"
                ],
                "proof_commands": ["python -m pip install -r requirements-test.txt -e ."],
                "affected_files": ["pyproject.toml"],
            }
        ],
    }


def test_assisted_patch_plan_is_review_only_for_unknown_failures() -> None:
    plan = adaptive_patch_plan.build_patch_plan(_diagnosis())

    assert plan["schema_version"] == "sdetkit.adaptive.patch_plan.v1"
    assert plan["status"] == "review_required"
    assert plan["safe_to_auto_fix"] is False
    assert plan["dry_run_only"] is True
    assert plan["requires_human_review"] is True
    assert plan["guardrails"]["automation_mutation_allowed"] is False
    assert plan["guardrails"]["deterministic_reproduction_available"] is True
    assert plan["guardrails"]["scenario_confidence_threshold_met"] is True
    assert plan["candidate_scenarios"] == [
        "PACKAGE_INSTALL_FAILURE",
        "CACHE_ARTIFACT_POISONING",
    ]
    assert all(step["mutation_allowed"] is False for step in plan["patch_steps"])
    assert plan["patch_steps"][0]["action"] == "reproduce"


def test_assisted_patch_plan_defers_safe_mechanical_diagnoses() -> None:
    plan = adaptive_patch_plan.build_patch_plan(_diagnosis("PRE_COMMIT_FORMAT_DRIFT", "high"))

    assert plan["status"] == "not_applicable"
    assert plan["safe_to_auto_fix"] is False
    assert plan["patch_steps"] == []
    assert "safe mechanical diagnosis" in plan["reason"]


def test_patch_plan_cli_writes_markdown(tmp_path: Path) -> None:
    diagnosis = tmp_path / "diagnosis.json"
    out = tmp_path / "patch-plan.md"
    diagnosis.write_text(json.dumps(_diagnosis()), encoding="utf-8")

    rc = adaptive_patch_plan.main([str(diagnosis), "--format", "md", "--out", str(out)])

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "# Adaptive assisted patch plan" in text
    assert "Mutation allowed: `false`" in text
    assert "python -m pip install" in text


def test_top_level_cli_adaptive_patch_plan_passthrough(tmp_path: Path) -> None:
    diagnosis = tmp_path / "diagnosis.json"
    out = tmp_path / "patch-plan.json"
    diagnosis.write_text(json.dumps(_diagnosis()), encoding="utf-8")

    rc = top_level_main(
        ["adaptive", "patch-plan", str(diagnosis), "--format", "json", "--out", str(out)]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "review_required"
    assert payload["guardrails"]["post_fix_proof_required"] is True
