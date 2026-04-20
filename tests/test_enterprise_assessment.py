from __future__ import annotations

import json
from pathlib import Path

from sdetkit import enterprise_assessment as ea


def test_build_enterprise_assessment_scores_real_repo() -> None:
    payload = ea.build_enterprise_assessment(Path("."))

    assert payload["summary"]["score"] >= 70
    assert payload["summary"]["tier"] in {"enterprise-ready", "pilot-ready", "not-ready"}
    assert payload["metrics"]["modules_count"] > 0
    assert "action_board" in payload
    assert "upgrade_contract" in payload
    assert payload["upgrade_contract"]["sla_review_hours"] >= 24


def test_build_enterprise_assessment_generates_boost_plan_when_controls_missing(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("project", encoding="utf-8")

    payload = ea.build_enterprise_assessment(tmp_path)

    assert payload["summary"]["score"] < 90
    assert payload["missing"]
    assert payload["boost_plan"]


def test_main_emit_pack_and_strict_failure(tmp_path: Path, capsys) -> None:
    out = tmp_path / "pack"

    rc = ea.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--strict",
            "--emit-pack-dir",
            str(out),
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["strict_pass"] is False
    assert (out / "enterprise-assessment-summary.json").exists()
    assert (out / "enterprise-assessment-report.md").exists()


def test_markdown_renderer_contains_boost_plan_section(tmp_path: Path) -> None:
    payload = ea.build_enterprise_assessment(tmp_path)

    md = ea._render_markdown(payload)

    assert md.startswith("# Enterprise assessment report")
    assert "Priority boost plan" in md
    assert "Action board" in md
    assert "Upgrade contract" in md


def test_execute_mode_attaches_command_results_and_writes_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    class _FakeProcess:
        def __init__(self, code: int, stdout: str) -> None:
            self.returncode = code
            self.stdout = stdout
            self.stderr = ""

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return _FakeProcess(0, '{"summary":{"status":"ok"}}\n')

    monkeypatch.setattr(ea.subprocess, "run", _fake_run)
    evidence_dir = tmp_path / "evidence"

    rc = ea.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--execute",
            "--evidence-dir",
            str(evidence_dir),
        ]
    )

    assert rc == 0
    summary = json.loads(
        (evidence_dir / "enterprise-assessment-execution-summary.json").read_text()
    )
    assert summary["all_green"] is True
    assert len(summary["commands"]) == 4
    assert all(row["error_kind"] == "none" for row in summary["commands"])
    assert (evidence_dir / "01-doctor.log").exists()


def test_execute_mode_returns_failure_when_any_command_fails(tmp_path: Path, monkeypatch) -> None:
    class _FakeProcess:
        def __init__(self, code: int) -> None:
            self.returncode = code
            self.stdout = '{"summary":{"status":"ok"}}\n'
            self.stderr = ""

    calls = {"count": 0}

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        calls["count"] += 1
        return _FakeProcess(1 if calls["count"] == 2 else 0)

    monkeypatch.setattr(ea.subprocess, "run", _fake_run)

    rc = ea.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--execute",
        ]
    )

    assert rc == 1


def test_baseline_summary_builds_trend_delta(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"summary":{"score":55}}', encoding="utf-8")

    rc = ea.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--baseline-summary",
            str(baseline),
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trend"]["has_baseline"] is True
    assert payload["trend"]["score_delta"] == payload["summary"]["score"] - 55


def test_production_profile_enables_pack_and_evidence_defaults(tmp_path: Path, monkeypatch) -> None:
    class _FakeProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = '{"summary":{"status":"ok"}}\n'
            self.stderr = ""

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return _FakeProcess()

    monkeypatch.setattr(ea.subprocess, "run", _fake_run)

    rc = ea.main(["--root", str(tmp_path), "--format", "json", "--production-profile"])

    assert rc == 1
    # strict is enabled by production profile and tmp_path is intentionally not enterprise-ready.


def test_fail_on_risk_band_policy_returns_non_zero_for_medium_or_higher(tmp_path: Path) -> None:
    rc = ea.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--fail-on-risk-band",
            "medium",
        ]
    )

    assert rc == 1
