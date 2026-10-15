"""The repo-audit composite action installs sdetkit, not the repository it audits.

It used to run `pip install -e "$GITHUB_WORKSPACE"` whenever the workspace had a
pyproject.toml, which in any other Python repository installed that project instead of
sdetkit, so the `sdetkit repo audit` that followed was not found. It also checked the
repository out a second time and referenced actions by moving tags.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION = yaml.safe_load(
    (ROOT / ".github/actions/repo-audit/action.yml").read_text(encoding="utf-8")
)
STEPS = {step["name"]: step for step in ACTION["runs"]["steps"]}
EXPRESSION = re.compile(r"\$\{\{\s*(.+?)\s*\}\}")


def test_every_action_is_pinned_and_none_checks_out_again() -> None:
    uses = [step["uses"] for step in ACTION["runs"]["steps"] if "uses" in step]

    assert uses and all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", ref) for ref in uses), uses
    assert not any(ref.startswith("actions/checkout@") for ref in uses)


def test_sdetkit_comes_from_the_action_not_the_workspace() -> None:
    install = STEPS["Install sdetkit"]["run"]

    assert '"$GITHUB_ACTION_PATH/../../.."' in install
    assert "GITHUB_WORKSPACE" not in install
    assert "-e " not in install
    assert (ROOT / ".github/actions/repo-audit/../../../pyproject.toml").resolve() == (
        ROOT / "pyproject.toml"
    )


def test_scripts_read_inputs_only_through_the_environment() -> None:
    declared = set(ACTION["inputs"])
    for step in ACTION["runs"]["steps"]:
        assert "${{" not in step.get("run", ""), step["name"]
        for value in (step.get("env") or {}).values():
            for expression in EXPRESSION.findall(str(value)):
                if expression.startswith("inputs."):
                    assert expression.removeprefix("inputs.") in declared


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_the_audit_and_summary_steps_run_in_another_python_project(tmp_path: Path) -> None:
    repo = tmp_path / "adopter"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "adopter-app"\nversion = "0.1.0"\n')
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    summary = tmp_path / "summary.md"
    env = {
        **os.environ,
        "SDETKIT_PYTHON": sys.executable,
        "GITHUB_STEP_SUMMARY": str(summary),
        "AUDIT_PATH": ".",
        "AUDIT_PROFILE": "default",
        "AUDIT_FAIL_ON": "none",
        "AUDIT_SARIF_PATH": "sdetkit-audit.sarif.json",
        "AUDIT_OUTPUT_JSON": "true",
        "AUDIT_JSON_PATH": "sdetkit-audit.json",
        "AUDIT_UPLOAD_SARIF": "false",
        "AUDIT_UPLOAD_JSON": "true",
        "AUDIT_JSON_ARTIFACT_NAME": "sdetkit-audit-json",
    }

    for name in ("Run sdetkit repo audit", "Write step summary"):
        proc = subprocess.run(
            ["bash", "-c", STEPS[name]["run"]], cwd=repo, env=env, capture_output=True, text=True
        )
        assert proc.returncode == 0, f"{name}: {proc.stderr}"

    report = json.loads((repo / "sdetkit-audit.json").read_text(encoding="utf-8"))
    assert report["summary"]["findings"] == len(report["findings"]) > 0
    assert json.loads((repo / "sdetkit-audit.sarif.json").read_text(encoding="utf-8"))["runs"]
    text = summary.read_text(encoding="utf-8")
    assert text.startswith("## sdetkit repo audit\n")
    assert f"- Findings: {report['summary']['findings']}" in text
    assert "- SARIF upload disabled." in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_a_failing_audit_still_writes_the_summary(tmp_path: Path) -> None:
    """The summary step runs after a failed audit (`always()`) and reports its findings."""

    assert STEPS["Write step summary"]["if"].startswith("${{ always() &&")
    assert STEPS["Upload SARIF"]["if"].startswith("${{ always() &&")
