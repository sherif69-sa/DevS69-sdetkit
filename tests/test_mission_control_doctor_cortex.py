import json

from sdetkit import mission_control


def _fake_doctor_cortex(repo, out_dir):
    diagnosis_path = out_dir / "doctor-cortex-diagnosis.json"
    prescriptions_path = out_dir / "doctor-cortex-prescriptions.json"
    diagnosis_path.write_text(
        '{"schema_version":"sdetkit.doctor.diagnosis.v1"}\n', encoding="utf-8"
    )
    prescriptions_path.write_text(
        '{"schema_version":"sdetkit.doctor.prescriptions.v1"}\n',
        encoding="utf-8",
    )
    return {
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
        "artifacts": [
            {
                "label": "Doctor Cortex diagnosis contract",
                "kind": "json",
                "path": diagnosis_path.as_posix(),
            },
            {
                "label": "Doctor Cortex prescription contract",
                "kind": "json",
                "path": prescriptions_path.as_posix(),
            },
        ],
    }


def test_mission_control_run_includes_doctor_cortex(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    monkeypatch.setattr(mission_control, "_collect_doctor_cortex", _fake_doctor_cortex)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--doctor-cortex",
            "--no-ledger",
        ]
    )

    assert rc == 0

    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))

    assert bundle["doctor_cortex"] == {
        "enabled": True,
        "ok": True,
        "diagnosis_status": "pass",
        "diagnosis_count": 0,
        "prescription_status": "pass",
        "prescription_count": 0,
    }

    labels = {artifact["label"] for artifact in bundle["artifacts"]}
    assert "Doctor Cortex diagnosis contract" in labels
    assert "Doctor Cortex prescription contract" in labels

    markdown = (out_dir / "mission-control.md").read_text(encoding="utf-8")
    assert "## Doctor Cortex" in markdown
    assert "Details omitted from markdown artifact" in markdown


def test_mission_control_summarize_prints_doctor_cortex(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    monkeypatch.setattr(mission_control, "_collect_doctor_cortex", _fake_doctor_cortex)

    mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--doctor-cortex",
            "--no-ledger",
        ]
    )
    capsys.readouterr()

    rc = mission_control.main(["summarize", "--bundle", str(out_dir / "mission-control.json")])

    assert rc == 0

    output = capsys.readouterr().out
    assert "doctor_cortex_ok=true" in output
    assert "doctor_cortex_diagnosis_count=0" in output
    assert "doctor_cortex_prescription_count=0" in output


def test_mission_control_report_includes_doctor_cortex_section(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    report_path = tmp_path / "report.md"

    monkeypatch.setattr(mission_control, "_collect_doctor_cortex", _fake_doctor_cortex)

    mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--doctor-cortex",
            "--no-ledger",
        ]
    )

    rc = mission_control.main(
        [
            "report",
            "--bundle",
            str(out_dir / "mission-control.json"),
            "--out",
            str(report_path),
        ]
    )

    assert rc == 0

    report = report_path.read_text(encoding="utf-8")
    assert "## Doctor Cortex" in report
    assert "Diagnosis status: pass" in report
    assert "Prescription status: pass" in report
