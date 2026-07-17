from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and str(item.get("name", ""))
    }


def _cpp_commands(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    items = payload["recommended_proof_commands"]
    assert isinstance(items, list)
    return {
        str(item["command"]): item
        for item in items
        if isinstance(item, dict) and item.get("surface") == "cpp"
    }


def test_cpp_presets_require_explicit_quality_security_and_compile_database_evidence(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")
    _write(
        tmp_path / "CMakePresets.json",
        json.dumps(
            {
                "version": 6,
                "configurePresets": [
                    {
                        "name": "secure",
                        "generator": "Ninja",
                        "cacheVariables": {
                            "CMAKE_CXX_CLANG_TIDY": "clang-tidy;-checks=bugprone-*",
                            "CMAKE_EXPORT_COMPILE_COMMANDS": True,
                            "CMAKE_CXX_FLAGS": "-fsanitize=address,undefined",
                        },
                    }
                ],
            }
        ),
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    artifacts = _named(payload["artifact_surfaces"])
    commands = _cpp_commands(payload)

    assert security["clang_tidy"]["evidence"] == ["CMakePresets.json"]
    assert security["address_sanitizer"]["evidence"] == ["CMakePresets.json"]
    assert security["undefined_behavior_sanitizer"]["evidence"] == ["CMakePresets.json"]
    assert artifacts["cpp_compile_database_contract"]["paths"] == ["CMakePresets.json"]
    assert "cmake --preset secure" in commands
    assert not any(command.startswith("clang-tidy ") for command in commands)
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_cpp_literal_analysis_commands_preserve_exact_nested_workspace_context(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "native"
    _write(workspace / "CMakeLists.txt", "project(native LANGUAGES CXX)\n")
    _write(workspace / "src" / "engine.cpp", "int engine() { return 1; }\n")
    proof = workspace / "scripts" / "quality.sh"
    _write(
        proof,
        "\n".join(
            (
                "clang-tidy -p build src/engine.cpp",
                "cppcheck --project=build/compile_commands.json --enable=warning",
                "clang-format --dry-run --Werror src/engine.cpp",
            )
        )
        + "\n",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    artifacts = _named(payload["artifact_surfaces"])
    commands = _cpp_commands(payload)

    assert security["clang_tidy"]["evidence"] == ["native/scripts/quality.sh"]
    assert security["cppcheck"]["evidence"] == ["native/scripts/quality.sh"]
    assert artifacts["clang_format_evidence"]["paths"] == ["native/scripts/quality.sh"]
    assert artifacts["cpp_compile_database_contract"]["paths"] == ["native/scripts/quality.sh"]

    for command, purpose, tool in (
        ("clang-tidy -p build src/engine.cpp", "lint", "clang-tidy"),
        (
            "cppcheck --project=build/compile_commands.json --enable=warning",
            "lint",
            "cppcheck",
        ),
        ("clang-format --dry-run --Werror src/engine.cpp", "quality", "clang-format"),
    ):
        item = commands[command]
        assert item["purpose"] == purpose
        assert item["executes_untrusted_code"] is True
        assert item["auto_run_allowed"] is False
        assert item["source"] == {
            "scope": "repository_command",
            "file": "native/scripts/quality.sh",
            "tool": tool,
            "working_directory": "native",
        }


def test_cpp_codeql_requires_literal_c_cpp_language_evidence(tmp_path: Path) -> None:
    _write(tmp_path / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")
    workflow = tmp_path / ".github" / "workflows" / "codeql.yml"
    _write(
        workflow,
        """name: CodeQL
jobs:
  analyze:
    steps:
      - uses: github/codeql-action/init@v3
        with:
          languages: c-cpp
      - uses: github/codeql-action/analyze@v3
""",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])

    assert security["codeql_cpp"]["evidence"] == [".github/workflows/codeql.yml"]
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False


def test_cpp_codeql_dynamic_language_remains_review_first(tmp_path: Path) -> None:
    _write(tmp_path / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")
    workflow = tmp_path / ".github" / "workflows" / "codeql.yml"
    _write(
        workflow,
        """jobs:
  analyze:
    strategy:
      matrix:
        language: [c-cpp, python]
    steps:
      - uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
""",
    )

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])

    assert "codeql_cpp" not in security
    assert (
        "CodeQL workflow .github/workflows/codeql.yml uses dynamic or non-C/C++ language "
        "evidence and was not claimed as C++"
    ) in payload["review_first_unknowns"]


def test_generic_cpp_source_tree_does_not_imply_quality_or_security_tools(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "src" / "engine.cpp", "int engine() { return 1; }\n")
    _write(tmp_path / "include" / "engine.hpp", "int engine();\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    artifacts = _named(payload["artifact_surfaces"])

    for name in (
        "clang_tidy",
        "cppcheck",
        "address_sanitizer",
        "undefined_behavior_sanitizer",
        "codeql_cpp",
    ):
        assert name not in security
    assert "clang_format_evidence" not in artifacts
    assert "cpp_compile_database_contract" not in artifacts


def test_cpp_comments_and_disabled_compile_database_do_not_create_claims(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "CMakeLists.txt",
        """project(example LANGUAGES CXX)
# set(CMAKE_CXX_CLANG_TIDY clang-tidy)
# target_compile_options(example PRIVATE -fsanitize=address)
set(CMAKE_EXPORT_COMPILE_COMMANDS OFF)
""",
    )
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    artifacts = _named(payload["artifact_surfaces"])

    assert "clang_tidy" not in security
    assert "address_sanitizer" not in security
    assert "cpp_compile_database_contract" not in artifacts


def test_cpp_generated_and_vendored_quality_evidence_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")
    _write(tmp_path / "build" / ".clang-tidy", "Checks: bugprone-*\n")
    _write(tmp_path / "build" / "compile_commands.json", "[]\n")
    _write(tmp_path / "vendor" / ".clang-format", "BasedOnStyle: LLVM\n")
    _write(tmp_path / "third_party" / "quality.sh", "cppcheck --enable=all .\n")

    payload = discover_adoption_surface(tmp_path)
    security = _named(payload["security_tools"])
    artifacts = _named(payload["artifact_surfaces"])

    assert "clang_tidy" not in security
    assert "cppcheck" not in security
    assert "clang_format_evidence" not in artifacts
    assert "cpp_compile_database_contract" not in artifacts


def test_cpp_dynamic_composite_and_mutating_commands_are_not_recommended(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")
    script = tmp_path / "scripts" / "quality.sh"
    _write(
        script,
        """clang-tidy $TIDY_ARGS src/main.cpp
clang-format -i src/main.cpp
cppcheck --project=build/compile_commands.json && echo complete
""",
    )

    payload = discover_adoption_surface(tmp_path)
    commands = _cpp_commands(payload)
    unknowns = payload["review_first_unknowns"]

    assert not any(command.startswith("clang-tidy ") for command in commands)
    assert not any(command.startswith("clang-format ") for command in commands)
    assert not any(command.startswith("cppcheck ") for command in commands)
    assert any("clang tidy command" in str(item) and "dynamic" in str(item) for item in unknowns)
    assert any("clang format command" in str(item) and "mutation" in str(item) for item in unknowns)
    assert any("cppcheck command" in str(item) and "dynamic" in str(item) for item in unknowns)
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False


def test_cpp_owned_compile_database_file_is_reported_but_build_copy_is_not(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "CMakeLists.txt", "project(example LANGUAGES CXX)\n")
    _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }\n")
    _write(tmp_path / "compile_commands.json", "[]\n")
    _write(tmp_path / "build" / "compile_commands.json", "[]\n")

    payload = discover_adoption_surface(tmp_path)
    artifacts = _named(payload["artifact_surfaces"])

    assert artifacts["cpp_compile_database_contract"]["paths"] == ["compile_commands.json"]
