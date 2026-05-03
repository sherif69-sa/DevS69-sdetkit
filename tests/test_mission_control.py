import json

import pytest

from sdetkit import cli, mission_control


def test_mission_control_run_writes_json_and_markdown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    rc = mission_control.main(["run", "--repo", str(repo), "--out-dir", str(out_dir)])

    assert rc == 0

    bundle_path = out_dir / "mission-control.json"
    brief_path = out_dir / "mission-control.md"

    assert bundle_path.exists()
    assert brief_path.exists()

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    assert bundle["schema_version"] == "1"
    assert bundle["ok"] is True
    assert bundle["decision"] == "SHIP"
    assert bundle["risk_band"] == "low"
    assert bundle["repo"]["path"] == repo.resolve().as_posix()
    assert bundle["repo"]["branch"] == "unknown"
    assert bundle["repo"]["commit"] == "unknown"
    assert bundle["repo"]["dirty"] is False
    assert [step["id"] for step in bundle["steps"]] == [
        "gate_fast",
        "gate_release",
        "doctor",
        "review",
        "readiness",
        "release_room",
    ]
    assert bundle["steps"][-1]["status"] == "planned"
    assert bundle["findings"] == []
    assert [artifact["path"] for artifact in bundle["artifacts"]] == [
        (out_dir.resolve() / "mission-control.json").as_posix(),
        (out_dir.resolve() / "mission-control.md").as_posix(),
    ]

    brief = brief_path.read_text(encoding="utf-8")
    assert "# Mission Control" in brief
    assert "Decision: SHIP" in brief
    assert "gate_fast" in brief
    assert "release_room" in brief


def test_mission_control_summarize_prints_stable_counts(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    assert mission_control.main(["run", "--repo", str(repo), "--out-dir", str(out_dir)]) == 0

    capsys.readouterr()

    rc = mission_control.main(["summarize", "--bundle", str(out_dir / "mission-control.json")])

    assert rc == 0

    output = capsys.readouterr().out
    assert "decision=SHIP" in output
    assert "risk_band=low" in output
    assert "steps=6" in output
    assert "findings=0" in output


def test_mission_control_schema_lists_required_top_level_keys(capsys):
    rc = mission_control.main(["schema"])

    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "1"
    assert "decision" in payload["required_top_level_keys"]
    assert "next_actions" in payload["required_top_level_keys"]


def test_root_cli_dispatches_mission_control(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    rc = cli.main(["mission-control", "run", "--repo", str(repo), "--out-dir", str(out_dir)])

    assert rc == 0
    assert (out_dir / "mission-control.json").exists()
    assert (out_dir / "mission-control.md").exists()

def test_root_cli_forwards_mission_control_help(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["mission-control", "--help"])

    assert exc.value.code == 0

    output = capsys.readouterr().out
    assert "sdetkit mission-control" in output
    assert "run" in output
    assert "summarize" in output
    assert "schema" in output
