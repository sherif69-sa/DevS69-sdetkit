from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

_INLINE_LINK_PATTERN = re.compile(r'\[[^\]]+\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
_REFERENCE_DEF_PATTERN = re.compile(r'^\s*\[([^\]]+)\]:\s*(\S+)\s*$', re.MULTILINE)
_REFERENCE_USE_PATTERN = re.compile(r'\[(?P<text>[^\]]+)\]\[(?P<label>[^\]]*)\]')
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_FENCE_PATTERN = re.compile(r"^```", re.MULTILINE)


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
    """Return heading anchors including duplicate-suffixed variants (e.g. -1)."""
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    for _, title in _HEADING_PATTERN.findall(markdown_text):
        base = _slugify(title)
        if not base:
            continue
        count = seen.get(base, 0)
        slug = base if count == 0 else f"{base}-{count}"
        anchors.add(slug)
        seen[base] = count + 1
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


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _in_fenced_code(text: str, offset: int) -> bool:
    return len(_FENCE_PATTERN.findall(text[:offset])) % 2 == 1


def _collect_reference_targets(content: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for match in _REFERENCE_DEF_PATTERN.finditer(content):
        if _in_fenced_code(content, match.start()):
            continue
        label = re.sub(r"\s+", " ", match.group(1).strip().lower())
        refs[label] = match.group(2).strip()
    return refs


def _normalize_fragment(frag: str) -> str:
    return unquote(frag).strip().lower()


def run_docs_qa(root: Path) -> Report:
    markdown_files = _iter_markdown_files(root)
    anchors_cache: dict[Path, set[str]] = {}
    for path in markdown_files:
        anchors_cache[path] = _anchors_for(path.read_text(encoding="utf-8"))

    issues: list[Issue] = []
    links_checked = 0

    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        refs = _collect_reference_targets(content)

        def check_target(target: str, line_no: int) -> None:
            nonlocal links_checked
            target = target.strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                return
            links_checked += 1
            if target.startswith("#"):
                frag = _normalize_fragment(target[1:])
                if frag and frag not in anchors_cache[path]:
                    issues.append(Issue(str(path.relative_to(root)), line_no, f"missing local anchor: {target}"))
                return

            target_path_str, _, frag = target.partition("#")
            resolved = (path.parent / target_path_str).resolve()
            if not resolved.exists():
                issues.append(Issue(str(path.relative_to(root)), line_no, f"missing link target: {target_path_str}"))
                return
            if resolved.suffix.lower() == ".md" and frag:
                anchors = anchors_cache.get(resolved)
                if anchors is None:
                    anchors = _anchors_for(resolved.read_text(encoding="utf-8"))
                    anchors_cache[resolved] = anchors
                normalized_frag = _normalize_fragment(frag)
                if normalized_frag not in anchors:
                    issues.append(
                        Issue(
                            str(path.relative_to(root)),
                            line_no,
                            f"missing target anchor in {target_path_str}: #{frag}",
                        )
                    )

        for match in _INLINE_LINK_PATTERN.finditer(content):
            if _in_fenced_code(content, match.start()):
                continue
            check_target(match.group(1), _line_number(content, match.start()))

        for match in _REFERENCE_USE_PATTERN.finditer(content):
            if _in_fenced_code(content, match.start()):
                continue
            raw_label = match.group("label") or match.group("text")
            norm_label = re.sub(r"\s+", " ", raw_label.strip().lower())
            target = refs.get(norm_label)
            if target is None:
                issues.append(
                    Issue(
                        str(path.relative_to(root)),
                        _line_number(content, match.start()),
                        f"missing reference definition: [{raw_label}]",
                    )
                )
                continue
            check_target(target, _line_number(content, match.start()))

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
