from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sdetkit import auto_fix

RUFF_LINT_LOG = """
ruff check..............................................................Failed
tests/test_foo.py:2:21: F401 [*] `pathlib.Path` imported but unused
help: Remove unused import: `pathlib.Path`
Found 1 error.
"""

FORMAT_DRIFT_LOG = "ruff format failed\n1 file reformatted\n"

ZERO_DIVISION_LOG = "ZeroDivisionError: division by zero in src/calc.py line 4\n"


def test_diagnose_evidence_clean_tree(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(root=tmp_path)
    assert evidence["clean"] is True
    assert evidence["safe_to_auto_fix"] is True
    assert evidence["classification"] == "CLEAN_TREE"


def test_diagnose_evidence_format_drift(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(FORMAT_DRIFT_LOG, root=tmp_path)
    assert evidence["classification"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert evidence["safe_to_auto_fix"] is True


def test_diagnose_evidence_ruff_lint(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(RUFF_LINT_LOG, root=tmp_path)
    assert evidence["classification"] == "RUFF_FIXABLE_LINT"
    assert evidence["safe_to_auto_fix"] is True


def test_diagnose_evidence_logic_error_blocks_auto_fix(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(ZERO_DIVISION_LOG, root=tmp_path)
    assert evidence["safe_to_auto_fix"] is False
    assert evidence["requires_human_review"] is True


def test_plan_remediation_clean_tree(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(root=tmp_path)
    plan = auto_fix.plan_remediation(evidence, root=tmp_path)
    assert plan["clean"] is True
    assert plan["safe_to_auto_fix"] is True
    assert plan["commands"] == []


def test_plan_remediation_format_drift(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(FORMAT_DRIFT_LOG, root=tmp_path)
    plan = auto_fix.plan_remediation(evidence, root=tmp_path)
    assert plan["safe_to_auto_fix"] is True
    assert plan["fix_type"] == "format_only"
    assert len(plan["commands"]) == 1
    assert "format" in plan["commands"][0]


def test_plan_remediation_ruff_fixable_lint(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(RUFF_LINT_LOG, root=tmp_path)
    plan = auto_fix.plan_remediation(evidence, root=tmp_path)
    assert plan["safe_to_auto_fix"] is True
    assert plan["fix_type"] == "ruff_fixable_lint"
    assert len(plan["commands"]) == 2
    assert "--fix" in plan["commands"][0]


def test_plan_remediation_ineligible(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(ZERO_DIVISION_LOG, root=tmp_path)
    plan = auto_fix.plan_remediation(evidence, root=tmp_path)
    assert plan["safe_to_auto_fix"] is False
    assert plan["requires_human_review"] is True
    assert plan["commands"] == []


def test_execute_safe_fix_blocked_when_not_eligible(tmp_path: Path) -> None:
    plan = {
        "safe_to_auto_fix": False,
        "classification": "ZERO_DIVISION_ERROR",
        "reason": "manual review required",
        "commands": [["python", "-m", "ruff", "format", "."]],
        "proof_commands": [],
    }
    outcome = auto_fix.execute_safe_fix(plan, root=tmp_path)
    assert outcome["ok"] is False
    assert outcome["applied"] is False
    assert outcome["requires_human_review"] is True


def test_execute_safe_fix_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["cmd"], 0, stdout="reformatted", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    plan = {
        "safe_to_auto_fix": True,
        "classification": "PRE_COMMIT_FORMAT_DRIFT",
        "commands": [["python", "-m", "ruff", "format", "."]],
        "proof_commands": [["python", "-m", "ruff", "format", "--check", "."]],
    }
    outcome = auto_fix.execute_safe_fix(plan, root=tmp_path)
    assert outcome["ok"] is True
    assert outcome["applied"] is True
    assert outcome["proof_passed"] is True


def test_render_markdown_clean_and_blocked() -> None:
    clean_res = {"clean": True}
    assert "CLEAN" in auto_fix.render_markdown(clean_res)

    blocked_res = {
        "clean": False,
        "safe_to_auto_fix": False,
        "classification": "ZERO_DIVISION_ERROR",
        "reason": "Logic error requires developer review.",
    }
    blocked_md = auto_fix.render_markdown(blocked_res)
    assert "BLOCKED" in blocked_md
    assert "ZERO_DIVISION_ERROR" in blocked_md


def test_render_markdown_preview() -> None:
    payload = {
        "safe_to_auto_fix": True,
        "classification": "PRE_COMMIT_FORMAT_DRIFT",
        "fix_type": "format_only",
        "reason": "Safe format drift",
        "commands": [["python", "-m", "ruff", "format", "."]],
        "proof_commands": [["python", "-m", "ruff", "format", "--check", "."]],
    }
    md = auto_fix.render_markdown(payload, dry_run=True)
    assert "PREVIEW (PRE_COMMIT_FORMAT_DRIFT)" in md
    assert "Planned fix commands" in md


def test_cli_main_dry_run_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = auto_fix.main(
        [
            "--repo-root",
            str(tmp_path),
            "--text",
            FORMAT_DRIFT_LOG,
            "--dry-run",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["classification"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert data["safe_to_auto_fix"] is True
    assert data["applied"] is False


def test_cli_main_with_out_file(tmp_path: Path) -> None:
    out_file = tmp_path / "result.json"
    rc = auto_fix.main(
        [
            "--repo-root",
            str(tmp_path),
            "--text",
            FORMAT_DRIFT_LOG,
            "--out",
            str(out_file),
        ]
    )
    assert rc == 0
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["safe_to_auto_fix"] is True


def test_cli_main_blocked_error_returns_one(tmp_path: Path) -> None:
    rc = auto_fix.main(
        [
            "--repo-root",
            str(tmp_path),
            "--text",
            ZERO_DIVISION_LOG,
        ]
    )
    assert rc == 1


def test_plan_remediation_with_rules(tmp_path: Path) -> None:
    evidence = auto_fix.diagnose_evidence(RUFF_LINT_LOG, root=tmp_path)

    plan_fmt = auto_fix.plan_remediation(evidence, root=tmp_path, rules=["format"])
    assert plan_fmt["safe_to_auto_fix"] is True
    assert any("format" in cmd for cmd in plan_fmt["commands"])
    assert not any("--fix" in cmd for cmd in plan_fmt["commands"])

    plan_imp = auto_fix.plan_remediation(evidence, root=tmp_path, rules=["imports"])
    assert plan_imp["safe_to_auto_fix"] is True
    assert any("--select" in cmd and "I" in cmd for cmd in plan_imp["commands"])

    plan_uimp = auto_fix.plan_remediation(evidence, root=tmp_path, rules=["unused_imports"])
    assert plan_uimp["safe_to_auto_fix"] is True
    assert any("--select" in cmd and "F401" in cmd for cmd in plan_uimp["commands"])

    plan_ws = auto_fix.plan_remediation(evidence, root=tmp_path, rules=["whitespace"])
    assert plan_ws["safe_to_auto_fix"] is True
    assert plan_ws["fix_whitespace"] is True


def test_execute_safe_fix_whitespace_repair(tmp_path: Path) -> None:
    test_file = tmp_path / "hello.py"
    test_file.write_text("x = 1   \ny = 2  ", encoding="utf-8")

    plan = {
        "safe_to_auto_fix": True,
        "classification": "WHITESPACE_DRIFT",
        "commands": [],
        "proof_commands": [],
        "affected_files": [str(test_file)],
        "fix_whitespace": True,
    }
    outcome = auto_fix.execute_safe_fix(plan, root=tmp_path)
    assert outcome["ok"] is True
    assert outcome["applied"] is True
    assert test_file.read_text(encoding="utf-8") == "x = 1\ny = 2\n"


def test_execute_safe_fix_syntax_preservation_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    py_file = tmp_path / "sample.py"
    original_code = "def foo() -> int:\n    return 42\n"
    py_file.write_text(original_code, encoding="utf-8")

    def corrupt_file(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        py_file.write_text("def foo() -> int:\n    invalid syntax (((\n", encoding="utf-8")
        return subprocess.CompletedProcess(["dummy"], 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", corrupt_file)

    plan = {
        "safe_to_auto_fix": True,
        "classification": "PRE_COMMIT_FORMAT_DRIFT",
        "commands": [["dummy", "fix"]],
        "proof_commands": [],
        "affected_files": [str(py_file)],
    }
    outcome = auto_fix.execute_safe_fix(plan, root=tmp_path)
    assert outcome["ok"] is False
    assert outcome["applied"] is False
    assert outcome["syntax_error"] is True
    assert py_file.read_text(encoding="utf-8") == original_code


def test_execute_safe_fix_diff_preview(tmp_path: Path) -> None:
    test_file = tmp_path / "mod.py"
    test_file.write_text("a = 1   \n", encoding="utf-8")

    plan = {
        "safe_to_auto_fix": True,
        "classification": "WHITESPACE_DRIFT",
        "commands": [],
        "proof_commands": [],
        "affected_files": [str(test_file)],
        "fix_whitespace": True,
    }
    outcome = auto_fix.execute_safe_fix(plan, root=tmp_path, dry_run=True, include_diff=True)
    assert outcome["ok"] is True
    assert outcome["applied"] is False
    assert outcome["dry_run"] is True
    assert "diff" in outcome
    assert "-a = 1" in outcome["diff"]
    assert "+a = 1" in outcome["diff"]
    assert test_file.read_text(encoding="utf-8") == "a = 1   \n"


def test_cli_main_rules_and_diff(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    test_file = tmp_path / "target.py"
    test_file.write_text("var = 100   \n", encoding="utf-8")

    rc = auto_fix.main(
        [
            "--repo-root",
            str(tmp_path),
            "--rules",
            "whitespace",
            "--preview",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["safe_to_auto_fix"] is True
    assert data["applied"] is False
    assert "diff" in data
