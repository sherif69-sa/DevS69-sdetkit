from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.repo.fit.v1"
DEFAULT_OUT = "build/sdetkit/repo-fit-screen.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _section(text: str, title: str) -> list[str]:
    marker = f"=== {title} ==="
    if marker not in text:
        return []
    tail = text.split(marker, 1)[1]
    body = tail.split("===", 1)[0]
    return [line.strip() for line in body.splitlines() if line.strip()]


def _section_text(text: str, title: str) -> str:
    return "\n".join(_section(text, title))


def _bool_signal(text: str, name: str) -> bool:
    pattern = re.compile(rf"\[{re.escape(name)}\]?:\s*(True|False)", re.IGNORECASE)
    match = pattern.search(text)
    return bool(match and match.group(1).lower() == "true")


def _repo_name(text: str) -> str:
    match = re.search(r"=== DONE:\s+([A-Za-z0-9_.-]+)\s+repo-fit screen", text)
    if match:
        return match.group(1)
    return "unknown"


def _commit(text: str) -> str:
    lines = _section(text, "COMMIT")
    return lines[0] if lines else ""


def _clean_paths(lines: list[str]) -> list[str]:
    return [
        line
        for line in lines
        if not line.startswith("./") or line in {"./LICENSE", "./README.md", "./pyproject.toml"}
    ]


def _counted_test_areas(lines: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines:
        match = re.match(r"(\d+)\s+(.+)", line)
        if match:
            counts[match.group(2)] = int(match.group(1))
    return counts


def _score(signals: dict[str, bool], counts: dict[str, int]) -> int:
    score = 0
    if signals["project"]:
        score += 20
    if signals["hatch"]:
        score += 10
    if signals["ruff"]:
        score += 10
    if counts["pkg"] > 0:
        score += 10
    if counts["tests"] > 0:
        score += 20
    if counts["test_areas"] >= 4:
        score += 10
    if signals["pytest_ini"]:
        score += 10
    else:
        score -= 5
    if not signals["optional_deps"]:
        score -= 5
    if not signals["mypy"]:
        score -= 5
    return max(score, 0)


def _fit(score: int) -> str:
    if score >= 65:
        return "promising screen"
    if score >= 45:
        return "needs research"
    return "weak screen"


def _recommendation(fit: str) -> str:
    if fit == "promising screen":
        return "continue evidence collection before freezing a candidate"
    if fit == "needs research":
        return "collect issue collision and local proof feasibility before candidate freeze"
    return "do not freeze candidate without stronger repo fit evidence"


def build_repo_fit_screen(screen_text: str) -> dict[str, Any]:
    top_files = _section(screen_text, "TOP LEVEL")
    package_areas = _section(screen_text, "PACKAGE AREAS")
    test_areas = _section(screen_text, "TEST AREAS")
    large_surface = _section(screen_text, "LARGE PUBLIC SURFACE CANDIDATE FILES")
    test_counts = _counted_test_areas(_section(screen_text, "TEST FILE COUNT BY AREA"))
    pyproject = _section_text(screen_text, "PYPROJECT BASIC SIGNALS")

    signals = {
        "project": _bool_signal(pyproject, "project"),
        "optional_deps": _bool_signal(pyproject, "project.optional-dependencies"),
        "pytest_ini": _bool_signal(pyproject, "tool.pytest.ini_options"),
        "hatch": _bool_signal(pyproject, "tool.hatch"),
        "ruff": _bool_signal(pyproject, "tool.ruff"),
        "mypy": _bool_signal(pyproject, "tool.mypy"),
    }
    counts = {
        "top_files": len(top_files),
        "pkg": len(package_areas),
        "tests": sum(test_counts.values()) if test_counts else len(test_areas),
        "test_areas": len(test_counts) if test_counts else len(test_areas),
        "large_surface": len(large_surface),
    }
    score = _score(signals, counts)
    fit = _fit(score)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "screen only",
        "repo": _repo_name(screen_text),
        "commit": _commit(screen_text),
        "candidate_frozen": False,
        "screen_only": True,
        "score": score,
        "fit": fit,
        "signals": signals,
        "counts": counts,
        "top_files": top_files,
        "package_samples": package_areas[:15],
        "test_area_counts": test_counts,
        "large_surface_samples": _clean_paths(large_surface[:20]),
        "risk_notes": [
            "large public surface needs issue collision review",
            "candidate cannot be frozen from repo screen alone",
        ],
        "recommended_action": _recommendation(fit),
        **AUTHORITY_BOUNDARY,
    }


def write_repo_fit_screen_artifact(
    *,
    screen_text_path: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_repo_fit_screen(Path(screen_text_path).read_text(encoding="utf-8"))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit repo-fit-screen",
        description="Build a read-only repo fit screen artifact without freezing a candidate.",
    )
    parser.add_argument("--screen-text", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_repo_fit_screen_artifact(screen_text_path=ns.screen_text, out=ns.out)

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"repo_fit_json={ns.out}\n")
        sys.stdout.write(f"repo={payload['repo']}\n")
        sys.stdout.write(f"fit={payload['fit']}\n")
        sys.stdout.write(f"candidate_frozen={str(payload['candidate_frozen']).lower()}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
