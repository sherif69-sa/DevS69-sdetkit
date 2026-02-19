import json

from sdetkit import cli, onboarding


def test_onboarding_default_text_lists_all_roles(capsys):
    rc = onboarding.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Day 1 onboarding paths" in out
    assert "SDET / QA engineer" in out
    assert "Platform / DevOps engineer" in out
    assert "Security / compliance lead" in out
    assert "Engineering manager / tech lead" in out
    assert "Day 5 platform onboarding snippets" in out


def test_onboarding_role_markdown_focuses_single_role(capsys):
    rc = onboarding.main(["--role", "platform", "--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Platform / DevOps engineer" in out
    assert "sdetkit repo audit --format markdown" in out
    assert "SDET / QA engineer" not in out


def test_onboarding_json_is_machine_readable(capsys):
    rc = onboarding.main(["--role", "security", "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "security" in data
    assert data["security"]["first_command"] == "sdetkit security --format markdown"
    assert "windows" in data["day5_platform_setup"]


def test_onboarding_platform_filter_renders_selected_os(capsys):
    rc = onboarding.main(["--platform", "windows", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Windows (PowerShell)" in out
    assert "Activate.ps1" in out
    assert "Linux (bash)" not in out


def test_main_cli_dispatches_onboarding(capsys):
    rc = cli.main(["onboarding", "--role", "manager", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Engineering manager / tech lead" in out
    assert "docs/automation-os.md" in out


def test_onboarding_writes_output_file(tmp_path, capsys):
    out_file = tmp_path / "onboarding.md"
    rc = onboarding.main(["--format", "markdown", "--output", str(out_file)])
    assert rc == 0
    stdout = capsys.readouterr().out
    written = out_file.read_text(encoding="utf-8")
    assert "| Role | First command | Next action |" in written
    assert written.rstrip("\n") == stdout.rstrip("\n")
