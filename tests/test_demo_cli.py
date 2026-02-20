import json

from sdetkit import cli, demo


def test_demo_default_text_contains_all_steps(capsys):
    rc = demo.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Day 2 demo path" in out
    assert "Health check" in out
    assert "Repository audit" in out
    assert "Security baseline" in out
    assert "Closeout hints" in out


def test_demo_markdown_has_copy_paste_commands(capsys):
    rc = demo.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| Step | Command | Expected output snippets | Outcome |" in out
    assert "python -m sdetkit doctor --format text" in out
    assert "## Closeout hints" in out


def test_demo_json_is_machine_readable(capsys):
    rc = demo.main(["--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "day2-demo-path"
    assert len(payload["steps"]) == 3
    assert payload["execution"] == []
    assert payload["sla"] == {}
    assert payload["hints"]


def test_cli_dispatches_demo(capsys):
    rc = cli.main(["demo", "--format", "text"])
    assert rc == 0
    assert "Closeout hints" in capsys.readouterr().out


def test_demo_writes_output_file(tmp_path, capsys):
    out_file = tmp_path / "demo.md"
    rc = demo.main(["--format", "markdown", "--output", str(out_file)])
    assert rc == 0
    stdout = capsys.readouterr().out
    written = out_file.read_text(encoding="utf-8")
    assert "# Day 2 demo path" in written
    assert written.rstrip("\n") == stdout.rstrip("\n")


def test_demo_execute_success(monkeypatch, capsys):
    def fake_run(_command: str, _timeout: float):
        return (
            0,
            """doctor score:
recommendations:
Repo audit:
Result:
security scan:
top findings:
""",
            "",
            0.2,
        )

    monkeypatch.setattr(demo, "_run_command", fake_run)
    rc = demo.main(["--execute", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert len(payload["execution"]) == 3
    assert all(item["status"] == "pass" for item in payload["execution"])
    assert payload["sla"]["within_target"] is True


def test_demo_execute_sla_can_fail(monkeypatch, capsys):
    def fake_run(_command: str, _timeout: float):
        return (
            0,
            "doctor score:\nrecommendations:\nRepo audit:\nResult:\nsecurity scan:\ntop findings:\n",
            "",
            30.0,
        )

    monkeypatch.setattr(demo, "_run_command", fake_run)
    rc = demo.main(["--execute", "--target-seconds", "60", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["sla"]["total_duration_seconds"] == 90.0
    assert payload["sla"]["within_target"] is False


def test_demo_execute_fail_fast_stops(monkeypatch, capsys):
    calls = {"count": 0}

    def fake_run(_command: str, _timeout: float):
        calls["count"] += 1
        return 1, "", "boom", 0.1

    monkeypatch.setattr(demo, "_run_command", fake_run)
    rc = demo.main(["--execute", "--fail-fast", "--format", "text"])
    out = capsys.readouterr().out
    assert rc == 1
    assert calls["count"] == 1
    assert "missing snippets" in out
