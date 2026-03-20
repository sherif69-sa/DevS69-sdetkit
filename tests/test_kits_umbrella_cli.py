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
    assert release["agent_workflows"]
    assert release["composes_with"]


def test_release_alias_routes_to_gate_and_backcompat_gate_still_works() -> None:
    a = _run("release", "gate", "--help")
    b = _run("gate", "--help")
    assert a.returncode == b.returncode == 0
    assert "usage:" in a.stdout
    assert "usage:" in b.stdout


def test_kits_search_ranks_topology_queries_to_integration() -> None:
    result = _run("kits", "search", "topology", "--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["matches"]
    top = payload["matches"][0]
    assert top["kit"]["id"] == "integration-assurance"
    assert "topology" in top["matched_terms"]
    assert top["recommended_start"].startswith("sdetkit integration")


def test_kits_blueprint_connects_agentos_control_plane_and_cross_kit_plan() -> None:
    result = _run(
        "kits",
        "blueprint",
        "agentized release upgrade search",
        "--format",
        "json",
        "--limit",
        "2",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    selected_ids = [item["id"] for item in payload["selected_kits"]]
    assert "release-confidence" in selected_ids
    assert "test-intelligence" in selected_ids
    assert payload["control_plane"]["name"] == "agentos-control-plane"
    assert any(
        command.startswith("sdetkit agent init") for command in payload["control_plane"]["commands"]
    )
    assert payload["phases"][1]["phase"] == "execute"
    assert payload["phases"][1]["kit_sequence"]


def test_kits_optimize_emits_alignment_plan_json() -> None:
    result = _run(
        "kits",
        "optimize",
        "upgrade umbrella architecture with agentos optimization",
        "--format",
        "json",
        "--limit",
        "2",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "sdetkit.kits.catalog.v1"
    assert payload["doctor_lane"]["command"].startswith("sdetkit doctor ")
    assert payload["quality_gate_lane"]["commands"]
    assert any(item["domain"] == "agentos" for item in payload["alignment_matrix"])
    assert payload["blueprint"]["control_plane"]["name"] == "agentos-control-plane"
