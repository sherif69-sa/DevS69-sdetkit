from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adoption


def test_adoption_cli_json_output_with_missing_inputs(tmp_path: Path, capsys) -> None:
    rc = adoption.main(
        [
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fit"] == "unknown"
    assert payload["decision"] == "NO-DATA"
    assert payload["decision_context"]["policy_profile"] == "balanced"
    assert payload["decision_context"]["fit_artifact_present"] is False
    assert payload["decision_context"]["summary_artifact_present"] is False


def test_adoption_cli_writes_markdown(tmp_path: Path, capsys) -> None:
    out = tmp_path / "adoption.md"
    rc = adoption.main(
        [
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "md",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    _ = capsys.readouterr()
    assert out.exists()
    rendered = out.read_text(encoding="utf-8")
    assert "# Adoption follow-up" in rendered
    assert "Why now:" in rendered
    assert "Rationale:" in rendered
    assert "Policy profile:" in rendered


def test_adoption_cli_history_and_rollup(tmp_path: Path, capsys) -> None:
    history = tmp_path / "adoption-history.jsonl"
    rollup = tmp_path / "adoption-history-rollup.json"
    rc = adoption.main(
        [
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "json",
            "--history",
            str(history),
            "--history-rollup-out",
            str(rollup),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "generated_at" in payload
    assert history.exists()
    assert rollup.exists()
    rollup_payload = json.loads(rollup.read_text(encoding="utf-8"))
    assert rollup_payload["schema_version"] == "sdetkit.adoption_followup_history.v1"
    assert rollup_payload["total_runs"] >= 1
    assert "escalation_recommended" in rollup_payload
    assert rollup_payload["escalation_reason"] in {"none", "consecutive_no_ship", "high_p0_rate"}
    assert rollup_payload["thresholds"]["escalation_consecutive_no_ship"] == 2


def test_adoption_cli_rollup_escalation_on_consecutive_no_ship(tmp_path: Path, capsys) -> None:
    summary = tmp_path / "summary.json"
    history = tmp_path / "history.jsonl"
    rollup = tmp_path / "rollup.json"
    summary.write_text(
        json.dumps({"decision": "NO-SHIP", "validation_errors": [], "schema_version": "x"}),
        encoding="utf-8",
    )
    for _ in range(2):
        rc = adoption.main(
            [
                "--fit",
                str(tmp_path / "missing-fit.json"),
                "--summary",
                str(summary),
                "--format",
                "json",
                "--history",
                str(history),
                "--history-rollup-out",
                str(rollup),
            ]
        )
        assert rc == 0
        _ = capsys.readouterr()
    rollup_payload = json.loads(rollup.read_text(encoding="utf-8"))
    assert rollup_payload["max_consecutive_no_ship"] >= 2
    assert rollup_payload["escalation_recommended"] is True
    assert rollup_payload["escalation_reason"] == "consecutive_no_ship"


def test_adoption_cli_custom_thresholds(tmp_path: Path, capsys) -> None:
    history = tmp_path / "history.jsonl"
    rollup = tmp_path / "rollup.json"
    rc = adoption.main(
        [
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "json",
            "--history",
            str(history),
            "--history-rollup-out",
            str(rollup),
            "--escalation-consecutive-no-ship",
            "5",
            "--escalation-min-runs",
            "1",
            "--escalation-min-p0-rate",
            "0.1",
        ]
    )
    assert rc == 0
    _ = capsys.readouterr()
    rollup_payload = json.loads(rollup.read_text(encoding="utf-8"))
    assert rollup_payload["thresholds"]["escalation_consecutive_no_ship"] == 5
    assert rollup_payload["thresholds"]["escalation_min_runs"] == 1
    assert rollup_payload["thresholds"]["escalation_min_p0_rate"] == 0.1


def test_adoption_cli_policy_profile_defaults(tmp_path: Path, capsys) -> None:
    history = tmp_path / "history.jsonl"
    rollup = tmp_path / "rollup.json"
    rc = adoption.main(
        [
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "json",
            "--history",
            str(history),
            "--history-rollup-out",
            str(rollup),
            "--policy-profile",
            "conservative",
        ]
    )
    assert rc == 0
    _ = capsys.readouterr()
    rollup_payload = json.loads(rollup.read_text(encoding="utf-8"))
    assert rollup_payload["thresholds"]["escalation_consecutive_no_ship"] == 3
    assert rollup_payload["thresholds"]["escalation_min_runs"] == 4
    assert rollup_payload["thresholds"]["escalation_min_p0_rate"] == 0.7
    latest = json.loads(history.read_text(encoding="utf-8").strip().splitlines()[-1])
    ctx = latest["decision_context"]["escalation_thresholds"]
    assert ctx["escalation_consecutive_no_ship"] == 3
    assert ctx["escalation_min_runs"] == 4
    assert ctx["escalation_min_p0_rate"] == 0.7
