from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = "sdetkit.safety_gate.v1"

FALSE_AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_claim",
)


class FailureVectorLike(Protocol):
    @property
    def failure_class(self) -> str:
        raise NotImplementedError

    @property
    def risk(self) -> str:
        raise NotImplementedError

    @property
    def scope(self) -> str:
        raise NotImplementedError

    @property
    def safe_fix_candidate(self) -> bool:
        raise NotImplementedError

    @property
    def affected_files(self) -> tuple[str, ...]:
        raise NotImplementedError

    @property
    def local_repro_command(self) -> str | None:
        raise NotImplementedError


SAFE_FIX_CLASSES = frozenset({"formatter_only", "lint"})

GENERAL_BLOCKED_ACTIONS = (
    "delete or " + "weaken tests",
    "skip CI or " + "verifier checks",
    "edit workflow gates " + "to hide the failure",
    "modify files outside allowed_files",
)


@dataclass(frozen=True)
class SafetyGateDecision:
    failure_class: str
    risk: str
    scope: str
    failure_kind: str
    affected_surface: str
    ownership_area: str
    retryability: str
    security_relevance: bool
    recommended_next_human_action: str
    reporting_only: bool
    automation_allowed: bool
    patch_application_allowed: bool
    security_dismissal_allowed: bool
    merge_authorized: bool
    semantic_equivalence_claim: bool
    safe_fix_allowed: bool
    review_first: bool
    reason: str
    allowed_files: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    proof_commands: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["allowed_files"] = list(self.allowed_files)
        payload["blocked_actions"] = list(self.blocked_actions)
        payload["proof_commands"] = list(self.proof_commands)
        return payload


def evaluate_failure_vector(vector: FailureVectorLike) -> SafetyGateDecision:
    contract = _normalized_contract(vector)
    safe_fix_allowed = _safe_fix_allowed(vector, contract)

    return SafetyGateDecision(
        failure_class=vector.failure_class,
        risk=vector.risk,
        scope=vector.scope,
        failure_kind=str(contract["failure_kind"]),
        affected_surface=str(contract["affected_surface"]),
        ownership_area=str(contract["ownership_area"]),
        retryability=str(contract["retryability"]),
        security_relevance=bool(contract["security_relevance"]),
        recommended_next_human_action=str(contract["recommended_next_human_action"]),
        reporting_only=bool(contract["reporting_only"]),
        automation_allowed=bool(contract["automation_allowed"]),
        patch_application_allowed=bool(contract["patch_application_allowed"]),
        security_dismissal_allowed=bool(contract["security_dismissal_allowed"]),
        merge_authorized=bool(contract["merge_authorized"]),
        semantic_equivalence_claim=bool(contract["semantic_equivalence_claim"]),
        safe_fix_allowed=safe_fix_allowed,
        review_first=not safe_fix_allowed,
        reason=_decision_reason(vector, contract, safe_fix_allowed),
        allowed_files=vector.affected_files if safe_fix_allowed else (),
        blocked_actions=GENERAL_BLOCKED_ACTIONS,
        proof_commands=_proof_commands(vector),
    )


def write_safety_gate_decision(decision: SafetyGateDecision, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(decision.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_safety_gate_decision_report(decision: SafetyGateDecision) -> str:
    allowed = "yes" if decision.safe_fix_allowed else "no"
    review_first = "yes" if decision.review_first else "no"
    security_relevance = "yes" if decision.security_relevance else "no"
    reporting_only = "yes" if decision.reporting_only else "no"
    allowed_files = ", ".join(decision.allowed_files) if decision.allowed_files else "none"
    proof_commands = ", ".join(decision.proof_commands) if decision.proof_commands else "none"

    return "\n".join(
        [
            "# Safety Gate Decision",
            "",
            f"- schema_version: `{decision.schema_version}`",
            f"- failure_class: `{decision.failure_class}`",
            f"- risk: `{decision.risk}`",
            f"- scope: `{decision.scope}`",
            f"- failure_kind: `{decision.failure_kind}`",
            f"- affected_surface: `{decision.affected_surface}`",
            f"- ownership_area: `{decision.ownership_area}`",
            f"- retryability: `{decision.retryability}`",
            f"- security_relevance: `{security_relevance}`",
            (f"- recommended_next_human_action: `{decision.recommended_next_human_action}`"),
            f"- reporting_only: `{reporting_only}`",
            f"- safe_fix_allowed: `{allowed}`",
            f"- review_first: `{review_first}`",
            f"- reason: `{decision.reason}`",
            f"- allowed_files: `{allowed_files}`",
            f"- proof_commands: `{proof_commands}`",
            "- automation_allowed: `false`",
            "- patch_application_allowed: `false`",
            "- security_dismissal_allowed: `false`",
            "- merge_authorized: `false`",
            "- semantic_equivalence_claim: `false`",
            "",
        ]
    )


def _safe_fix_allowed(
    vector: FailureVectorLike,
    contract: Mapping[str, object],
) -> bool:
    return (
        _contract_preserves_authority_boundary(contract)
        and not bool(contract["security_relevance"])
        and str(contract["failure_kind"]) in SAFE_FIX_CLASSES
        and str(contract["retryability"]) != "human_review_required"
        and vector.safe_fix_candidate
        and vector.failure_class in SAFE_FIX_CLASSES
        and vector.risk == "low"
        and vector.scope == "pr_owned_only"
        and bool(vector.affected_files)
        and bool(vector.local_repro_command)
    )


def _decision_reason(
    vector: FailureVectorLike,
    contract: Mapping[str, object],
    safe_fix_allowed: bool,
) -> str:
    if safe_fix_allowed:
        return (
            "normalized failure-vector contract is low-risk, PR-owned, "
            "mechanically eligible, and has required proof"
        )
    if not _contract_preserves_authority_boundary(contract):
        return "normalized failure-vector contract does not preserve authority boundary"
    if bool(contract["security_relevance"]):
        return "normalized failure-vector contract marks this security-relevant"
    if str(contract["retryability"]) == "human_review_required":
        return (
            f"failure_class {vector.failure_class!r} requires human review "
            "by normalized failure-vector contract"
        )
    if not vector.safe_fix_candidate:
        return (
            f"failure_class {vector.failure_class!r} is review-first or not mechanically eligible"
        )
    if not vector.affected_files:
        return "safe candidate lacks affected files, so patch scope cannot be verified"
    if not vector.local_repro_command:
        return "safe candidate lacks local repro command, so required proof cannot be selected"
    if vector.scope != "pr_owned_only":
        return f"scope {vector.scope!r} is not eligible for mechanical remediation"
    if vector.risk != "low":
        return f"risk {vector.risk!r} requires human review"
    return "failure vector does not satisfy SafetyGate eligibility"


def _proof_commands(vector: FailureVectorLike) -> tuple[str, ...]:
    commands: list[str] = []
    if vector.local_repro_command:
        commands.append(vector.local_repro_command)
    commands.append("make proof-after-format")
    return tuple(commands)


def _normalized_contract(vector: FailureVectorLike) -> dict[str, object]:
    raw = _contract_from_vector(vector)
    return {
        "failure_kind": _contract_text(raw, "failure_kind", vector.failure_class),
        "affected_surface": _contract_text(
            raw,
            "affected_surface",
            _affected_surface(vector.affected_files),
        ),
        "ownership_area": _contract_text(
            raw,
            "ownership_area",
            _ownership_area(vector),
        ),
        "retryability": _contract_text(
            raw,
            "retryability",
            _retryability(vector.failure_class),
        ),
        "security_relevance": _contract_bool(
            raw,
            "security_relevance",
            vector.failure_class == "security",
        ),
        "recommended_next_human_action": _contract_text(
            raw,
            "recommended_next_human_action",
            "triage failure and rerun focused proof",
        ),
        "reporting_only": _contract_bool(raw, "reporting_only", True),
        "automation_allowed": _contract_bool(raw, "automation_allowed", False),
        "patch_application_allowed": _contract_bool(
            raw,
            "patch_application_allowed",
            False,
        ),
        "security_dismissal_allowed": _contract_bool(
            raw,
            "security_dismissal_allowed",
            False,
        ),
        "merge_authorized": _contract_bool(raw, "merge_authorized", False),
        "semantic_equivalence_claim": _contract_bool(
            raw,
            "semantic_equivalence_claim",
            False,
        ),
    }


def _contract_from_vector(vector: FailureVectorLike) -> Mapping[str, object]:
    to_dict = getattr(vector, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, Mapping):
            contract = payload.get("contract")
            if isinstance(contract, Mapping):
                return contract

    contract = getattr(vector, "contract", None)
    if isinstance(contract, Mapping):
        return contract

    return {}


def _contract_text(
    contract: Mapping[str, object],
    key: str,
    default: str,
) -> str:
    value = contract.get(key)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _contract_bool(
    contract: Mapping[str, object],
    key: str,
    default: bool,
) -> bool:
    value = contract.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    if value is None:
        return default
    return bool(value)


def _contract_preserves_authority_boundary(contract: Mapping[str, object]) -> bool:
    return bool(contract["reporting_only"]) and all(
        not bool(contract[field]) for field in FALSE_AUTHORITY_FIELDS
    )


def _affected_surface(affected_files: tuple[str, ...]) -> str:
    if not affected_files:
        return "unknown"
    if all(path.startswith("tests/") for path in affected_files):
        return "tests"
    if all(path.startswith("src/") for path in affected_files):
        return "source"
    if all(path.startswith(("src/", "tests/")) for path in affected_files):
        return "code"
    return "repo_wide"


def _ownership_area(vector: FailureVectorLike) -> str:
    if vector.affected_files:
        return vector.affected_files[0]
    return "unknown"


def _retryability(failure_class: str) -> str:
    if failure_class in {"dependency", "merge_conflict", "release", "security", "unknown"}:
        return "human_review_required"
    return "not_retryable_without_change"


SHIP_SCHEMA_VERSION = "sdetkit.ship_gate.v1"

CRITICAL_PATH_PATTERNS: tuple[str, ...] = (
    "auth",
    "billing",
    "migration",
    "infra",
    "security",
    "ci",
    "governance",
    "secrets",
    "keys",
)


def determine_risk_tier(
    repo_root: Path,
    explicit_tier: str = "auto",
    blast_radius: float | None = None,
) -> tuple[int, str, float, list[str]]:
    if explicit_tier in ("1", "2", "3"):
        tier_int = int(explicit_tier)
        tier_names = {1: "Fast Path", 2: "Elevated Path", 3: "Sovereign Release Path"}
        return (
            tier_int,
            tier_names[tier_int],
            blast_radius or 0.0,
            [f"Explicitly requested Tier {tier_int}"],
        )

    reasons: list[str] = []
    touched_files: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if len(line) > 3:
                    touched_files.append(line[3:].strip())
    except Exception as exc:
        reasons.append(
            f"Unable to inspect git working tree; defaulting to fallback risk signals ({exc})"
        )

    critical_touched = [
        f for f in touched_files if any(p in f.lower() for p in CRITICAL_PATH_PATTERNS)
    ]
    if critical_touched:
        reasons.append(
            f"Critical path touched ({len(critical_touched)} files): {', '.join(critical_touched[:3])}"
        )
        return 3, "Sovereign Release Path", blast_radius or 85.0, reasons

    br = blast_radius
    if br is None:
        if not touched_files:
            br = 0.0
            reasons.append("Clean working tree (0% blast radius)")
        else:
            br = min(100.0, round(len(touched_files) * 5.0, 1))
            reasons.append(
                f"Computed blast radius: {br:.1f}% from {len(touched_files)} modified files"
            )

    if br < 20.0:
        return 1, "Fast Path", br, reasons or ["Localized blast radius < 20%"]
    elif br <= 60.0:
        return 2, "Elevated Path", br, reasons or ["Moderate blast radius 20-60%"]
    else:
        return 3, "Sovereign Release Path", br, reasons or ["Wide blast radius > 60%"]


def evaluate_ship_gate(
    *,
    repo_root: Path,
    tier: str = "auto",
    blast_radius: float | None = None,
    offline_strict: bool = False,
    use_cache: bool = False,
    max_bloat: float | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    guard = None
    if offline_strict:
        from .network_boundary import install_loopback_audit_guard

        guard = install_loopback_audit_guard(strict=True)

    tier_int, tier_name, br_score, reasons = determine_risk_tier(
        repo_root=repo_root,
        explicit_tier=tier,
        blast_radius=blast_radius,
    )

    ast_cache_info: dict[str, Any] = {"enabled": False}
    if use_cache:
        from .dependency_map import shard_test_suite

        try:
            shard_rep = shard_test_suite(repo_root, use_cache=True)
            ast_cache_info = {
                "enabled": True,
                "cached_tests_skipped": shard_rep.get("cached_tests_skipped", 0),
                "active_tests": shard_rep.get("active_tests_distributed", 0),
                "avoided_duration_seconds": shard_rep.get("avoided_duration_sec", 0.0),
            }
        except Exception:
            ast_cache_info = {
                "enabled": True,
                "cached_tests_skipped": 0,
                "active_tests": 0,
                "avoided_duration_seconds": 0.0,
            }

    env = dict(os.environ)
    if offline_strict:
        env["SDETKIT_OFFLINE_STRICT"] = "1"

    checks_to_run: list[tuple[str, list[str], str]] = []
    # Tier 1 checks
    checks_to_run.append(
        ("doctor", ["doctor", "--ascii"], "Repository hygiene and ASCII compliance")
    )
    checks_to_run.append(
        ("gate_fast", ["gate", "fast", "--skip", "ci_templates,pytest,tests"], "Fast static gate")
    )
    checks_to_run.append(
        ("test_integrity", ["verify", "change", "--runner", "auto"], "Anti-cheating test proof")
    )

    # Tier 2 checks
    if tier_int >= 2:
        checks_to_run.append(
            ("flake_risk", ["genome", "--summary-only"], "AST test smell and flake risk")
        )
        checks_to_run.append(
            ("perf_profile", ["perf", "--benchmarks", "3"], "Execution latency benchmark")
        )

    # Tier 3 checks
    if tier_int >= 3:
        checks_to_run.append(
            (
                "provenance_audit",
                ["provenance", "--verify-hashes"],
                "Supply-chain provenance audit",
            )
        )
        checks_to_run.append(
            ("release_dossier", ["release-room", "--format", "json"], "Release room audit dossier")
        )

    if max_bloat is not None:
        checks_to_run.append(
            (
                "test_suite_bloat",
                ["prune", "--max-bloat", str(float(max_bloat))],
                "Test suite bloat and dead code audit",
            )
        )

    executed_checks: list[dict[str, Any]] = []
    all_passed = True
    any_failed = False

    start_total = time.monotonic()
    per_check_timeout = max(10, timeout // len(checks_to_run))
    for name, args, desc in checks_to_run:
        start_check = time.monotonic()
        try:
            cmd = [sys.executable, "-m", "sdetkit", *args]
            proc = subprocess.run(
                cmd,
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=per_check_timeout,
            )
            dur = round(time.monotonic() - start_check, 2)
            passed = proc.returncode == 0
            if not passed:
                any_failed = True
                all_passed = False
            lines = (proc.stdout or proc.stderr or "").strip().splitlines()
            summary_line = lines[-1] if lines else "Execution completed"
        except subprocess.TimeoutExpired:
            dur = round(time.monotonic() - start_check, 2)
            passed = False
            any_failed = True
            all_passed = False
            summary_line = "Execution timed out"
        except Exception as exc:
            dur = round(time.monotonic() - start_check, 2)
            passed = False
            any_failed = True
            all_passed = False
            summary_line = str(exc)

        executed_checks.append(
            {
                "name": name,
                "description": desc,
                "passed": passed,
                "duration_seconds": dur,
                "summary": summary_line[:120],
            }
        )

    total_duration = round(time.monotonic() - start_total, 2)

    network_egress_status = "NOT_AUDITED"
    air_gap_certified = False
    blocked_violations: list[dict[str, Any]] = []

    if offline_strict and guard is not None:
        blocked_violations = list(guard.blocked_attempts)
        if len(blocked_violations) == 0:
            network_egress_status = "ZERO_BYTES"
            air_gap_certified = True
        else:
            network_egress_status = "VIOLATION"
            air_gap_certified = False
            all_passed = False

    if not all_passed:
        verdict = "NO_SHIP"
    elif any_failed:
        verdict = "REVIEW"
    else:
        verdict = "SHIP"

    return {
        "schema_version": SHIP_SCHEMA_VERSION,
        "repo_root": str(repo_root),
        "verdict": verdict,
        "tier": tier_int,
        "tier_name": tier_name,
        "blast_radius_percent": br_score,
        "reasons": reasons,
        "offline_strict": offline_strict,
        "ast_cache": ast_cache_info,
        "network_egress": network_egress_status,
        "air_gap_certified": air_gap_certified,
        "blocked_network_attempts": blocked_violations,
        "total_duration_seconds": total_duration,
        "checks_count": len(executed_checks),
        "passed_checks_count": sum(1 for c in executed_checks if c["passed"]),
        "failed_checks_count": sum(1 for c in executed_checks if not c["passed"]),
        "checks": executed_checks,
    }


def render_ship_markdown(report: dict[str, Any]) -> str:
    verdict = report.get("verdict", "UNKNOWN")
    badge = f"[{verdict}]"
    tier_num = report.get("tier", 1)
    tier_name = report.get("tier_name", "Fast Path")
    br = report.get("blast_radius_percent", 0.0)
    dur = report.get("total_duration_seconds", 0.0)
    egress = report.get("network_egress", "NOT_AUDITED")
    checks = report.get("checks", [])
    reasons = report.get("reasons", [])

    lines = [
        f"# SDETKit Sovereign Release Gate: {badge}",
        "",
        f"- **Verdict**: **{verdict}**",
        f"- **Verification Tier**: **Tier {tier_num} ({tier_name})**",
        f"- **Blast Radius**: `{br:.1f}%`",
        f"- **Strict Air-Gap Mode**: `{str(report.get('offline_strict', False)).lower()}`",
        f"- **Network Egress**: `{egress}` (Air-Gap Certified: `{str(report.get('air_gap_certified', False)).lower()}`)",
        f"- **Total Duration**: `{dur:.2f}s`",
    ]
    ast_cache = report.get("ast_cache", {})
    if ast_cache.get("enabled"):
        lines.append(
            f"- **AST Result Cache**: `{ast_cache.get('cached_tests_skipped', 0)} tests skipped` "
            f"({ast_cache.get('avoided_duration_seconds', 0.0):.2f}s avoided)"
        )
    lines.extend(
        [
            "",
            "## Risk Assessment & Tier Routing",
            "",
        ]
    )
    for r in reasons:
        lines.append(f"- {r}")

    lines.extend(
        [
            "",
            "## Check Execution Matrix",
            "",
            "| Check | Status | Duration | Details |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )

    for c in checks:
        st = "PASS" if c.get("passed") else "FAIL"
        c_dur = f"{c.get('duration_seconds', 0.0):.2f}s"
        details = str(c.get("summary", "")).replace("|", "/").replace("\n", " ")[:80]
        lines.append(f"| `{c.get('name')}` | `{st}` | {c_dur} | {details} |")

    lines.extend(
        [
            "",
            "## Sovereign Release Guidance",
            "",
        ]
    )
    if verdict == "SHIP":
        lines.append(
            "All tier-governed verification criteria passed with zero egress. Release artifact is ready to ship."
        )
    elif verdict == "REVIEW":
        lines.append(
            "Verification succeeded with warnings. Review highlighted notices before deployment."
        )
    else:
        lines.append(
            "Release gate failed. Address failing check outputs and network boundary violations before proceeding."
        )

    return "\n".join(lines) + "\n"


def render_ship_text(report: dict[str, Any]) -> str:
    verdict = report.get("verdict", "UNKNOWN")
    tier_num = report.get("tier", 1)
    tier_name = report.get("tier_name", "Fast Path")
    br = report.get("blast_radius_percent", 0.0)
    dur = report.get("total_duration_seconds", 0.0)
    egress = report.get("network_egress", "NOT_AUDITED")

    lines = [
        f"SDETKit Sovereign Release Gate: verdict={verdict}",
        f"Tier: {tier_num} ({tier_name}) | Blast Radius: {br:.1f}% | Egress: {egress} | Duration: {dur:.2f}s",
    ]
    ast_cache = report.get("ast_cache", {})
    if ast_cache.get("enabled"):
        lines.append(
            f"AST Cache: {ast_cache.get('cached_tests_skipped', 0)} skipped ({ast_cache.get('avoided_duration_seconds', 0.0):.2f}s avoided)"
        )
    for c in report.get("checks", []):
        st = "PASS" if c.get("passed") else "FAIL"
        lines.append(
            f"  [{st}] {c.get('name')}: {c.get('duration_seconds', 0.0):.2f}s - {c.get('summary')}"
        )
    return "\n".join(lines) + "\n"


def ship_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit ship",
        description="Adaptive risk-tiered release gate with strict air-gap isolation",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root directory")
    parser.add_argument(
        "--tier", choices=["auto", "1", "2", "3"], default="auto", help="Verification tier"
    )
    parser.add_argument("--blast-radius", type=float, help="Manual blast radius score (0-100)")
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Enable AST test result cache to skip unimpacted tests",
    )
    parser.add_argument(
        "--offline-strict",
        action="store_true",
        help="Enforce strict air-gap socket audit hooks (allowlisting loopback/IPC only)",
    )
    parser.add_argument(
        "--max-bloat",
        type=float,
        default=None,
        help="Maximum allowable test suite bloat score (0-100)",
    )
    parser.add_argument(
        "--format", choices=["text", "json", "md"], default="text", help="Output format"
    )
    parser.add_argument("--out", help="Write output to file")
    parser.add_argument("--summary-out", help="Append markdown summary to file")

    ns = parser.parse_args(argv)

    root = Path(ns.repo_root).resolve()
    report = evaluate_ship_gate(
        repo_root=root,
        tier=ns.tier,
        blast_radius=ns.blast_radius,
        offline_strict=ns.offline_strict,
        use_cache=ns.cache,
        max_bloat=ns.max_bloat,
    )

    if ns.format == "json":
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    elif ns.format == "md":
        output = render_ship_markdown(report)
    else:
        output = render_ship_text(report)

    if ns.out:
        out_path = Path(ns.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    if ns.summary_out:
        summary_path = Path(ns.summary_out).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        md_summary = render_ship_markdown(report)
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(md_summary)

    return 0 if report.get("verdict") in ("SHIP", "REVIEW") else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "ship":
        args = args[1:]
    return ship_main(args)
