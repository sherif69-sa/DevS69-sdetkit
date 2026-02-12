from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sdetkit import doctor


def test_doctor_missing_policy_uses_defaults(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = doctor.main(["--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["policy"]["fail_on"] == "high"


def test_policy_can_disable_check(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bad.py").write_bytes(b"x = \xff\n")
    policy = tmp_path / "sdetkit.policy.toml"
    policy.write_text(
        """
[checks.ascii]
enabled = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--ascii", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["checks"]["ascii"]["skipped"] is True
    assert data["checks"]["ascii"]["ok"] is True


def test_policy_severity_high_failure_triggers_gate(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bad.py").write_bytes(b"x = \xff\n")
    policy = tmp_path / "p.toml"
    policy.write_text(
        """
[checks.ascii]
severity = "high"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--ascii", "--policy", str(policy), "--fail-on", "high", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["checks"]["ascii"]["severity"] == "high"


def test_cli_fail_on_overrides_policy(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bad.py").write_bytes(b"x = \xff\n")
    policy = tmp_path / "p.toml"
    policy.write_text(
        """
[thresholds]
fail_on = "high"

[checks.ascii]
severity = "medium"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--ascii", "--policy", str(policy), "--fail-on", "medium", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["policy"]["fail_on"] == "medium"


def test_json_purity_stdlib_shadowing_warning_to_stderr(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "tomllib.py").write_text("x = 1\n", encoding="utf-8")

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit.doctor", "--format", "json"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 2
    assert proc.stdout.startswith("{")
    payload = json.loads(proc.stdout)
    assert payload["checks"]["stdlib_shadowing"]["ok"] is False
    assert "stdlib-shadow" in proc.stderr


def test_ci_workflows_missing_lists_evidence(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--ci", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    check = data["checks"]["ci_workflows"]
    assert check["ok"] is False
    assert check["evidence"]
    assert {item["type"] for item in check["evidence"]} == {"missing_group"}


def test_security_files_pass(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "SECURITY.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "CODE_OF_CONDUCT.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "LICENSE.md").write_text("ok\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--ci", "--json", "--fail-on", "high"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["checks"]["security_files"]["ok"] is True
