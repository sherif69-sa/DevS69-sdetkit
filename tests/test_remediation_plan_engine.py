from __future__ import annotations

import json
from pathlib import Path

from sdetkit.diagnostic_vector_engine import (
    AFFECTED_FILES,
    DIAGNOSIS_ID,
    FAILURE_SURFACE,
    HISTORY_CONTEXT,
    PROOF_COMMANDS,
    RECOMMENDED_NEXT_ACTION,
    REVIEW_FIRST,
    REVIEW_FIRST_REASON,
    SAFE_FIX_CANDIDATE,
)
from sdetkit.remediation_plan_engine import (
    ALLOWED_STRATEGY,
    BLOCKED_REASON,
    CLASSIFICATION,
    COMMANDS_TO_RUN,
    HUMAN_REVIEW_ACTION,
    REQUIRES_FRESH_LOGS,
    REQUIRES_RELEASE_VALIDATION,
    REQUIRES_SECURITY_REVIEW,
    RISK_LEVEL,
    SAFE_TO_AUTO_FIX,
    STRATEGY_RUN_PRE_COMMIT,
    build_remediation_plan,
    main,
)


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_remediation_plan_allows_only_formatting_candidate() -> None:
    diagnostic_vector = {
        "diagnoses": [
            {
                DIAGNOSIS_ID: "formatting-autopilot",
                FAILURE_SURFACE: "formatting",
                SAFE_FIX_CANDIDATE: True,
                REVIEW_FIRST: False,
                RECOMMENDED_NEXT_ACTION: STRATEGY_RUN_PRE_COMMIT,
                AFFECTED_FILES: ["src/sdetkit/example.py"],
                PROOF_COMMANDS: ["python -m pre_commit run -a"],
                HISTORY_CONTEXT: "recurring",
                "confidence": "high",
            }
        ]
    }

    payload = build_remediation_plan(diagnostic_vector)
    plan = payload["plans"][0]

    assert payload["summary"]["executable_plan_count"] == 1
    assert plan[CLASSIFICATION] == "formatting_only"
    assert plan[SAFE_TO_AUTO_FIX] is True
    assert plan[ALLOWED_STRATEGY] == STRATEGY_RUN_PRE_COMMIT
    assert plan[COMMANDS_TO_RUN] == ["python -m pre_commit run -a"]
    assert plan[BLOCKED_REASON] == ""
    assert plan[RISK_LEVEL] == "low"


def test_remediation_plan_keeps_type_runtime_release_dependency_security_review_first() -> None:
    diagnostic_vector = {
        "diagnoses": [
            {
                DIAGNOSIS_ID: "type-case",
                FAILURE_SURFACE: "type_contract",
                SAFE_FIX_CANDIDATE: False,
                REVIEW_FIRST: True,
                REVIEW_FIRST_REASON: "type failures remain review-first",
            },
            {
                DIAGNOSIS_ID: "runtime-case",
                FAILURE_SURFACE: "runtime",
                SAFE_FIX_CANDIDATE: False,
                REVIEW_FIRST: True,
            },
            {
                DIAGNOSIS_ID: "release-case",
                FAILURE_SURFACE: "release",
                SAFE_FIX_CANDIDATE: False,
                REVIEW_FIRST: True,
            },
            {
                DIAGNOSIS_ID: "dependency-case",
                FAILURE_SURFACE: "dependency",
                SAFE_FIX_CANDIDATE: False,
                REVIEW_FIRST: True,
            },
            {
                DIAGNOSIS_ID: "security-case",
                FAILURE_SURFACE: "security",
                SAFE_FIX_CANDIDATE: False,
                REVIEW_FIRST: True,
            },
        ]
    }

    payload = build_remediation_plan(diagnostic_vector)
    plans = {plan[DIAGNOSIS_ID]: plan for plan in payload["plans"]}

    assert payload["summary"]["executable_plan_count"] == 0
    assert payload["summary"]["review_first_plan_count"] == 5
    assert plans["type-case"][SAFE_TO_AUTO_FIX] is False
    assert plans["type-case"][CLASSIFICATION] == "type_contract"
    assert plans["runtime-case"][REQUIRES_FRESH_LOGS] is True
    assert plans["release-case"][REQUIRES_RELEASE_VALIDATION] is True
    assert plans["dependency-case"][ALLOWED_STRATEGY] == "review_first_dependency_alignment"
    assert plans["security-case"][REQUIRES_SECURITY_REVIEW] is True
    assert plans["security-case"][ALLOWED_STRATEGY] == "review_first_security_review"


def test_remediation_plan_unknown_collects_logs_and_blocks_mutation() -> None:
    diagnostic_vector = {
        "diagnoses": [
            {
                DIAGNOSIS_ID: "unknown-fast-ci",
                FAILURE_SURFACE: "unknown",
                SAFE_FIX_CANDIDATE: False,
                REVIEW_FIRST: True,
                AFFECTED_FILES: [],
            }
        ]
    }

    plan = build_remediation_plan(diagnostic_vector)["plans"][0]

    assert plan[CLASSIFICATION] == "unknown"
    assert plan[SAFE_TO_AUTO_FIX] is False
    assert plan[ALLOWED_STRATEGY] == "collect_logs_and_classify"
    assert plan[COMMANDS_TO_RUN] == []
    assert plan[REQUIRES_FRESH_LOGS] is True
    assert "collect failed check logs" in plan[HUMAN_REVIEW_ACTION]


def test_remediation_plan_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    vector_path = _write(
        tmp_path / "diagnostic-vector.json",
        {
            "diagnoses": [
                {
                    DIAGNOSIS_ID: "release-case",
                    FAILURE_SURFACE: "release",
                    SAFE_FIX_CANDIDATE: False,
                    REVIEW_FIRST: True,
                    PROOF_COMMANDS: [
                        "PYTHONPATH=src python -m build",
                        "PYTHONPATH=src python -m twine check dist/*",
                    ],
                }
            ]
        },
    )
    out_dir = tmp_path / "remediation"

    rc = main(
        [
            "--diagnostic-vector",
            str(vector_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads((out_dir / "remediation-plan.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "remediation-plan.md").read_text(encoding="utf-8")
    assert payload["summary"]["plan_count"] == 1
    assert payload["plans"][0][REQUIRES_RELEASE_VALIDATION] is True
    assert "Remediation Plan" in markdown
    assert "remediation_plan_json" in stdout
