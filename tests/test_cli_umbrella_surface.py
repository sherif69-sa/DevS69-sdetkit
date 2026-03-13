from __future__ import annotations

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True)


def test_root_help_prioritizes_umbrella_then_compatibility() -> None:
    proc = _run("--help")
    assert proc.returncode == 0
    out = proc.stdout
    assert "umbrella kits" in out.lower()
    assert "compatibility aliases" in out.lower()
    assert out.index("umbrella kits") < out.index("compatibility aliases")


def test_kits_list_and_describe_contract() -> None:
    list_proc = _run("kits", "list", "--format", "json")
    assert list_proc.returncode == 0
    payload = json.loads(list_proc.stdout)
    assert payload["schema_version"] == "sdetkit.kits.catalog.v1"
    assert [item["slug"] for item in payload["kits"]] == [
        "forensics",
        "integration",
        "release",
        "intelligence",
    ]

    describe_proc = _run("kits", "describe", "release", "--format", "json")
    assert describe_proc.returncode == 0
    describe_payload = json.loads(describe_proc.stdout)
    assert describe_payload["schema_version"] == "sdetkit.kits.catalog.v1"
    assert describe_payload["kit"]["id"] == "release-confidence"
    assert describe_payload["kit"]["slug"] == "release"


def test_kits_describe_unknown_is_usage_error() -> None:
    proc = _run("kits", "describe", "unknown-kit")
    assert proc.returncode == 2
    assert "kits error" in proc.stderr
