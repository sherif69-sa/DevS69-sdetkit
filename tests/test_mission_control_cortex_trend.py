import json

from sdetkit import mission_control_cortex_trend


def _write_bundle(root, name, *, ok, diagnosis_count, prescription_count):
    out_dir = root / name
    out_dir.mkdir()
    bundle = {
        "schema_version": "1",
        "decision": "SHIP" if ok else "SHIP_WITH_FINDINGS",
        "risk_band": "low" if ok else "medium",
        "doctor_cortex": {
            "enabled": True,
            "ok": ok,
            "diagnosis": {
                "status": "pass" if ok else "watch",
                "severity": "low" if ok else "medium",
                "diagnosis_count": diagnosis_count,
            },
            "prescriptions": {
                "status": "pass" if ok else "action_required",
                "severity": "low" if ok else "medium",
                "prescription_count": prescription_count,
            },
        },
    }
    (out_dir / "mission-control.json").write_text(json.dumps(bundle), encoding="utf-8")
    return out_dir


def test_build_trend_payload_loads_doctor_cortex_from_artifact_dirs(tmp_path):
    first = _write_bundle(tmp_path, "one", ok=False, diagnosis_count=3, prescription_count=2)
    second = _write_bundle(tmp_path, "two", ok=True, diagnosis_count=1, prescription_count=0)
    ledger = tmp_path / "runs.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "run_id": "one",
                        "timestamp": "2026-05-04T00:00:00Z",
                        "decision": "SHIP_WITH_FINDINGS",
                        "risk_band": "medium",
                        "artifact_dir": first.as_posix(),
                    }
                ),
                json.dumps(
                    {
                        "run_id": "two",
                        "timestamp": "2026-05-04T01:00:00Z",
                        "decision": "SHIP",
                        "risk_band": "low",
                        "artifact_dir": second.as_posix(),
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mission_control_cortex_trend.build_trend_payload(ledger)

    assert payload["schema_version"] == "sdetkit.mission_control.doctor_cortex_trend.v1"
    assert payload["source"]["ledger_path"] == "[REDACTED]"
    assert payload["runs"] == 2
    assert payload["doctor_cortex_runs"] == 2
    assert payload["doctor_cortex_ok"] == 1
    assert payload["doctor_cortex_not_ok"] == 1
    assert payload["latest_run_id"] == "two"
    assert payload["latest_doctor_cortex_ok"] is True
    assert payload["latest_diagnosis_count"] == 1
    assert payload["latest_prescription_count"] == 0
    assert payload["max_diagnosis_count"] == 3
    assert payload["max_prescription_count"] == 2
    assert payload["diagnosis_trend"] == "improving"
    assert payload["prescription_trend"] == "improving"


def test_build_trend_payload_uses_embedded_ledger_doctor_cortex(tmp_path):
    ledger = tmp_path / "runs.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "run_id": "embedded",
                "timestamp": "2026-05-04T00:00:00Z",
                "decision": "SHIP",
                "risk_band": "low",
                "doctor_cortex": {
                    "enabled": True,
                    "ok": True,
                    "diagnosis": {
                        "status": "pass",
                        "severity": "low",
                        "diagnosis_count": 0,
                    },
                    "prescriptions": {
                        "status": "pass",
                        "severity": "low",
                        "prescription_count": 0,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mission_control_cortex_trend.build_trend_payload(ledger)

    assert payload["doctor_cortex_runs"] == 1
    assert payload["latest_run_id"] == "embedded"
    assert payload["latest_diagnosis_count"] == 0
    assert payload["latest_prescription_count"] == 0
    assert payload["diagnosis_trend"] == "insufficient_data"


def test_text_and_markdown_rendering_are_summary_only(tmp_path):
    out_dir = _write_bundle(tmp_path, "one", ok=False, diagnosis_count=2, prescription_count=1)
    ledger = tmp_path / "runs.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "run_id": "one",
                "timestamp": "2026-05-04T00:00:00Z",
                "decision": "SHIP_WITH_FINDINGS",
                "risk_band": "medium",
                "artifact_dir": out_dir.as_posix(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    payload = mission_control_cortex_trend.build_trend_payload(ledger)

    text = mission_control_cortex_trend.render_text(payload)
    markdown = mission_control_cortex_trend.render_markdown(payload)

    assert "doctor_cortex_runs=1" in text
    assert "latest_diagnosis_count=2" in text
    assert "# Mission Control Doctor Cortex Trend" in markdown
    assert "Latest prescription count: 1" in markdown
    assert out_dir.as_posix() not in text
    assert out_dir.as_posix() not in markdown


def test_cli_writes_json_and_text(tmp_path, capsys):
    out_dir = _write_bundle(tmp_path, "one", ok=True, diagnosis_count=0, prescription_count=0)
    ledger = tmp_path / "runs.jsonl"
    output = tmp_path / "trend.json"
    ledger.write_text(
        json.dumps(
            {
                "run_id": "one",
                "timestamp": "2026-05-04T00:00:00Z",
                "decision": "SHIP",
                "risk_band": "low",
                "artifact_dir": out_dir.as_posix(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rc = mission_control_cortex_trend.main(
        ["--ledger-path", str(ledger), "--format", "json", "--out", str(output)]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["doctor_cortex_runs"] == 1

    rc = mission_control_cortex_trend.main(["--ledger-path", str(ledger)])
    assert rc == 0
    assert "doctor_cortex_runs=1" in capsys.readouterr().out
