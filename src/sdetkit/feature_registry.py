from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .public_surface_contract import PUBLIC_SURFACE_CONTRACT

_REQUIRED_FIELDS = {
    "command",
    "tier",
    "status",
    "problem_solved",
    "example",
    "expected_output",
    "test_file",
    "docs_page",
}
_ALLOWED_TIERS = {"A", "B", "C"}
_ALLOWED_STATUSES = {"stable", "advanced", "experimental"}
_DOC_TABLE_START = "<!-- feature-registry:table:start -->"
_DOC_TABLE_END = "<!-- feature-registry:table:end -->"


@dataclass(frozen=True)
class FeatureEntry:
    command: str
    tier: str
    status: str
    problem_solved: str
    example: str
    expected_output: str
    test_file: str
    docs_page: str


def _registry_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "feature_registry.json"


def _known_top_level_commands() -> set[str]:
    commands: set[str] = set()
    for family in PUBLIC_SURFACE_CONTRACT:
        commands.update(family.top_level_commands)
    return commands


def load_feature_registry() -> list[FeatureEntry]:
    payload = json.loads(_registry_path().read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("feature registry must be a list")

    rows: list[FeatureEntry] = []
    seen: set[str] = set()
    for i, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"feature registry item #{i} must be an object")
        missing = sorted(_REQUIRED_FIELDS - set(item))
        if missing:
            raise ValueError(f"feature registry item #{i} missing fields: {', '.join(missing)}")

        entry = FeatureEntry(
            command=str(item["command"]).strip(),
            tier=str(item["tier"]).strip(),
            status=str(item["status"]).strip(),
            problem_solved=str(item["problem_solved"]).strip(),
            example=str(item["example"]).strip(),
            expected_output=str(item["expected_output"]).strip(),
            test_file=str(item["test_file"]).strip(),
            docs_page=str(item["docs_page"]).strip(),
        )
        if not entry.command:
            raise ValueError(f"feature registry item #{i} has empty command")
        if entry.command in seen:
            raise ValueError(f"feature registry duplicate command: {entry.command}")
        seen.add(entry.command)
        rows.append(entry)

    return rows


def _table_line(item: FeatureEntry) -> str:
    return (
        f"| `{item.command}` | {item.tier} | {item.status} | {item.problem_solved} | "
        f"`{item.example}` | [{item.test_file}]({item.test_file}) | [{item.docs_page}]({item.docs_page}) |"
    )


def render_feature_registry_table(rows: list[FeatureEntry]) -> str:
    lines = [
        "| Command | Tier | Status | Problem solved | Example | Test | Docs |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(_table_line(item) for item in sorted(rows, key=lambda x: (x.tier, x.command)))
    return "\n".join(lines)


def render_feature_registry_docs_block(rows: list[FeatureEntry]) -> str:
    lines = [
        "| Command | Tier | Status | Problem solved | Example | Test | Docs |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in sorted(rows, key=lambda x: (x.tier, x.command)):
        test_link = f"../{item.test_file}"
        docs_link = item.docs_page.removeprefix("docs/")
        lines.append(
            f"| `{item.command}` | {item.tier} | {item.status} | {item.problem_solved} | "
            f"`{item.example}` | [{item.test_file}]({test_link}) | [{item.docs_page}]({docs_link}) |"
        )
    table = "\n".join(lines)
    return f"{_DOC_TABLE_START}\n{table}\n{_DOC_TABLE_END}"


def summarize_feature_registry(rows: list[FeatureEntry]) -> dict[str, object]:
    by_tier: dict[str, int] = {}
    by_status: dict[str, int] = {}
    commands: list[str] = []
    for item in sorted(rows, key=lambda x: x.command):
        by_tier[item.tier] = by_tier.get(item.tier, 0) + 1
        by_status[item.status] = by_status.get(item.status, 0) + 1
        commands.append(item.command)
    return {
        "total": len(rows),
        "by_tier": by_tier,
        "by_status": by_status,
        "commands": commands,
    }


def ensure_feature_registry_docs_synced(repo_root: Path) -> list[str]:
    docs_path = repo_root / "docs" / "feature-registry.md"
    if not docs_path.exists():
        return ["feature-registry docs page is missing"]

    text = docs_path.read_text(encoding="utf-8")
    start = text.find(_DOC_TABLE_START)
    end = text.find(_DOC_TABLE_END)
    if start == -1 or end == -1 or end < start:
        return ["feature-registry docs markers are missing or malformed"]

    end += len(_DOC_TABLE_END)
    current = text[start:end].strip()
    expected = render_feature_registry_docs_block(load_feature_registry()).strip()
    if current != expected:
        return ["feature-registry docs table is stale; run scripts/sync_feature_registry_docs.py"]
    return []


def validate_feature_registry_contract(repo_root: Path) -> list[str]:
    errors: list[str] = []
    known_commands = _known_top_level_commands()

    for item in load_feature_registry():
        if item.tier not in _ALLOWED_TIERS:
            errors.append(f"{item.command}: tier must be one of {_ALLOWED_TIERS}")
        if item.status not in _ALLOWED_STATUSES:
            errors.append(f"{item.command}: status must be one of {_ALLOWED_STATUSES}")
        if not item.example.startswith("python -m sdetkit"):
            errors.append(f"{item.command}: example must start with 'python -m sdetkit'")
        if item.command not in known_commands:
            errors.append(f"{item.command}: command is not in the public surface contract")
        if item.tier == "A" and item.status != "stable":
            errors.append(f"{item.command}: tier A commands must use stable status")

        test_path = repo_root / item.test_file
        if not test_path.exists():
            errors.append(f"{item.command}: missing test file: {item.test_file}")

        docs_path = repo_root / item.docs_page
        if not docs_path.exists():
            errors.append(f"{item.command}: missing docs page: {item.docs_page}")

    errors.extend(ensure_feature_registry_docs_synced(repo_root))
    return errors
