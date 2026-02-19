from __future__ import annotations

import json
from pathlib import Path

from sdetkit import premium_gate_engine as eng


def test_collect_signals_reads_artifacts_and_extracts_warnings_and_recommendations(
    tmp_path: Path,
) -> None:
    out = tmp_path
    (out / "doctor.json").write_text(
        json.dumps(
            {
                "score": 65,
                "checks": {"policy": {"ok": False, "severity": "high", "message": "policy drift"}},
                "recommendations": ["enable pre-commit"],
            }
        ),
        encoding="utf-8",
    )
    (out / "maintenance.json").write_text(
        json.dumps(
            {
                "score": 60,
                "checks": [
                    {"name": "tests", "ok": False, "severity": "medium", "summary": "tests failed"}
                ],
                "recommendations": ["stabilize flaky tests"],
            }
        ),
        encoding="utf-8",
    )
    (out / "security-check.json").write_text(
        json.dumps({"findings": [{"rule_id": "SEC_X", "severity": "high", "path": "src/app.py"}]}),
        encoding="utf-8",
    )
    (out / "premium-gate.CI.log").write_text("warning: drift\n", encoding="utf-8")

    payload = eng.collect_signals(out)
    assert payload["counts"]["warnings"] == 3
    assert payload["counts"]["recommendations"] >= 4
    assert payload["counts"]["engine_checks"] == 2
    assert payload["required_artifacts"] == {
        "doctor.json": True,
        "maintenance.json": True,
        "security-check.json": True,
    }
    assert payload["hotspots"] == {"doctor": 1, "maintenance": 1, "security": 1}
    assert payload["ok"] is False


def test_collect_signals_missing_artifacts_adds_engine_checks(tmp_path: Path) -> None:
    payload = eng.collect_signals(tmp_path)
    assert payload["counts"]["engine_checks"] == 7
    assert payload["counts"]["steps"] == 0
    assert payload["ok"] is False


def test_collect_signals_reads_step_logs_and_marks_failures(tmp_path: Path) -> None:
    (tmp_path / "premium-gate.CI.log").write_text("ERROR: step failed: CI\n", encoding="utf-8")
    payload = eng.collect_signals(tmp_path)
    assert payload["counts"]["steps"] == 1
    assert payload["step_status"][0]["ok"] is False


def test_main_writes_json_output_and_double_check(tmp_path: Path, capsys) -> None:
    out = tmp_path
    (out / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (out / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": ["all good"]}), encoding="utf-8"
    )
    (out / "security-check.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (out / "premium-gate.Quality.log").write_text("all clear\n", encoding="utf-8")

    summary_path = out / "premium-summary.json"
    rc = eng.main(
        [
            "--out-dir",
            str(out),
            "--double-check",
            "--format",
            "json",
            "--json-output",
            str(summary_path),
        ]
    )
    assert rc == 0
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert stdout_payload["counts"] == file_payload["counts"]


def test_main_min_score_gate_can_fail(tmp_path: Path) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {"x": {"ok": False, "severity": "critical", "message": "boom"}}}),
        encoding="utf-8",
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "security-check.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (tmp_path / "premium-gate.Quality.log").write_text("ok\n", encoding="utf-8")
    rc = eng.main(["--out-dir", str(tmp_path), "--min-score", "95", "--format", "json"])
    assert rc == 2


def test_auto_fix_applies_supported_security_rules(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    target = src / "app.py"
    target.write_text(
        "import requests\nimport subprocess\nimport yaml\n"
        "requests.get('https://example.com')\n"
        "subprocess.run('echo hi', shell=True)\n"
        "yaml.load(data)\n",
        encoding="utf-8",
    )

    (tmp_path / "security-check.json").write_text(
        json.dumps(
            {
                "findings": [
                    {"rule_id": "SEC_REQUESTS_NO_TIMEOUT", "path": "src/app.py"},
                    {"rule_id": "SEC_SUBPROCESS_SHELL_TRUE", "path": "src/app.py"},
                    {"rule_id": "SEC_YAML_LOAD", "path": "src/app.py"},
                ]
            }
        ),
        encoding="utf-8",
    )

    results = eng.run_autofix(tmp_path, tmp_path)
    assert [r.status for r in results] == ["fixed", "fixed", "fixed"]
    new_text = target.read_text(encoding="utf-8")
    assert "timeout=10" in new_text
    assert "shell=False" in new_text
    assert "yaml.safe_load(" in new_text


def test_main_auto_fix_adds_manual_followup_recommendation(tmp_path: Path, capsys) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "security-check.json").write_text(
        json.dumps({"findings": [{"rule_id": "SEC_UNKNOWN", "path": "src/missing.py"}]}),
        encoding="utf-8",
    )
    (tmp_path / "premium-gate.Quality.log").write_text("ok\n", encoding="utf-8")

    rc = eng.main(
        ["--out-dir", str(tmp_path), "--auto-fix", "--fix-root", str(tmp_path), "--format", "json"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(item["status"] in {"manual", "skipped"} for item in payload["auto_fix_results"])
    assert any(item["category"] == "manual-followup" for item in payload["recommendations"])
    assert payload["manual_fix_plan"]
    assert payload["manual_fix_plan"][0]["suggested_edit"]


def test_main_markdown_format_includes_five_heads_and_plan(tmp_path: Path, capsys) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "security-check.json").write_text(
        json.dumps({"findings": [{"rule_id": "SEC_UNKNOWN", "path": "src/missing.py"}]}),
        encoding="utf-8",
    )
    (tmp_path / "premium-gate.Quality.log").write_text("ok\n", encoding="utf-8")
    rc = eng.main(
        [
            "--out-dir",
            str(tmp_path),
            "--auto-fix",
            "--fix-root",
            str(tmp_path),
            "--format",
            "markdown",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "# premium gate brain report" in out
    assert "## five heads" in out
    assert "## manual fix plan" in out


def test_guideline_store_is_editable(tmp_path: Path) -> None:
    db_path = tmp_path / "insights.db"
    gid = eng.add_guideline(db_path, "secure-subprocess", "avoid shell", ["security", "high"])
    assert gid > 0
    updated = eng.update_guideline(
        db_path,
        gid,
        "secure-subprocess-v2",
        "replace shell=True with args list",
        ["security", "critical"],
    )
    assert updated is True
    guidelines = eng.list_guidelines(db_path)
    assert guidelines[0]["title"] == "secure-subprocess-v2"
    assert "critical" in guidelines[0]["tags"]


def test_main_learn_db_and_commit_persists_records(tmp_path: Path) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "security-check.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (tmp_path / "premium-gate.Quality.log").write_text("ok\n", encoding="utf-8")
    db = tmp_path / "premium-insights.db"

    rc = eng.main(
        [
            "--out-dir",
            str(tmp_path),
            "--db-path",
            str(db),
            "--learn-db",
            "--learn-commit",
            "--format",
            "json",
        ]
    )
    assert rc == 0

    import sqlite3

    with sqlite3.connect(db) as conn:
        runs = conn.execute("SELECT COUNT(*) FROM insights_runs").fetchone()[0]
        commits = conn.execute("SELECT COUNT(*) FROM commit_learning").fetchone()[0]
    assert runs >= 1
    assert commits >= 1


def test_main_applies_learned_guidelines_to_recommendations(tmp_path: Path, capsys) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps(
            {
                "checks": {"policy": {"ok": False, "severity": "high", "message": "policy drift"}},
                "recommendations": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "security-check.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (tmp_path / "premium-gate.Quality.log").write_text("ok\n", encoding="utf-8")
    db = tmp_path / "premium-insights.db"

    eng.add_guideline(
        db,
        "doctor:policy",
        "enforce policy baseline in CI and regenerate policy snapshots.",
        ["doctor:policy", "high"],
        source="manual",
    )

    rc = eng.main(
        [
            "--out-dir",
            str(tmp_path),
            "--db-path",
            str(db),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(item["category"] == "learned-guideline" for item in payload["recommendations"])
    assert payload.get("manual_fix_plan")
