from __future__ import annotations

import argparse
import csv
import html
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SignalRow:
    name: str
    markdown_cell: str

    @property
    def has_badge_link(self) -> bool:
        return "![" in self.markdown_cell and "](" in self.markdown_cell

    @property
    def badge_image_url(self) -> str | None:
        match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", self.markdown_cell)
        return match.group(1) if match else None

    @property
    def target_url(self) -> str | None:
        match = re.search(r"\]\(([^)]+)\)$", self.markdown_cell.strip())
        return match.group(1) if match else None


@dataclass(frozen=True)
class PaletteRow:
    media: str
    scheme: str
    primary: str
    accent: str


@dataclass(frozen=True)
class SnapshotData:
    signals: list[SignalRow]
    palettes: list[PaletteRow]
    proof_rows: list[dict[str, str]]


def _extract_signal_rows(readme_text: str) -> list[SignalRow]:
    rows: list[SignalRow] = []
    in_table = False
    for line in readme_text.splitlines():
        if line.strip() == "| Signal | Live status |":
            in_table = True
            continue
        if in_table and line.strip() == "|---|---|":
            continue
        if in_table:
            if not line.startswith("|"):
                break
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 2:
                rows.append(SignalRow(name=parts[0], markdown_cell=parts[1]))
    return rows


def _extract_palette(mkdocs_text: str) -> list[PaletteRow]:
    entries: list[PaletteRow] = []
    media_blocks = re.split(r"\n\s*- media:", mkdocs_text)
    for block in media_blocks[1:]:
        media_line = block.splitlines()[0].strip().strip('"')
        primary = re.search(r"^\s*primary:\s*(.+)$", block, flags=re.MULTILINE)
        accent = re.search(r"^\s*accent:\s*(.+)$", block, flags=re.MULTILINE)
        scheme = re.search(r"^\s*scheme:\s*(.+)$", block, flags=re.MULTILINE)
        entries.append(
            PaletteRow(
                media=media_line,
                scheme=scheme.group(1).strip() if scheme else "unknown",
                primary=primary.group(1).strip() if primary else "unknown",
                accent=accent.group(1).strip() if accent else "unknown",
            )
        )
    return entries


def _load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _build_data(readme: Path, mkdocs: Path, proof_csv: Path) -> SnapshotData:
    return SnapshotData(
        signals=_extract_signal_rows(readme.read_text(encoding="utf-8")),
        palettes=_extract_palette(mkdocs.read_text(encoding="utf-8")),
        proof_rows=_load_csv_rows(proof_csv),
    )


def _readability_score(data: SnapshotData) -> int:
    badge_quality = sum(1 for s in data.signals if s.has_badge_link)
    active_streams = sum(1 for row in data.proof_rows if row.get("status") == "active")
    palette_rows = len(data.palettes)
    return badge_quality * 2 + active_streams + palette_rows


def _score_grade(score: int) -> str:
    if score >= 16:
        return "A"
    if score >= 12:
        return "B"
    if score >= 8:
        return "C"
    return "D"


def build_snapshot_markdown(data: SnapshotData) -> str:
    score = _readability_score(data)
    grade = _score_grade(score)
    lines = [
        "# Repo visual snapshot",
        "",
        "This artifact summarizes README live signals, docs palette settings, and proof map readability.",
        "",
        "## Scorecard",
        "",
        f"- Composite readability score: **{score}**",
        f"- Grade: **{grade}**",
        f"- Signal rows found: **{len(data.signals)}**",
        f"- Active proof streams: **{sum(1 for row in data.proof_rows if row.get('status') == 'active')}**",
        "",
        "## README live-signal coverage",
        "",
        "| Signal | Badge/Link present | Badge image URL found |",
        "|---|---|---|",
    ]
    for signal in data.signals:
        lines.append(
            f"| {signal.name} | {'✅' if signal.has_badge_link else '❌'} | {'✅' if signal.badge_image_url else '❌'} |"
        )

    lines.extend(
        [
            "",
            "## Docs theme palette",
            "",
            "| Media query | Scheme | Primary | Accent |",
            "|---|---|---|---|",
        ]
    )
    for entry in data.palettes:
        lines.append(f"| {entry.media} | `{entry.scheme}` | `{entry.primary}` | `{entry.accent}` |")

    lines.extend(
        [
            "",
            "## Proof map CSV view",
            "",
            "| Stream | Owner | KPI target | Risk | Status |",
            "|---|---|---|---|---|",
        ]
    )
    for row in data.proof_rows:
        lines.append(
            "| "
            f"{row.get('stream', 'n/a')} | "
            f"{row.get('owner', 'n/a')} | "
            f"{row.get('kpi_target', 'n/a')} | "
            f"{row.get('risk_flag', 'n/a')} | "
            f"{row.get('status', 'n/a')} |"
        )

    lines.extend(["", "## Signal targets", "", "| Signal | Target URL |", "|---|---|"])
    for signal in data.signals:
        lines.append(f"| {signal.name} | {signal.target_url or 'n/a'} |")

    return "\n".join(lines) + "\n"


def build_snapshot_html(data: SnapshotData) -> str:
    score = _readability_score(data)
    grade = _score_grade(score)
    active_streams = sum(1 for row in data.proof_rows if row.get("status") == "active")
    max_score = 20
    progress = min(100, int((score / max_score) * 100))

    signal_cards = "\n".join(
        (
            "<div class='card'>"
            f"<h3>{html.escape(signal.name)}</h3>"
            f"<p>Status: {'✅ linked badge' if signal.has_badge_link else '❌ missing badge link'}</p>"
            f"<p><a href='{html.escape(signal.target_url or '#')}'>{html.escape(signal.target_url or 'n/a')}</a></p>"
            "</div>"
        )
        for signal in data.signals
    )

    palette_rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(entry.media)}</td>"
            f"<td>{html.escape(entry.scheme)}</td>"
            f"<td><span class='chip'>{html.escape(entry.primary)}</span></td>"
            f"<td><span class='chip'>{html.escape(entry.accent)}</span></td>"
            "</tr>"
        )
        for entry in data.palettes
    )

    proof_rows = "\n".join(
        (
            "<tr>"
            f"<td>{html.escape(row.get('stream', 'n/a'))}</td>"
            f"<td>{html.escape(row.get('owner', 'n/a'))}</td>"
            f"<td>{html.escape(row.get('kpi_target', 'n/a'))}</td>"
            f"<td>{html.escape(row.get('risk_flag', 'n/a'))}</td>"
            f"<td>{html.escape(row.get('status', 'n/a'))}</td>"
            "</tr>"
        )
        for row in data.proof_rows
    )

    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>Repo Visual Snapshot</title>
  <style>
    body {{ font-family: Inter, Segoe UI, system-ui, sans-serif; margin: 0; background: #0b1020; color: #e6e9f4; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    .hero {{ background: linear-gradient(135deg, #5b4bff, #0ea5a4); padding: 20px; border-radius: 14px; }}
    .hero h1 {{ margin: 0 0 8px 0; }}
    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }}
    .kpi {{ background: #131b33; border: 1px solid #273458; border-radius: 12px; padding: 12px; }}
    .progress {{ height: 10px; background: #1f2b4d; border-radius: 999px; overflow: hidden; margin-top: 8px; }}
    .bar {{ height: 100%; width: {progress}%; background: linear-gradient(90deg, #10b981, #22d3ee); }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 20px; }}
    .card {{ background: #121a30; border: 1px solid #283659; border-radius: 12px; padding: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 14px; background: #121a30; border-radius: 12px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #243256; text-align: left; padding: 10px; }}
    th {{ background: #192548; }}
    .chip {{ background: #243256; border-radius: 999px; padding: 2px 8px; }}
    a {{ color: #7dd3fc; }}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='hero'>
      <h1>Repo Visual Snapshot</h1>
      <p>A high-contrast dashboard for README signals, docs theme palette, and proof-map readability.</p>
      <div class='progress'><div class='bar'></div></div>
      <p>Readability score: <strong>{score}</strong>/20 · Grade <strong>{grade}</strong></p>
    </section>

    <section class='kpis'>
      <div class='kpi'><strong>Signal rows</strong><br />{len(data.signals)}</div>
      <div class='kpi'><strong>Badge links</strong><br />{sum(1 for s in data.signals if s.has_badge_link)}</div>
      <div class='kpi'><strong>Palettes</strong><br />{len(data.palettes)}</div>
      <div class='kpi'><strong>Active streams</strong><br />{active_streams}</div>
    </section>

    <h2>Signal cards</h2>
    <section class='cards'>
      {signal_cards}
    </section>

    <h2>Docs theme palette</h2>
    <table>
      <thead><tr><th>Media</th><th>Scheme</th><th>Primary</th><th>Accent</th></tr></thead>
      <tbody>{palette_rows}</tbody>
    </table>

    <h2>Proof stream table</h2>
    <table>
      <thead><tr><th>Stream</th><th>Owner</th><th>KPI</th><th>Risk</th><th>Status</th></tr></thead>
      <tbody>{proof_rows}</tbody>
    </table>
  </div>
</body>
</html>
"""


def capture_private_screenshot(html_report: str, screenshot_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "playwright is required for screenshots. "
            "Install with: python -m pip install playwright && python -m playwright install chromium"
        ) from exc

    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as handle:
        handle.write(html_report)
        temp_html = Path(handle.name)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1366, "height": 2200})
            page.goto(temp_html.as_uri(), wait_until="networkidle")
            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
    finally:
        temp_html.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render visual snapshot reports for repo presentation assets."
    )
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--mkdocs", type=Path, default=Path("mkdocs.yml"))
    parser.add_argument(
        "--proof-csv",
        type=Path,
        default=Path("docs/artifacts/case-snippet-closeout-pack/proof-map.csv"),
    )
    parser.add_argument(
        "--out-md", type=Path, default=Path("docs/artifacts/repo-visual-snapshot.md")
    )
    parser.add_argument(
        "--out-html", type=Path, default=Path("docs/artifacts/repo-visual-snapshot.html")
    )
    parser.add_argument(
        "--private-screenshot",
        type=Path,
        default=Path(".sdetkit/out/repo-visual-snapshot.png"),
        help="Private screenshot path (ignored by git by default).",
    )
    parser.add_argument(
        "--capture-screenshot",
        action="store_true",
        help="Capture a private local screenshot with Playwright.",
    )
    args = parser.parse_args(argv)

    data = _build_data(args.readme, args.mkdocs, args.proof_csv)
    markdown = build_snapshot_markdown(data)
    html_report = build_snapshot_html(data)

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_html.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(markdown, encoding="utf-8")
    args.out_html.write_text(html_report, encoding="utf-8")
    print(f"wrote {args.out_md}")
    print(f"wrote {args.out_html}")
    if args.capture_screenshot:
        capture_private_screenshot(html_report, args.private_screenshot)
        print(f"wrote private screenshot {args.private_screenshot}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
