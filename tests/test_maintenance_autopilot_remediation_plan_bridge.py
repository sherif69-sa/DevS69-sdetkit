from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sdetkit import adaptive_safe_remediation

BRIDGE_ONLY_MODE = "_".join(("pr", "quality", "safe", "bridge", "only"))


def _load_autopilot():
    path = Path("tools/maintenance_autopilot.py")
    spec = importlib.util.spec_from_file_location("maintenance_autopilot", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _formatting_plan(path: Path, *, affected_files: list[str] | None = None) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "sdetkit.remediation_plan.v1",
            "plans": [
                {
                    "diagnosis_id": "formatting-autopilot",
                    "failure_surface": "formatting",
                    "classification": "formatting_only",
                    "safe_to_auto_fix": True,
                    "allowed_strategy": "run_pre_commit",
                    "affected_files": affected_files or ["tests/test_example.py"],
                    "commands_to_run": ["python -m pre_commit run -a"],
                    "proof_commands": ["python -m pytest -q tests/test_example.py -o addopts="],
                    "requires_security_review": False,
                    "requires_release_validation": False,
                }
            ],
        },
    )


def test_autopilot_executes_approved_formatting_remediation_plan(
    tmp_path: Path, monkeypatch
) -> None:
    autopilot = _load_autopilot()
    remediation_plan = _formatting_plan(tmp_path / "remediation-plan.json")
    captured: dict[str, dict] = {}

    def fake_run_plan(plan, cwd):
        captured["plan"] = plan
        return {
            "schema_version": "sdetkit.adaptive_safe_remediation.v1",
            "ok": True,
            "safe_to_auto_fix": True,
            "fix_type": "format_only",
            "commands": [{"command": "python -m pre_commit run -a", "ok": True}],
        }

    def fake_commit(out_dir, plan, result):
        captured["commit_plan"] = plan
        captured["commit_result"] = result
        return {
            "ok": True,
            "attempted": True,
            "committed": True,
            "pushed": True,
            "commit_sha": "abc123",
            "reason": "pushed",
        }

    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fake_run_plan)
    monkeypatch.setattr(autopilot, "_commit_safe_fix_changes", fake_commit)

    out_dir = tmp_path / "autopilot"
    result = autopilot._write_remediation_execution_from_plan(out_dir, remediation_plan)

    assert result["attempted"] is True
    assert result["allowed"] is True
    assert result["pushed"] is True
    assert result["commit_sha"] == "abc123"
    assert captured["plan"]["safe_to_auto_fix"] is True
    assert captured["plan"]["fix_type"] == "format_only"
    assert captured["plan"]["requires_human_review"] is False
    assert captured["plan"]["affected_files"] == ["tests/test_example.py"]
    assert (out_dir / "remediation-execution.json").exists()
    assert (out_dir / "remediation-execution.md").exists()
    assert (out_dir / "remediation-commit-result.json").exists()
    assert (out_dir / "safe-fix-plan.json").exists()


def test_autopilot_refuses_mixed_review_first_remediation_plan(tmp_path: Path, monkeypatch) -> None:
    autopilot = _load_autopilot()
    remediation_plan = _write_json(
        tmp_path / "remediation-plan.json",
        {
            "schema_version": "sdetkit.remediation_plan.v1",
            "plans": [
                {
                    "diagnosis_id": "formatting-autopilot",
                    "failure_surface": "formatting",
                    "classification": "formatting_only",
                    "safe_to_auto_fix": True,
                    "allowed_strategy": "run_pre_commit",
                    "affected_files": ["tests/test_example.py"],
                },
                {
                    "diagnosis_id": "security-case",
                    "failure_surface": "security",
                    "classification": "security",
                    "safe_to_auto_fix": False,
                    "allowed_strategy": "review_first_security_review",
                    "affected_files": [],
                },
            ],
        },
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("review-first remediation plan must not execute")

    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fail_if_called)
    monkeypatch.setattr(autopilot, "_commit_safe_fix_changes", fail_if_called)

    out_dir = tmp_path / "autopilot"
    result = autopilot._write_remediation_execution_from_plan(out_dir, remediation_plan)

    assert result["attempted"] is False
    assert result["allowed"] is False
    assert "review-first" in result["refused_reason"]
    assert result["remaining_review_first_blockers"] == ["security-case"]
    assert (out_dir / "remediation-execution.json").exists()
    assert (out_dir / "remediation-commit-result.json").exists()


def test_autopilot_refuses_unsafe_remediation_plan_files(tmp_path: Path, monkeypatch) -> None:
    autopilot = _load_autopilot()
    remediation_plan = _formatting_plan(
        tmp_path / "remediation-plan.json",
        affected_files=["../outside.py"],
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("unsafe affected files must not execute")

    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fail_if_called)
    monkeypatch.setattr(autopilot, "_commit_safe_fix_changes", fail_if_called)

    result = autopilot._write_remediation_execution_from_plan(tmp_path / "out", remediation_plan)

    assert result["attempted"] is False
    assert result["allowed"] is False
    assert "unsafe affected files" in result["refused_reason"]


def test_autopilot_refuses_non_allowlisted_remediation_strategy(
    tmp_path: Path, monkeypatch
) -> None:
    autopilot = _load_autopilot()
    remediation_plan = _write_json(
        tmp_path / "remediation-plan.json",
        {
            "schema_version": "sdetkit.remediation_plan.v1",
            "plans": [
                {
                    "diagnosis_id": "test-case",
                    "failure_surface": "test",
                    "classification": "formatting_only",
                    "safe_to_auto_fix": True,
                    "allowed_strategy": "fix_tests",
                    "affected_files": ["tests/test_example.py"],
                }
            ],
        },
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("non-allowlisted strategy must not execute")

    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fail_if_called)
    monkeypatch.setattr(autopilot, "_commit_safe_fix_changes", fail_if_called)

    result = autopilot._write_remediation_execution_from_plan(tmp_path / "out", remediation_plan)

    assert result["attempted"] is False
    assert result["allowed"] is False
    assert "not allowlisted" in result["refused_reason"]


def test_autopilot_remediation_plan_bridge_only_mode_skips_baseline(
    tmp_path: Path, monkeypatch
) -> None:
    autopilot = _load_autopilot()
    remediation_plan = _formatting_plan(tmp_path / "remediation-plan.json")

    def fail_if_baseline_runs(*args, **kwargs):
        raise AssertionError("bridge-only mode must not run the full maintenance baseline")

    def fake_run_plan(plan, cwd):
        return {
            "schema_version": "sdetkit.adaptive_safe_remediation.v1",
            "ok": True,
            "safe_to_auto_fix": True,
            "fix_type": "format_only",
            "commands": [{"command": "python -m pre_commit run -a", "ok": True}],
        }

    def fake_commit(out_dir, plan, result):
        return {"ok": False, "attempted": False, "pushed": False, "reason": "commit disabled"}

    monkeypatch.setattr(autopilot, "_run", fail_if_baseline_runs)
    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fake_run_plan)
    monkeypatch.setattr(autopilot, "_commit_safe_fix_changes", fake_commit)

    rc = autopilot.main(
        [
            "--owner",
            "sherif69-sa",
            "--repo",
            "DevS69-sdetkit",
            "--remediation-plan-json",
            str(remediation_plan),
            "--pr-quality-safe-bridge-only",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )

    assert rc == 0
    report = json.loads((tmp_path / "out" / "autopilot-report.json").read_text())
    assert report["mode"] == BRIDGE_ONLY_MODE
    assert report["steps"]["remediation_plan_execution"]["attempted"] is True
    assert "baseline_pre_commit" not in report["steps"]
