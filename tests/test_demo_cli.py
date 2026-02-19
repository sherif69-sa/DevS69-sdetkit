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


def test_demo_markdown_has_copy_paste_commands(capsys):
    rc = demo.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| Step | Command | Expected output snippets | Outcome |" in out
    assert "python -m sdetkit doctor --format text" in out


def test_demo_json_is_machine_readable(capsys):
    rc = demo.main(["--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "day2-demo-path"
    assert len(payload["steps"]) == 3


def test_cli_dispatches_demo(capsys):
    rc = cli.main(["demo", "--format", "text"])
    assert rc == 0
    assert "Tip: copy this plan" in capsys.readouterr().out


def test_demo_writes_output_file(tmp_path, capsys):
    out_file = tmp_path / "demo.md"
    rc = demo.main(["--format", "markdown", "--output", str(out_file)])
    assert rc == 0
    stdout = capsys.readouterr().out
    written = out_file.read_text(encoding="utf-8")
    assert "# Day 2 demo path" in written
    assert written.rstrip("\n") == stdout.rstrip("\n")
