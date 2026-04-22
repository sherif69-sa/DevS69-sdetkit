from __future__ import annotations

import json
import zipfile
from pathlib import Path

from sdetkit.checks import main_ as checks_main
from sdetkit.checks.artifacts import render_record_artifacts
from sdetkit.checks.results import CheckRecord


def _sample_records(repo_root: Path) -> tuple[CheckRecord, ...]:
    out_dir = repo_root / ".sdetkit" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "check.tests_full.log").write_text("full test failure\n", encoding="utf-8")
    (out_dir / "doctor.json").write_text('{"ok": false}\n', encoding="utf-8")
    return (
        CheckRecord(
            id="tests_full",
            title="Full pytest suite",
            status="failed",
            blocking=True,
            reason="command failed (rc=1)",
            command="python -m pytest -q -o addopts=",
            log_path=".sdetkit/out/check.tests_full.log",
            evidence_paths=(".sdetkit/out/doctor.json",),
            metadata={
                "category": "tests",
                "truth_level": "merge",
                "target_mode": "targeted",
                "target_reason": "targeted pytest scope from changed files",
                "changed_paths": ["src/sdetkit/demo.py"],
                "selected_targets": ["tests/test_demo.py"],
                "cache": {"status": "hit"},
            },
        ),
        CheckRecord(
            id="format_check",
            title="Ruff format check",
            status="failed",
            blocking=True,
            reason="command failed (rc=1)",
            command="python -m ruff format --check .",
            metadata={
                "category": "format",
                "truth_level": "standard",
                "target_mode": "full",
                "cache": {"status": "fresh"},
            },
        ),
        CheckRecord(
            id="doctor_core",
            title="Doctor core report",
            status="skipped",
            blocking=False,
            reason="adaptive selected a narrower validation slice",
            advisory=("doctor signal omitted in this targeted lane",),
            metadata={
                "category": "doctor",
                "truth_level": "standard",
                "target_mode": "smoke",
                "cache": {"status": "not-applicable"},
            },
        ),
    )


def test_render_record_artifacts_writes_stable_schema_outputs(tmp_path: Path) -> None:
    payload = render_record_artifacts(
        repo_root=tmp_path,
        out_dir=tmp_path / ".sdetkit" / "out",
        profile="standard",
        requested_profile="adaptive",
        profile_notes="Adaptive resolved to standard after targeted local planning.",
        metadata={
            "source": "unit-test",
            "requested_profile": "adaptive",
            "adaptive_reason": "small code change set keeps adaptive on standard validation",
            "changed_files": ["src/sdetkit/demo.py"],
            "changed_areas": ["source", "tests"],
            "execution": {"mode": "parallel", "workers": 2},
            "checks_recorded": 3,
            "cache_enabled": True,
        },
        records=_sample_records(tmp_path),
    )

    verdict = json.loads(
        (tmp_path / ".sdetkit" / "out" / "verdict.json").read_text(encoding="utf-8")
    )
    fix_plan = json.loads(
        (tmp_path / ".sdetkit" / "out" / "fix-plan.json").read_text(encoding="utf-8")
    )
    risk = json.loads(
        (tmp_path / ".sdetkit" / "out" / "risk-summary.json").read_text(encoding="utf-8")
    )
    summary_md = (tmp_path / ".sdetkit" / "out" / "summary.md").read_text(encoding="utf-8")

    assert payload["verdict"]["schema_version"] == "sdetkit.artifacts.verdict.v1"
    assert verdict["profile"]["requested"] == "adaptive"
    assert verdict["profile"]["selected"] == "standard"
    assert verdict["profile"]["adaptive_resolved"] is True
    assert verdict["targeting"]["used_targeted_execution"] is True
    assert verdict["cache"]["used_cache_hits"] is True
    assert verdict["check_results_summary"]["target_modes"] == {
        "full": 1,
        "smoke": 1,
        "targeted": 1,
    }
    assert fix_plan["schema_version"] == "sdetkit.artifacts.fix-plan.v1"
    assert [item["check_id"] for item in fix_plan["auto_fixable_candidates"]] == ["format_check"]
    assert [item["check_id"] for item in fix_plan["manual_fixes"]] == ["tests_full", "doctor_core"]
    assert risk["schema_version"] == "sdetkit.artifacts.risk-summary.v1"
    assert risk["execution_truth"]["used_targeted_execution"] is True
    assert risk["execution_truth"]["used_cache_hits"] is True
    assert "targeted execution was used" in summary_md
    assert "cached check results were reused" in summary_md
    assert "requested `adaptive`, selected `standard`" in summary_md


def test_evidence_zip_manifest_and_contents_are_deterministic(tmp_path: Path) -> None:
    out_dir = tmp_path / ".sdetkit" / "out"
    render_record_artifacts(
        repo_root=tmp_path,
        out_dir=out_dir,
        profile="strict",
        requested_profile="strict",
        metadata={
            "source": "unit-test",
            "execution": {"mode": "sequential", "workers": 1},
            "checks_recorded": 3,
            "cache_enabled": False,
        },
        records=_sample_records(tmp_path),
    )
    first_zip = out_dir / "evidence.zip"
    first_bytes = first_zip.read_bytes()
    render_record_artifacts(
        repo_root=tmp_path,
        out_dir=out_dir,
        profile="strict",
        requested_profile="strict",
        metadata={
            "source": "unit-test",
            "execution": {"mode": "sequential", "workers": 1},
            "checks_recorded": 3,
            "cache_enabled": False,
        },
        records=_sample_records(tmp_path),
    )

    with zipfile.ZipFile(first_zip) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    assert names[0] == "manifest.json"
    assert names[1:] == sorted(names[1:])
    assert names[1:6] == [
        "fix-plan.json",
        "raw/check.tests_full.log",
        "raw/doctor.json",
        "risk-summary.json",
        "run-report.json",
    ]
    assert "summary.md" in names
    assert "verdict.json" in names
    assert manifest["schema_version"] == "sdetkit.artifacts.evidence.v1"
    assert any(item["path"] == "raw/check.tests_full.log" for item in manifest["contents"])
    assert any(item["path"] == "raw/doctor.json" for item in manifest["contents"])
    assert first_bytes == first_zip.read_bytes()


def test_render_ledger_cli_writes_artifacts_for_shell_wrappers(tmp_path: Path) -> None:
    ledger = tmp_path / "premium-step-results.ndjson"
    log = tmp_path / ".sdetkit" / "out" / "premium.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("premium lane\n", encoding="utf-8")
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "quality",
                        "title": "Quality (fast/smoke)",
                        "status": "passed",
                        "blocking": True,
                        "cmd": "bash quality.sh ci",
                        "log": ".sdetkit/out/premium.log",
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "id": "premium_engine",
                        "title": "Premium Gate Engine",
                        "status": "skipped",
                        "blocking": False,
                        "reason": "engine-only mode skips premium engine execution",
                    },
                    sort_keys=True,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rc = checks_main.main(
        [
            "render-ledger",
            "--profile",
            "quick",
            "--requested-profile",
            "adaptive",
            "--ledger",
            str(ledger),
            "--repo-root",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / ".sdetkit" / "out"),
            "--profile-notes",
            "Smoke shell wrapper lane.",
            "--metadata-json",
            json.dumps(
                {
                    "source": "premium-gate.sh",
                    "mode": "fast",
                    "execution": {"mode": "sequential", "workers": 1},
                    "checks_recorded": 2,
                },
                sort_keys=True,
            ),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    verdict = json.loads(
        (tmp_path / ".sdetkit" / "out" / "verdict.json").read_text(encoding="utf-8")
    )
    assert verdict["profile"]["requested"] == "adaptive"
    assert verdict["execution"]["source"] == "premium-gate.sh"
    assert (tmp_path / ".sdetkit" / "out" / "fix-plan.json").exists()
    assert (tmp_path / ".sdetkit" / "out" / "risk-summary.json").exists()
    assert (tmp_path / ".sdetkit" / "out" / "evidence.zip").exists()


def test_summary_markdown_handles_no_advisories_and_no_actions(tmp_path: Path) -> None:
    records = (
        CheckRecord(
            id="lint",
            title="Lint",
            status="passed",
            blocking=True,
            metadata={"category": "lint", "truth_level": "smoke", "target_mode": "full"},
        ),
    )
    payload = render_record_artifacts(
        repo_root=tmp_path,
        out_dir=tmp_path / ".sdetkit" / "out",
        profile="strict",
        requested_profile="strict",
        metadata={"execution": {"mode": "sequential", "workers": 1}, "checks_recorded": 1},
        records=records,
    )
    summary_md = payload["summary_markdown"]
    assert "## Advisories\n- None" in summary_md
    assert "- No follow-up actions required." in summary_md


def test_artifact_helpers_cover_misc_branches(tmp_path: Path) -> None:
    from sdetkit.checks import artifacts as a

    item_security = {
        "category": "security",
        "blocking": False,
        "status": "failed",
        "target_mode": "smoke",
    }
    assert a._severity_for_record(item_security) == "medium"

    item_failed_non_blocking = {
        "category": "tests",
        "blocking": False,
        "status": "failed",
        "target_mode": "full",
    }
    assert a._severity_for_record(item_failed_non_blocking) == "low"

    item_skipped_blocking = {
        "category": "tests",
        "blocking": True,
        "status": "skipped",
        "target_mode": "full",
    }
    assert a._severity_for_record(item_skipped_blocking) == "medium"

    assert a._cache_status({"cache": "not-a-dict"}) == "not-applicable"
    assert a._exclude_from_evidence(tmp_path / "cache" / "x.txt", tmp_path) is True
    assert a._exclude_from_evidence(tmp_path / "normal.txt", tmp_path) is False

    verdict_payload = {
        "cache": {"used_cache_hits": True},
    }
    assert (
        a._follow_up_reason({"target_mode": "full"}, verdict_payload)
        == "Re-run after remediation to refresh any cached evidence."
    )
    assert a._owner_for_category("unknown") == "repository-maintainers"


def test_write_evidence_zip_skips_missing_and_excluded_sources(tmp_path: Path) -> None:
    from sdetkit.checks.artifacts import artifact_paths_for, write_evidence_zip

    out_dir = tmp_path / ".sdetkit" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = artifact_paths_for(out_dir)

    missing_log = "missing.log"
    excluded = ".pytest_cache/evidence.txt"
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / excluded).write_text("skip", encoding="utf-8")

    rec = CheckRecord(
        id="lint",
        title="Lint",
        status="failed",
        blocking=True,
        log_path=missing_log,
        evidence_paths=(excluded,),
        metadata={"category": "lint", "truth_level": "smoke", "target_mode": "full"},
    )

    verdict_payload = {
        "profile": {"requested": "quick", "selected": "quick"},
        "recommendation": "do-not-merge",
        "confidence": "low (smoke-only)",
    }
    write_evidence_zip(
        repo_root=tmp_path,
        out_dir=out_dir,
        paths=paths,
        verdict_payload=verdict_payload,
        fix_plan={"x": 1},
        risk_summary={"y": 1},
        summary_md="# test\n",
        run_report_payload={"z": 1},
        records=(rec,),
    )

    with zipfile.ZipFile(paths.evidence_zip) as archive:
        names = archive.namelist()
    assert "repo/.pytest_cache/evidence.txt" not in names
    assert all("missing.log" not in name for name in names)


def test_check_results_summary_unknown_cache_status_maps_to_not_applicable() -> None:
    from sdetkit.checks.artifacts import _check_results_summary

    summary = _check_results_summary(
        [
            {
                "status": "passed",
                "blocking": True,
                "advisory": [],
                "target_mode": "full",
                "cache_status": "mystery",
            }
        ]
    )
    assert summary["cache_status"]["not-applicable"] == 1


def test_render_report_artifacts_wrapper_path(tmp_path: Path) -> None:
    from sdetkit.checks.artifacts import render_report_artifacts
    from sdetkit.checks.planner import CheckPlan
    from sdetkit.checks.results import build_final_verdict
    from sdetkit.checks.runner import CheckRunReport

    plan = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(),
        skipped_checks=(),
    )
    verdict = build_final_verdict(profile="quick", checks=[])
    report = CheckRunReport(plan=plan, records=(), verdict=verdict)

    payload = render_report_artifacts(
        report,
        repo_root=tmp_path,
        out_dir=tmp_path / ".sdetkit" / "out",
    )
    assert payload["verdict"]["schema_version"] == "sdetkit.artifacts.verdict.v1"
    assert (tmp_path / ".sdetkit" / "out" / "run-report.json").exists()
