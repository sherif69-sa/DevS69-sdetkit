from __future__ import annotations

import json
from pathlib import Path

from sdetkit.public_command_surface_report import (
    SCHEMA_VERSION,
    build_public_command_surface_report,
    write_artifacts,
)


def test_public_command_surface_report_classifies_stable_advanced_and_hidden_commands() -> None:
    payload = build_public_command_surface_report(".")

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["report_status"] == "review_required"
    assert payload["command_count"] > 50
    assert payload["stable_command_count"] >= 1
    assert payload["hidden_command_count"] >= 1

    commands = {item["command"]: item for item in payload["commands"]}

    assert commands["start"]["tier"] == "public_stable"
    assert commands["security"]["tier"] == "public_stable"
    assert commands["evidence"]["tier"] == "public_stable"
    assert commands["contract"]["tier"] == "public_stable"

    assert commands["adoption-surface"]["tier"] == "advanced_supported"
    assert commands["release-anti-hijack-threat-model"]["tier"] == "hidden_internal"
    assert commands["product-maturity-radar"]["tier"] == "hidden_internal"

    assert payload["rules"] == {
        "read_only": True,
        "public_behavior_changed": False,
        "hidden_commands_exposed": False,
        "review_first": True,
        "safe_to_patch": False,
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_public_command_surface_report_writes_json_and_markdown(tmp_path: Path) -> None:
    out = tmp_path / "reports" / "public-command-surface-report.json"

    payload = write_artifacts(root=".", out=out)

    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()

    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == SCHEMA_VERSION
    assert persisted["command_count"] == payload["command_count"]

    rendered = markdown.read_text(encoding="utf-8")
    assert "# SDETKit public command surface report" in rendered
    assert "## Stable public commands" in rendered
    assert "`start`" in rendered
    assert "## Hidden/internal commands" in rendered
    assert "`product-maturity-radar`" in rendered
    assert "automation_allowed: false" in rendered


def test_public_command_surface_report_public_cli_dispatch(tmp_path: Path, capsys) -> None:
    from sdetkit.cli import main as cli_main

    out = tmp_path / "reports" / "public-command-surface-report.json"

    rc = cli_main(
        [
            "public-command-surface-report",
            "--root",
            ".",
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "# SDETKit public command surface report" in stdout
    assert "stable_command_count:" in stdout
    assert "hidden_command_count:" in stdout
    assert "automation_allowed: false" in stdout
    assert out.is_file()
    assert out.with_suffix(".md").is_file()


def test_public_command_surface_report_stays_hidden_from_default_help() -> None:
    from sdetkit import cli

    default_help = cli._build_root_parser()[0].format_help()
    hidden_help = cli._build_root_parser(show_hidden_commands=True)[0].format_help()

    assert "public-command-surface-report" not in default_help
    assert "public-command-surface-report" in hidden_help
