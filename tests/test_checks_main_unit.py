from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sdetkit.checks import main as checks_main
from sdetkit.checks.results import CheckRecord, build_final_verdict


def _fake_registry():
    return SimpleNamespace(snapshot=lambda: ())


def test_load_records_and_artifact_paths(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "id": "lint",
                "title": "Lint",
                "status": "passed",
                "blocking": True,
                "reason": "",
                "cmd": "ruff check .",
                "advisory": ["ok"],
                "log": "lint.log",
                "evidence_paths": ["build/x.json"],
                "elapsed_s": 1.25,
                "metadata": {"k": "v"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    records = checks_main._load_records_from_ledger(ledger)
    assert len(records) == 1
    assert records[0].id == "lint"
    assert records[0].command == "ruff check ."

    ns = SimpleNamespace(
        json_output=None,
        markdown_output=None,
        fix_plan_output=None,
        risk_summary_output=None,
        evidence_output=None,
        run_report_output=None,
    )
    paths = checks_main._artifact_paths(ns, tmp_path)
    assert paths.verdict_json.name.endswith(".json")


def test_checks_main_plan_and_render_ledger(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(checks_main, "default_registry", _fake_registry)

    selected = [SimpleNamespace(id="lint", target_mode="full")]
    skipped = [SimpleNamespace(id="mypy", reason="not needed")]
    fake_plan = SimpleNamespace(
        profile="adaptive",
        requested_profile="adaptive",
        planner_selected=True,
        selected_checks=selected,
        skipped_checks=skipped,
        notes=("n1",),
        changed_files=("a.py",),
        changed_areas=("src",),
        adaptive_reason="targeted",
    )
    monkeypatch.setattr(checks_main.CheckPlanner, "plan", lambda self, *_a, **_k: fake_plan)

    rc = checks_main.main(["plan", "--profile", "adaptive", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "adaptive"
    assert payload["selected_checks"][0]["id"] == "lint"

    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps({"id": "lint", "title": "Lint", "status": "passed"}) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        checks_main,
        "render_record_artifacts",
        lambda **_k: {"verdict": {"ok": True, "verdict_contract": "v2", "recommendation": "go"}},
    )
    rc = checks_main.main(
        [
            "render-ledger",
            "--profile",
            "standard",
            "--ledger",
            str(ledger),
            "--format",
            "json",
            "--emit-legacy-summary",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "verdict_contract" in out


def test_checks_main_run_path(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(checks_main, "default_registry", _fake_registry)
    fake_plan = SimpleNamespace(
        profile="quick",
        requested_profile="quick",
        planner_selected=False,
        selected_checks=[],
        skipped_checks=[],
        notes=(),
        changed_files=(),
        changed_areas=(),
        adaptive_reason=None,
    )
    monkeypatch.setattr(checks_main.CheckPlanner, "plan", lambda self, *_a, **_k: fake_plan)

    class _Report:
        verdict = SimpleNamespace(ok=True)

        def as_dict(self):
            return {
                "ok": True,
                "verdict_contract": "sdetkit.final-verdict.v2",
                "recommendation": "ready-for-merge-review",
                "checks_run": [],
                "checks_skipped": [],
                "blocking_failures": [],
                "advisory_findings": [],
                "confidence_level": "low (smoke-only)",
                "metadata": {},
            }

    monkeypatch.setattr(checks_main.CheckRunner, "run", lambda self, *_a, **_k: _Report())
    monkeypatch.setattr(checks_main, "render_report_artifacts", lambda *args, **kwargs: None)

    rc = checks_main.main(
        ["run", "--profile", "quick", "--format", "text", "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert "[quality] final verdict contract" in capsys.readouterr().out


def test_results_final_verdict_rendering() -> None:
    record = CheckRecord(id="lint", title="Lint", status="passed", advisory=("a",))
    verdict = build_final_verdict(
        profile="quick", checks=[record], metadata={"execution": {"mode": "seq", "workers": 1}}
    )
    assert verdict.ok is True
    assert "Final Verdict" in verdict.to_markdown()
    assert '"verdict_contract"' in verdict.to_json()


def test_checks_main_text_and_emit_paths(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(checks_main, "default_registry", _fake_registry)
    selected = [SimpleNamespace(id="lint", target_mode="targeted")]
    skipped = [SimpleNamespace(id="docs", reason="not selected")]
    fake_plan = SimpleNamespace(
        profile="adaptive",
        requested_profile="quick",
        planner_selected=True,
        selected_checks=selected,
        skipped_checks=skipped,
        notes=("n1",),
        changed_files=("x.py",),
        changed_areas=("source",),
        adaptive_reason="delta-aware",
    )
    monkeypatch.setattr(checks_main.CheckPlanner, "plan", lambda self, *_a, **_k: fake_plan)
    rc = checks_main.main(["plan", "--profile", "adaptive", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "adaptive reason: delta-aware" in out
    assert "- lint [targeted]" in out

    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        "\n" + json.dumps({"id": "lint", "title": "Lint", "status": "failed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        checks_main,
        "render_record_artifacts",
        lambda **_k: {
            "verdict": {
                "ok": False,
                "profile": {"used": "strict"},
                "verdict_contract": "v2",
                "recommendation": "stop",
                "blocking_failures": ["lint"],
                "advisory_findings": ["docs"],
            }
        },
    )
    rc = checks_main.main(
        [
            "render-ledger",
            "--profile",
            "strict",
            "--ledger",
            str(ledger),
            "--format",
            "text",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert rc == 1
    assert "[quality] blocking failures:" in capsys.readouterr().out

    class _Report:
        verdict = SimpleNamespace(ok=True)

        def as_dict(self):
            return {
                "ok": True,
                "verdict_contract": "sdetkit.final-verdict.v2",
                "recommendation": "ready-for-merge-review",
                "checks_run": [],
                "checks_skipped": [],
                "blocking_failures": [],
                "advisory_findings": [],
                "confidence_level": "low (smoke-only)",
                "metadata": {},
            }

    monkeypatch.setattr(checks_main.CheckRunner, "run", lambda self, *_a, **_k: _Report())
    monkeypatch.setattr(checks_main, "render_report_artifacts", lambda *_a, **_k: None)
    rc = checks_main.main(
        [
            "run",
            "--profile",
            "quick",
            "--format",
            "json",
            "--emit-legacy-summary",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert '"verdict_contract"' in out
    assert "[quality] final verdict contract:" in out
