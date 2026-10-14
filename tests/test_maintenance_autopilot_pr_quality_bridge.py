from __future__ import annotations

import importlib.util
import json
from pathlib import Path


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


def test_autopilot_bridge_creates_missing_output_directory(tmp_path: Path) -> None:
    autopilot = _load_autopilot()
    check_intelligence = _write_json(tmp_path / "check-intelligence.json", {"failed_checks": []})
    missing_out = tmp_path / "missing" / "safe-formatting-autopilot"

    result = autopilot._write_safe_fix_artifacts_from_check_intelligence(
        missing_out,
        check_intelligence,
    )

    assert result["ok"] is True
    assert (missing_out / "pr-quality-safe-remediation-bridge.json").exists()
