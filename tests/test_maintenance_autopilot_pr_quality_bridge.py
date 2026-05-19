from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sdetkit import adaptive_safe_remediation


def _load_autopilot():
    path = Path("tools/maintenance_autopilot.py")
    spec = importlib.util.spec_from_file_location("maintenance_autopilot", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIDGE_ONLY_MODE = "_".join(("pr", "quality", "safe", "bridge", "only"))


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_autopilot_bridges_pr_quality_safe_remediation_to_existing_commit_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    autopilot = _load_autopilot()
    check_intelligence = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "failed_checks": [
                {
                    "name": "autopilot",
                    "safe_to_auto_fix": True,
                    "diagnosis": {"code": "PRE_COMMIT_FORMAT_DRIFT"},
                    "first_failure": {
                        "line": "- files were modified by this hook",
                        "tool": "pre_commit",
                        "kind": "format_drift",
                    },
                    "safe_remediation": {
                        "schema_version": "sdetkit.safe_remediation_eligibility.v1",
                        "safe_to_auto_fix": True,
                        "strategy": "run_pre_commit",
                        "category": "formatting_only",
                        "affected_files": ["tests/test_example.py"],
                        "proof_commands": ["python -m pre_commit run -a"],
                    },
                }
            ]
        },
    )

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
        return {"ok": True, "attempted": True, "pushed": True, "reason": "pushed"}

    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fake_run_plan)
    monkeypatch.setattr(autopilot, "_commit_safe_fix_changes", fake_commit)

    result = autopilot._write_safe_fix_artifacts_from_check_intelligence(
        tmp_path,
        check_intelligence,
    )

    assert result["attempted"] is True
    assert result["remediation_ok"] is True
    assert result["commit_pushed"] is True
    assert captured["plan"]["safe_to_auto_fix"] is True
    assert captured["plan"]["fix_type"] == "format_only"
    assert captured["plan"]["requires_human_review"] is False
    assert captured["plan"]["commands"] == ["python -m pre_commit run -a"]
    assert captured["plan"]["affected_files"] == ["tests/test_example.py"]
    assert (tmp_path / "safe-fix-plan.json").exists()
    assert (tmp_path / "pr-quality-safe-remediation-bridge.json").exists()


def test_autopilot_bridge_refuses_mixed_review_first_failures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    autopilot = _load_autopilot()
    check_intelligence = _write_json(
        tmp_path / "check-intelligence.json",
        {
            "failed_checks": [
                {
                    "name": "autopilot",
                    "safe_to_auto_fix": True,
                    "diagnosis": {"code": "PRE_COMMIT_FORMAT_DRIFT"},
                    "safe_remediation": {
                        "schema_version": "sdetkit.safe_remediation_eligibility.v1",
                        "safe_to_auto_fix": True,
                        "strategy": "run_pre_commit",
                        "category": "formatting_only",
                        "affected_files": ["tests/test_example.py"],
                    },
                },
                {
                    "name": "ci",
                    "safe_to_auto_fix": False,
                    "diagnosis": {"code": "MYPY_TYPE_CONTRACT_DRIFT"},
                    "safe_remediation": {
                        "schema_version": "sdetkit.safe_remediation_eligibility.v1",
                        "safe_to_auto_fix": False,
                        "strategy": "review_first",
                        "category": "review_first",
                    },
                },
            ]
        },
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("mixed review-first failures must not remediate")

    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fail_if_called)
    monkeypatch.setattr(autopilot, "_commit_safe_fix_changes", fail_if_called)

    result = autopilot._write_safe_fix_artifacts_from_check_intelligence(
        tmp_path,
        check_intelligence,
    )

    assert result["attempted"] is False
    assert result["ok"] is False
    assert "review-first" in result["reason"]
    assert result["failed_check_count"] == 2
    assert result["eligible_plan_count"] == 1

def test_autopilot_bridge_only_mode_skips_full_baseline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    autopilot = _load_autopilot()
    check_intelligence = _write_json(tmp_path / "check-intelligence.json", {"failed_checks": []})

    def fail_if_baseline_runs(*args, **kwargs):
        raise AssertionError("bridge-only mode must not run the full maintenance baseline")

    monkeypatch.setattr(autopilot, "_run", fail_if_baseline_runs)

    rc = autopilot.main(
        [
            "--owner",
            "sherif69-sa",
            "--repo",
            "DevS69-sdetkit",
            "--check-intelligence-json",
            str(check_intelligence),
            "--pr-quality-safe-bridge-only",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )

    assert rc == 0
    report = json.loads((tmp_path / "out" / "autopilot-report.json").read_text())
    assert report["mode"] == BRIDGE_ONLY_MODE
    assert report["steps"]["pr_quality_safe_remediation_bridge"]["reason"] == (
        "no failed checks to remediate"
    )
    assert "baseline_pre_commit" not in report["steps"]

