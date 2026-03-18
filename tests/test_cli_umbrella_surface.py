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
    release_kit = next(item for item in payload["kits"] if item["slug"] == "release")
    assert "capabilities" in release_kit
    assert "typical_inputs" in release_kit
    assert "key_artifacts" in release_kit
    assert "learning_path" in release_kit
    assert release_kit["learning_path"][0] == "sdetkit release gate fast"

    describe_proc = _run("kits", "describe", "release", "--format", "json")
    assert describe_proc.returncode == 0
    describe_payload = json.loads(describe_proc.stdout)
    assert describe_payload["schema_version"] == "sdetkit.kits.catalog.v1"
    assert describe_payload["kit"]["id"] == "release-confidence"
    assert describe_payload["kit"]["slug"] == "release"
    assert "Pre-merge quality gates" in describe_payload["kit"]["capabilities"]


def test_kits_describe_unknown_is_usage_error() -> None:
    proc = _run("kits", "describe", "unknown-kit")
    assert proc.returncode == 2
    assert "kits error" in proc.stderr


def test_kits_describe_text_includes_capability_map() -> None:
    proc = _run("kits", "describe", "integration")
    assert proc.returncode == 0
    assert "capabilities:" in proc.stdout
    assert "typical inputs:" in proc.stdout
    assert "key artifacts:" in proc.stdout
    assert "learning path:" in proc.stdout
