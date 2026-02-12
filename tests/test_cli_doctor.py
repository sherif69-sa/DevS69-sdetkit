import json

from sdetkit import cli


def test_doctor_json_smoke(capsys):
    rc = cli.main(["doctor", "--json"])
    out = capsys.readouterr().out.strip()
    data = json.loads(out)

    assert rc in (0, 1)
    assert "python" in data and "version" in data["python"]
    assert "package" in data and data["package"]["name"] == "sdetkit"
    assert "missing" in data and isinstance(data["missing"], list)


def test_doctor_dev_tools_present_in_ci(capsys):
    rc = cli.main(["doctor", "--json", "--dev"])
    out = capsys.readouterr().out.strip()
    data = json.loads(out)

    assert rc == 0
    assert data["missing"] == []
    assert "tools" in data
    assert "pytest" in data["tools"]


def test_doctor_accepts_format_json_alias() -> None:
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")

    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit.doctor", "--format", "json"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert isinstance(data, dict)
    assert "ok" in data
    assert "score" in data


def test_doctor_json_includes_structured_checks(tmp_path) -> None:
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")

    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit.doctor", "--format", "json"],
        cwd=str(tmp_path),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    checks = data.get("checks")
    assert isinstance(checks, dict)
    std = checks.get("stdlib_shadowing")
    assert isinstance(std, dict)
    assert isinstance(std.get("ok"), bool)
    shadow = std.get("shadow")
    assert isinstance(shadow, list)


def test_doctor_json_reports_stdlib_shadowing_from_cwd_src(tmp_path) -> None:
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "tomllib.py").write_text("x = 1\n", encoding="utf-8")

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")

    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit.doctor", "--format", "json"],
        cwd=str(tmp_path),
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 2, proc.stderr
    data = json.loads(proc.stdout)
    checks = data.get("checks") or {}
    std = checks.get("stdlib_shadowing")
    assert isinstance(std, dict)
    assert std.get("ok") is False
    shadow = std.get("shadow") or []
    assert any("tomllib" in item for item in shadow)
