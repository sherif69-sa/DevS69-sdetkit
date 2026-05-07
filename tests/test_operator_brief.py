import json
import subprocess
import sys
from pathlib import Path

from sdetkit import operator_brief


def _diagnosis_payload():
    return {
        "schema_version": "sdetkit.adaptive.diagnosis.v1",
        "status": "needs_fix",
        "summary": "Primary issue: Failure needs human review.",
        "diagnoses": [
            {
                "code": "UNKNOWN_REVIEW_REQUIRED",
                "severity": "high",
                "confidence": "medium",
                "title": "Failure needs human review",
                "evidence": [
                    "candidate_scenarios=RELEASE_VERSION_CONFLICT,DOCS_BUILD_CONTRACT",
                    "candidate_calibration=RELEASE_VERSION_CONFLICT:promote_and_increase_risk:confidence_delta=2:risk_delta=12",
                ],
                "recommended_fix": [
                    "Check candidate RELEASE_VERSION_CONFLICT: Compare package version."
                ],
                "proof_commands": ["git tag --points-at HEAD"],
            }
        ],
        "fix_plan": [
            {
                "code": "UNKNOWN_REVIEW_REQUIRED",
                "title": "Failure needs human review",
                "safe_to_auto_fix": False,
            }
        ],
    }


def _learning_summary():
    return {
        "schema_version": "sdetkit.adaptive.learn.summary.v1",
        "calibration_summary": {
            "promote": 1,
            "demote": 0,
            "increase_risk": 1,
            "lower_confidence": 0,
        },
        "top_recurring_scenarios": [{"code": "RELEASE_VERSION_CONFLICT"}],
        "weakest_lanes": [{"lane": "release"}],
    }


def test_build_operator_brief_collects_decision_surfaces():
    payload = operator_brief.build_operator_brief(
        gate={"ok": False, "failed_steps": ["release-preflight"]},
        diagnosis=_diagnosis_payload(),
        learning_summary=_learning_summary(),
    )

    assert payload["schema_version"] == "sdetkit.operator_brief.v1"
    assert payload["ok"] is False
    assert payload["gate_result"]["status"] == "no_ship"
    assert payload["adaptive_diagnosis"]["candidate_scenarios"].startswith(
        "RELEASE_VERSION_CONFLICT"
    )
    assert payload["adaptive_diagnosis"]["first_proof_command"] == "git tag --points-at HEAD"
    assert payload["safe_fix_decision"]["safe_to_auto_fix"] is False
    assert "git tag --points-at HEAD" in payload["next_owner_action"]


def test_render_markdown_includes_operator_handoff_sections():
    payload = operator_brief.build_operator_brief(
        gate={"ok": True, "decision": "SHIP"},
        diagnosis=_diagnosis_payload(),
        learning_summary=_learning_summary(),
    )
    rendered = operator_brief.render_markdown(payload)

    assert "# SDETKit Operator Brief" in rendered
    assert "## Gate result" in rendered
    assert "## Adaptive diagnosis" in rendered
    assert "Candidate calibration" in rendered
    assert "## Safe-fix decision" in rendered
    assert "## Next owner action" in rendered


def test_render_pr_comment_green_run_has_no_fake_adaptive_block():
    payload = operator_brief.build_operator_brief(
        gate={"ok": True, "decision": "SHIP"},
        diagnosis={"status": "clear", "diagnoses": [], "fix_plan": []},
    )

    rendered = operator_brief.render_pr_comment(payload)

    assert "SDETKit release signal" in rendered
    assert "adaptive handoff" not in rendered
    assert "no adaptive remediation block" in rendered


def test_render_pr_comment_safe_mechanical_path_is_scoped():
    diagnosis = _diagnosis_payload()
    diagnosis["diagnoses"][0]["code"] = "PRE_COMMIT_FORMAT_DRIFT"
    diagnosis["diagnoses"][0]["title"] = "Formatter drift blocked pre-commit"
    diagnosis["fix_plan"][0] = {
        "code": "PRE_COMMIT_FORMAT_DRIFT",
        "title": "Formatter drift blocked pre-commit",
        "safe_to_auto_fix": True,
    }
    payload = operator_brief.build_operator_brief(
        gate={"ok": False, "failed_steps": ["format"]}, diagnosis=diagnosis
    )

    rendered = operator_brief.render_pr_comment(payload)

    assert "SDETKit adaptive handoff" in rendered
    assert "Scoped safe-fix path is available" in rendered
    assert "guardrails and proof artifacts" in rendered


def test_render_pr_comment_unknown_failure_is_review_first():
    payload = operator_brief.build_operator_brief(
        gate={"ok": False, "failed_steps": ["gate-fast"]},
        diagnosis=_diagnosis_payload(),
        learning_summary=_learning_summary(),
    )

    rendered = operator_brief.render_pr_comment(payload)

    assert "Review-first" in rendered
    assert "Candidate scenarios" in rendered
    assert "First proof" in rendered
    assert "git tag --points-at HEAD" in rendered


def test_operator_brief_cli_writes_markdown_and_json(tmp_path, capsys):
    gate_path = tmp_path / "gate.json"
    diagnosis_path = tmp_path / "diagnosis.json"
    learning_path = tmp_path / "learning.json"
    md_out = tmp_path / "operator-brief.md"
    json_out = tmp_path / "operator-brief.json"
    gate_path.write_text(json.dumps({"ok": False, "failed_steps": ["gate-fast"]}), encoding="utf-8")
    diagnosis_path.write_text(json.dumps(_diagnosis_payload()), encoding="utf-8")
    learning_path.write_text(json.dumps(_learning_summary()), encoding="utf-8")

    rc = operator_brief.main(
        [
            "--gate",
            str(gate_path),
            "--diagnosis",
            str(diagnosis_path),
            "--learning-summary",
            str(learning_path),
            "--out",
            str(md_out),
        ]
    )
    assert rc == 0
    assert "SDETKit Operator Brief" in md_out.read_text(encoding="utf-8")
    assert capsys.readouterr().out == ""

    rc = operator_brief.main(
        [
            "--gate",
            str(gate_path),
            "--diagnosis",
            str(diagnosis_path),
            "--format",
            "json",
            "--out",
            str(json_out),
        ]
    )
    assert rc == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["schema_version"] == (
        "sdetkit.operator_brief.v1"
    )

    comment_out = tmp_path / "operator-comment.md"
    rc = operator_brief.main(
        [
            "--gate",
            str(gate_path),
            "--diagnosis",
            str(diagnosis_path),
            "--format",
            "comment",
            "--out",
            str(comment_out),
        ]
    )
    assert rc == 0
    assert "SDETKit adaptive handoff" in comment_out.read_text(encoding="utf-8")


def test_sdetkit_adaptive_brief_subprocess(tmp_path: Path):
    gate_path = tmp_path / "gate.json"
    diagnosis_path = tmp_path / "diagnosis.json"
    out = tmp_path / "brief.md"
    gate_path.write_text(json.dumps({"ok": False, "failed_steps": ["gate-fast"]}), encoding="utf-8")
    diagnosis_path.write_text(json.dumps(_diagnosis_payload()), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "adaptive",
            "brief",
            "--gate",
            str(gate_path),
            "--diagnosis",
            str(diagnosis_path),
            "--out",
            str(out),
        ],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "SDETKit Operator Brief" in out.read_text(encoding="utf-8")
