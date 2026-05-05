import importlib.util
import json

from sdetkit import adaptive_safe_fix, adaptive_safe_remediation


def _load_autopilot():
    spec = importlib.util.spec_from_file_location(
        "maintenance_autopilot", "tools/maintenance_autopilot.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_write_safe_fix_artifacts_writes_safe_fix_learning_outcome(tmp_path, monkeypatch):
    autopilot = _load_autopilot()
    monkeypatch.chdir(tmp_path)
    plan = {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "safe_to_auto_fix": True,
        "fix_type": "format_only",
        "requires_human_review": False,
        "source_code": "PRE_COMMIT_FORMAT_DRIFT",
        "confidence": "high",
        "commands": ["PYTHONPATH=src python -m ruff format src/sdetkit/example.py"],
        "proof_commands": ["PYTHONPATH=src python -m ruff format --check src/sdetkit/example.py"],
        "affected_files": ["src/sdetkit/example.py"],
    }

    monkeypatch.setattr(adaptive_safe_fix, "build_plan", lambda payload: plan)
    monkeypatch.setattr(
        adaptive_safe_remediation,
        "run_plan",
        lambda payload, cwd: {
            "schema_version": "sdetkit.adaptive_safe_remediation.v1",
            "ok": True,
            "status": "success",
            "attempted": True,
            "command_count": 3,
        },
    )
    monkeypatch.setattr(
        adaptive_safe_remediation,
        "render_markdown",
        lambda payload: "# Adaptive Safe Remediation Result\n",
    )
    monkeypatch.setattr(
        autopilot,
        "_commit_safe_fix_changes",
        lambda out_dir, plan, result: {
            "schema_version": "sdetkit.maintenance.autopilot.safe_fix_commit.v1",
            "ok": False,
            "attempted": False,
            "pushed": False,
            "reason": "commit-safe-fixes flag is disabled",
        },
    )

    autopilot._write_safe_fix_artifacts_on_failure(
        tmp_path, {"schema_version": "sdetkit.adaptive.diagnosis.v1"}
    )

    learning_path = tmp_path / "adaptive-safe-fix-learning-result.json"
    assert learning_path.exists()
    payload = json.loads(learning_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["input_records"] == 1
    assert payload["fix_type"] == "format_only"
    assert payload["remediation_status"] == "success"
    assert payload["commit_pushed"] is False


def test_autopilot_writes_safe_fix_plan_and_remediation_artifacts(tmp_path, monkeypatch):
    autopilot = _load_autopilot()
    plan = {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "safe_to_auto_fix": True,
        "fix_type": "format_only",
        "requires_human_review": False,
        "source_code": "PRE_COMMIT_FORMAT_DRIFT",
        "commands": ["PYTHONPATH=src python -m ruff format src/sdetkit/example.py"],
    }
    result = {
        "schema_version": "sdetkit.adaptive_safe_remediation.v1",
        "ok": True,
        "status": "success",
        "attempted": True,
        "safe_to_auto_fix": True,
        "fix_type": "format_only",
        "source_code": "PRE_COMMIT_FORMAT_DRIFT",
        "validation_errors": [],
        "command_count": 1,
        "commands": [],
    }

    monkeypatch.setattr(adaptive_safe_fix, "build_plan", lambda payload: plan)
    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", lambda payload, cwd: result)
    monkeypatch.setattr(
        adaptive_safe_remediation,
        "render_markdown",
        lambda payload: "# Adaptive Safe Remediation Result\n",
    )

    autopilot._write_safe_fix_artifacts_on_failure(
        tmp_path, {"schema_version": "sdetkit.adaptive.diagnosis.v1"}
    )

    assert (tmp_path / "safe-fix-plan.json").exists()
    assert (tmp_path / "adaptive-safe-remediation-result.json").exists()
    assert (tmp_path / "adaptive-safe-remediation-result.md").exists()


def test_autopilot_writes_plan_only_when_human_review_required(tmp_path, monkeypatch):
    autopilot = _load_autopilot()
    plan = {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "safe_to_auto_fix": False,
        "fix_type": "review_required",
        "requires_human_review": True,
        "source_code": "PYTEST_ASSERTION_FAILURE",
        "commands": [],
    }

    monkeypatch.setattr(adaptive_safe_fix, "build_plan", lambda payload: plan)

    def fail_if_called(payload, cwd):
        raise AssertionError("unsafe plans must not run remediation")

    monkeypatch.setattr(adaptive_safe_remediation, "run_plan", fail_if_called)

    autopilot._write_safe_fix_artifacts_on_failure(
        tmp_path, {"schema_version": "sdetkit.adaptive.diagnosis.v1"}
    )

    assert (tmp_path / "safe-fix-plan.json").exists()
    assert not (tmp_path / "adaptive-safe-remediation-result.json").exists()
    assert not (tmp_path / "adaptive-safe-remediation-result.md").exists()


def test_autopilot_records_safe_remediation_errors(tmp_path, monkeypatch):
    autopilot = _load_autopilot()

    def raise_build_plan(payload):
        raise RuntimeError("planner failed")

    monkeypatch.setattr(adaptive_safe_fix, "build_plan", raise_build_plan)

    autopilot._write_safe_fix_artifacts_on_failure(
        tmp_path, {"schema_version": "sdetkit.adaptive.diagnosis.v1"}
    )

    error_path = tmp_path / "adaptive-safe-remediation-error.json"
    assert error_path.exists()
    assert "planner failed" in error_path.read_text(encoding="utf-8")
