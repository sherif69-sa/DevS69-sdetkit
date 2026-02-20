from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

_PAGE_PATH = "docs/integrations-release-narrative.md"

_SECTION_HEADER = "# Release narrative (Day 20)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 20",
    "## Story inputs",
    "## Fast verification commands",
    "## Execution evidence mode",
    "## Narrative channels",
    "## Storytelling checklist",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit release-narrative --format json --strict",
    "python -m sdetkit release-narrative --emit-pack-dir docs/artifacts/day20-release-narrative-pack --format json --strict",
    "python -m sdetkit release-narrative --execute --evidence-dir docs/artifacts/day20-release-narrative-pack/evidence --format json --strict",
    "python scripts/check_day20_release_narrative_contract.py",
]

_EXECUTION_COMMANDS = [
    "python -m sdetkit release-narrative --format json --strict",
    "python -m sdetkit release-narrative --emit-pack-dir docs/artifacts/day20-release-narrative-pack --format json --strict",
    "python scripts/check_day20_release_narrative_contract.py --skip-evidence",
]

_DAY20_DEFAULT_PAGE = """# Release narrative (Day 20)

Day 20 translates release readiness evidence into non-maintainer changelog storytelling.

## Who should run Day 20

- Maintainers writing release notes for mixed technical/non-technical audiences.
- Developer advocates preparing community launch posts.
- Product and support teams aligning on what changed and why it matters.

## Story inputs

- Day 19 release-readiness summary (`release_score`, `gate_status`, recommendations).
- Changelog highlights for user-visible updates.

## Fast verification commands

```bash
python -m sdetkit release-narrative --format json --strict
python -m sdetkit release-narrative --emit-pack-dir docs/artifacts/day20-release-narrative-pack --format json --strict
python -m sdetkit release-narrative --execute --evidence-dir docs/artifacts/day20-release-narrative-pack/evidence --format json --strict
python scripts/check_day20_release_narrative_contract.py
```

## Execution evidence mode

`--execute` runs the Day 20 command chain and writes deterministic logs into `--evidence-dir`.

## Narrative channels

- Release notes (maintainer + product audiences)
- Community post (social + discussion channels)
- Internal weekly update (engineering + support)

## Storytelling checklist

- [ ] Outcome-first summary is present.
- [ ] Risks and follow-ups are explicit.
- [ ] Validation evidence is linked.
- [ ] Audience-specific blurbs are generated.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_day19_summary(path: Path) -> tuple[float, str, list[str]]:
    payload = _read_json(path)
    summary = payload.get("summary", payload)
    if not isinstance(summary, dict):
        raise ValueError("day19 summary payload must include a summary object")

    release_score_raw = summary.get("release_score", 0.0)
    try:
        release_score = float(release_score_raw)
    except (TypeError, ValueError):
        raise ValueError("day19 summary release_score must be numeric") from None

    gate_status_raw = summary.get("gate_status", "review")
    gate_status = str(gate_status_raw).strip().lower() or "review"

    recommendations_raw = payload.get("recommendations", summary.get("recommendations", []))
    recommendations: list[str] = []
    if isinstance(recommendations_raw, list):
        for item in recommendations_raw:
            if isinstance(item, str) and item.strip():
                recommendations.append(item.strip())

    return release_score, gate_status, recommendations


def _extract_changelog_bullets(path: Path, limit: int = 6) -> list[str]:
    if not path.exists():
        return ["No CHANGELOG entry was found; include notable user-impact updates before release."]

    bullets: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith(("- ", "* ")):
            bullets.append(line[2:].strip())
        if len(bullets) >= limit:
            break

    if bullets:
        return bullets
    return ["CHANGELOG currently has no bullet highlights; add outcome-focused release notes."]


def build_release_narrative(day19_summary: Path, changelog: Path, *, day19_label: str = "", changelog_label: str = "") -> dict[str, object]:
    release_score, gate_status, recommendations = _load_day19_summary(day19_summary)
    highlights = _extract_changelog_bullets(changelog)

    readiness_label = "ready" if gate_status == "pass" and release_score >= 90 else "review"
    headline = (
        "This release is ready to communicate broadly with a stable quality posture."
        if readiness_label == "ready"
        else "This release needs focused follow-up before broad promotion."
    )

    risks = recommendations if recommendations else ["No explicit Day 19 recommendations were provided."]

    channels = {
        "release_notes": f"{headline} Key highlights: {highlights[0]}",
        "community_post": "Shipping update: stronger quality gates, clearer evidence, and a smoother adoption path for teams.",
        "internal_update": "Day 20 narrative pack is ready. Reuse the highlights/risks sections in weekly status and customer comms.",
    }

    return {
        "name": "day20-release-narrative",
        "inputs": {
            "day19_summary": day19_label or str(day19_summary),
            "changelog": changelog_label or str(changelog),
        },
        "summary": {
            "release_score": round(release_score, 2),
            "gate_status": gate_status,
            "readiness_label": readiness_label,
            "headline": headline,
        },
        "highlights": highlights,
        "risks": risks,
        "audience_blurbs": {
            "non_maintainers": "What changed: clearer quality gates, faster release confidence, and traceable evidence for audits.",
            "engineering": "Ship with confidence by tying Day 19 release score to concrete checklist and evidence artifacts.",
            "support": "Use highlights + risks sections to pre-brief known changes and probable user questions.",
        },
        "narrative_channels": channels,
        "call_to_action": "Share this narrative in release notes, weekly updates, and community announcements.",
    }


def _render_text(payload: dict[str, object]) -> str:
    lines = [
        "Day 20 release narrative",
        "",
        f"Headline: {payload['summary']['headline']}",
        f"Release score: {payload['summary']['release_score']}",
        f"Gate status: {payload['summary']['gate_status']}",
        "",
        "Highlights:",
    ]
    lines.extend(f"- {item}" for item in payload["highlights"])
    lines.append("")
    lines.append("Risks and follow-ups:")
    lines.extend(f"- {item}" for item in payload["risks"])
    lines.append("")
    lines.append("Narrative channels:")
    lines.extend(f"- {name}: {copy}" for name, copy in payload["narrative_channels"].items())
    lines.append("")
    lines.append(f"Call to action: {payload['call_to_action']}")
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Day 20 release narrative",
        "",
        f"**Headline:** {payload['summary']['headline']}",
        "",
        "## Release posture",
        "",
        f"- Release score: **{payload['summary']['release_score']}**",
        f"- Gate status: **{payload['summary']['gate_status']}**",
        f"- Readiness label: **{payload['summary']['readiness_label']}**",
        "",
        "## Highlights",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["highlights"])
    lines.extend(["", "## Risks and follow-ups", ""])
    lines.extend(f"- {item}" for item in payload["risks"])
    lines.extend(["", "## Audience blurbs", ""])
    lines.extend(f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in payload["audience_blurbs"].items())
    lines.extend(["", "## Narrative channels", ""])
    lines.extend(f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in payload["narrative_channels"].items())
    lines.extend(["", f"**Call to action:** {payload['call_to_action']}"])
    return "\n".join(lines) + "\n"


def _emit_pack(root: Path, out_dir: Path, payload: dict[str, object]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "day20-release-narrative-summary.json"
    markdown = out_dir / "day20-release-narrative.md"
    blurbs = out_dir / "day20-audience-blurbs.md"
    channels = out_dir / "day20-channel-posts.md"
    validation = out_dir / "day20-validation-commands.md"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown.write_text(_render_markdown(payload), encoding="utf-8")
    blurbs.write_text(
        "\n".join(
            [
                "# Day 20 audience blurbs",
                "",
                *[f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in payload["audience_blurbs"].items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    channels.write_text(
        "\n".join(
            [
                "# Day 20 narrative channels",
                "",
                *[f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in payload["narrative_channels"].items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    validation.write_text(
        "\n".join(["# Day 20 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```", ""]),
        encoding="utf-8",
    )

    return [str(path.relative_to(root)) for path in (summary, markdown, blurbs, channels, validation)]


def _execute_commands(commands: list[str], timeout_sec: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx, command in enumerate(commands, start=1):
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            rows.append(
                {
                    "index": idx,
                    "command": command,
                    "returncode": proc.returncode,
                    "ok": proc.returncode == 0,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                }
            )
        except subprocess.TimeoutExpired as exc:
            rows.append(
                {
                    "index": idx,
                    "command": command,
                    "returncode": 124,
                    "ok": False,
                    "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                    "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
                    "error": f"timed out after {timeout_sec}s",
                }
            )
    return rows


def _write_execution_evidence(root: Path, evidence_dir: str, rows: list[dict[str, object]]) -> list[str]:
    out = root / evidence_dir
    out.mkdir(parents=True, exist_ok=True)
    summary = out / "day20-execution-summary.json"
    payload = {
        "name": "day20-release-narrative-execution",
        "total_commands": len(rows),
        "passed_commands": len([r for r in rows if r["ok"]]),
        "failed_commands": len([r for r in rows if not r["ok"]]),
        "results": rows,
    }
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    emitted = [summary]
    for row in rows:
        log = out / f"command-{row['index']:02d}.log"
        log.write_text(
            "\n".join(
                [
                    f"command: {row['command']}",
                    f"returncode: {row['returncode']}",
                    f"ok: {row['ok']}",
                    "--- stdout ---",
                    str(row.get("stdout", "")),
                    "--- stderr ---",
                    str(row.get("stderr", "")),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        emitted.append(log)

    return [str(path.relative_to(root)) for path in emitted]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit release-narrative",
        description="Generate Day 20 non-maintainer release storytelling from Day 19 posture.",
    )
    p.add_argument("--root", default=".", help="Repository root path.")
    p.add_argument(
        "--day19-summary",
        default="docs/artifacts/day19-release-readiness-pack/day19-release-readiness-summary.json",
        help="Path to Day 19 release summary JSON.",
    )
    p.add_argument("--changelog", default="CHANGELOG.md", help="Path to changelog markdown file.")
    p.add_argument("--min-release-score", type=float, default=90.0, help="Minimum release score for strict pass.")
    p.add_argument("--write-defaults", action="store_true", help="Create default Day 20 integration page if missing.")
    p.add_argument("--emit-pack-dir", default="", help="Optional output directory for generated Day 20 files.")
    p.add_argument("--execute", action="store_true", help="Run Day 20 command chain and emit evidence logs.")
    p.add_argument(
        "--evidence-dir",
        default="docs/artifacts/day20-release-narrative-pack/evidence",
        help="Output directory for execution evidence logs.",
    )
    p.add_argument("--timeout-sec", type=int, default=120, help="Per-command timeout used by --execute.")
    p.add_argument("--strict", action="store_true", help="Fail when release posture or docs contract checks are not ready.")
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format.")
    p.add_argument("--output", default="", help="Optional file to write primary output.")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    page = root / _PAGE_PATH
    if ns.write_defaults:
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(_DAY20_DEFAULT_PAGE, encoding="utf-8")

    page_text = _read(page)
    missing_sections = [section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]

    payload = build_release_narrative(
        root / ns.day19_summary,
        root / ns.changelog,
        day19_label=ns.day19_summary,
        changelog_label=ns.changelog,
    )
    payload["strict_failures"] = [*missing_sections, *missing_commands]
    payload["score"] = 100.0 if not payload["strict_failures"] else 0.0

    if ns.emit_pack_dir:
        payload["emitted_pack_files"] = _emit_pack(root, root / ns.emit_pack_dir, payload)

    if ns.execute:
        payload["execution_artifacts"] = _write_execution_evidence(
            root,
            ns.evidence_dir,
            _execute_commands(_EXECUTION_COMMANDS, ns.timeout_sec),
        )

    strict_failed = (
        payload["summary"]["readiness_label"] != "ready"
        or payload["summary"]["release_score"] < ns.min_release_score
        or bool(payload["strict_failures"])
    )

    if ns.format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True)
    elif ns.format == "markdown":
        rendered = _render_markdown(payload)
    else:
        rendered = _render_text(payload)

    if ns.output:
        out = root / ns.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered if rendered.endswith("\n") else rendered + "\n", encoding="utf-8")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")

    return 1 if ns.strict and strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
