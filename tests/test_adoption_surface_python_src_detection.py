from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.adoption_surface import discover_adoption_surface

PYTHON_TEST_UNKNOWN = "Python project detected but test command is not proven"
AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item for item in items if isinstance(item, dict) and item.get("name")
    }


def _commands(payload: dict[str, object]) -> list[dict[str, object]]:
    commands = payload["recommended_proof_commands"]
    assert isinstance(commands, list)
    return [item for item in commands if isinstance(item, dict)]


@pytest.mark.parametrize(
    ("manifest", "manifest_text", "source", "expected_language"),
    [
        (
            "pom.xml",
            "<project />\n",
            "src/main/java/com/example/Application.java",
            "java",
        ),
        (
            "package.json",
            json.dumps({"name": "web", "scripts": {"test": "vitest"}}) + "\n",
            "src/index.ts",
            "javascript_typescript",
        ),
    ],
)
def test_non_python_src_trees_do_not_imply_python_adoption(
    tmp_path: Path,
    manifest: str,
    manifest_text: str,
    source: str,
    expected_language: str,
) -> None:
    _write(tmp_path / manifest, manifest_text)
    _write(tmp_path / source, "// repository-owned non-Python source\n")

    payload = discover_adoption_surface(tmp_path)
    languages = _named(payload["detected_languages"])
    runners = _named(payload["test_runners"])

    assert expected_language in languages
    assert "python" not in languages
    assert "pytest" not in runners
    assert PYTHON_TEST_UNKNOWN not in payload["review_first_unknowns"]
    assert all(item.get("surface") != "python" for item in _commands(payload))
    assert all(payload[field] is False for field in AUTHORITY_FIELDS)


def test_empty_src_directory_does_not_imply_python_adoption(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()

    payload = discover_adoption_surface(tmp_path)

    assert "python" not in _named(payload["detected_languages"])
    assert PYTHON_TEST_UNKNOWN not in payload["review_first_unknowns"]
    assert all(payload[field] is False for field in AUTHORITY_FIELDS)


@pytest.mark.parametrize("source_name", ["module.py", "types.pyi"])
def test_python_files_under_src_remain_high_confidence_evidence(
    tmp_path: Path,
    source_name: str,
) -> None:
    _write(tmp_path / "src" / "example" / source_name, "VALUE = 1\n")

    payload = discover_adoption_surface(tmp_path)
    python = _named(payload["detected_languages"])["python"]

    assert python["confidence"] == "high"
    assert python["evidence"] == ["src/"]
    assert PYTHON_TEST_UNKNOWN in payload["review_first_unknowns"]
    assert all(payload[field] is False for field in AUTHORITY_FIELDS)


@pytest.mark.parametrize(
    ("metadata_path", "metadata_text", "expected_unknown", "expected_command"),
    [
        ("pyproject.toml", "[project]\nname = 'example'\n", True, None),
        ("setup.cfg", "[metadata]\nname = example\n", True, None),
        ("setup.py", "from setuptools import setup\nsetup(name='example')\n", True, None),
        ("requirements.txt", "requests==2.32.4\n", True, None),
        ("tox.ini", "[tox]\nenvlist = py\n", False, "python -m tox"),
    ],
)
def test_python_metadata_detection_is_preserved_without_python_src_files(
    tmp_path: Path,
    metadata_path: str,
    metadata_text: str,
    expected_unknown: bool,
    expected_command: str | None,
) -> None:
    _write(tmp_path / metadata_path, metadata_text)
    _write(tmp_path / "src" / "index.ts", "export const value = 1;\n")

    payload = discover_adoption_surface(tmp_path)
    python = _named(payload["detected_languages"])["python"]
    commands = {str(item.get("command")) for item in _commands(payload)}

    assert python["confidence"] == "high"
    assert python["evidence"] == [metadata_path]
    assert (PYTHON_TEST_UNKNOWN in payload["review_first_unknowns"]) is expected_unknown
    if expected_command is not None:
        assert expected_command in commands
    assert all(payload[field] is False for field in AUTHORITY_FIELDS)
