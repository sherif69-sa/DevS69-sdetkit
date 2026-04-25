from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class ReadinessResult:
    passed: bool
    evidence: str


@dataclass(frozen=True)
class ReadinessCheck:
    key: str
    description: str
    weight: int
    evaluator: Callable[[Path], ReadinessResult]
    recommendation_hint: str


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _contains_all(path: Path, terms: tuple[str, ...]) -> ReadinessResult:
    text = _read_text(path).lower()
    if not text:
        return ReadinessResult(False, f"missing file: {path.name}")

    missing = [term for term in terms if term not in text]
    if missing:
        return ReadinessResult(False, f"missing keywords: {', '.join(missing)}")
    return ReadinessResult(True, f"found keywords: {', '.join(terms)}")


def _check_security_policy(root: Path) -> ReadinessResult:
    return _contains_all(root / "SECURITY.md", ("vulnerability", "report"))


def _check_release_process(root: Path) -> ReadinessResult:
    return _contains_all(root / "RELEASE.md", ("release", "checklist"))


def _check_quality_playbook(root: Path) -> ReadinessResult:
    return _contains_all(root / "QUALITY_PLAYBOOK.md", ("quality", "gate"))


def _check_ci_pipeline(root: Path) -> ReadinessResult:
    workflow = root / ".github" / "workflows" / "ci.yml"
    text = _read_text(workflow).lower()
    if not text:
        return ReadinessResult(False, "missing ci workflow")

    missing: list[str] = []
    if "pytest" not in text:
        missing.append("pytest")
    if "ruff" not in text and "quality.sh" not in text:
        missing.append("ruff or quality.sh")

    if missing:
        return ReadinessResult(False, f"pipeline missing: {', '.join(missing)}")
    return ReadinessResult(True, "workflow includes test and lint/quality steps")


def _check_tests_coverage_surface(root: Path) -> ReadinessResult:
    tests_dir = root / "tests"
    if not tests_dir.exists() or not tests_dir.is_dir():
        return ReadinessResult(False, "tests directory missing")

    test_files = [path for path in tests_dir.glob("test_*.py") if path.is_file()]
    if len(test_files) < 10:
        return ReadinessResult(False, f"only {len(test_files)} test files (need >= 10)")
    return ReadinessResult(True, f"{len(test_files)} test files detected")


def _check_docs_entrypoint(root: Path) -> ReadinessResult:
    docs_index = root / "docs" / "index.md"
    return _contains_all(docs_index, ("gate fast", "gate release", "doctor"))


def _check_dependency_locks(root: Path) -> ReadinessResult:
    requirements = root / "requirements.lock"
    poetry = root / "poetry.lock"
    missing = [path.name for path in (requirements, poetry) if not path.exists()]
    if missing:
        return ReadinessResult(False, f"missing lockfiles: {', '.join(missing)}")
    return ReadinessResult(True, "requirements.lock and poetry.lock both present")


def _check_artifact_evidence(root: Path) -> ReadinessResult:
    artifacts = root / "artifacts"
    docs_artifacts = root / "docs" / "artifacts"
    if artifacts.exists() and docs_artifacts.exists():
        return ReadinessResult(True, "artifacts and docs/artifacts directories exist")
    if artifacts.exists():
        return ReadinessResult(True, "artifacts directory exists")
    return ReadinessResult(False, "missing artifacts evidence directory")


def _check_governance_docs(root: Path) -> ReadinessResult:
    required = ("CODE_OF_CONDUCT.md", "SUPPORT.md", "CONTRIBUTING.md")
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        return ReadinessResult(False, f"missing governance docs: {', '.join(missing)}")
    return ReadinessResult(True, "core governance docs present")


def _check_recent_changelog(root: Path) -> ReadinessResult:
    changelog = root / "CHANGELOG.md"
    text = _read_text(changelog)
    if not text:
        return ReadinessResult(False, "missing CHANGELOG.md")

    dates: list[date] = []
    for token in re.findall(r"20\d{2}-\d{2}-\d{2}", text):
        try:
            dates.append(date.fromisoformat(token))
        except ValueError:
            continue
    if not dates:
        return ReadinessResult(False, "no dated release entries found")
    latest = max(dates).isoformat()
    return ReadinessResult(True, f"latest dated entry found: {latest}")


def _scan_test_scenario_capacity(root: Path) -> dict[str, object]:
    tests_dir = root / "tests"
    target_scenarios = 250
    if not tests_dir.exists() or not tests_dir.is_dir():
        return {
            "target_scenarios": target_scenarios,
            "detected_scenarios": 0,
            "gap": target_scenarios,
            "status": "needs-expansion",
            "estimated_from": "tests directory missing",
        }

    test_files = [path for path in tests_dir.glob("test_*.py") if path.is_file()]
    test_functions = 0
    for path in test_files:
        text = _read_text(path)
        test_functions += len(re.findall(r"^def\s+test_", text, flags=re.MULTILINE))

    gap = max(0, target_scenarios - test_functions)
    status = "ready" if gap == 0 else "needs-expansion"
    return {
        "target_scenarios": target_scenarios,
        "detected_scenarios": test_functions,
        "gap": gap,
        "status": status,
        "estimated_from": f"{len(test_files)} test files",
    }


CHECKS: tuple[ReadinessCheck, ...] = (
    ReadinessCheck(
        "security_policy",
        "Security policy includes vulnerability reporting guidance",
        12,
        _check_security_policy,
        "Document security reporting flow in SECURITY.md (contact channel + disclosure process).",
    ),
    ReadinessCheck(
        "release_process",
        "Release process includes explicit checklist guidance",
        12,
        _check_release_process,
        "Add/expand release checklist steps in RELEASE.md.",
    ),
    ReadinessCheck(
        "quality_playbook",
        "Quality playbook defines gate/quality policy",
        8,
        _check_quality_playbook,
        "Define quality gate policy and ownership in QUALITY_PLAYBOOK.md.",
    ),
    ReadinessCheck(
        "ci_pipeline",
        "CI workflow runs both tests and lint/quality steps",
        14,
        _check_ci_pipeline,
        "Update .github/workflows/ci.yml to run pytest and ruff/quality checks.",
    ),
    ReadinessCheck(
        "test_surface",
        "Repository has baseline automated test surface",
        10,
        _check_tests_coverage_surface,
        "Increase test breadth so tests/test_*.py includes at least 10 suites.",
    ),
    ReadinessCheck(
        "docs_entrypoint",
        "Docs entrypoint highlights canonical release-confidence flow",
        8,
        _check_docs_entrypoint,
        "Ensure docs/index.md calls out gate fast -> gate release -> doctor.",
    ),
    ReadinessCheck(
        "dependency_locks",
        "Dependency lock strategy is present for reproducibility",
        10,
        _check_dependency_locks,
        "Commit both requirements.lock and poetry.lock (or align lock strategy).",
    ),
    ReadinessCheck(
        "artifact_evidence",
        "Evidence artifact directories are available",
        8,
        _check_artifact_evidence,
        "Create artifact storage paths (artifacts/ and/or docs/artifacts).",
    ),
    ReadinessCheck(
        "governance_docs",
        "Contributor governance docs are present",
        8,
        _check_governance_docs,
        "Add CODE_OF_CONDUCT.md, SUPPORT.md, and CONTRIBUTING.md.",
    ),
    ReadinessCheck(
        "changelog_hygiene",
        "Changelog contains dated release history",
        10,
        _check_recent_changelog,
        "Maintain dated release entries in CHANGELOG.md.",
    ),
)


def _adaptive_action_for_failure(check: dict[str, object]) -> dict[str, object]:
    weight = int(check.get("weight", 0))
    priority = 80 if weight >= 12 else 65 if weight >= 10 else 50
    lane = "now" if weight >= 12 else "next"
    evidence = str(check.get("evidence", "")).strip()
    hint = str(check.get("recommendation", "")).strip()
    action = hint if hint else f"Address readiness gap: {check.get('key', 'unknown')}"
    rationale = f"{check.get('description', 'readiness control')} failed ({evidence})"
    return {
        "check_id": str(check.get("key", "")),
        "lane": lane,
        "priority": priority,
        "action": action,
        "rationale": rationale,
    }


def _adaptive_scenario_action(scenario_capacity: dict[str, object]) -> dict[str, object] | None:
    gap = int(scenario_capacity.get("gap", 0))
    if gap <= 0:
        return None
    detected = int(scenario_capacity.get("detected_scenarios", 0))
    target = int(scenario_capacity.get("target_scenarios", 250))
    return {
        "check_id": "test_scenario_capacity",
        "lane": "now" if gap >= 100 else "next",
        "priority": 82 if gap >= 100 else 68,
        "action": (
            f"Expand automated test scenarios from {detected} to at least {target} "
            "to support large-scale release validation."
        ),
        "rationale": f"scenario gap is {gap} toward target {target}",
    }


def build_readiness_report(repo_root: Path) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    total = sum(item.weight for item in CHECKS)
    earned = 0

    for item in CHECKS:
        result = item.evaluator(repo_root)
        if result.passed:
            earned += item.weight

        checks.append(
            {
                "key": item.key,
                "description": item.description,
                "weight": item.weight,
                "passed": result.passed,
                "status": "pass" if result.passed else "miss",
                "evidence": result.evidence,
                "recommendation": item.recommendation_hint,
            }
        )

    score = round((earned / total) * 100, 2) if total else 0.0
    tier = "excellent" if score >= 90 else "strong" if score >= 75 else "needs-work"
    achievement_level = "gold" if score >= 90 else "silver" if score >= 75 else "bronze"

    failing = sorted(
        (check for check in checks if not check["passed"]), key=lambda c: -int(c["weight"])
    )
    adaptive_actions = [_adaptive_action_for_failure(check) for check in failing]
    scenario_capacity = _scan_test_scenario_capacity(repo_root)
    scenario_action = _adaptive_scenario_action(scenario_capacity)
    if scenario_action is not None:
        adaptive_actions.insert(0, scenario_action)
    scenario_ready = str(scenario_capacity.get("status", "needs-expansion")) == "ready"
    operational_tier = tier
    if tier == "excellent" and not scenario_ready:
        operational_tier = "strong"
    top_tier_ready = bool(score >= 90.0 and scenario_ready)
    if achievement_level == "gold" and not top_tier_ready:
        achievement_level = "silver"
    top_actions = [str(action["action"]) for action in adaptive_actions[:5]]
    passing = [check for check in checks if check["passed"]]
    pass_rate = round((len(passing) / len(checks)) * 100, 2) if checks else 0.0
    check_scorecard = {
        "total_checks": len(checks),
        "passed_checks": len(passing),
        "missed_checks": len(failing),
        "pass_rate": pass_rate,
    }
    achieved_controls = [str(check["key"]) for check in passing[:5]]

    return {
        "schema_version": "sdetkit.readiness.v2",
        "repo_root": str(repo_root),
        "score": score,
        "tier": tier,
        "operational_tier": operational_tier,
        "top_tier_ready": top_tier_ready,
        "achievement_level": achievement_level,
        "weight_total": total,
        "weight_earned": earned,
        "check_scorecard": check_scorecard,
        "achieved_controls": achieved_controls,
        "checks": checks,
        "failed_checks": [str(check["key"]) for check in failing],
        "scenario_capacity": scenario_capacity,
        "adaptive_actions": adaptive_actions,
        "top_actions": top_actions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit readiness",
        description=(
            "Generate a production-readiness snapshot for investor and leadership reviews."
        ),
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository root to evaluate")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def _render_text(report: dict[str, object]) -> str:
    lines = [
        "SDETKit Production Readiness Snapshot",
        f"score: {report['score']} / 100 ({report['tier']})",
        f"operational tier: {report['operational_tier']} (top-tier-ready={report['top_tier_ready']})",
        f"achievement: {report['achievement_level']}",
        f"earned: {report['weight_earned']} of {report['weight_total']} weighted points",
        (
            "checks summary: "
            f"pass={report['check_scorecard']['passed_checks']}, "
            f"miss={report['check_scorecard']['missed_checks']}, "
            f"pass_rate={report['check_scorecard']['pass_rate']}%"
        ),
        "",
        "checks:",
    ]

    for check in report["checks"]:
        marker = "PASS" if check["passed"] else "MISS"
        lines.append(
            f"- [{marker}] {check['description']} (weight={check['weight']}) -> {check['evidence']}"
        )

    actions = report["adaptive_actions"]
    if actions:
        lines.append("")
        lines.append("recommended next actions:")
        for action in actions:
            lines.append(
                f"- [{action['lane']}] {action['action']} "
                f"(priority={action['priority']}; reason={action['rationale']})"
            )

    achieved_controls = report.get("achieved_controls", [])
    if achieved_controls:
        lines.append("")
        lines.append("achieved controls:")
        for control in achieved_controls:
            lines.append(f"- {control}")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    report = build_readiness_report(Path(ns.path).resolve())

    if ns.format == "json":
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    print(_render_text(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
