from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True)


def test_root_help_lists_new_umbrella_kits_commands() -> None:
    result = _run("--help")
    assert result.returncode == 0
    assert "kits" in result.stdout
    assert "release" in result.stdout
    assert "intelligence" in result.stdout
    assert "integration" in result.stdout
    assert "forensics" in result.stdout


def test_kits_list_json_schema_and_order() -> None:
    result = _run("kits", "list", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "sdetkit.kits.catalog.v1"
    ids = [x["id"] for x in payload["kits"]]
    assert ids == sorted(ids)
    assert "release-confidence" in ids
    release = next(x for x in payload["kits"] if x["id"] == "release-confidence")
    assert release["capabilities"]
    assert release["typical_inputs"]
    assert release["key_artifacts"]
    assert release["learning_path"]


def test_release_alias_routes_to_gate_and_backcompat_gate_still_works() -> None:
    a = _run("release", "gate", "--help")
    b = _run("gate", "--help")
    assert a.returncode == b.returncode == 0
    assert "usage:" in a.stdout
    assert "usage:" in b.stdout
