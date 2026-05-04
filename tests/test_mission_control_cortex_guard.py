import json

from sdetkit import mission_control_cortex_guard


def _doctor_cortex(ok, diagnosis_count, prescription_count):
    return {
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
    }


def _write_ledger(tmp_path, samples):
    ledger = tmp_path / "mission-control-runs.jsonl"
    rows = []
    for index, sample in enumerate(samples, start=1):
        rows.append(
            json.dumps(
                {
                    "run_id": f"secret-run-{index}",
                    "timestamp": f"2026-05-04T0{index}:00:00Z",
                    "decision": "SHIP",
                    "risk_band": "low",
                    "artifact_dir": (tmp_path / f"secret-artifacts-{index}").as_posix(),
                    "doctor_cortex": _doctor_cortex(
                        sample.get("ok", True),
                        sample.get("diagnosis_count", 0),
                        sample.get("prescription_count", 0),
                    ),
                }
            )
        )
    ledger.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return ledger


def _assert_public_safe(text, tmp_path):
    forbidden = [
        "secret-run",
        "secret-artifacts",
        "2026-05-04T",
        tmp_path.as_posix(),
        "samples",
        "artifact_dir",
        "run_id",
        "timestamp",
        "diagnosis": {
            "status",
        },
    ]
    for token in forbidden:
        assert str(token) not in text


def test_guard_reports_insufficient_data_for_zero_doctor_cortex_runs(tmp_path):
    ledger = _write_ledger(tmp_path, [])

    payload = mission_control_cortex_guard.build_guard_payload(ledger)

    assert payload["schema_version"] == "sdetkit.mission_control.doctor_cortex_guard.v1"
    assert payload["ok"] is True
    assert payload["status"] == "insufficient_data"
    assert payload["runs"] == 0
    assert payload["doctor_cortex_runs"] == 0
    assert payload["latest_diagnosis_count"] == 0
    assert payload["previous_diagnosis_count"] == 0
    assert payload["diagnosis_delta"] == 0
    assert payload["latest_prescription_count"] == 0
    assert payload["previous_prescription_count"] == 0
    assert payload["prescription_delta"] == 0


def test_guard_reports_insufficient_data_for_one_doctor_cortex_run(tmp_path):
    ledger = _write_ledger(
        tmp_path,
        [
            {
                "diagnosis_count": 2,
                "prescription_count": 1,
            }
        ],
    )

    payload = mission_control_cortex_guard.build_guard_payload(ledger)

    assert payload["ok"] is True
    assert payload["status"] == "insufficient_data"
    assert payload["runs"] == 1
    assert payload["doctor_cortex_runs"] == 1
    assert payload["latest_diagnosis_count"] == 2
    assert payload["previous_diagnosis_count"] == 0
    assert payload["diagnosis_delta"] == 0
    assert payload["latest_prescription_count"] == 1
    assert payload["previous_prescription_count"] == 0
    assert payload["prescription_delta"] == 0


def test_guard_passes_when_latest_counts_are_stable(tmp_path):
    ledger = _write_ledger(
        tmp_path,
        [
            {"diagnosis_count": 1, "prescription_count": 1},
            {"diagnosis_count": 1, "prescription_count": 1},
        ],
    )

    payload = mission_control_cortex_guard.build_guard_payload(ledger)

    assert payload["ok"] is True
    assert payload["status"] == "pass"
    assert payload["latest_diagnosis_count"] == 1
    assert payload["previous_diagnosis_count"] == 1
    assert payload["diagnosis_delta"] == 0
    assert payload["latest_prescription_count"] == 1
    assert payload["previous_prescription_count"] == 1
    assert payload["prescription_delta"] == 0


def test_guard_passes_when_latest_counts_improve(tmp_path):
    ledger = _write_ledger(
        tmp_path,
        [
            {"diagnosis_count": 4, "prescription_count": 3},
            {"diagnosis_count": 1, "prescription_count": 0},
        ],
    )

    payload = mission_control_cortex_guard.build_guard_payload(ledger)

    assert payload["ok"] is True
    assert payload["status"] == "pass"
    assert payload["diagnosis_delta"] == -3
    assert payload["prescription_delta"] == -3


def test_guard_warns_when_regression_is_within_threshold(tmp_path):
    ledger = _write_ledger(
        tmp_path,
        [
            {"diagnosis_count": 1, "prescription_count": 0},
            {"diagnosis_count": 2, "prescription_count": 1},
        ],
    )

    payload = mission_control_cortex_guard.build_guard_payload(
        ledger,
        max_diagnosis_regression=1,
        max_prescription_regression=1,
    )

    assert payload["ok"] is True
    assert payload["status"] == "warn"
    assert payload["diagnosis_delta"] == 1
    assert payload["prescription_delta"] == 1
    assert payload["max_diagnosis_regression"] == 1
    assert payload["max_prescription_regression"] == 1


def test_guard_fails_when_regression_exceeds_threshold(tmp_path):
    ledger = _write_ledger(
        tmp_path,
        [
            {"diagnosis_count": 1, "prescription_count": 0},
            {"diagnosis_count": 3, "prescription_count": 1},
        ],
    )

    payload = mission_control_cortex_guard.build_guard_payload(
        ledger,
        max_diagnosis_regression=1,
        max_prescription_regression=2,
    )

    assert payload["ok"] is False
    assert payload["status"] == "fail"
    assert payload["diagnosis_delta"] == 2
    assert payload["prescription_delta"] == 1


def test_guard_formats_are_public_safe(tmp_path):
    ledger = _write_ledger(
        tmp_path,
        [
            {"diagnosis_count": 1, "prescription_count": 0},
            {"diagnosis_count": 2, "prescription_count": 1},
        ],
    )
    payload = mission_control_cortex_guard.build_guard_payload(
        ledger,
        max_diagnosis_regression=1,
        max_prescription_regression=1,
    )

    text = mission_control_cortex_guard.render_text(payload)
    markdown = mission_control_cortex_guard.render_markdown(payload)
    encoded = json.dumps(payload, sort_keys=True)

    assert "schema_version=sdetkit.mission_control.doctor_cortex_guard.v1" in text
    assert "status=warn" in text
    assert "# Mission Control Doctor Cortex Guard" in markdown
    assert "Diagnosis delta: 1" in markdown
    assert "recommendation" in encoded
    _assert_public_safe(text, tmp_path)
    _assert_public_safe(markdown, tmp_path)
    _assert_public_safe(encoded, tmp_path)


def test_guard_cli_writes_json_file_and_stdout_text(tmp_path, capsys):
    ledger = _write_ledger(
        tmp_path,
        [
            {"diagnosis_count": 3, "prescription_count": 2},
            {"diagnosis_count": 1, "prescription_count": 0},
        ],
    )
    output = tmp_path / "guard.json"

    rc = mission_control_cortex_guard.main(
        [
            "--ledger-path",
            str(ledger),
            "--format",
            "json",
            "--out",
            str(output),
        ]
    )

    assert rc == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["ok"] is True
    assert payload["diagnosis_delta"] == -2
    assert payload["prescription_delta"] == -2
    _assert_public_safe(json.dumps(payload), tmp_path)

    rc = mission_control_cortex_guard.main(["--ledger-path", str(ledger), "--format", "text"])

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "status=pass" in stdout
    assert "diagnosis_delta=-2" in stdout
    _assert_public_safe(stdout, tmp_path)
