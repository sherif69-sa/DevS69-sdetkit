from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.adoption_surface import discover_adoption_surface


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and item.get("name")
    }


def _commands(payload: dict[str, object]) -> set[str]:
    items = payload["recommended_proof_commands"]
    assert isinstance(items, list)
    return {
        str(item["command"])
        for item in items
        if isinstance(item, dict) and item.get("command")
    }


def _assert_authority_is_false(payload: dict[str, object]) -> None:
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_java_src_tree_does_not_imply_python(tmp_path: Path) -> None:
    _write(
        tmp_path / "pom.xml",
        """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>example</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
</project>
""",
    )
    _write(tmp_path / "src" / "main" / "java" / "example" / "App.java", "class App {}\n")

    payload = discover_adoption_surface(tmp_path)
    languages = _named(payload["detected_languages"])

    assert set(languages) == {"java"}
    assert "mvn test" in _commands(payload)
    assert not any("Python project detected" in str(item) for item in payload["review_first_unknowns"])
    _assert_authority_is_false(payload)


def test_typescript_src_tree_does_not_imply_python(tmp_path: Path) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"name": "demo", "scripts": {"test": "vitest run"}}),
    )
    _write(tmp_path / "src" / "index.ts", "export const value = 1;\n")

    payload = discover_adoption_surface(tmp_path)
    languages = _named(payload["detected_languages"])

    assert set(languages) == {"javascript_typescript"}
    assert "npm test" in _commands(payload)
    assert not any("Python project detected" in str(item) for item in payload["review_first_unknowns"])
    _assert_authority_is_false(payload)


def test_empty_or_vendor_only_src_tree_does_not_imply_python(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    _write(tmp_path / "src" / "node_modules" / "generated.py", "value = 1\n")

    payload = discover_adoption_surface(tmp_path)

    assert _named(payload["detected_languages"]) == {}
    assert payload["review_first_unknowns"] == []
    _assert_authority_is_false(payload)


@pytest.mark.parametrize("suffix", [".py", ".pyi"])
def test_python_source_or_stub_under_src_preserves_python_detection(
    tmp_path: Path,
    suffix: str,
) -> None:
    _write(tmp_path / "src" / "example" / f"module{suffix}", "value: int = 1\n")

    payload = discover_adoption_surface(tmp_path)
    languages = _named(payload["detected_languages"])

    assert languages["python"]["evidence"] == ["src/"]
    assert payload["review_first_unknowns"] == [
        "Python project detected but test command is not proven"
    ]
    _assert_authority_is_false(payload)


def test_python_manifest_detection_is_unchanged_without_src_source(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        """[project]
name = "demo"
version = "0.1.0"
dependencies = ["pytest"]
""",
    )

    payload = discover_adoption_surface(tmp_path)
    languages = _named(payload["detected_languages"])

    assert languages["python"]["evidence"] == ["pyproject.toml"]
    assert "python -m pytest -q -o addopts=" in _commands(payload)
    assert payload["review_first_unknowns"] == []
    _assert_authority_is_false(payload)
