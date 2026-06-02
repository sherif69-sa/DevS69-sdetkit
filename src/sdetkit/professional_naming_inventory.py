from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.professional.naming.inventory.v1"
DEFAULT_OUT = "build/sdetkit/professional-naming-inventory.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

DEFAULT_TERMS = [
    "phase1",
    "phase2",
    "phase3",
    "phase4",
    "phase5",
    "phase6",
    "gate-phase2",
    "closeout",
    "demo",
    "toy",
    "scratch",
    "temp",
    "tutorial",
    "lesson",
    "education",
    "finish-signal",
    "retire-plan",
    "next-pass",
]

TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".txt", ".sh", ".ini", ".cfg"}
SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "artifacts",
    ".artifacts",
    "site",
    ".tox",
    "node_modules",
    "sdetkit.egg-info",
    ".eggs",
}


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def _surface(path: Path) -> str:
    parts = path.parts
    if path.parts[0] == "tests":
        return "test"
    if path.parts[0] == "docs" or path.suffix.lower() == ".md":
        return "docs"
    if ".github" in parts or path.suffix.lower() in {".yml", ".yaml"}:
        return "workflow"
    if path.parts[0] == "src":
        return "source"
    return "other"


def _classification(path: Path, term: str) -> str:
    surface = _surface(path)
    text = path.as_posix()

    if surface == "test":
        return "safe_cleanup_internal"
    if surface == "docs":
        return "docs_only_cleanup"
    if surface == "workflow":
        return "workflow_alias_migration"
    if surface == "source" and ("cli.py" in text or "artifact_contract" in text):
        return "public_surface_requires_alias"
    if surface == "source" and term in text:
        return "internal_path_requires_migration"
    if surface == "source":
        return "safe_cleanup_internal"
    return "defer_until_related_pr"


def _replacement_hint(term: str) -> str:
    replacements = {
        "phase1": "baseline",
        "phase2": "release_readiness",
        "phase3": "platform_readiness",
        "phase4": "operational_readiness",
        "phase5": "adoption_readiness",
        "phase6": "scale_readiness",
        "gate-phase2": "release_readiness_gate",
        "closeout": "completion_report",
        "demo": "example",
        "toy": "sample",
        "scratch": "workspace",
        "temp": "temporary_workspace",
        "tutorial": "guide",
        "lesson": "guide",
        "education": "operator_guidance",
        "finish-signal": "completion_signal",
        "retire-plan": "deprecation_plan",
        "next-pass": "followup_pass",
    }
    return replacements.get(term, "production_name_required")


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])")


def _term_matches(text: str, term: str) -> bool:
    return bool(_term_pattern(term).search(text))


def _line_hits(path: Path, term: str, root: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    rel = path.relative_to(root).as_posix()
    rel_path = Path(rel)

    if _term_matches(rel, term):
        classification = _classification(rel_path, term)
        hits.append(
            {
                "path": rel,
                "line": 0,
                "sample_lines": [],
                "occurrence_count": 1,
                "surface": _surface(rel_path),
                "match_type": "path",
                "term": term,
                "classification": classification,
                "replacement_hint": _replacement_hint(term),
                "requires_compatibility_plan": classification
                in {
                    "public_surface_requires_alias",
                    "workflow_alias_migration",
                    "internal_path_requires_migration",
                },
                **AUTHORITY_BOUNDARY,
            }
        )

    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return hits

    pattern = _term_pattern(term)
    matching_lines: list[int] = []
    for number, line in enumerate(lines, start=1):
        if pattern.search(line):
            matching_lines.append(number)

    if matching_lines:
        classification = _classification(rel_path, term)
        sample_lines = matching_lines[:5]
        hits.append(
            {
                "path": rel,
                "line": sample_lines[0],
                "sample_lines": sample_lines,
                "occurrence_count": len(matching_lines),
                "surface": _surface(rel_path),
                "match_type": "content",
                "term": term,
                "classification": classification,
                "replacement_hint": _replacement_hint(term),
                "requires_compatibility_plan": classification
                in {
                    "public_surface_requires_alias",
                    "workflow_alias_migration",
                    "internal_path_requires_migration",
                },
                **AUTHORITY_BOUNDARY,
            }
        )
    return hits


def build_professional_naming_inventory(
    *,
    root: str | Path = ".",
    terms: Sequence[str] = DEFAULT_TERMS,
) -> dict[str, Any]:
    root_path = Path(root)
    items: list[dict[str, Any]] = []

    for path in _iter_files(root_path):
        for term in terms:
            items.extend(_line_hits(path, term, root_path))

    by_term = Counter(str(item["term"]) for item in items)
    by_class = Counter(str(item["classification"]) for item in items)
    by_surface = Counter(str(item["surface"]) for item in items)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "review required" if items else "clean",
        "terms": list(terms),
        "finding_count": len(items),
        "by_term": dict(sorted(by_term.items())),
        "by_classification": dict(sorted(by_class.items())),
        "by_surface": dict(sorted(by_surface.items())),
        "items": items,
        "recommended_action": "review naming debt inventory before any rename or compatibility migration",
        "rename_allowed": False,
        "compatibility_required": any(bool(item["requires_compatibility_plan"]) for item in items),
        **AUTHORITY_BOUNDARY,
    }


def write_professional_naming_inventory_artifact(
    *,
    root: str | Path = ".",
    out: str | Path = DEFAULT_OUT,
    terms: Sequence[str] = DEFAULT_TERMS,
) -> dict[str, Any]:
    payload = build_professional_naming_inventory(root=root, terms=terms)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit professional-naming-inventory",
        description="Build read-only professional naming debt inventory.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--term", action="append", dest="terms")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_professional_naming_inventory_artifact(
        root=ns.root,
        out=ns.out,
        terms=ns.terms or DEFAULT_TERMS,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"naming_inventory_json={ns.out}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"finding_count={payload['finding_count']}\n")
        sys.stdout.write(
            f"compatibility_required={str(payload['compatibility_required']).lower()}\n"
        )
        sys.stdout.write(f"rename_allowed={str(payload['rename_allowed']).lower()}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
