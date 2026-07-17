from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _named(items: object) -> dict[str, dict]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and str(item.get("name", ""))
    }


def _cpp_commands(payload: dict) -> list[dict]:
    return [item for item in payload["recommended_proof_commands"] if item.get("surface") == "cpp"]


def _command_by_scope(payload: dict) -> dict[tuple[str, str], dict]:
    scoped: dict[tuple[str, str], dict] = {}
    for item in _cpp_commands(payload):
        source = item.get("source")
        assert isinstance(source, dict)
        scoped[(str(item["command"]), str(source["working_directory"]))] = item
    return scoped


def test_cpp_discovery_recommends_named_cmake_presets_with_exact_context(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "CMakeLists.txt", "cmake_minimum_required(VERSION 3.24)\n")
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")
    _write(
        tmp_path / "CMakePresets.json",
        json.dumps(
            {
                "version": 6,
                "configurePresets": [{"name": "linux-debug", "generator": "Ninja"}],
                "buildPresets": [{"name": "linux-debug", "configurePreset": "linux-debug"}],
                "testPresets": [{"name": "linux-debug", "configurePreset": "linux-debug"}],
            }
        ),
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _command_by_scope(payload)
    languages = _named(payload["detected_languages"])
    runners = _named(payload["test_runners"])

    assert languages["cpp"]["confidence"] == "high"
    assert languages["cpp"]["evidence"] == [
        "CMakeLists.txt",
        "CMakePresets.json",
        "src/main.cpp",
    ]
    assert commands[("cmake --preset linux-debug", ".")]["purpose"] == "configure"
    assert commands[("cmake --build --preset linux-debug", ".")]["purpose"] == "build"
    test_command = commands[("ctest --preset linux-debug", ".")]
    assert test_command["purpose"] == "test"
    assert test_command["source"] == {
        "scope": "repository_root",
        "file": "CMakePresets.json",
        "working_directory": ".",
        "preset_kind": "testPresets",
        "preset_name": "linux-debug",
    }
    assert runners["ctest"]["commands"] == ["ctest --preset linux-debug"]
    assert payload["review_first_unknowns"] == []
    assert all(item["auto_run_allowed"] is False for item in _cpp_commands(payload))
    assert all(item["executes_untrusted_code"] is True for item in _cpp_commands(payload))
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_cpp_discovery_preserves_identical_presets_in_distinct_nested_workspaces(
    tmp_path: Path,
) -> None:
    for workspace in ("services/alpha", "services/beta"):
        _write(tmp_path / workspace / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
        _write(
            tmp_path / workspace / "CMakePresets.json",
            json.dumps(
                {
                    "version": 6,
                    "configurePresets": [{"name": "ci", "generator": "Ninja"}],
                    "buildPresets": [{"name": "ci", "configurePreset": "ci"}],
                    "testPresets": [{"name": "ci", "configurePreset": "ci"}],
                }
            ),
        )
        _write(tmp_path / workspace / "src" / "main.cpp", "int value = 1;\n")

    payload = discover_adoption_surface(tmp_path)
    commands = _command_by_scope(payload)

    for workspace in ("services/alpha", "services/beta"):
        assert ("cmake --preset ci", workspace) in commands
        assert ("cmake --build --preset ci", workspace) in commands
        assert ("ctest --preset ci", workspace) in commands
        assert commands[("ctest --preset ci", workspace)]["source"]["scope"] == ("nested_workspace")
    assert payload["review_first_unknowns"] == []


def test_cpp_discovery_extracts_literal_owned_commands_and_rejects_dynamic_content(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "native" / "CMakeLists.txt", "project(native LANGUAGES CXX)\n")
    _write(
        tmp_path / "native" / "scripts" / "proof.sh",
        "\n".join(
            (
                "cmake -S . -B build",
                "cmake --build build",
                "ctest --test-dir build",
                'cmake --build "$BUILD_DIR"',
            )
        )
        + "\n",
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _command_by_scope(payload)

    assert commands[("cmake -S . -B build", "native")]["purpose"] == "configure"
    assert commands[("cmake --build build", "native")]["purpose"] == "build"
    assert commands[("ctest --test-dir build", "native")]["purpose"] == "test"
    assert all(
        item["source"]["file"] == "native/scripts/proof.sh" for item in _cpp_commands(payload)
    )
    assert payload["review_first_unknowns"] == [
        "C++ command in native/scripts/proof.sh is dynamic or compound and was not guessed"
    ]


def test_cpp_discovery_reports_source_only_evidence_review_first(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "engine.cpp", "int engine() { return 1; }\n")
    _write(tmp_path / "include" / "engine.hpp", "int engine();\n")

    payload = discover_adoption_surface(tmp_path)
    cpp = _named(payload["detected_languages"])["cpp"]

    assert cpp["confidence"] == "medium"
    assert cpp["evidence"] == ["include/engine.hpp", "src/engine.cpp"]
    assert _cpp_commands(payload) == []
    assert payload["review_first_unknowns"] == [
        "C++ source files detected but build or test command is not proven"
    ]


def test_cpp_discovery_ignores_generated_and_vendored_trees(tmp_path: Path) -> None:
    _write(tmp_path / "build" / "CMakeLists.txt", "project(generated LANGUAGES CXX)\n")
    _write(tmp_path / "cmake-build-debug" / "generated.cpp", "int generated = 1;\n")
    _write(tmp_path / "third_party" / "lib" / "meson.build", "project('vendor', 'cpp')\n")
    _write(tmp_path / "vendor" / "lib.hpp", "int vendor();\n")

    payload = discover_adoption_surface(tmp_path)

    assert "cpp" not in _named(payload["detected_languages"])
    assert _cpp_commands(payload) == []
    assert payload["review_first_unknowns"] == []


def test_cpp_discovery_fails_closed_for_malformed_presets(tmp_path: Path) -> None:
    _write(tmp_path / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
    _write(tmp_path / "CMakePresets.json", "{not-json\n")

    payload = discover_adoption_surface(tmp_path)

    assert _cpp_commands(payload) == []
    assert payload["review_first_unknowns"] == [
        "C++ workspace . detected but configure/build/test command is not proven",
        "CMake preset file CMakePresets.json is malformed and was not used for proof commands",
    ]
