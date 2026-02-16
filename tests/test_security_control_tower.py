from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def _run(args: list[str]) -> int:
    return cli.main(["security", *args])


def test_security_scan_offline_and_sbom_and_order(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "b.py").write_text("import os\nos.system('x')\n", encoding="utf-8")
    (src / "a.py").write_text("import os\nos.system('y')\n", encoding="utf-8")
    sbom = tmp_path / "sbom.json"

    rc = _run(
        [
            "scan",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--fail-on",
            "none",
            "--sbom-output",
            str(sbom),
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    paths = [item["path"] for item in payload["findings"]]
    assert paths == sorted(paths)
    assert "sbom" in payload
    assert sbom.exists()


def test_security_report_sarif_contains_help_and_location(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("import os\nos.system('x')\n", encoding="utf-8")

    rc = _run(
        [
            "report",
            "--root",
            str(tmp_path),
            "--format",
            "sarif",
            "--output",
            str(tmp_path / "out.sarif"),
        ]
    )
    assert rc == 0
    data = json.loads((tmp_path / "out.sarif").read_text(encoding="utf-8"))
    run = data["runs"][0]
    assert run["tool"]["driver"]["rules"][0]["id"].startswith("SEC_")
    assert "help" in run["tool"]["driver"]["rules"][0]
    loc = run["results"][0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"]
    assert loc["region"]["startLine"] >= 1


def test_security_fix_dry_run_and_apply(tmp_path: Path, capsys) -> None:
    target = tmp_path / "mod.py"
    target.write_text("import yaml\nobj = yaml.load(data)\n", encoding="utf-8")

    assert _run(["fix", "--root", str(tmp_path)]) == 0
    dry_out = capsys.readouterr().out
    assert "dry-run" in dry_out
    assert "yaml.safe_load" not in target.read_text(encoding="utf-8")

    assert _run(["fix", "--root", str(tmp_path), "--apply"]) == 0
    assert "yaml.safe_load" in target.read_text(encoding="utf-8")


def test_security_fix_dry_run_previews_and_applies_requests_timeout(tmp_path: Path, capsys) -> None:
    target = tmp_path / "api.py"
    target.write_text(
        "import requests\nresp = requests.get('https://example.com')\n", encoding="utf-8"
    )

    assert _run(["fix", "--root", str(tmp_path)]) == 0
    dry_out = capsys.readouterr().out
    assert "+resp = requests.get('https://example.com', timeout=10)" in dry_out
    assert "timeout=10" not in target.read_text(encoding="utf-8")

    assert _run(["fix", "--root", str(tmp_path), "--apply"]) == 0
    assert "timeout=10" in target.read_text(encoding="utf-8")


def test_premium_gate_script_smoke_contains_commands() -> None:
    text = Path("premium-gate.sh").read_text(encoding="utf-8")
    assert "bash quality.sh" in text
    assert "bash ci.sh" in text
    assert "python3 -m sdetkit doctor --ascii" in text
    assert "python3 -m sdetkit security scan" in text


def test_scan_online_mode_without_cmd_falls_back(tmp_path: Path, capsys) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    rc = _run(["scan", "--root", str(tmp_path), "--online", "--fail-on", "none"])
    assert rc == 0
    assert "security scan" in capsys.readouterr().out


def test_security_scan_ignores_test_fixture_secret_tokens(tmp_path: Path, capsys) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_fixture.py").write_text(
        'token = "bearer:TOPSECRET"\nheader = "X-Api-Key:SHOULD_NOT_LEAK"\n',
        encoding="utf-8",
    )
    rc = _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert not any(item["rule_id"] == "SEC_SECRET_PATTERN" for item in payload["findings"])


def test_security_scan_does_not_flag_compile_only_usage(tmp_path: Path, capsys) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "triage_like.py").write_text(
        'compiled_obj = compile("x=1", "demo", "exec")\n', encoding="utf-8"
    )
    rc = _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert not any(item["rule_id"] == "SEC_DANGEROUS_EVAL" for item in payload["findings"])
