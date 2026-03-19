from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from sdetkit import premium_gate_engine as eng


def _write_topology_artifact(
    path: Path,
    *,
    pass_rate: float = 100.0,
    app_services: int = 3,
    checks: list[dict[str, object]] | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "checks": checks or [],
                "summary": {"pass_rate": pass_rate, "passed": pass_rate == 100.0},
                "inventory": {"counts": {"application_services": app_services}},
            }
        ),
        encoding="utf-8",
    )


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
    _write_topology_artifact(out / "integration-topology.json")
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
        "integration-topology.json": True,
        "security-check.json": True,
    }
    assert payload["hotspots"] == {"doctor": 1, "maintenance": 1, "security": 1}
    assert payload["ok"] is False


def test_collect_signals_missing_artifacts_adds_engine_checks(tmp_path: Path) -> None:
    payload = eng.collect_signals(tmp_path)
    assert payload["counts"]["engine_checks"] == 9
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
    _write_topology_artifact(out / "integration-topology.json")
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
    _write_topology_artifact(tmp_path / "integration-topology.json")
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


def test_autofix_timeout_skips_invalid_ast_offsets(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "import requests\nrequests.get(url)\n"
    tree = ast.parse(text)
    call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call))
    call.end_lineno = None

    monkeypatch.setattr(eng.ast, "parse", lambda _text: tree)

    patched, changed = eng._autofix_timeout(text)
    assert patched == text
    assert changed is False


def test_main_auto_fix_adds_manual_followup_recommendation(tmp_path: Path, capsys) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    _write_topology_artifact(tmp_path / "integration-topology.json")
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


def test_collect_signals_ignores_info_security_findings(tmp_path: Path) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    _write_topology_artifact(tmp_path / "integration-topology.json")
    (tmp_path / "security-check.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "rule_id": "SEC_DEBUG_PRINT",
                        "severity": "info",
                        "path": "src/app.py",
                        "line": 12,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = eng.collect_signals(tmp_path)
    assert payload["counts"]["warnings"] == 0


def test_run_autofix_ignores_info_findings(tmp_path: Path) -> None:
    (tmp_path / "security-check.json").write_text(
        json.dumps(
            {"findings": [{"rule_id": "SEC_DEBUG_PRINT", "severity": "info", "path": "src/app.py"}]}
        ),
        encoding="utf-8",
    )

    results = eng.run_autofix(tmp_path, tmp_path)
    assert results == []


def test_main_markdown_format_includes_five_heads_and_plan(tmp_path: Path, capsys) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    _write_topology_artifact(tmp_path / "integration-topology.json")
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
    _write_topology_artifact(tmp_path / "integration-topology.json")
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
    _write_topology_artifact(tmp_path / "integration-topology.json")
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


def test_collect_signals_reads_integration_topology_contract(tmp_path: Path) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps({"checks": [], "recommendations": []}), encoding="utf-8"
    )
    _write_topology_artifact(
        tmp_path / "integration-topology.json",
        pass_rate=92.5,
        app_services=2,
        checks=[
            {
                "kind": "dependency-contract",
                "name": "ml-serving",
                "passed": False,
                "reason": "missing dependency",
            }
        ],
    )
    (tmp_path / "security-check.json").write_text(json.dumps({"findings": []}), encoding="utf-8")

    payload = eng.collect_signals(tmp_path)
    assert payload["required_artifacts"]["integration-topology.json"] is True
    assert payload["hotspots"]["integration"] == 1
    categories = {item["category"] for item in payload["engine_checks"]}
    assert "pass-rate" in categories
    assert "service-count" in categories


def test_build_script_candidates_targets_doctor_maintenance_and_security(tmp_path: Path) -> None:
    payload = {
        "warnings": [
            {"source": "doctor", "category": "policy", "severity": "high", "message": "drift"},
            {
                "source": "maintenance",
                "category": "tests",
                "severity": "medium",
                "message": "failed",
            },
            {"source": "security", "category": "SEC_X", "severity": "high", "message": "finding"},
        ],
        "engine_checks": [],
        "recommendations": [],
        "step_status": [{"name": "ruff_lint", "ok": False, "details": "failed"}],
    }

    candidates = eng._build_script_candidates(
        payload,
        out_dir=tmp_path,
        fix_root=tmp_path,
        auto_fix_results=[eng.AutoFixResult("SEC_X", "src/app.py", "fixed", "patched")],
    )

    assert [item.script_id for item in candidates] == [
        "gate_fast_fix_only",
        "doctor_refresh",
        "maintenance_fix",
        "security_triage_refresh",
    ]


def test_main_auto_run_scripts_records_results_and_score_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    (tmp_path / "doctor.json").write_text(
        json.dumps({"checks": {}, "recommendations": []}), encoding="utf-8"
    )
    (tmp_path / "maintenance.json").write_text(
        json.dumps(
            {
                "score": 60,
                "checks": [
                    {"name": "tests", "ok": False, "severity": "medium", "summary": "tests failed"}
                ],
                "recommendations": [],
            }
        ),
        encoding="utf-8",
    )
    _write_topology_artifact(tmp_path / "integration-topology.json")
    (tmp_path / "security-check.json").write_text(
        json.dumps({"findings": [{"rule_id": "SEC_X", "severity": "high", "path": "src/app.py"}]}),
        encoding="utf-8",
    )
    (tmp_path / "premium-gate.Quality.log").write_text("warning: drift\n", encoding="utf-8")

    calls: list[str] = []

    def fake_run_scripts(payload, *, out_dir, fix_root, auto_fix_results=None, max_scripts=4):
        assert out_dir == tmp_path
        assert fix_root == tmp_path
        calls.append("run")
        (tmp_path / "maintenance.json").write_text(
            json.dumps({"score": 100, "checks": [], "recommendations": []}), encoding="utf-8"
        )
        (tmp_path / "security-check.json").write_text(
            json.dumps({"findings": [], "totals": {"critical": 0, "high": 0}}), encoding="utf-8"
        )
        return (
            [
                eng.ScriptCandidate(
                    "maintenance_fix",
                    "refresh maintenance",
                    ["python", "-m", "sdetkit", "maintenance"],
                    ["maintenance.json"],
                )
            ],
            [
                eng.ScriptRunResult(
                    "maintenance_fix",
                    "passed",
                    0,
                    ["python", "-m", "sdetkit", "maintenance"],
                    "refresh maintenance",
                    ["maintenance.json"],
                    str(tmp_path / "premium-autofix.maintenance_fix.log"),
                    "script completed successfully",
                )
            ],
        )

    monkeypatch.setattr(eng, "run_smart_scripts", fake_run_scripts)

    rc = eng.main(
        [
            "--out-dir",
            str(tmp_path),
            "--fix-root",
            str(tmp_path),
            "--auto-run-scripts",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert calls == ["run"]
    assert payload["script_runs"][0]["script_id"] == "maintenance_fix"
    assert payload["smart_remediation"]["selected_scripts"] == ["maintenance_fix"]
    assert payload["smart_remediation"]["score_delta"] >= 0
    assert payload["counts"]["script_runs"] == 1
