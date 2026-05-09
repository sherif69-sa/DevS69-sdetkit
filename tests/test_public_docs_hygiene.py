from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {".md", ".rst", ".txt", ".toml", ".yml", ".yaml", ".json", ".ini", ".cfg", ".sh"}


def _public_docs_paths() -> list[Path]:
    paths: list[Path] = []
    for root in [Path("docs"), Path(".")]:
        if root == Path("."):
            candidates = [Path("CHANGELOG.md"), Path("README.md")]
        else:
            candidates = sorted(root.rglob("*"))

        for path in candidates:
            if not path.is_file():
                continue
            if path.parts[:2] == ("docs", "artifacts"):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES:
                paths.append(path)

    return sorted(set(paths))


def test_public_docs_do_not_ship_unresolved_task_markers() -> None:
    forbidden_markers = ("TO" + "DO", "FIX" + "ME", "H" + "ACK", "X" + "XX", "W" + "IP")
    offenders: list[str] = []

    for path in _public_docs_paths():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in forbidden_markers):
                offenders.append(f"{path}:{line_number}: {line.strip()}")

    assert offenders == []


def test_public_security_docs_do_not_include_copyable_unsafe_yaml_loader_call() -> None:
    offenders: list[str] = []

    for path in _public_docs_paths():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), 1):
            if "yaml.load(" in line:
                offenders.append(f"{path}:{line_number}: {line.strip()}")

    assert offenders == []


def test_security_gate_docs_still_name_the_safe_yaml_replacement() -> None:
    text = Path("docs/security-gate.md").read_text(encoding="utf-8")

    assert "PyYAML unsafe loader calls -> `yaml.safe_load(...)`" in text
