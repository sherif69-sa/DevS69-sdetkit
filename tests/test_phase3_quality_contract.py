from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import check_phase3_quality_contract as contract


def _write_summary(path: Path, checks: list[dict[str, object]]) -> Path:
    payload = {
        "schema_version": "sdetkit.phase1_baseline.v1",
        "generated_at_utc": "2026-04-19T00:00:00Z",
        "out_dir": "build/phase1-baseline",
        "ok": False,
        "checks": checks,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _write_doctor(path: Path, reason: str) -> Path:
    path.write_text(json.dumps({"enterprise": {"next_pass_reason": reason}}), encoding="utf-8")
    return path


def _assert_contract_shape(payload: dict[str, object]) -> None:
    required_keys = {
        "schema_version",
        "ok",
        "decision",
        "checks",
        "failures",
        "doctor_handoff_alignment",
        "doctor_handoff_alignment_reason",
        "doctor_alignment_mode",
        "summary",
        "summary_by_lane",
    }
    assert required_keys.issubset(payload)


def test_phase3_quality_contract_positive_path(tmp_path: Path) -> None:
    summary = _write_summary(
        tmp_path / "phase1-summary.json",
        [
            {"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"},
            {"id": "pytest", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"},
            {"id": "ruff", "ok": True, "rc": 0, "stdout_log": "a", "stderr_log": "b"},
        ],
    )
    out_dir = tmp_path / "phase3"
    rc = contract.main(["--summary", str(summary), "--out-dir", str(out_dir), "--format", "json"])

    assert rc == 0
    assert (out_dir / "phase3-adaptive-planning.json").exists()
    assert (out_dir / "phase3-remediation-v2.json").exists()
    assert (out_dir / "phase3-trend-delta.json").exists()
    assert (out_dir / "phase3-next-pass-handoff.json").exists()
    payload = json.loads((out_dir / "phase3-next-pass-handoff.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.phase3_next_pass.v1"


def test_phase3_quality_contract_missing_summary_fails(tmp_path: Path) -> None:
    rc = contract.main(["--summary", str(tmp_path / "missing.json"), "--format", "json"])
    assert rc == 1


def test_phase3_quality_contract_missing_summary_has_lane_summary_values(
    tmp_path: Path, capsys
) -> None:
    rc = contract.main(["--summary", str(tmp_path / "missing.json"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    _assert_contract_shape(payload)
    assert payload["decision"] == "fail"
    lane_summary = payload["summary_by_lane"]
    assert lane_summary["global"] == {"total": 1, "passed": 0, "failed": 1}
    assert lane_summary["adaptive"] == {"total": 0, "passed": 0, "failed": 0}
    assert lane_summary["remediation"] == {"total": 0, "passed": 0, "failed": 0}
    assert lane_summary["trend"] == {"total": 0, "passed": 0, "failed": 0}
    assert lane_summary["next_pass"] == {"total": 0, "passed": 0, "failed": 0}


def test_phase3_quality_contract_missing_summary_text_includes_failure_header(
    tmp_path: Path, capsys
) -> None:
    rc = contract.main(["--summary", str(tmp_path / "missing.json"), "--format", "text"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "phase3-quality-contract: FAIL" in out
    assert "- decision: fail" in out
    assert "- doctor_handoff_alignment_reason: doctor_next_pass_unavailable" in out


def test_phase3_quality_contract_auto_uses_history_previous_summary(tmp_path: Path, capsys) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    _write_summary(
        tmp_path / "history" / "phase1-baseline-summary-older.json",
        [{"id": "doctor", "ok": True, "rc": 0, "stdout_log": "a", "stderr_log": "b"}],
    )
    out_dir = tmp_path / "phase3"
    rc = contract.main(["--summary", str(summary), "--out-dir", str(out_dir), "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    trend = json.loads((out_dir / "phase3-trend-delta.json").read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["ok"] is True
    assert payload["decision"] == "pass"
    assert trend["status"] == "worsening"
    assert payload["summary_by_lane"]["adaptive"]["total"] >= 1
    assert payload["doctor_handoff_alignment_reason"] == "doctor_next_pass_unavailable"


def test_phase3_quality_contract_json_shape_contains_required_top_level_fields(
    tmp_path: Path, capsys
) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    rc = contract.main(["--summary", str(summary), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    _assert_contract_shape(payload)
    assert "artifacts" in payload


def test_phase3_quality_contract_fails_when_doctor_handoff_mismatches(
    tmp_path: Path, capsys
) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "none")
    out_dir = tmp_path / "phase3"
    rc = contract.main(
        [
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["decision"] == "fail"
    assert payload["doctor_handoff_alignment"] == "mismatch"
    assert (
        payload["doctor_handoff_alignment_reason"]
        == "doctor_next_pass_mismatch"
    )
    assert "doctor handoff alignment mismatch" in payload["failures"]
    assert payload["summary"]["failed"] >= 1


def test_phase3_quality_contract_warn_mode_allows_doctor_mismatch(tmp_path: Path, capsys) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "none")
    out_dir = tmp_path / "phase3"
    rc = contract.main(
        [
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--doctor-alignment-mode",
            "warn",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["decision"] == "warn"
    assert payload["doctor_handoff_alignment"] == "mismatch"
    assert payload["doctor_alignment_mode"] == "warn"
    assert (
        payload["doctor_handoff_alignment_reason"]
        == "doctor_next_pass_mismatch"
    )
    assert "doctor handoff alignment mismatch" not in payload["failures"]


def test_phase3_quality_contract_off_mode_ignores_doctor_mismatch(tmp_path: Path, capsys) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "none")
    out_dir = tmp_path / "phase3"
    rc = contract.main(
        [
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--doctor-alignment-mode",
            "off",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["decision"] == "pass"
    assert payload["doctor_handoff_alignment"] == "mismatch"
    assert "doctor handoff alignment mismatch" not in payload["failures"]


def test_phase3_quality_contract_module_invocation_off_mode(tmp_path: Path) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "none")
    out_dir = tmp_path / "phase3"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_phase3_quality_contract",
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--doctor-alignment-mode",
            "off",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["decision"] == "pass"
    assert payload["doctor_alignment_mode"] == "off"


def test_phase3_quality_contract_text_format_includes_decision_lines(
    tmp_path: Path, capsys
) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    rc = contract.main(["--summary", str(summary), "--format", "text"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "- decision: pass" in out
    assert "- doctor_handoff_alignment:" in out
    assert "- doctor_handoff_alignment_reason:" in out


def test_phase3_quality_contract_doctor_reason_unrecognized(tmp_path: Path, capsys) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "something-new")
    rc = contract.main(
        [
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--doctor-alignment-mode",
            "off",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["doctor_handoff_alignment"] == "no-doctor"
    assert payload["doctor_handoff_alignment_reason"] == "doctor_next_pass_reason_unrecognized"


def test_phase3_quality_contract_doctor_reason_blockers_present_aligns(
    tmp_path: Path, capsys
) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "blockers_present")
    rc = contract.main(
        [
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["doctor_handoff_alignment"] == "aligned"
    assert payload["doctor_handoff_alignment_reason"] == "doctor_next_pass_consistent"


def test_phase3_quality_contract_doctor_reason_failed_checks_present_aligns(
    tmp_path: Path, capsys
) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "pytest", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "failed_checks_present")
    rc = contract.main(
        [
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["doctor_handoff_alignment"] == "aligned"
    assert payload["doctor_handoff_alignment_reason"] == "doctor_next_pass_consistent"


def test_phase3_quality_contract_module_invocation_strict_mismatch_fails(tmp_path: Path) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    )
    doctor = _write_doctor(tmp_path / "doctor.json", "none")
    out_dir = tmp_path / "phase3"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_phase3_quality_contract",
            "--summary",
            str(summary),
            "--doctor-summary",
            str(doctor),
            "--doctor-alignment-mode",
            "strict",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["decision"] == "fail"
    assert "doctor handoff alignment mismatch" in payload["failures"]


def test_phase3_quality_contract_ignores_malformed_history_previous_summary(
    tmp_path: Path, capsys
) -> None:
    summary = _write_summary(
        tmp_path / "phase1-baseline-summary.json",
        [{"id": "doctor", "ok": True, "rc": 0, "stdout_log": "a", "stderr_log": "b"}],
    )
    bad_history = tmp_path / "history" / "phase1-baseline-summary-latest.json"
    bad_history.parent.mkdir(parents=True, exist_ok=True)
    bad_history.write_text("{not-json", encoding="utf-8")

    out_dir = tmp_path / "phase3"
    rc = contract.main(["--summary", str(summary), "--out-dir", str(out_dir), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    trend = json.loads((out_dir / "phase3-trend-delta.json").read_text(encoding="utf-8"))

    assert rc == 0
    assert payload["ok"] is True
    assert trend["status"] == "bootstrap"
