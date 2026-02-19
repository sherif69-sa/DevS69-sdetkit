from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

_LINK_PATTERN = re.compile(r'\[[^\]]+\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Issue:
    file: str
    line: int
    message: str


@dataclass(frozen=True)
class Report:
    files_checked: int
    links_checked: int
    issues: list[Issue]

    @property
    def ok(self) -> bool:
        return not self.issues


def _slugify(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^a-z0-9\-\s]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _anchors_for(markdown_text: str) -> set[str]:
    anchors: set[str] = set()
    for _, title in _HEADING_PATTERN.findall(markdown_text):
        slug = _slugify(title)
        if slug:
            anchors.add(slug)
    return anchors


def _iter_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    readme = root / "README.md"
    if readme.exists():
        files.append(readme)
    docs = root / "docs"
    if docs.exists():
        files.extend(sorted(docs.rglob("*.md")))
    return files


def run_docs_qa(root: Path) -> Report:
    markdown_files = _iter_markdown_files(root)
    anchors_cache: dict[Path, set[str]] = {}
    for path in markdown_files:
        anchors_cache[path] = _anchors_for(path.read_text(encoding="utf-8"))

    issues: list[Issue] = []
    links_checked = 0

    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), start=1):
            for match in _LINK_PATTERN.findall(line):
                target = match.strip()
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.startswith("#"):
                    links_checked += 1
                    frag = target[1:]
                    if frag and frag not in anchors_cache[path]:
                        issues.append(Issue(str(path.relative_to(root)), i, f"missing local anchor: {target}"))
                    continue

                links_checked += 1
                target_path_str, _, frag = target.partition("#")
                resolved = (path.parent / target_path_str).resolve()
                if not resolved.exists():
                    issues.append(Issue(str(path.relative_to(root)), i, f"missing link target: {target_path_str}"))
                    continue
                if resolved.suffix.lower() == ".md" and frag:
                    rel = resolved.relative_to(root)
                    anchors = anchors_cache.get(root / rel)
                    if anchors is None:
                        anchors = _anchors_for(resolved.read_text(encoding="utf-8"))
                        anchors_cache[root / rel] = anchors
                    if frag not in anchors:
                        issues.append(Issue(str(path.relative_to(root)), i, f"missing target anchor in {target_path_str}: #{frag}"))

    return Report(files_checked=len(markdown_files), links_checked=links_checked, issues=issues)


def _render_text(report: Report) -> str:
    lines = [
        "# Day 6 conversion QA report",
        f"- files checked: {report.files_checked}",
        f"- internal markdown links checked: {report.links_checked}",
        f"- status: {'pass' if report.ok else 'fail'}",
    ]
    if report.issues:
        lines.append("- issues:")
        lines.extend(f"  - {item.file}:{item.line} — {item.message}" for item in report.issues)
    else:
        lines.append("- issues: none")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit docs-qa", description="Validate README/docs markdown links and anchors.")
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", default=None, help="Optional output path for generated report.")
    ns = parser.parse_args(argv)

    report = run_docs_qa(Path(ns.root).resolve())

    if ns.format == "json":
        payload = {
            "ok": report.ok,
            "files_checked": report.files_checked,
            "links_checked": report.links_checked,
            "issues": [item.__dict__ for item in report.issues],
        }
        rendered = json.dumps(payload, indent=2) + "\n"
    else:
        rendered = _render_text(report)

    if ns.output:
        out_path = Path(ns.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
