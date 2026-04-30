from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = "sdetkit.boost.scan.v1"
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".json", ".txt", ".ini", ".cfg"}
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "site",
    "htmlcov",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
}


@dataclass(frozen=True)
class Risk:
    title: str
    severity: str
    file: str
    signal: str


@dataclass(frozen=True)
class Fix:
    title: str
    reason: str
    file: str
    priority: int


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _unique_dicts(values: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    seen: set[object] = set()
    out: list[dict[str, object]] = []
    for item in values:
        marker = item.get(key)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out


def _limited_text_files(root: Path, limit: int) -> list[Path]:
    out: list[Path] = []
    for current, dirs, files in __import__("os").walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        base = Path(current)
        if any(part in IGNORED_DIRS for part in base.parts):
            continue
        for name in sorted(files):
            if len(out) >= limit:
                return out
            path = base / name
            try:
                if path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= 500_000:
                    out.append(path)
            except OSError:
                continue
    return out


def _marker_counts(paths: list[Path]) -> dict[str, int]:
    counts = {"todo": 0, "fixme": 0, "operator_json": 0, "schema_version": 0, "strict_findings": 0}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        counts["todo"] += text.count("todo")
        counts["fixme"] += text.count("fixme")
        counts["operator_json"] += text.count("operator-json") + text.count("operator_json")
        counts["schema_version"] += text.count("schema_version")
        counts["strict_findings"] += text.count("strict_findings")
    return counts


def _workflow_surface(root: Path) -> tuple[list[Risk], list[Fix], list[str], dict[str, object]]:
    risks: list[Risk] = []
    fixes: list[Fix] = []
    workflow_dir = root / ".github" / "workflows"
    workflows = sorted(workflow_dir.glob("*.y*ml")) if workflow_dir.exists() else []
    files = [_rel(root, path) for path in workflows[:8]]
    signals: dict[str, object] = {"workflow_count": len(workflows)}
    if not workflows:
        risks.append(
            Risk("No CI workflows detected", "major", ".github/workflows", "workflow_count=0")
        )
        fixes.append(
            Fix(
                "Add deterministic CI workflow coverage",
                "No workflow files were found.",
                ".github/workflows",
                10,
            )
        )
        return risks, fixes, files, signals
    secret_if_hits: list[str] = []
    for path in workflows:
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(line.strip().startswith("if:") and "secrets." in line for line in text.splitlines()):
            secret_if_hits.append(_rel(root, path))
    signals["workflow_secret_if_hits"] = len(secret_if_hits)
    if secret_if_hits:
        risks.append(
            Risk(
                "Workflow if expression uses direct secrets context",
                "major",
                secret_if_hits[0],
                "secrets_in_if",
            )
        )
        fixes.append(
            Fix(
                "Move secret checks inside shell steps",
                "Workflow step if expressions should not directly reference secrets.",
                secret_if_hits[0],
                9,
            )
        )
    return risks, fixes, files, signals


def _test_surface(root: Path) -> tuple[list[Risk], list[Fix], list[str], dict[str, object]]:
    tests_dir = root / "tests"
    test_files = sorted(tests_dir.rglob("test*.py")) if tests_dir.exists() else []
    contract_hits = [
        path
        for path in test_files
        if any(word in path.name for word in ("contract", "review", "gate", "boost"))
    ]
    risks: list[Risk] = []
    fixes: list[Fix] = []
    signals: dict[str, object] = {
        "has_tests_dir": tests_dir.exists(),
        "test_file_count": len(test_files),
        "contract_test_file_count": len(contract_hits),
    }
    if not tests_dir.exists():
        risks.append(Risk("No tests directory detected", "major", "tests/", "has_tests_dir=false"))
        fixes.append(Fix("Add focused test suite", "No tests directory was found.", "tests/", 10))
    elif len(test_files) < 3:
        risks.append(
            Risk("Low test inventory", "moderate", "tests/", f"test_file_count={len(test_files)}")
        )
        fixes.append(
            Fix(
                "Expand high-signal test inventory",
                "Fewer than three test files were found.",
                "tests/",
                7,
            )
        )
    if test_files and not contract_hits:
        risks.append(
            Risk(
                "No obvious contract tests detected",
                "minor",
                "tests/",
                "contract_test_file_count=0",
            )
        )
        fixes.append(
            Fix(
                "Add CLI and JSON contract tests",
                "The test suite lacks obvious contract test coverage.",
                "tests/",
                5,
            )
        )
    return risks, fixes, [_rel(root, p) for p in test_files[:8]], signals


def _docs_surface(root: Path) -> tuple[list[Risk], list[Fix], list[str], dict[str, object]]:
    readme = root / "README.md"
    docs_dir = root / "docs"
    mkdocs = root / "mkdocs.yml"
    docs_files = sorted(docs_dir.rglob("*.md")) if docs_dir.exists() else []
    risks: list[Risk] = []
    fixes: list[Fix] = []
    files: list[str] = []
    if readme.exists():
        files.append("README.md")
    else:
        risks.append(Risk("Missing README.md", "major", "README.md", "has_readme=false"))
        fixes.append(
            Fix("Add top-level operator quickstart", "README.md is missing.", "README.md", 10)
        )
    if mkdocs.exists():
        files.append("mkdocs.yml")
    elif docs_dir.exists():
        risks.append(
            Risk(
                "Docs exist without mkdocs.yml",
                "moderate",
                "mkdocs.yml",
                "has_docs_dir=true has_mkdocs=false",
            )
        )
        fixes.append(
            Fix(
                "Add deterministic docs navigation",
                "Docs exist but mkdocs.yml is missing.",
                "mkdocs.yml",
                7,
            )
        )
    files.extend(_rel(root, p) for p in docs_files[:6])
    return (
        risks,
        fixes,
        files,
        {
            "has_readme": readme.exists(),
            "has_docs_dir": docs_dir.exists(),
            "has_mkdocs": mkdocs.exists(),
            "docs_file_count": len(docs_files),
        },
    )


def _security_surface(root: Path) -> tuple[list[Risk], list[Fix], list[str], dict[str, object]]:
    markers = [
        root / "SECURITY.md",
        root / "docs" / "security.md",
        root / ".github" / "dependabot.yml",
    ]
    files = [_rel(root, path) for path in markers if path.exists()]
    if files:
        return [], [], files, {"security_marker_count": len(files)}
    return (
        [
            Risk(
                "Security posture markers missing",
                "moderate",
                "SECURITY.md",
                "security_marker_count=0",
            )
        ],
        [
            Fix(
                "Add security posture documentation",
                "No SECURITY.md or equivalent marker was found.",
                "SECURITY.md",
                7,
            )
        ],
        [],
        {"security_marker_count": 0},
    )


def _evidence_surface(root: Path) -> tuple[list[Risk], list[Fix], list[str], dict[str, object]]:
    build = root / "build"
    names = {
        "repo-check.json",
        "repo-check-default.json",
        "repo-check-enterprise.json",
        "gate-release.json",
        "review-operator.json",
        "review-operator-json.json",
        "premium-gate.json",
        "portfolio-scorecard.json",
    }
    files: list[str] = []
    if build.exists():
        for path in sorted(build.rglob("*.json")):
            if path.name in names:
                files.append(_rel(root, path))
    return [], [], files[:12], {"evidence_file_count": len(files)}


def _source_surface(
    root: Path, limit: int
) -> tuple[list[Risk], list[Fix], list[str], dict[str, object]]:
    source_dir = root / "src"
    source_files = sorted(source_dir.rglob("*.py")) if source_dir.exists() else []
    text_files = _limited_text_files(root, limit)
    markers = _marker_counts(text_files)
    risks: list[Risk] = []
    fixes: list[Fix] = []
    if not source_files:
        risks.append(
            Risk("No Python source files detected", "major", "src/", "source_file_count=0")
        )
        fixes.append(
            Fix(
                "Add Python source package or scan the repository root",
                "No Python source files were found under src/.",
                "src/",
                10,
            )
        )
    if markers["fixme"]:
        risks.append(Risk("FIXME markers present", "minor", "repo", f"fixme={markers['fixme']}"))
        fixes.append(
            Fix(
                "Triage FIXME markers", "FIXME markers were found in scanned text files.", "repo", 3
            )
        )
    signals = {
        "source_file_count": len(source_files),
        "text_files_scanned": len(text_files),
        **markers,
    }
    return risks, fixes, [_rel(root, p) for p in source_files[:8]], signals


def _package_surface(root: Path) -> tuple[list[Risk], list[Fix], list[str], dict[str, object]]:
    pyproject = root / "pyproject.toml"
    requirements = root / "requirements.txt"
    files = [name for name in ("pyproject.toml", "requirements.txt") if (root / name).exists()]
    if pyproject.exists() or requirements.exists():
        return (
            [],
            [],
            files,
            {"has_pyproject": pyproject.exists(), "has_requirements": requirements.exists()},
        )
    return (
        [
            Risk(
                "No Python packaging metadata detected",
                "major",
                "pyproject.toml",
                "has_pyproject=false",
            )
        ],
        [
            Fix(
                "Add Python packaging metadata",
                "No pyproject.toml or requirements.txt was found.",
                "pyproject.toml",
                9,
            )
        ],
        files,
        {"has_pyproject": False, "has_requirements": False},
    )


def _score(risks: list[Risk]) -> int:
    penalties = {"major": 35, "moderate": 15, "minor": 5}
    return max(0, 100 - sum(penalties.get(risk.severity, 5) for risk in risks))


def _decision(score: int, risks: list[Risk]) -> str:
    if any(risk.severity == "major" for risk in risks):
        return "NO-SHIP"
    if score >= 85:
        return "SHIP"
    return "BOOST"


def _next_prs(risks: list[Risk], fixes: list[Fix]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    if any(risk.file.startswith(".github/workflows") for risk in risks):
        candidates.append(
            {
                "title": "ci-bootstrap",
                "reason": "Restore deterministic CI workflow coverage.",
                "files": [".github/workflows"],
                "priority": 10,
            }
        )
    if any(risk.file.startswith("tests") for risk in risks):
        candidates.append(
            {
                "title": "contract-test-boost",
                "reason": "Expand high-signal CLI and JSON contract coverage.",
                "files": ["tests/"],
                "priority": 8,
            }
        )
    if any(risk.file in {"README.md", "mkdocs.yml"} for risk in risks):
        candidates.append(
            {
                "title": "docs-front-door",
                "reason": "Tighten adopter docs and navigation readiness.",
                "files": ["README.md", "docs/", "mkdocs.yml"],
                "priority": 7,
            }
        )
    if any(risk.file == "SECURITY.md" for risk in risks):
        candidates.append(
            {
                "title": "security-posture",
                "reason": "Document security contact and vulnerability handling posture.",
                "files": ["SECURITY.md"],
                "priority": 7,
            }
        )
    if not candidates and fixes:
        first = fixes[0]
        candidates.append(
            {
                "title": "release-hardening",
                "reason": first.reason,
                "files": [first.file],
                "priority": first.priority,
            }
        )
    if not candidates:
        candidates.append(
            {
                "title": "policy-threshold-hardening",
                "reason": "No hard blockers found; raise confidence by tightening release gate evidence.",
                "files": ["src/", "tests/", "docs/"],
                "priority": 4,
            }
        )
    return sorted(candidates, key=lambda item: (-int(item["priority"]), str(item["title"])))[:8]


def build_scan(root: Path, minutes: int, max_lines: int) -> dict[str, object]:
    resolved = root.resolve()
    scan_limit = max(100, min(1000, int(minutes) * 200))
    risks: list[Risk] = []
    fixes: list[Fix] = []
    high_files: list[str] = []
    evidence_files: list[str] = []
    signals: dict[str, object] = {}
    collectors = (
        _workflow_surface,
        _test_surface,
        _docs_surface,
        _security_surface,
        _evidence_surface,
        _package_surface,
    )
    for collector in collectors:
        local_risks, local_fixes, local_files, local_signals = collector(resolved)
        risks.extend(local_risks)
        fixes.extend(local_fixes)
        if collector is _evidence_surface:
            evidence_files.extend(local_files)
        else:
            high_files.extend(local_files)
        signals.update(local_signals)
    source_risks, source_fixes, source_files, source_signals = _source_surface(resolved, scan_limit)
    risks.extend(source_risks)
    fixes.extend(source_fixes)
    high_files.extend(source_files)
    signals.update(source_signals)
    signals["scan_budget_file_limit"] = scan_limit
    risks = sorted(
        risks,
        key=lambda r: ({"major": 0, "moderate": 1, "minor": 2}.get(r.severity, 3), r.title, r.file),
    )
    fixes = sorted(fixes, key=lambda f: (-f.priority, f.title, f.file))
    score = _score(risks)
    decision = _decision(score, risks)
    risk_dicts = _unique_dicts([asdict(risk) for risk in risks], "title")
    fix_dicts = _unique_dicts([asdict(fix) for fix in fixes], "title")
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit boost scan",
        "root": str(resolved),
        "decision": decision,
        "score": score,
        "budget": {
            "minutes": int(minutes),
            "max_lines": int(max_lines),
            "scan_file_limit": scan_limit,
        },
        "summary": f"{len(risk_dicts)} risk signal(s), {len(fix_dicts)} fix recommendation(s), {len(evidence_files)} evidence file(s).",
        "top_risks": risk_dicts[:8],
        "recommended_fixes": fix_dicts[:10],
        "high_signal_files": _unique(high_files)[:16],
        "next_pr_candidates": _next_prs(risks, fixes),
        "evidence_files": _unique(sorted(evidence_files))[:12],
        "signals": dict(sorted(signals.items())),
    }


def _render_section(lines: list[str], title: str, items: list[object], formatter) -> None:
    lines.append(f"{title}:")
    if not items:
        lines.append("- none")
        return
    for item in items:
        lines.append(formatter(item))


def render_text(payload: dict[str, object], max_lines: int) -> str:
    lines = [
        "Boost Scan Engine Report",
        f"decision: {payload['decision']}",
        f"score: {payload['score']}",
        f"summary: {payload['summary']}",
    ]
    _render_section(
        lines,
        "top risks",
        payload["top_risks"],
        lambda item: f"- {item['severity']}: {item['title']} ({item['file']})",
    )
    _render_section(
        lines,
        "recommended fixes",
        payload["recommended_fixes"],
        lambda item: f"- {item['title']} ({item['file']})",
    )
    _render_section(
        lines, "high-signal files", payload["high_signal_files"], lambda item: f"- {item}"
    )
    _render_section(
        lines,
        "next PR candidates",
        payload["next_pr_candidates"],
        lambda item: f"- {item['title']}: {item['reason']}",
    )
    _render_section(lines, "evidence files", payload["evidence_files"], lambda item: f"- {item}")
    return "\n".join(lines[: max(1, int(max_lines))])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdetkit boost")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan = sub.add_parser("scan", help="Run deterministic high-signal local repo scan")
    scan.add_argument("path")
    scan.add_argument("--minutes", type=int, default=5)
    scan.add_argument("--max-lines", type=int, default=100)
    scan.add_argument("--format", choices=["text", "operator-json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    payload = build_scan(Path(ns.path), int(ns.minutes), int(ns.max_lines))
    if ns.format == "operator-json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload, int(ns.max_lines)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
