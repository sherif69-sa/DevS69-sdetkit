from __future__ import annotations

import json
from pathlib import Path

from sdetkit.public_command_surface_report import (
    SCHEMA_VERSION,
    build_public_command_surface_report,
    check_public_command_surface_report_freshness,
    public_command_surface_input_provenance,
    validate_public_command_surface_report_freshness,
    write_artifacts,
)


def test_public_command_surface_report_classifies_stable_advanced_and_hidden_commands() -> None:
    payload = build_public_command_surface_report(".")

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["report_status"] == "review_required"
    assert payload["command_count"] > 50
    assert payload["stable_command_count"] >= 1
    assert payload["hidden_command_count"] >= 1
    assert payload["stable_public_commands"] == payload["stable_commands"]
    assert payload["hidden_internal_commands"] == payload["hidden_commands"]
    assert payload["review_first"] is True
    assert payload["safe_to_patch"] is False
    provenance = payload["input_provenance"]
    assert provenance["digest_algorithm"] == "sha256"
    assert len(provenance["input_digest"]) == 64
    assert provenance["input_count"] == 3
    assert provenance["source_file_count"] == 1
    assert provenance["generator_schema_version"] == SCHEMA_VERSION
    assert provenance["generator_source"] == "src/sdetkit/public_command_surface_report.py"
    assert provenance["source_file"] == "src/sdetkit/_legacy_cli.py"

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
    assert "input_digest:" in rendered
    assert "digest_algorithm: `sha256`" in rendered
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

    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["stable_public_commands"] == document["stable_commands"]
    assert document["hidden_internal_commands"] == document["hidden_commands"]
    assert document["review_first"] is True
    assert document["safe_to_patch"] is False
    assert document["rules"]["public_behavior_changed"] is False
    assert document["rules"]["hidden_commands_exposed"] is False


def test_public_command_surface_report_stays_hidden_from_default_help() -> None:
    from sdetkit import cli

    default_help = cli._build_root_parser()[0].format_help()
    hidden_help = cli._build_root_parser(show_hidden_commands=True)[0].format_help()

    assert "public-command-surface-report" not in default_help
    assert "public-command-surface-report" in hidden_help


def _write_public_command_source(root: Path, *, suffix: str = "") -> Path:
    path = root / "src" / "sdetkit" / "_legacy_cli.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "import argparse\n\n"
        "sub = argparse.ArgumentParser().add_subparsers()\n"
        'sub.add_parser("start", help="[Public / stable] Start")\n' + suffix,
        encoding="utf-8",
    )
    return path


def test_public_command_surface_input_digest_is_deterministic_and_root_independent(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_generator = first / "generator.py"
    second_generator = second / "generator.py"
    first_generator.parent.mkdir(parents=True, exist_ok=True)
    second_generator.parent.mkdir(parents=True, exist_ok=True)
    first_generator.write_text("generator-v1\n", encoding="utf-8")
    second_generator.write_text("generator-v1\n", encoding="utf-8")
    _write_public_command_source(first)
    _write_public_command_source(second)

    first_payload = public_command_surface_input_provenance(
        first,
        generator_path=first_generator,
    )
    second_payload = public_command_surface_input_provenance(
        second,
        generator_path=second_generator,
    )

    assert first_payload == second_payload
    assert first_payload["digest_algorithm"] == "sha256"
    assert len(first_payload["input_digest"]) == 64
    assert first_payload["input_count"] == 3
    assert first_payload["source_file_count"] == 1
    assert first_payload["generator_schema_version"] == SCHEMA_VERSION


def test_public_command_surface_input_digest_changes_with_source_or_generator(
    tmp_path: Path,
) -> None:
    generator = tmp_path / "generator.py"
    generator.write_text("generator-v1\n", encoding="utf-8")
    command_source = _write_public_command_source(tmp_path)
    baseline = public_command_surface_input_provenance(
        tmp_path,
        generator_path=generator,
    )

    command_source.write_text(
        command_source.read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )
    source_changed = public_command_surface_input_provenance(
        tmp_path,
        generator_path=generator,
    )
    assert source_changed["input_digest"] != baseline["input_digest"]

    _write_public_command_source(tmp_path)
    generator.write_text("generator-v2\n", encoding="utf-8")
    generator_changed = public_command_surface_input_provenance(
        tmp_path,
        generator_path=generator,
    )
    assert generator_changed["input_digest"] != baseline["input_digest"]


def test_public_command_surface_freshness_detects_matching_and_stale_reports(
    tmp_path: Path,
) -> None:
    command_source = _write_public_command_source(tmp_path)
    out = tmp_path / "build" / "public-command-surface-report.json"
    write_artifacts(root=tmp_path, out=out)

    fresh = check_public_command_surface_report_freshness(
        root=tmp_path,
        report_path=out,
    )
    assert fresh["status"] == "fresh"
    assert fresh["fresh"] is True
    assert fresh["reasons"] == []
    assert fresh["repo_mutation"] is False
    assert fresh["automation_allowed"] is False
    assert fresh["patch_application_allowed"] is False
    assert fresh["merge_authorized"] is False
    assert fresh["semantic_equivalence_proven"] is False

    command_source.write_text(
        command_source.read_text(encoding="utf-8") + "\n# stale\n",
        encoding="utf-8",
    )
    stale = check_public_command_surface_report_freshness(
        root=tmp_path,
        report_path=out,
    )
    assert stale["status"] == "stale"
    assert stale["fresh"] is False
    assert "input_digest_mismatch" in stale["reasons"]


def test_public_command_surface_freshness_rejects_missing_invalid_or_unprovenanced(
    tmp_path: Path,
) -> None:
    _write_public_command_source(tmp_path)

    missing_provenance = validate_public_command_surface_report_freshness(
        tmp_path,
        {"schema_version": SCHEMA_VERSION},
    )
    assert missing_provenance["status"] == "stale"
    assert missing_provenance["fresh"] is False
    assert "missing_input_provenance" in missing_provenance["reasons"]

    missing_path = tmp_path / "build" / "missing.json"
    missing = check_public_command_surface_report_freshness(
        root=tmp_path,
        report_path=missing_path,
    )
    assert missing["status"] == "stale"
    assert missing["fresh"] is False
    assert "report_missing" in missing["reasons"]

    invalid_path = tmp_path / "build" / "invalid.json"
    invalid_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_path.write_text("{invalid", encoding="utf-8")
    invalid = check_public_command_surface_report_freshness(
        root=tmp_path,
        report_path=invalid_path,
    )
    assert invalid["status"] == "stale"
    assert invalid["fresh"] is False
    assert "report_invalid_json" in invalid["reasons"]


def test_public_command_surface_cli_checks_freshness_without_rewriting(
    tmp_path: Path,
    capsys,
) -> None:
    command_source = _write_public_command_source(tmp_path)
    out = tmp_path / "build" / "public-command-surface-report.json"
    write_artifacts(root=tmp_path, out=out)
    original = out.read_text(encoding="utf-8")

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "public-command-surface-report",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--check-freshness",
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "freshness_status=fresh" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == original

    command_source.write_text(
        command_source.read_text(encoding="utf-8") + "\n# stale\n",
        encoding="utf-8",
    )
    rc = cli_main(
        [
            "public-command-surface-report",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--check-freshness",
            "--format",
            "json",
        ]
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "stale"
    assert payload["fresh"] is False
    assert out.read_text(encoding="utf-8") == original
