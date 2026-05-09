from __future__ import annotations

from pathlib import Path


def test_platform_problem_templates_do_not_ship_unresolved_task_markers() -> None:
    root = Path("templates/platform_problem")
    forbidden_markers = ("TO" + "DO", "FIX" + "ME", "H" + "ACK", "X" + "XX", "W" + "IP")
    offenders: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {
            ".py",
            ".md",
            ".txt",
            ".toml",
            ".yml",
            ".yaml",
            ".json",
            ".sh",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in forbidden_markers):
                offenders.append(f"{path}:{line_number}: {line.strip()}")

    assert offenders == []


def test_rich_text_template_explains_full_justify_style_lookup() -> None:
    text = Path("templates/platform_problem/rich/solution/rich/text.py").read_text(encoding="utf-8")

    assert "This localized style lookup is only needed for full justification." in text
    assert "This is a little inefficient" not in text
