from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_CHECK_OWNERS = {
    "canonical_path_clarity": "product-docs",
    "release_controls_present": "release-engineering",
    "security_governance_present": "security",
    "quality_automation_surface": "qa-platform",
    "commercial_packaging_baseline": "developer-relations",
    "operating_model_docs": "platform-ops",
    "workflow_sprawl_risk": "devops",
    "surface_area_rationalization": "platform-architecture",
}


@dataclass(frozen=True)
class AssessmentCheck:
    check_id: str
    weight: int
    passed: bool
    evidence: str
    impact: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "weight": self.weight,
            "passed": self.passed,
            "evidence": self.evidence,
            "impact": self.impact,
            "remediation": self.remediation,
        }


def _exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def _contains(root: Path, rel: str, snippets: tuple[str, ...]) -> bool:
    path = root / rel
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return all(snippet in text for snippet in snippets)


def _build_boost_plan(
    checks: list[AssessmentCheck], metrics: dict[str, int]
) -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    for check in checks:
        if check.passed:
            continue
        lane = "P0" if check.weight >= 20 else "P1"
        plan.append(
            {
                "priority": lane,
                "check_id": check.check_id,
                "action": check.remediation,
            }
        )

    if metrics["workflows_count"] > 25:
        plan.append(
            {
                "priority": "P1",
                "check_id": "workflow_sprawl_risk",
                "action": "Consolidate overlapping workflows into core/security/release bundles.",
            }
        )
    if metrics["modules_count"] > 220:
        plan.append(
            {
                "priority": "P2",
                "check_id": "surface_area_rationalization",
                "action": "Rationalize closeout-era modules into curated stable surfaces.",
            }
        )
    return plan


def _priority_to_sla_hours(priority: str) -> int:
    if priority == "P0":
        return 24
    if priority == "P1":
        return 72
    return 168


def _build_action_board(boost_plan: list[dict[str, str]]) -> dict[str, Any]:
    now_actions = [row for row in boost_plan if row["priority"] == "P0"]
    next_actions = [row for row in boost_plan if row["priority"] == "P1"]
    later_actions = [row for row in boost_plan if row["priority"] == "P2"]

    catalog: list[dict[str, Any]] = []
    for idx, row in enumerate(boost_plan, start=1):
        priority = row["priority"]
        check_id = row["check_id"]
        catalog.append(
            {
                "id": f"EA-{idx:03d}",
                "priority": priority,
                "check_id": check_id,
                "owner_team": _CHECK_OWNERS.get(check_id, "platform"),
                "response_sla_hours": _priority_to_sla_hours(priority),
                "action": row["action"],
            }
        )

    return {
        "now": now_actions,
        "next": next_actions,
        "later": later_actions,
        "catalog": catalog,
    }


def _compute_upgrade_contract(
    score: int,
    *,
    strict_pass: bool,
    executed_all_green: bool | None,
    action_board: dict[str, Any],
) -> dict[str, Any]:
    risk_score = max(0, 100 - score) + (0 if strict_pass else 10)
    if executed_all_green is False:
        risk_score += 15
    risk_score = min(100, risk_score)

    if risk_score >= 60:
        risk_band = "high"
    elif risk_score >= 30:
        risk_band = "medium"
    else:
        risk_band = "low"

    gate_decision = (
        "go"
        if strict_pass and (executed_all_green in (None, True))
        else "conditional-go"
        if risk_band == "medium"
        else "no-go"
    )

    return {
        "gate_decision": gate_decision,
        "risk_score": risk_score,
        "risk_band": risk_band,
        "sla_review_hours": 24 if risk_band == "high" else 48 if risk_band == "medium" else 168,
        "top_now_actions": action_board["now"][:3],
        "top_next_actions": action_board["next"][:3],
    }


def _build_trend(
    summary: dict[str, Any], baseline_summary: dict[str, Any] | None
) -> dict[str, Any]:
    if not baseline_summary:
        return {
            "has_baseline": False,
            "score_delta": None,
            "status": "no-baseline",
        }
    previous_score = int(baseline_summary.get("score", 0))
    current_score = int(summary["score"])
    delta = current_score - previous_score
    status = "improved" if delta > 0 else "declined" if delta < 0 else "flat"
    return {
        "has_baseline": True,
        "previous_score": previous_score,
        "score_delta": delta,
        "status": status,
    }


def build_enterprise_assessment(root: Path) -> dict[str, Any]:
    metrics = {
        "modules_count": len(list((root / "src/sdetkit").glob("**/*.py"))),
        "tests_count": len(list((root / "tests").glob("test_*.py"))),
        "workflows_count": len(list((root / ".github/workflows").glob("*.yml"))),
        "docs_markdown_count": len(list((root / "docs").glob("**/*.md"))),
    }

    checks = [
        AssessmentCheck(
            check_id="canonical_path_clarity",
            weight=20,
            passed=_contains(
                root,
                "README.md",
                ("gate fast", "gate release", "doctor"),
            ),
            evidence="README canonical path mentions gate fast/gate release/doctor",
            impact="Reduces onboarding confusion for platform adoption.",
            remediation="Make canonical command path explicit in README top section.",
        ),
        AssessmentCheck(
            check_id="release_controls_present",
            weight=20,
            passed=all(
                _exists(root, rel)
                for rel in (
                    "RELEASE.md",
                    "docs/release-readiness.md",
                    ".github/workflows/release.yml",
                )
            ),
            evidence="RELEASE docs + release readiness page + release workflow",
            impact="Prevents ad-hoc release cuts and missing publication checks.",
            remediation="Ship deterministic release docs and CI release workflow.",
        ),
        AssessmentCheck(
            check_id="security_governance_present",
            weight=20,
            passed=all(
                _exists(root, rel)
                for rel in ("SECURITY.md", "docs/security.md", "tools/security_allowlist.json")
            ),
            evidence="Security policy + security docs + allowlist baseline",
            impact="Improves audit readiness and vulnerability handling consistency.",
            remediation="Add security policy docs and machine-readable security baseline files.",
        ),
        AssessmentCheck(
            check_id="quality_automation_surface",
            weight=15,
            passed=all(
                _exists(root, rel) for rel in ("quality.sh", "Makefile", ".github/workflows/ci.yml")
            )
            and metrics["tests_count"] >= 50,
            evidence=f"quality.sh + Makefile + ci workflow + tests={metrics['tests_count']}",
            impact="Improves deterministic quality gates in local and CI lanes.",
            remediation="Add test execution lanes and ensure baseline test depth reaches 50 files.",
        ),
        AssessmentCheck(
            check_id="commercial_packaging_baseline",
            weight=15,
            passed=all(
                _exists(root, rel)
                for rel in (
                    "LICENSE",
                    "SUPPORT.md",
                    "ENTERPRISE_OFFERINGS.md",
                    "docs/why-not-just-tools.md",
                )
            ),
            evidence="License + support + enterprise offerings + differentiator docs",
            impact="Makes enterprise procurement and buyer evaluation easier.",
            remediation="Add enterprise packaging, support, and value-positioning docs.",
        ),
        AssessmentCheck(
            check_id="operating_model_docs",
            weight=10,
            passed=all(
                _exists(root, rel)
                for rel in ("ARCHITECTURE.md", "WORKFLOW.md", "docs/operations-handbook.md")
            ),
            evidence="Architecture + workflow + operations handbook",
            impact="Improves team handoff quality and operational continuity.",
            remediation="Publish architecture and operations docs for maintainers/operators.",
        ),
    ]

    total_weight = sum(c.weight for c in checks)
    earned = sum(c.weight for c in checks if c.passed)
    score = int(round((earned / total_weight) * 100)) if total_weight else 0
    missing = [c.check_id for c in checks if not c.passed]
    plan = _build_boost_plan(checks, metrics)
    action_board = _build_action_board(plan)
    tier = (
        "enterprise-ready"
        if score >= 90 and not missing
        else "pilot-ready"
        if score >= 75
        else "not-ready"
    )
    strict_pass = tier == "enterprise-ready"
    upgrade_contract = _compute_upgrade_contract(
        score,
        strict_pass=strict_pass,
        executed_all_green=None,
        action_board=action_board,
    )

    return {
        "summary": {
            "score": score,
            "tier": tier,
            "total_checks": len(checks),
            "passed_checks": sum(1 for c in checks if c.passed),
            "strict_pass": strict_pass,
        },
        "metrics": metrics,
        "checks": [c.to_dict() for c in checks],
        "missing": missing,
        "boost_plan": plan,
        "action_board": action_board,
        "upgrade_contract": upgrade_contract,
    }


def _render_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "enterprise-assessment",
        f"score: {summary['score']}",
        f"tier: {summary['tier']}",
        f"checks: {summary['passed_checks']}/{summary['total_checks']}",
        "metrics:",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"  - {key}: {value}")
    lines.append("checks:")
    for check in payload["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"  - [{status}] {check['check_id']} ({check['weight']}): {check['evidence']}")
    if payload["boost_plan"]:
        lines.append("boost_plan:")
        for row in payload["boost_plan"]:
            lines.append(f"  - [{row['priority']}] {row['check_id']}: {row['action']}")
    contract = payload.get("upgrade_contract")
    if isinstance(contract, dict):
        lines.append("upgrade_contract:")
        lines.append(f"  - gate_decision: {contract.get('gate_decision')}")
        lines.append(f"  - risk_band: {contract.get('risk_band')}")
        lines.append(f"  - risk_score: {contract.get('risk_score')}")
    trend = payload.get("trend")
    if isinstance(trend, dict):
        lines.append("trend:")
        lines.append(f"  - status: {trend.get('status')}")
        lines.append(f"  - score_delta: {trend.get('score_delta')}")
    executed = payload.get("executed_assessments")
    if isinstance(executed, dict):
        lines.append("executed_assessments:")
        lines.append(f"  - all_green: {executed.get('all_green')}")
        for row in executed.get("commands", []):
            lines.append(
                f"  - [{row['return_code']}] {row['id']}: ok={row['ok']} command={row['command']}"
            )
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Enterprise assessment report",
        "",
        f"- **Score:** {summary['score']}",
        f"- **Tier:** `{summary['tier']}`",
        f"- **Checks passed:** {summary['passed_checks']}/{summary['total_checks']}",
        "",
        "## Metrics",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"- `{key}`: {value}")

    lines.extend(
        [
            "",
            "## Check breakdown",
            "",
            "| Check | Status | Weight | Evidence | Impact |",
            "|---|---|---:|---|---|",
        ]
    )
    for check in payload["checks"]:
        status = "✅ pass" if check["passed"] else "❌ fail"
        lines.append(
            f"| `{check['check_id']}` | {status} | {check['weight']} | "
            f"{check['evidence']} | {check['impact']} |"
        )

    if payload["boost_plan"]:
        lines.extend(["", "## Priority boost plan", ""])
        for row in payload["boost_plan"]:
            lines.append(f"- **{row['priority']}** `{row['check_id']}`: {row['action']}")
    action_board = payload.get("action_board")
    if isinstance(action_board, dict):
        lines.extend(["", "## Action board", ""])
        lines.append("| ID | Priority | Owner | SLA (hours) | Action |")
        lines.append("|---|---|---|---:|---|")
        for item in action_board.get("catalog", []):
            lines.append(
                f"| `{item['id']}` | {item['priority']} | `{item['owner_team']}` | "
                f"{item['response_sla_hours']} | {item['action']} |"
            )
    contract = payload.get("upgrade_contract")
    if isinstance(contract, dict):
        lines.extend(
            [
                "",
                "## Upgrade contract",
                "",
                f"- **Gate decision:** `{contract.get('gate_decision')}`",
                f"- **Risk band:** `{contract.get('risk_band')}`",
                f"- **Risk score:** {contract.get('risk_score')}",
            ]
        )
    trend = payload.get("trend")
    if isinstance(trend, dict):
        lines.extend(
            [
                "",
                "## Trend",
                "",
                f"- **Status:** `{trend.get('status')}`",
                f"- **Score delta:** {trend.get('score_delta')}",
            ]
        )
    executed = payload.get("executed_assessments")
    if isinstance(executed, dict):
        lines.extend(
            [
                "",
                "## Execution evidence",
                "",
                f"- **All green:** `{executed.get('all_green')}`",
                "",
                "| Command | Return code | Status |",
                "|---|---:|---|",
            ]
        )
        for row in executed.get("commands", []):
            status = "✅ pass" if row["ok"] else "❌ fail"
            lines.append(f"| `{row['id']}` | {row['return_code']} | {status} |")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit enterprise-assessment",
        description="Generate a company-grade enterprise assessment with a prioritized boost plan.",
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root path.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 when enterprise-ready tier is not reached.",
    )
    parser.add_argument(
        "--emit-pack-dir",
        type=Path,
        default=None,
        help="Optional output directory for report artifacts.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run core readiness commands and attach execution evidence to output.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help="Optional directory for per-command execution logs and summary.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=300,
        help="Per-command timeout in seconds for --execute mode.",
    )
    parser.add_argument(
        "--baseline-summary",
        type=Path,
        default=None,
        help="Optional previous enterprise-assessment summary JSON for trend comparison.",
    )
    parser.add_argument(
        "--fail-on-risk-band",
        choices=["none", "medium", "high"],
        default="none",
        help="Optional failure policy based on computed upgrade-contract risk band.",
    )
    parser.add_argument(
        "--production-profile",
        action="store_true",
        help=(
            "Apply production defaults: --execute, --strict, "
            "--fail-on-risk-band medium, and artifact pack paths."
        ),
    )
    return parser


def _extract_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    start = text.find("{")
    if start == -1:
        return {}
    candidate = text[start:]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _execute_assessments(
    root: Path,
    *,
    timeout_sec: int,
    evidence_dir: Path | None,
) -> list[dict[str, Any]]:
    commands = [
        ("doctor", "python -m sdetkit doctor --format json"),
        ("production_readiness", "python -m sdetkit production-readiness --format json"),
        ("release_readiness", "python -m sdetkit release-readiness --format json"),
        ("enterprise_readiness", "python -m sdetkit enterprise-readiness --format json"),
    ]
    rows: list[dict[str, Any]] = []
    if evidence_dir:
        evidence_dir.mkdir(parents=True, exist_ok=True)

    for idx, (name, command) in enumerate(commands, start=1):
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        env = dict(os.environ)
        src_path = str(root / "src")
        env["PYTHONPATH"] = (
            src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
        )
        try:
            proc = subprocess.run(
                argv,
                cwd=str(root),
                shell=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            row = {
                "id": name,
                "command": command,
                "return_code": 124,
                "ok": False,
                "error": f"timeout after {timeout_sec}s",
                "error_kind": "timeout",
                "parsed_summary": {},
            }
            rows.append(row)
            if evidence_dir:
                (evidence_dir / f"{idx:02d}-{name}.log").write_text(
                    f"$ {command}\nreturn_code: 124\n\nerror:\n{exc}\n",
                    encoding="utf-8",
                )
            continue
        parsed = _extract_json(proc.stdout)
        row = {
            "id": name,
            "command": command,
            "return_code": proc.returncode,
            "ok": proc.returncode == 0,
            "error_kind": "none" if proc.returncode == 0 else "command_failed",
            "parsed_summary": parsed.get("summary", {}) if isinstance(parsed, dict) else {},
        }
        rows.append(row)

        if evidence_dir:
            log_path = evidence_dir / f"{idx:02d}-{name}.log"
            log_path.write_text(
                "\n".join(
                    [
                        f"$ {command}",
                        f"return_code: {proc.returncode}",
                        "",
                        "stdout:",
                        proc.stdout.rstrip(),
                        "",
                        "stderr:",
                        proc.stderr.rstrip(),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

    if evidence_dir:
        (evidence_dir / "enterprise-assessment-execution-summary.json").write_text(
            json.dumps(
                {
                    "commands": rows,
                    "all_green": all(r["ok"] for r in rows),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return rows


def _risk_meets_fail_policy(risk_band: str, policy: str) -> bool:
    if policy == "none":
        return False
    order = {"low": 0, "medium": 1, "high": 2}
    threshold = order[policy]
    current = order.get(risk_band, 2)
    return current >= threshold


def _build_contract_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    digest = hashlib.blake2s(
        json.dumps(
            {
                "summary": payload.get("summary", {}),
                "metrics": payload.get("metrics", {}),
                "upgrade_contract": payload.get("upgrade_contract", {}),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return {
        "schema_version": "sdetkit.enterprise_assessment.v2",
        "generated_at_utc": generated_at,
        "contract_id": f"ea-{digest}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.production_profile:
        args.execute = True
        args.strict = True
        args.fail_on_risk_band = "medium"
        if args.emit_pack_dir is None:
            args.emit_pack_dir = Path("docs/artifacts/enterprise-assessment-pack")
        if args.evidence_dir is None:
            args.evidence_dir = Path("docs/artifacts/enterprise-assessment-pack/evidence")

    payload = build_enterprise_assessment(args.root)
    baseline_summary: dict[str, Any] | None = None
    if args.baseline_summary and args.baseline_summary.exists():
        baseline_raw = _extract_json(args.baseline_summary.read_text(encoding="utf-8"))
        baseline_summary = baseline_raw.get("summary", {}) if baseline_raw else None
    payload["trend"] = _build_trend(payload["summary"], baseline_summary)
    if args.execute:
        executed = _execute_assessments(
            args.root,
            timeout_sec=args.timeout_sec,
            evidence_dir=args.evidence_dir,
        )
        payload["executed_assessments"] = {
            "all_green": all(row["ok"] for row in executed),
            "commands": executed,
        }
        payload["upgrade_contract"] = _compute_upgrade_contract(
            payload["summary"]["score"],
            strict_pass=payload["summary"]["strict_pass"],
            executed_all_green=payload["executed_assessments"]["all_green"],
            action_board=payload["action_board"],
        )
    payload["contract"] = _build_contract_metadata(payload)

    if args.emit_pack_dir:
        args.emit_pack_dir.mkdir(parents=True, exist_ok=True)
        (args.emit_pack_dir / "enterprise-assessment-summary.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        (args.emit_pack_dir / "enterprise-assessment-report.md").write_text(
            _render_markdown(payload), encoding="utf-8"
        )

    if args.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    elif args.format == "markdown":
        sys.stdout.write(_render_markdown(payload))
    else:
        sys.stdout.write(_render_text(payload))

    if args.strict and not payload["summary"]["strict_pass"]:
        return 1
    if args.execute and not payload["executed_assessments"]["all_green"]:
        return 1
    if _risk_meets_fail_policy(payload["upgrade_contract"]["risk_band"], args.fail_on_risk_band):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
