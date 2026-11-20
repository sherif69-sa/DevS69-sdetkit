from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import investigate


def test_classify_log_issue_categories() -> None:
    cat, sev, conf, _, _, cmd = investigate._classify_log_issue(
        "Deadlock detected in worker thread"
    )
    assert cat == investigate.CATEGORY_CONCURRENCY_RACE
    assert sev == "BLOCKER"
    assert "chaos" in cmd

    cat, sev, conf, _, _, cmd = investigate._classify_log_issue(
        "AssertionError: expected time.sleep(1.0)"
    )
    assert cat == investigate.CATEGORY_UNMOCKED_CLOCK_FLAKE
    assert sev == "BLOCKER"
    assert "freeze-clock" in cmd

    cat, sev, conf, _, _, cmd = investigate._classify_log_issue(
        "no such column: user_id in sql migration"
    )
    assert cat == investigate.CATEGORY_DESTRUCTIVE_MIGRATION
    assert sev == "BLOCKER"

    cat, sev, conf, _, _, cmd = investigate._classify_log_issue(
        "KeyError: 'DATABASE_URL' missing environment"
    )
    assert cat == investigate.CATEGORY_CONFIG_PARITY_GAP
    assert sev == "BLOCKER"

    cat, sev, conf, _, _, cmd = investigate._classify_log_issue("AssertionError: assert 1 == 2")
    assert cat == investigate.CATEGORY_ASSERTION_BLIND_SPOT
    assert sev == "HIGH"


def test_advisor_clean_workspace(tmp_path: Path) -> None:
    report = investigate.run_operational_advisor(root=tmp_path)
    assert report["schema_version"] == "1.0"
    assert report["verdict"] == "SHIP"
    assert report["total_suggestions"] == 0
    assert report["mode"] == "OFFLINE_DETERMINISTIC"


def test_advisor_with_log_and_ranking(tmp_path: Path) -> None:
    log_file = tmp_path / "ci.log"
    log_file.write_text("socket.timeout: connection refused to 127.0.0.1", encoding="utf-8")

    report = investigate.run_operational_advisor(
        root=tmp_path,
        log_path=log_file,
        blast_radius=85.0,
    )
    assert report["schema_version"] == "1.0"
    assert report["verdict"] == "NO_SHIP"
    assert report["total_suggestions"] >= 1
    assert report["highest_severity"] == "BLOCKER"

    top = report["suggestions"][0]
    assert top["rank"] == 1
    assert top["category"] == investigate.CATEGORY_CONCURRENCY_RACE
    assert top["severity"] == "BLOCKER"
    assert top["impact_score"] > 80.0
    assert "exact_command" in top


def test_advisor_ast_smell_detection(tmp_path: Path) -> None:
    test_dir = tmp_path / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    smelly_test = test_dir / "test_smell.py"
    smelly_test.write_text(
        "import os\n"
        "import time\n"
        "def test_foo():\n"
        "    os.environ['DIRTY'] = '1'\n"
        "    time.sleep(0.5)\n",
        encoding="utf-8",
    )

    report = investigate.run_operational_advisor(
        root=tmp_path,
        target=smelly_test,
        blast_radius=15.0,
    )
    assert report["verdict"] in ("REVIEW", "NO_SHIP")
    categories = [s["category"] for s in report["suggestions"]]
    assert investigate.CATEGORY_ENV_POLLUTION in categories
    assert investigate.CATEGORY_UNMOCKED_CLOCK_FLAKE in categories

    for s in report["suggestions"]:
        assert s["impact_score"] > 0
        assert s["rank"] >= 1


def test_advisor_quarantine_detection(tmp_path: Path) -> None:
    quarantine_file = tmp_path / ".sdetkit" / "quarantine.json"
    quarantine_file.parent.mkdir(parents=True, exist_ok=True)
    quarantine_payload = {
        "tests": {
            "tests/test_flaky.py::test_race": {
                "reason": "Timing race on slow CI runners",
                "quarantined_at": "2026-01-01T00:00:00Z",
                "ttl_days": 1,
            }
        }
    }
    quarantine_file.write_text(json.dumps(quarantine_payload), encoding="utf-8")

    report = investigate.run_operational_advisor(root=tmp_path)
    assert report["total_suggestions"] >= 1
    categories = [s["category"] for s in report["suggestions"]]
    assert investigate.CATEGORY_CONCURRENCY_RACE in categories


def test_advisor_cli_formats_and_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_file = tmp_path / "failure.log"
    log_file.write_text("KeyError: 'SECRET_KEY' missing from environ", encoding="utf-8")
    out_json = tmp_path / "report.json"
    summary_md = tmp_path / "summary.md"

    rc = investigate.advise_main(
        [
            "--repo-root",
            str(tmp_path),
            "--log",
            str(log_file),
            "--blast-radius",
            "40.0",
            "--format",
            "json",
            "--out",
            str(out_json),
            "--summary-out",
            str(summary_md),
        ]
    )
    assert rc == 1  # BLOCKER leads to NO_SHIP -> rc 1
    assert out_json.exists()
    assert summary_md.exists()

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["verdict"] == "NO_SHIP"
    assert data["suggestions"][0]["category"] == investigate.CATEGORY_CONFIG_PARITY_GAP

    # Test text format
    rc_text = investigate.advise_main(
        [
            "--repo-root",
            str(tmp_path),
            "--log",
            str(log_file),
            "--format",
            "text",
        ]
    )
    assert rc_text == 1
    captured = capsys.readouterr()
    assert "SDETKit Operational Advisor: verdict=NO_SHIP" in captured.out

    # Test markdown format
    rc_md = investigate.advise_main(
        [
            "--repo-root",
            str(tmp_path),
            "--format",
            "md",
        ]
    )
    assert rc_md == 0
    captured_md = capsys.readouterr()
    assert "# [ADVISE: SHIP] SDETKit Deterministic Operational Advisor" in captured_md.out
