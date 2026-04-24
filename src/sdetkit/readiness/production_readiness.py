from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PHASE_BOOST_BLUEPRINT_FILES = ("docs/production-s-class-90-day-boost.md",)


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    weight: int
    passed: bool
    evidence: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "weight": self.weight,
            "passed": self.passed,
            "evidence": self.evidence,
            "remediation": self.remediation,
        }


def _exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def _first_existing(root: Path, candidates: tuple[str, ...]) -> str | None:
    for rel in candidates:
        if _exists(root, rel):
            return rel
    return None


def _category_progress(checks: list[ReadinessCheck]) -> list[dict[str, Any]]:
    category_map: dict[str, tuple[str, ...]] = {
        "governance": ("governance_core_docs",),
        "engineering": ("engineering_baseline_files", "src_package_present", "lockfiles_present"),
        "quality_and_ci": ("ci_workflows_present", "tests_folder_present"),
        "docs_and_ops": ("docs_operating_surface", "phase_boost_blueprint_present"),
    }
    check_by_id = {check.check_id: check for check in checks}
    categories: list[dict[str, Any]] = []
    for category, check_ids in category_map.items():
        scoped = [check_by_id[cid] for cid in check_ids if cid in check_by_id]
        total_weight = sum(check.weight for check in scoped)
        earned_weight = sum(check.weight for check in scoped if check.passed)
        percent = int(round((earned_weight / total_weight) * 100)) if total_weight else 0
        categories.append(
            {
                "category": category,
                "score": percent,
                "weight_total": total_weight,
                "weight_earned": earned_weight,
                "passed_checks": sum(1 for check in scoped if check.passed),
                "total_checks": len(scoped),
            }
        )
    return categories


def _main_aspect_readiness(checks: list[ReadinessCheck]) -> list[dict[str, Any]]:
    aspect_map: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("governance_and_security", ("governance_core_docs",)),
        ("engineering_baseline", ("engineering_baseline_files", "lockfiles_present")),
        ("quality_execution", ("ci_workflows_present", "tests_folder_present")),
        ("documentation_ops", ("docs_operating_surface", "phase_boost_blueprint_present")),
        ("package_entrypoints", ("src_package_present",)),
    )
    check_by_id = {check.check_id: check for check in checks}
    aspects: list[dict[str, Any]] = []
    for aspect, check_ids in aspect_map:
        scoped = [check_by_id[cid] for cid in check_ids if cid in check_by_id]
        total_weight = sum(check.weight for check in scoped)
        earned_weight = sum(check.weight for check in scoped if check.passed)
        score = int(round((earned_weight / total_weight) * 100)) if total_weight else 0
        aspects.append(
            {
                "aspect": aspect,
                "ready": all(check.passed for check in scoped) and bool(scoped),
                "score": score,
                "passed_checks": sum(1 for check in scoped if check.passed),
                "total_checks": len(scoped),
            }
        )
    return aspects


def build_production_readiness_summary(root: Path) -> dict[str, Any]:
    phase_boost_path = _first_existing(root, _PHASE_BOOST_BLUEPRINT_FILES)
    required_files = [
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "pyproject.toml",
        "Dockerfile",
        "noxfile.py",
        "docs/index.md",
        "docs/repo-audit.md",
        "docs/security.md",
        _PHASE_BOOST_BLUEPRINT_FILES[0],
        "tests/test_cli_sdetkit.py",
    ]
    required_workflows = [
        ".github/workflows/ci.yml",
        ".github/workflows/quality.yml",
        ".github/workflows/security.yml",
        ".github/workflows/pages.yml",
    ]

    checks = [
        ReadinessCheck(
            check_id="governance_core_docs",
            weight=15,
            passed=all(
                _exists(root, p)
                for p in ["README.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md"]
            ),
            evidence="README/CONTRIBUTING/SECURITY/CODE_OF_CONDUCT",
            remediation="Add missing governance docs and require link visibility from README.",
        ),
        ReadinessCheck(
            check_id="engineering_baseline_files",
            weight=15,
            passed=_exists(root, "pyproject.toml") and _exists(root, "Dockerfile"),
            evidence="pyproject.toml + Dockerfile",
            remediation="Ensure packaging/build/test automation entry points are present.",
        ),
        ReadinessCheck(
            check_id="ci_workflows_present",
            weight=15,
            passed=all(_exists(root, p) for p in required_workflows),
            evidence=", ".join(required_workflows),
            remediation="Ship baseline CI, quality, security, and docs publishing workflows.",
        ),
        ReadinessCheck(
            check_id="docs_operating_surface",
            weight=15,
            passed=all(
                _exists(root, p)
                for p in ["docs/index.md", "docs/repo-audit.md", "docs/security.md"]
            ),
            evidence="docs/index.md + docs/repo-audit.md + docs/security.md",
            remediation="Create central docs index and operating guides.",
        ),
        ReadinessCheck(
            check_id="phase_boost_blueprint_present",
            weight=10,
            passed=phase_boost_path is not None,
            evidence=phase_boost_path or " / ".join(_PHASE_BOOST_BLUEPRINT_FILES),
            remediation=(
                "Add a concrete 90-impact execution blueprint and keep it versioned "
                f"(accepted paths: {', '.join(_PHASE_BOOST_BLUEPRINT_FILES)})."
            ),
        ),
        ReadinessCheck(
            check_id="tests_folder_present",
            weight=10,
            passed=(root / "tests").exists() and any((root / "tests").glob("test_*.py")),
            evidence="tests/test_*.py exists",
            remediation="Add executable tests and fail-fast CI gating.",
        ),
        ReadinessCheck(
            check_id="src_package_present",
            weight=10,
            passed=(root / "src/sdetkit").exists() and (root / "src/sdetkit/cli.py").exists(),
            evidence="src/sdetkit and CLI entry",
            remediation="Keep package layout deterministic with stable command entrypoints.",
        ),
        ReadinessCheck(
            check_id="lockfiles_present",
            weight=10,
            passed=_exists(root, "poetry.lock")
            or _exists(root, "requirements.lock")
            or _exists(root, "requirements.txt.lock"),
            evidence="poetry.lock or requirements.lock or requirements.txt.lock",
            remediation="Pin dependencies for reproducible installs.",
        ),
    ]

    total_weight = sum(c.weight for c in checks)
    earned = sum(c.weight for c in checks if c.passed)
    score = int(round((earned / total_weight) * 100)) if total_weight else 0
    missing_items = [c.check_id for c in checks if not c.passed]
    stage = (
        "production-ready"
        if score >= 90
        else "stabilizing"
        if score >= 75
        else "foundation-building"
    )
    category_breakdown = _category_progress(checks)
    main_aspects = _main_aspect_readiness(checks)
    main_aspects_ready = sum(1 for aspect in main_aspects if aspect["ready"])
    accomplishment_percent = round((earned / total_weight) * 100, 2) if total_weight else 0.0
    boost_plan = [
        {
            "check_id": check.check_id,
            "impact": check.weight,
            "action": check.remediation,
        }
        for check in sorted((c for c in checks if not c.passed), key=lambda c: -c.weight)
    ]

    return {
        "summary": {
            "score": score,
            "accomplishment_percent": accomplishment_percent,
            "stage": stage,
            "total_checks": len(checks),
            "passed_checks": sum(1 for c in checks if c.passed),
            "strict_pass": score >= 90 and not missing_items,
            "production_ready": score >= 90 and not missing_items,
            "job_done_ready": main_aspects_ready == len(main_aspects) and not missing_items,
            "main_aspects_ready_count": main_aspects_ready,
            "main_aspects_total": len(main_aspects),
            "required_files_count": len(required_files),
            "required_workflows_count": len(required_workflows),
        },
        "main_aspects": main_aspects,
        "category_breakdown": category_breakdown,
        "checks": [c.to_dict() for c in checks],
        "missing": missing_items,
        "boost_plan": boost_plan,
    }


def _render_text(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "production-readiness",
        f"score: {s['score']}",
        f"accomplished: {s['accomplishment_percent']}%",
        f"stage: {s['stage']}",
        f"checks: {s['passed_checks']}/{s['total_checks']}",
        f"main_aspects_ready: {s['main_aspects_ready_count']}/{s['main_aspects_total']}",
        f"job_done_ready: {s['job_done_ready']}",
        f"strict_pass: {s['strict_pass']}",
    ]
    for c in payload["checks"]:
        status = "PASS" if c["passed"] else "FAIL"
        lines.append(f"- [{status}] {c['check_id']} ({c['weight']}): {c['evidence']}")
    lines.append("")
    lines.append("main aspects:")
    for aspect in payload.get("main_aspects", []):
        marker = "READY" if aspect["ready"] else "GAP"
        lines.append(
            f"- [{marker}] {aspect['aspect']} ({aspect['passed_checks']}/{aspect['total_checks']}; score={aspect['score']}%)"
        )
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Production readiness report",
        "",
        f"- **Score:** {s['score']}",
        f"- **Accomplished:** {s['accomplishment_percent']}%",
        f"- **Stage:** `{s['stage']}`",
        f"- **Checks passed:** {s['passed_checks']}/{s['total_checks']}",
        f"- **Main aspects ready:** {s['main_aspects_ready_count']}/{s['main_aspects_total']}",
        f"- **Job done ready:** `{s['job_done_ready']}`",
        f"- **Strict pass:** `{s['strict_pass']}`",
        "",
        "## Check breakdown",
        "",
        "| Check | Status | Weight | Evidence |",
        "|---|---|---:|---|",
    ]
    for c in payload["checks"]:
        status = "\u2705 pass" if c["passed"] else "\u274c fail"
        lines.append(f"| `{c['check_id']}` | {status} | {c['weight']} | {c['evidence']} |")

    lines.extend(
        [
            "",
            "## Category progress",
            "",
            "| Category | Score | Passed | Weight |",
            "|---|---:|---:|---:|",
        ]
    )
    for category in payload.get("category_breakdown", []):
        lines.append(
            "| `{}` | {}% | {}/{} | {}/{} |".format(
                category["category"],
                category["score"],
                category["passed_checks"],
                category["total_checks"],
                category["weight_earned"],
                category["weight_total"],
            )
        )

    lines.extend(
        [
            "",
            "## Main aspects readiness",
            "",
            "| Main aspect | Ready | Score | Passed checks |",
            "|---|---|---:|---:|",
        ]
    )
    for aspect in payload.get("main_aspects", []):
        ready = "\u2705 ready" if aspect["ready"] else "\u274c gap"
        lines.append(
            f"| `{aspect['aspect']}` | {ready} | {aspect['score']}% | {aspect['passed_checks']}/{aspect['total_checks']} |"
        )

    if payload["missing"]:
        lines.extend(["", "## Remediation priorities", ""])
        for action in payload.get("boost_plan", []):
            lines.append(
                f"- `{action['check_id']}` (impact={action['impact']}): {action['action']}"
            )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m sdetkit production-readiness",
        description="Score repository production readiness for company onboarding.",
    )
    p.add_argument("--root", type=Path, default=Path("."), help="Repository root to evaluate.")
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    p.add_argument(
        "--strict", action="store_true", help="Return exit code 1 if strict pass is false."
    )
    p.add_argument(
        "--emit-pack-dir",
        type=Path,
        default=None,
        help="Optional output directory for report artifacts.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_production_readiness_summary(args.root)

    if args.emit_pack_dir:
        args.emit_pack_dir.mkdir(parents=True, exist_ok=True)
        (args.emit_pack_dir / "production-readiness-summary.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        (args.emit_pack_dir / "production-readiness-report.md").write_text(
            _render_markdown(payload), encoding="utf-8"
        )

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    elif args.format == "markdown":
        print(_render_markdown(payload), end="")
    else:
        print(_render_text(payload), end="")

    if args.strict and not payload["summary"]["strict_pass"]:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
