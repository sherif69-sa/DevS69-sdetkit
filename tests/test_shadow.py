"""Tests for autonomous multi-environment shadow qualification harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli, integration


def test_shadow_constants_and_default_profiles() -> None:
    assert integration.SHADOW_SCHEMA_VERSION == "sdetkit.shadow.v1"
    profiles = integration.DEFAULT_SHADOW_PROFILES
    assert "baseline" in profiles
    assert "prod_strict" in profiles
    assert "ci_isolated" in profiles
    assert profiles["baseline"]["timeout_multiplier"] == 1.0
    assert profiles["prod_strict"]["timeout_multiplier"] == 0.5
    assert profiles["prod_strict"]["env"]["SDETKIT_STRICT_MODE"] == "1"
    assert profiles["ci_isolated"]["env"]["CI"] == "true"


def test_execute_shadow_profile_success(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_always_pass(): assert 1 + 1 == 2\n", encoding="utf-8")

    result = integration.execute_shadow_profile(
        repo_root=tmp_path,
        target=str(test_file),
        profile_name="baseline",
        profile_config={"description": "Test profile", "env": {}, "timeout_multiplier": 1.0},
        base_timeout=10.0,
    )
    assert result["profile"] == "baseline"
    assert result["passed"] is True
    assert result["exit_code"] == 0
    assert result["duration_seconds"] >= 0.0
    assert result["timed_out"] is False
    assert result["error_summary"] == ""


def test_execute_shadow_profile_failure(tmp_path: Path) -> None:
    test_file = tmp_path / "test_fail.py"
    test_file.write_text(
        "def test_always_fail(): assert False, 'intentional failure'\n", encoding="utf-8"
    )

    result = integration.execute_shadow_profile(
        repo_root=tmp_path,
        target=str(test_file),
        profile_name="baseline",
        profile_config={"description": "Failing profile", "env": {}, "timeout_multiplier": 1.0},
        base_timeout=10.0,
    )
    assert result["passed"] is False
    assert result["exit_code"] != 0
    assert "intentional failure" in result["error_summary"] or result["error_summary"] != ""


def test_run_shadow_qualification_qualified(tmp_path: Path) -> None:
    test_file = tmp_path / "test_pure.py"
    test_file.write_text("def test_pure(): assert len('hello') == 5\n", encoding="utf-8")

    report = integration.run_shadow_qualification(
        repo_root=tmp_path,
        target=str(test_file),
        profiles=["baseline", "ci_isolated"],
        timeout=15.0,
    )
    assert report["schema_version"] == integration.SHADOW_SCHEMA_VERSION
    assert report["verdict"] == "QUALIFIED"
    assert report["summary"]["qualified"] is True
    assert report["summary"]["total_profiles"] == 2
    assert report["summary"]["passed_profiles"] == 2
    assert report["summary"]["divergences_count"] == 0
    assert len(report["divergences"]) == 0


def test_run_shadow_qualification_divergence_detected(tmp_path: Path) -> None:
    test_file = tmp_path / "test_diverge.py"
    # Fails when SDETKIT_STRICT_MODE is set to '1'
    test_file.write_text(
        "import os\n"
        "def test_env_sensitive():\n"
        "    if os.environ.get('SDETKIT_STRICT_MODE') == '1':\n"
        "        raise RuntimeError('Strict mode violation!')\n"
        "    assert True\n",
        encoding="utf-8",
    )

    report = integration.run_shadow_qualification(
        repo_root=tmp_path,
        target=str(test_file),
        profiles=["baseline", "prod_strict"],
        timeout=15.0,
    )
    assert report["verdict"] == "BLOCKED"
    assert report["summary"]["qualified"] is False
    assert report["summary"]["divergences_count"] == 1
    assert len(report["divergences"]) == 1
    div = report["divergences"][0]
    assert div["profile"] == "prod_strict"
    assert div["baseline_status"] == "PASS"
    assert div["shadow_status"] == "FAIL"
    assert div["severity"] == "CRITICAL"


def test_render_shadow_markdown_and_text(tmp_path: Path) -> None:
    mock_report = {
        "schema_version": "sdetkit.shadow.v1",
        "target": "tests/test_feature.py",
        "repo_root": str(tmp_path),
        "verdict": "BLOCKED",
        "summary": {
            "total_profiles": 2,
            "passed_profiles": 1,
            "failed_profiles": 1,
            "divergences_count": 1,
            "qualified": False,
        },
        "profiles": [
            {
                "profile": "baseline",
                "description": "Standard",
                "passed": True,
                "exit_code": 0,
                "duration_seconds": 0.12,
                "error_summary": "",
            },
            {
                "profile": "prod_strict",
                "description": "Strict",
                "passed": False,
                "exit_code": 1,
                "duration_seconds": 0.08,
                "error_summary": "RuntimeError: Strict mode violation!",
            },
        ],
        "divergences": [
            {
                "profile": "prod_strict",
                "baseline_status": "PASS",
                "shadow_status": "FAIL",
                "severity": "CRITICAL",
                "reason": "RuntimeError: Strict mode violation!",
            }
        ],
    }

    md = integration.render_shadow_markdown(mock_report)
    assert "# Autonomous Multi-Environment Shadow Qualification Report [BLOCKED]" in md
    assert "Environment Qualification Matrix" in md
    assert "`prod_strict`" in md
    assert "CRITICAL" in md
    assert "Remediation Guidance" in md
    assert all(ord(c) < 128 for c in md)

    txt = integration.render_shadow_text(mock_report)
    assert "Shadow Qualification: verdict=BLOCKED" in txt
    assert "DIVERGENCE in prod_strict" in txt
    assert all(ord(c) < 128 for c in txt)


def test_shadow_cli_routing_and_execution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = tmp_path / "test_cli.py"
    test_file.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")

    rc = integration.main(
        [
            "shadow",
            str(test_file),
            "--repo-root",
            str(tmp_path),
            "--profiles",
            "baseline",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "sdetkit.shadow.v1"
    assert payload["verdict"] == "QUALIFIED"

    # Test via cli.main
    rc_cli = cli.main(
        [
            "shadow",
            str(test_file),
            "--repo-root",
            str(tmp_path),
            "--profiles",
            "baseline",
            "--format",
            "text",
        ]
    )
    assert rc_cli == 0
    captured_cli = capsys.readouterr()
    assert "Shadow Qualification: verdict=QUALIFIED" in captured_cli.out


def test_shadow_cli_verify_subcommand_routing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_file = tmp_path / "test_verify.py"
    test_file.write_text("def test_verify(): assert True\n", encoding="utf-8")

    rc = cli.main(
        [
            "verify",
            "shadow",
            str(test_file),
            "--repo-root",
            str(tmp_path),
            "--profiles",
            "baseline",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["verdict"] == "QUALIFIED"


def test_shadow_cli_custom_config_and_out_files(tmp_path: Path) -> None:
    test_file = tmp_path / "test_custom.py"
    test_file.write_text("def test_custom(): assert True\n", encoding="utf-8")

    cfg_file = tmp_path / "custom_profiles.json"
    cfg_file.write_text(
        json.dumps(
            {
                "custom_fast": {
                    "description": "Fast custom profile",
                    "env": {"SDETKIT_CUSTOM": "1"},
                    "timeout_multiplier": 1.0,
                }
            }
        ),
        encoding="utf-8",
    )

    out_file = tmp_path / "output.md"
    summary_file = tmp_path / "step_summary.md"

    rc = integration.shadow_main(
        [
            str(test_file),
            "--repo-root",
            str(tmp_path),
            "--profile-config",
            str(cfg_file),
            "--profiles",
            "custom_fast",
            "--format",
            "md",
            "--out",
            str(out_file),
            "--summary-out",
            str(summary_file),
        ]
    )
    assert rc == 0
    assert out_file.is_file()
    assert summary_file.is_file()
    assert (
        "# Autonomous Multi-Environment Shadow Qualification Report [QUALIFIED]"
        in out_file.read_text(encoding="utf-8")
    )


def test_shadow_cli_missing_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = integration.shadow_main(["--profile-config", str(tmp_path / "nonexistent.json")])
    assert rc == 2
    captured = capsys.readouterr()
    assert "profile config not found" in captured.err
