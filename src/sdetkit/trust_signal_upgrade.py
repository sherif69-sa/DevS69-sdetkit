from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

_PAGE_PATH = "docs/integrations-trust-signal-upgrade.md"

_SECTION_HEADER = "# Trust signal upgrade (Day 22)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 22",
    "## Trust signal inputs",
    "## Fast verification commands",
    "## Scoring model",
    "## Execution evidence mode",
    "## Visibility checklist",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit trust-signal-upgrade --format json --strict",
    "python -m sdetkit trust-signal-upgrade --emit-pack-dir docs/artifacts/day22-trust-pack --format json --strict",
    "python -m sdetkit trust-signal-upgrade --execute --evidence-dir docs/artifacts/day22-trust-pack/evidence --format json --strict",
    "python scripts/check_day22_trust_signal_upgrade_contract.py",
]

_EXECUTION_COMMANDS = [
    "python -m sdetkit trust-signal-upgrade --format json --strict",
    "python -m sdetkit trust-signal-upgrade --emit-pack-dir docs/artifacts/day22-trust-pack --format json --strict",
    "python scripts/check_day22_trust_signal_upgrade_contract.py --skip-evidence",
]

_DAY22_DEFAULT_PAGE = """# Trust signal upgrade (Day 22)

Day 22 tightens trust posture visibility by keeping reliability badges and policy docs obvious for new adopters.

## Who should run Day 22

- Maintainers responsible for external project trust posture.
- Security/compliance reviewers validating governance visibility.
- DevRel contributors preparing launch-ready README and docs snapshots.

## Trust signal inputs

- README badge row for CI, quality, mutation tests, security, and pages.
- Governance docs (`SECURITY.md`, `docs/security.md`, and policy baseline docs).
- Workflow visibility checks for core trust lanes (`security.yml`, `pages.yml`, and `ci.yml`).

## Fast verification commands

```bash
python -m sdetkit trust-signal-upgrade --format json --strict
python -m sdetkit trust-signal-upgrade --emit-pack-dir docs/artifacts/day22-trust-pack --format json --strict
python -m sdetkit trust-signal-upgrade --execute --evidence-dir docs/artifacts/day22-trust-pack/evidence --format json --strict
python scripts/check_day22_trust_signal_upgrade_contract.py
```

## Scoring model

Day 22 computes a weighted trust score (0-100):

- Badge visibility: 50 points
- Policy docs + discoverability links: 30 points
- Workflow + docs index governance visibility: 20 points

`--strict` fails if critical checks are missing or score is below `--min-trust-score`.

## Execution evidence mode

`--execute` runs the Day 22 command chain and writes deterministic logs into `--evidence-dir`.

## Visibility checklist

- [ ] CI/reliability badges are present in README.
- [ ] Security and policy docs are linked from README governance section.
- [ ] Core trust workflows (`ci.yml`, `security.yml`, `pages.yml`) are present.
- [ ] Day 22 trust score summary is emitted for closeout.
"""

_BADGE_SIGNALS = [
    {"key": "ci_badge", "marker": "actions/workflows/ci.yml/badge.svg", "weight": 10},
    {"key": "quality_badge", "marker": "actions/workflows/quality.yml/badge.svg", "weight": 10},
    {"key": "mutation_badge", "marker": "actions/workflows/mutation-tests.yml/badge.svg", "weight": 10},
    {"key": "security_badge", "marker": "actions/workflows/security.yml/badge.svg", "weight": 10},
    {"key": "pages_badge", "marker": "actions/workflows/pages.yml/badge.svg", "weight": 10},
]

_POLICY_SIGNALS = [
    {
        "key": "security_doc_exists",
        "path": "SECURITY.md",
        "readme_marker": "[Security Docs](docs/security.md)",
        "weight": 10,
    },
    {
        "key": "security_guide_exists",
        "path": "docs/security.md",
        "readme_marker": "[Security docs](docs/security.md)",
        "weight": 10,
    },
    {
        "key": "policy_baseline_exists",
        "path": "docs/policy-and-baselines.md",
        "readme_marker": "[policy baselines](docs/policy-and-baselines.md)",
        "weight": 10,
    },
]

_GOVERNANCE_SIGNALS = [
    {"key": "ci_workflow", "path": ".github/workflows/ci.yml", "weight": 6},
    {"key": "security_workflow", "path": ".github/workflows/security.yml", "weight": 8},
    {"key": "pages_workflow", "path": ".github/workflows/pages.yml", "weight": 4},
    {"key": "docs_index_day22", "marker": "day-22-ultra-upgrade-report.md", "weight": 2},
]

_CRITICAL_FAILURE_KEYS = {"security_doc_exists", "security_workflow", "ci_workflow"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _evaluate_signals(root: Path, readme_text: str, docs_index_text: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for signal in _BADGE_SIGNALS:
        passed = signal["marker"] in readme_text
        rows.append(
            {
                "key": signal["key"],
                "category": "badges",
                "weight": signal["weight"],
                "passed": passed,
                "evidence": signal["marker"],
            }
        )

    for signal in _POLICY_SIGNALS:
        exists = (root / signal["path"]).exists()
        linked = signal["readme_marker"] in readme_text
        passed = exists and linked
        rows.append(
            {
                "key": signal["key"],
                "category": "policy",
                "weight": signal["weight"],
                "passed": passed,
                "evidence": {"path": signal["path"], "exists": exists, "readme_link": linked},
            }
        )

    for signal in _GOVERNANCE_SIGNALS:
        if "path" in signal:
            passed = (root / signal["path"]).exists()
            evidence: object = signal["path"]
        else:
            passed = signal["marker"] in docs_index_text
            evidence = signal["marker"]
        rows.append(
            {
                "key": signal["key"],
                "category": "governance",
                "weight": signal["weight"],
                "passed": passed,
                "evidence": evidence,
            }
        )

    return rows


def build_trust_signal_summary(root: Path, *, readme_path: str = "README.md", docs_index_path: str = "docs/index.md") -> dict[str, object]:
    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    checks = _evaluate_signals(root, readme_text, docs_index_text)

    total_weight = sum(int(item["weight"]) for item in checks)
    earned_weight = sum(int(item["weight"]) for item in checks if item["passed"])
    trust_score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    by_category: dict[str, dict[str, int]] = {}
    for item in checks:
        category = str(item["category"])
        slot = by_category.setdefault(category, {"passed": 0, "total": 0})
        slot["total"] += 1
        if item["passed"]:
            slot["passed"] += 1

    failed = [item for item in checks if not item["passed"]]
    critical_failures = [item["key"] for item in failed if item["key"] in _CRITICAL_FAILURE_KEYS]

    recommendations: list[str] = []
    if any(item["category"] == "badges" for item in failed):
        recommendations.append("Restore missing trust badges in README so reliability status is visible at a glance.")
    if any(item["category"] == "policy" for item in failed):
        recommendations.append("Ensure policy documents exist and are linked from README governance references.")
    if any(item["category"] == "governance" for item in failed):
        recommendations.append("Keep CI/security/pages workflows and docs index trust references present for reviewers.")
    if not recommendations:
        recommendations.append("Trust signals are complete; keep trust badges, policy links, and workflows current each release.")

    return {
        "name": "day22-trust-signal-upgrade",
        "inputs": {"readme": readme_path, "docs_index": docs_index_path},
        "summary": {
            "trust_score": trust_score,
            "trust_label": "strong" if trust_score >= 90 and not critical_failures else "review",
            "weighted_points": {"earned": earned_weight, "total": total_weight},
            "category_coverage": by_category,
            "failed_checks": len(failed),
            "critical_failures": critical_failures,
        },
        "checks": checks,
        "badge_checks": {item["key"]: item["passed"] for item in checks if item["category"] == "badges"},
        "policy_checks": {item["key"]: item["passed"] for item in checks if item["category"] == "policy"},
        "governance_checks": {item["key"]: item["passed"] for item in checks if item["category"] == "governance"},
        "recommendations": recommendations,
    }


def _render_text(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    points = summary["weighted_points"]
    lines = [
        "Day 22 trust signal upgrade",
        "",
        f"Trust score: {summary['trust_score']}",
        f"Trust label: {summary['trust_label']}",
        f"Weighted points: {points['earned']}/{points['total']}",
        f"Failed checks: {summary['failed_checks']}",
        f"Critical failures: {', '.join(summary['critical_failures']) or 'none'}",
        "",
        "Recommendations:",
    ]
    lines.extend(f"- {item}" for item in payload["recommendations"])
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    points = summary["weighted_points"]
    lines = [
        "# Day 22 trust signal upgrade",
        "",
        "## Trust posture",
        "",
        f"- Trust score: **{summary['trust_score']}**",
        f"- Trust label: **{summary['trust_label']}**",
        f"- Weighted points: **{points['earned']}/{points['total']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        f"- Critical failures: **{', '.join(summary['critical_failures']) or 'none'}**",
        "",
        "## Check matrix",
        "",
    ]
    lines.extend(
        f"- **{item['category']}::{item['key']}** ({item['weight']} pts): {'pass' if item['passed'] else 'missing'}"
        for item in payload["checks"]
    )
    lines.extend(["", "## Recommendations", ""])
    lines.extend(f"- {item}" for item in payload["recommendations"])
    return "\n".join(lines) + "\n"


def _emit_pack(root: Path, out_dir: Path, payload: dict[str, object]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "day22-trust-summary.json"
    markdown = out_dir / "day22-trust-scorecard.md"
    checklist = out_dir / "day22-visibility-checklist.md"
    validation = out_dir / "day22-validation-commands.md"
    action_plan = out_dir / "day22-trust-action-plan.md"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown.write_text(_render_markdown(payload), encoding="utf-8")
    checklist.write_text(
        "\n".join(
            [
                "# Day 22 visibility checklist",
                "",
                "- [ ] README trust badges are up to date.",
                "- [ ] Security and policy docs are discoverable from README/docs index.",
                "- [ ] Core trust workflows (ci/security/pages) are present.",
                "- [ ] Day 22 trust score is attached to release closeout.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    action_plan.write_text(
        "\n".join(["# Day 22 trust action plan", "", *[f"- {item}" for item in payload["recommendations"]], ""]),
        encoding="utf-8",
    )
    validation.write_text(
        "\n".join(["# Day 22 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```", ""]),
        encoding="utf-8",
    )
    return [str(path.relative_to(root)) for path in (summary, markdown, checklist, action_plan, validation)]


def _execute_commands(commands: list[str], timeout_sec: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx, command in enumerate(commands, start=1):
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout_sec, check=False)
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
    summary = out / "day22-execution-summary.json"
    payload = {
        "name": "day22-trust-signal-upgrade-execution",
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
        prog="sdetkit trust-signal-upgrade",
        description="Generate Day 22 trust signal posture from badges, policy visibility, and governance checks.",
    )
    p.add_argument("--root", default=".", help="Repository root path.")
    p.add_argument("--readme", default="README.md", help="README path used for trust checks.")
    p.add_argument("--docs-index", default="docs/index.md", help="Docs index path used for visibility checks.")
    p.add_argument("--min-trust-score", type=float, default=90.0, help="Minimum trust score for strict pass.")
    p.add_argument("--write-defaults", action="store_true", help="Create default Day 22 integration page if missing.")
    p.add_argument("--emit-pack-dir", default="", help="Optional output directory for generated Day 22 files.")
    p.add_argument("--execute", action="store_true", help="Run Day 22 command chain and emit evidence logs.")
    p.add_argument(
        "--evidence-dir",
        default="docs/artifacts/day22-trust-pack/evidence",
        help="Output directory for execution evidence logs.",
    )
    p.add_argument("--timeout-sec", type=int, default=120, help="Per-command timeout used by --execute.")
    p.add_argument("--strict", action="store_true", help="Fail when trust score/docs contract/critical checks are not ready.")
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format.")
    p.add_argument("--output", default="", help="Optional file to write primary output.")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    root = Path(ns.root).resolve()

    page = root / _PAGE_PATH
    if ns.write_defaults:
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(_DAY22_DEFAULT_PAGE, encoding="utf-8")

    page_text = _read(page)
    missing_sections = [section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]

    payload = build_trust_signal_summary(root, readme_path=ns.readme, docs_index_path=ns.docs_index)
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
        bool(payload["strict_failures"])
        or payload["summary"]["trust_score"] < ns.min_trust_score
        or bool(payload["summary"]["critical_failures"])
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
