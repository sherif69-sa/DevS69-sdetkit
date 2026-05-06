from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sdetkit import investigate


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    return env


def _write_surface_fixture(root: Path) -> None:
    src = root / "src" / "sdetkit"
    src.mkdir(parents=True)
    (src / "netclient.py").write_text(
        "class SdetHttpClient:\n"
        "    def get_json(self):\n"
        "        return {}\n"
        "    def get_json_envelope(self):\n"
        "        return {}\n"
        "\n"
        "class SdetAsyncHttpClient:\n"
        "    async def get_json(self):\n"
        "        return {}\n",
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_netclient.py").write_text(
        "def test_netclient_surface():\n    assert True\n",
        encoding="utf-8",
    )


def test_surface_investigation_finds_files_symbols_and_parity_risks(tmp_path):
    _write_surface_fixture(tmp_path)

    payload = investigate._payload_for_surface(str(tmp_path), "netclient")

    assert payload["schema_version"] == "sdetkit.investigate.surface.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["production_files"] == ["src/sdetkit/netclient.py"]
    assert payload["test_files"] == ["tests/test_netclient.py"]
    assert "SdetHttpClient" in payload["public_symbols"]
    assert "SdetHttpClient.get_json_envelope" in payload["public_symbols"]
    assert payload["parity_risks"] == [
        {
            "kind": "sync_async_method_gap",
            "sync_symbol": "SdetHttpClient.get_json_envelope",
            "async_symbol": "get_json_envelope",
            "status": "missing",
        }
    ]
    assert payload["recommended_probe"] == "write focused parity repro"


def test_surface_investigation_json_cli_writes_output(tmp_path, capsys):
    _write_surface_fixture(tmp_path)
    out = tmp_path / "surface.json"

    rc = investigate.main(
        [
            "surface",
            "--root",
            str(tmp_path),
            "--surface",
            "netclient",
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert written["schema_version"] == "sdetkit.investigate.surface.v1"
    assert printed["surface"] == "netclient"
    assert written["automation_allowed"] is False


def test_surface_investigation_markdown_cli(tmp_path, capsys):
    _write_surface_fixture(tmp_path)

    rc = investigate.main(
        ["surface", "--root", str(tmp_path), "--surface", "netclient", "--format", "markdown"]
    )

    assert rc == 0
    rendered = capsys.readouterr().out
    assert "# Surface investigation" in rendered
    assert "surface: **netclient**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "SdetHttpClient.get_json_envelope" in rendered
    assert "sync_async_method_gap" in rendered


def test_surface_investigation_missing_root_returns_2(tmp_path, capsys):
    missing = tmp_path / "missing"

    rc = investigate.main(
        ["surface", "--root", str(missing), "--surface", "netclient", "--format", "json"]
    )

    assert rc == 2
    assert "repository root does not exist" in capsys.readouterr().err


def test_surface_investigation_blank_surface_returns_2(tmp_path, capsys):
    rc = investigate.main(
        ["surface", "--root", str(tmp_path), "--surface", " ", "--format", "json"]
    )

    assert rc == 2
    assert "surface name is required" in capsys.readouterr().err


def test_python_m_sdetkit_investigate_surface_outputs_json(tmp_path):
    _write_surface_fixture(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "investigate",
            "surface",
            "--root",
            str(tmp_path),
            "--surface",
            "netclient",
            "--format",
            "json",
        ],
        cwd=Path.cwd(),
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "sdetkit.investigate.surface.v1"
    assert payload["surface"] == "netclient"
    assert payload["parity_risks"][0]["kind"] == "sync_async_method_gap"
