from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def build_production_readiness_summary(root: Path) -> dict[str, Any]:
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
        "docs/production-s-class-90-day-boost.md",
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
            passed=all(_exists(root, p) for p in ["pyproject.toml", "Dockerfile", "noxfile.py"]),
            evidence="pyproject.toml + Dockerfile + noxfile.py",
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
            passed=_exists(root, "docs/production-s-class-90-day-boost.md"),
            evidence="docs/production-s-class-90-day-boost.md",
            remediation="Add a concrete 90-day execution blueprint and keep it versioned.",
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
            passed=all(_exists(root, p) for p in ["poetry.lock", "requirements.lock"]),
            evidence="poetry.lock + requirements.lock",
            remediation="Pin dependencies for reproducible installs.",
        ),
    ]

    total_weight = sum(c.weight for c in checks)
    earned = sum(c.weight for c in checks if c.passed)
    score = int(round((earned / total_weight) * 100)) if total_weight else 0
    missing_items = [c.check_id for c in checks if not c.passed]

    return {
        "summary": {
            "score": score,
            "total_checks": len(checks),
            "passed_checks": sum(1 for c in checks if c.passed),
            "strict_pass": score >= 90 and not missing_items,
            "required_files_count": len(required_files),
            "required_workflows_count": len(required_workflows),
        },
        "checks": [c.to_dict() for c in checks],
        "missing": missing_items,
    }


def _render_text(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "production-readiness",
        f"score: {s['score']}",
        f"checks: {s['passed_checks']}/{s['total_checks']}",
        f"strict_pass: {s['strict_pass']}",
    ]
    for c in payload["checks"]:
        status = "PASS" if c["passed"] else "FAIL"
        lines.append(f"- [{status}] {c['check_id']} ({c['weight']}): {c['evidence']}")
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Production readiness report",
        "",
        f"- **Score:** {s['score']}",
        f"- **Checks passed:** {s['passed_checks']}/{s['total_checks']}",
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

    if payload["missing"]:
        lines.extend(["", "## Remediation priorities", ""])
        for c in payload["checks"]:
            if not c["passed"]:
                lines.append(f"- `{c['check_id']}`: {c['remediation']}")
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
