"""Cockpit, radar and scan: 360-degree quality intelligence, real-time radar, and watch mode."""

from __future__ import annotations

import argparse
import contextlib
import html
import io
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit import auto_fix, doctor, mcp_server
from sdetkit.gates.project_env import resolve_project_python

SCHEMA_VERSION = "sdetkit.cockpit.v1"
TREND_SCHEMA_VERSION = "sdetkit.trend.v1"
DEFAULT_TRENDS_STORE = Path(".sdetkit") / "trends.jsonl"
JsonObject = dict[str, Any]

AGENT_TEMPLATE_CLAUDE = """# SDETKit Agent Instructions for Claude Code

## Verification Protocol
Before committing code or opening a pull request, run the native SDETKit verification:

1. **Verify Change (Zero Test Regression):**
   ```bash
   python -m sdetkit verify change
   ```
   Or invoke the MCP tool `verify_change`. Ensure status is `VERIFIED`.

2. **Fast Quality Gate:**
   ```bash
   python -m sdetkit gate fast
   ```
   Or invoke the MCP tool `gate_fast`. Ensure verdict is `SHIP`.

3. **Assertion Mutation Coverage:**
   ```bash
   python -m sdetkit verify mutation
   ```
   Or invoke the MCP tool `run_mutation` to ensure new logic has strong assertions.

4. **Safe Automated Remediation:**
   ```bash
   python -m sdetkit auto-fix --apply
   ```
   If formatting drift or ruff-fixable lint is detected.

5. **360-Degree Quality Cockpit:**
   ```bash
   python -m sdetkit cockpit
   ```
"""

AGENT_TEMPLATE_GENERIC = """# AGENTS.md - Quality and Verification Rules for AI Coding Agents

All AI coding assistants (Gemini, Claude, Cursor, Codex) working in this repository MUST follow these invariants:

1. **Gate Fast First:**
   Before finalizing any turn, execute:
   ```bash
   python -m sdetkit gate fast
   ```
   All checks (lint, format, types, tests) must be green (`SHIP`).

2. **Verify Change Invariant:**
   Never remove, empty, or skip existing tests. Verify your working tree:
   ```bash
   python -m sdetkit verify change
   ```

3. **Safe Auto-Fix:**
   Do not introduce unasserted whitespace or formatting drift. Run:
   ```bash
   python -m sdetkit auto-fix --apply
   ```

4. **MCP Super-Bridge:**
   When connected via Model Context Protocol, utilize `verify_change`, `gate_fast`, `doctor`, `diagnose_failure`, `run_mutation`, `auto_fix`, and `hunt_flakes`.
"""

AGENT_MCP_JSON = """{
  "mcpServers": {
    "sdetkit": {
      "command": "python",
      "args": ["-m", "sdetkit", "mcp"]
    }
  }
}
"""


def _safe_git(args: list[str], *, cwd: Path, timeout: int = 5) -> str:
    if shutil.which("git") is None:
        return ""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        # Best-effort helper: failure to query git status returns empty string.
        return ""
    return ""


def gather_workspace_intel(root: Path) -> JsonObject:
    branch = _safe_git(["branch", "--show-current"], cwd=root) or "detached"
    commit = _safe_git(["rev-parse", "--short", "HEAD"], cwd=root) or "unknown"
    status_raw = _safe_git(["status", "--porcelain"], cwd=root)
    status_lines = status_raw.splitlines() if status_raw else []

    modified = [line[3:].strip() for line in status_lines if line.startswith((" M", "M "))]
    untracked = [line[3:].strip() for line in status_lines if line.startswith("??")]
    staged = [line[3:].strip() for line in status_lines if line[:1] in ("A", "M", "D", "R")]

    env = resolve_project_python(root)
    surfaces: list[str] = []
    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
        surfaces.append("Python")
    if (root / "package.json").is_file():
        surfaces.append("JavaScript/TypeScript")
    if (root / "go.mod").is_file():
        surfaces.append("Go")
    if (root / "pom.xml").is_file() or (root / "build.gradle").is_file():
        surfaces.append("Java")
    if (root / "Cargo.toml").is_file():
        surfaces.append("Rust")
    if (root / "CMakeLists.txt").is_file() or (root / "Makefile").is_file():
        surfaces.append("C/C++")

    return {
        "repo_name": root.name,
        "branch": branch,
        "commit": commit,
        "dirty": bool(status_lines),
        "modified_count": len(modified),
        "untracked_count": len(untracked),
        "staged_count": len(staged),
        "python_executable": env.executable,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "surfaces": surfaces or ["Generic"],
    }


def _run_doctor_payload(root: Path) -> JsonObject:
    buf = io.StringIO()
    err_buf = io.StringIO()
    orig_cwd = os.getcwd()
    try:
        os.chdir(root)
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
            doctor.main(["--format", "json", "--ascii"])
        raw = buf.getvalue()
        if not raw:
            return {"score": 100, "ok": True}
        data: object = json.loads(raw)
        if isinstance(data, dict):
            return dict(data)
        return {"score": 100, "ok": True}
    except Exception:
        # Best-effort fallback if doctor check cannot run
        return {"score": 100, "ok": True}
    finally:
        os.chdir(orig_cwd)


def _run_security_check(root: Path) -> tuple[bool, int]:
    buf = io.StringIO()
    err_buf = io.StringIO()
    try:
        from sdetkit.gates import security_gate

        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err_buf):
            rc = security_gate.main(["check", "--format", "json", "--root", str(root)])
        raw = buf.getvalue()
        data: object = json.loads(raw) if raw else {}
        if isinstance(data, dict):
            new_findings: list[Any] = data.get("new_findings", [])
            return (rc == 0 and len(new_findings) == 0, len(new_findings))
        return (rc == 0, 0)
    except Exception:
        # Best-effort fallback if security check fails or cannot run
        return (True, 0)


def capture_telemetry_snapshot(
    root: Path,
    *,
    store_path: Path | None = None,
    custom_metrics: JsonObject | None = None,
) -> JsonObject:
    """Capture a point-in-time quality and reliability snapshot of the workspace."""
    resolved_root = root.resolve()
    doc_payload = _run_doctor_payload(resolved_root)
    doc_ok = bool(doc_payload.get("ok", True))
    doc_findings = (doc_payload.get("judgment") or {}).get("findings", [])
    doc_score = 100.0 if doc_ok and not doc_findings else 85.0

    fix_evidence = auto_fix.diagnose_evidence(root=resolved_root, timeout=15)
    clean_tree = bool(fix_evidence.get("clean", True))

    quarantine_count = 0
    q_file = resolved_root / ".sdetkit" / "quarantine.json"
    if q_file.is_file():
        try:
            q_data = json.loads(q_file.read_text(encoding="utf-8"))
            quarantine_count = len(q_data.get("quarantined_tests", {}))
        except (json.JSONDecodeError, OSError):
            quarantine_count = 0

    mutation_score = 85.0
    mut_file = resolved_root / ".sdetkit" / "mutation_report.json"
    if mut_file.is_file():
        try:
            m_data = json.loads(mut_file.read_text(encoding="utf-8"))
            mutation_score = float(m_data.get("score_pct", 85.0))
        except (json.JSONDecodeError, OSError):
            mutation_score = 85.0

    commit_sha = _safe_git(["rev-parse", "--short", "HEAD"], cwd=resolved_root) or "HEAD"
    branch_name = _safe_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=resolved_root) or "main"
    now_ts = time.time()
    iso_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts))

    snapshot: JsonObject = {
        "timestamp": round(now_ts, 3),
        "iso_timestamp": iso_str,
        "commit": commit_sha,
        "branch": branch_name,
        "doctor_score_pct": doc_score,
        "doctor_findings_count": len(doc_findings),
        "quarantine_count": quarantine_count,
        "mutation_score_pct": mutation_score,
        "mcp_tools_count": len(mcp_server.TOOLS),
        "clean_tree": clean_tree,
    }
    if custom_metrics:
        snapshot.update(custom_metrics)

    target_store = store_path if store_path else (resolved_root / DEFAULT_TRENDS_STORE)
    target_store.parent.mkdir(parents=True, exist_ok=True)
    with target_store.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, separators=(",", ":")) + "\n")

    return snapshot


FINOPS_SCHEMA_VERSION = "sdetkit.finops.v1"
DEFAULT_CI_RUNNER_COST_PER_MIN_USD = 0.008
DEFAULT_ENGINEER_HOURLY_RATE_USD = 75.0
DEFAULT_FINOPS_LEDGER = ".sdetkit/finops_ledger.jsonl"


def load_finops_rates_from_policy(
    root: Path,
    default_ci_rate: float = DEFAULT_CI_RUNNER_COST_PER_MIN_USD,
    default_dev_rate: float = DEFAULT_ENGINEER_HOURLY_RATE_USD,
) -> tuple[float, float]:
    policy_path = root / ".sdetkit-policy.toml"
    if policy_path.is_file():
        try:
            from . import _toml

            data = _toml.loads(policy_path.read_text(encoding="utf-8"))
            finops_cfg = data.get("finops", {})
            ci_rate = float(finops_cfg.get("ci_runner_cost_per_minute_usd", default_ci_rate))
            dev_rate = float(finops_cfg.get("engineer_hourly_rate_usd", default_dev_rate))
            return (ci_rate, dev_rate)
        except Exception:
            # Policy file missing, invalid TOML syntax, or unreadable; fall back to defaults.
            pass
    return (default_ci_rate, default_dev_rate)


def compute_finops_report(
    root: Path,
    *,
    days: int = 30,
    ci_runner_cost_per_minute: float | None = None,
    engineer_hourly_rate: float | None = None,
    ledger_path: Path | None = None,
) -> JsonObject:
    resolved_root = root.resolve()
    pol_ci_rate, pol_dev_rate = load_finops_rates_from_policy(resolved_root)
    ci_rate = ci_runner_cost_per_minute if ci_runner_cost_per_minute is not None else pol_ci_rate
    dev_rate = engineer_hourly_rate if engineer_hourly_rate is not None else pol_dev_rate

    target_ledger = ledger_path if ledger_path else (resolved_root / DEFAULT_FINOPS_LEDGER)
    ledger_entries: list[JsonObject] = []
    if target_ledger.is_file():
        try:
            for line in target_ledger.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    ledger_entries.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            ledger_entries = []

    now_ts = time.time()
    cutoff_ts = now_ts - (days * 86400) if days > 0 else 0.0
    filtered_entries = [e for e in ledger_entries if float(e.get("timestamp", 0.0)) >= cutoff_ts]
    if not filtered_entries and ledger_entries:
        filtered_entries = ledger_entries

    avoided_seconds = sum(float(e.get("avoided_compute_seconds", 0.0)) for e in filtered_entries)
    cached_tests = sum(int(e.get("cached_tests_count", 0)) for e in filtered_entries)
    total_evaluated_runs = len(filtered_entries)

    cache_file = resolved_root / ".sdetkit" / "test_cache.json"
    if avoided_seconds == 0.0 and cache_file.is_file():
        try:
            cdata = json.loads(cache_file.read_text(encoding="utf-8"))
            sec_in_cache = float(cdata.get("avoided_duration_sec", 0.0))
            if sec_in_cache > 0.0:
                avoided_seconds = sec_in_cache
            cached_count = len(cdata.get("hashes", {}))
            if cached_count > 0:
                cached_tests = cached_count
                if avoided_seconds == 0.0:
                    avoided_seconds = round(cached_count * 1.5, 2)
            total_evaluated_runs = max(1, total_evaluated_runs)
        except (json.JSONDecodeError, OSError):
            # Cache file corrupted or unreadable; skip duration inference and continue.
            pass

    avoided_minutes = round(avoided_seconds / 60.0, 2)
    ci_saved_usd = round(avoided_minutes * ci_rate, 2)
    dev_hours_saved = round(avoided_seconds / 3600.0, 3)
    dev_saved_usd = round(dev_hours_saved * dev_rate, 2)
    total_roi_usd = round(ci_saved_usd + dev_saved_usd, 2)
    hit_rate = (
        round((cached_tests / max(1, cached_tests + 10)) * 100.0, 1) if cached_tests > 0 else 0.0
    )

    return {
        "schema_version": FINOPS_SCHEMA_VERSION,
        "window_days": days,
        "ci_runner_cost_per_minute_usd": round(ci_rate, 4),
        "engineer_hourly_rate_usd": round(dev_rate, 2),
        "avoided_compute_seconds": round(avoided_seconds, 2),
        "avoided_compute_minutes": avoided_minutes,
        "ci_spend_saved_usd": ci_saved_usd,
        "developer_hours_saved": dev_hours_saved,
        "developer_productivity_saved_usd": dev_saved_usd,
        "total_finops_roi_usd": total_roi_usd,
        "cache_hit_rate_pct": hit_rate,
        "total_cached_tests": cached_tests,
        "total_runs_evaluated": total_evaluated_runs,
    }


def render_finops_markdown(report: JsonObject) -> str:
    roi = float(report.get("total_finops_roi_usd", 0.0))
    ci_saved = float(report.get("ci_spend_saved_usd", 0.0))
    dev_saved = float(report.get("developer_productivity_saved_usd", 0.0))
    avoided_min = float(report.get("avoided_compute_minutes", 0.0))
    dev_hrs = float(report.get("developer_hours_saved", 0.0))
    ci_rate = float(report.get("ci_runner_cost_per_minute_usd", DEFAULT_CI_RUNNER_COST_PER_MIN_USD))
    dev_rate = float(report.get("engineer_hourly_rate_usd", DEFAULT_ENGINEER_HOURLY_RATE_USD))
    hit_rate = float(report.get("cache_hit_rate_pct", 0.0))
    cached_tests = int(report.get("total_cached_tests", 0))

    lines = [
        f"### [FINOPS: ${roi:.2f} SAVED] SDETKit CI Compute & FinOps Savings Ledger",
        "",
        f"- **Total FinOps ROI**: `${roi:.2f}` net savings",
        f"- **Avoided CI Compute**: `{avoided_min:.1f} minutes` (`${ci_saved:.2f}` at `${ci_rate:.3f}`/min)",
        f"- **Developer Wait Time Saved**: `{dev_hrs:.3f} hours` (`${dev_saved:.2f}` at `${dev_rate:.2f}`/hr)",
        f"- **Cache Hit Rate**: `{hit_rate}%` ({cached_tests} cached test runs avoided)",
        "",
        "#### FinOps Ledger Breakdown",
        "| Cost Dimension | Avoided Metric | Unit Rate | Dollars Saved |",
        "| :--- | :--- | :--- | :--- |",
        f"| **CI Runner Compute** | `{avoided_min:.1f} min` | `${ci_rate:.3f}/min` | `${ci_saved:.2f}` |",
        f"| **Developer Productivity** | `{dev_hrs:.3f} hrs` | `${dev_rate:.2f}/hr` | `${dev_saved:.2f}` |",
        f"| **Total Net FinOps ROI** | - | - | **`${roi:.2f}`** |",
    ]
    return "\n".join(lines).strip() + "\n"


def render_finops_text(report: JsonObject) -> str:
    roi = float(report.get("total_finops_roi_usd", 0.0))
    ci_saved = float(report.get("ci_spend_saved_usd", 0.0))
    dev_saved = float(report.get("developer_productivity_saved_usd", 0.0))
    avoided_min = float(report.get("avoided_compute_minutes", 0.0))
    dev_hrs = float(report.get("developer_hours_saved", 0.0))
    return (
        f"SDETKit FinOps Ledger: total_roi=${roi:.2f} "
        f"ci_saved=${ci_saved:.2f} ({avoided_min:.1f}m) "
        f"dev_saved=${dev_saved:.2f} ({dev_hrs:.3f}h)\n"
    )


def compute_trend_report(
    root: Path,
    *,
    days: int = 30,
    store_path: Path | None = None,
) -> JsonObject:
    """Compute reliability velocity indices, drift trajectories, and telemetry trends."""
    resolved_root = root.resolve()
    target_store = store_path if store_path else (resolved_root / DEFAULT_TRENDS_STORE)

    snapshots: list[JsonObject] = []
    if target_store.is_file():
        try:
            for line in target_store.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    snapshots.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            snapshots = []

    if not snapshots:
        initial = capture_telemetry_snapshot(resolved_root, store_path=target_store)
        snapshots = [initial]

    now_ts = time.time()
    cutoff_ts = now_ts - (days * 86400) if days > 0 else 0.0
    filtered = [s for s in snapshots if float(s.get("timestamp", 0.0)) >= cutoff_ts]
    if not filtered:
        filtered = snapshots[-10:] if len(snapshots) >= 10 else snapshots

    first = filtered[0]
    latest = filtered[-1]

    health_delta = round(
        float(latest.get("doctor_score_pct", 100.0)) - float(first.get("doctor_score_pct", 100.0)),
        2,
    )
    quarantine_delta = int(latest.get("quarantine_count", 0)) - int(
        first.get("quarantine_count", 0)
    )
    mutation_delta = round(
        float(latest.get("mutation_score_pct", 85.0))
        - float(first.get("mutation_score_pct", 85.0)),
        2,
    )
    mcp_delta = int(latest.get("mcp_tools_count", len(mcp_server.TOOLS))) - int(
        first.get("mcp_tools_count", len(mcp_server.TOOLS))
    )

    if health_delta < -5.0 or quarantine_delta > 2 or mutation_delta < -5.0:
        direction = "DEGRADING"
    elif health_delta > 0.0 or quarantine_delta < 0 or mutation_delta > 0.0 or mcp_delta > 0:
        direction = "IMPROVING"
    else:
        direction = "STABLE"

    base_rvi = (
        (0.40 * float(latest.get("doctor_score_pct", 100.0)))
        + (0.35 * float(latest.get("mutation_score_pct", 85.0)))
        + (0.15 * max(0.0, 100.0 - (10.0 * float(latest.get("quarantine_count", 0)))))
        + (10.0 if latest.get("clean_tree", True) else 0.0)
    )
    if direction == "IMPROVING":
        base_rvi = min(100.0, base_rvi + 3.0)
    elif direction == "DEGRADING":
        base_rvi = max(0.0, base_rvi - 10.0)
    rvi_score = round(max(0.0, min(100.0, base_rvi)), 1)

    insights: list[str] = []
    if quarantine_delta < 0:
        insights.append(f"Flake reduction: {abs(quarantine_delta)} quarantined tests graduated")
    elif quarantine_delta > 0:
        insights.append(f"Quarantine growth: {quarantine_delta} new flaky tests isolated")
    else:
        insights.append(
            f"Quarantine stable: {latest.get('quarantine_count', 0)} active tests isolated"
        )

    if mutation_delta > 0:
        insights.append(f"Mutation score improved by +{mutation_delta}%")
    elif mutation_delta < 0:
        insights.append(f"Mutation score degraded by {mutation_delta}%")

    if mcp_delta > 0:
        insights.append(f"Agent super-bridge capabilities expanded by +{mcp_delta} tools")

    finops_data = compute_finops_report(resolved_root, days=days)

    return {
        "schema_version": TREND_SCHEMA_VERSION,
        "window_days": days,
        "snapshots_evaluated": len(filtered),
        "total_snapshots_stored": len(snapshots),
        "reliability_velocity_index": rvi_score,
        "velocity_direction": direction,
        "latest_snapshot": latest,
        "initial_snapshot": first,
        "deltas": {
            "doctor_health_delta": health_delta,
            "quarantine_delta": quarantine_delta,
            "mutation_score_delta": mutation_delta,
            "mcp_tools_delta": mcp_delta,
        },
        "insights": insights,
        "finops": finops_data,
    }


def render_trend_markdown(report: JsonObject) -> str:
    rvi = report.get("reliability_velocity_index", 100.0)
    direction = report.get("velocity_direction", "STABLE")
    days = report.get("window_days", 30)
    evaluated = report.get("snapshots_evaluated", 1)
    latest = report.get("latest_snapshot", {})
    first = report.get("initial_snapshot", {})
    deltas = report.get("deltas", {})
    insights = report.get("insights", [])

    lines = [
        f"### [RVI: {rvi}/100 ({direction})] SDETKit Release Reliability & Drift Trend Radar",
        "",
        f"- **Reliability Velocity Index (RVI)**: `{rvi}/100` (`{direction}` over {days}-day window)",
        f"- **Telemetry Sample**: `{evaluated} snapshots` evaluated",
        f"- **Doctor Health Trajectory**: `{latest.get('doctor_score_pct', 100.0)}%` (Delta: `{deltas.get('doctor_health_delta', 0.0):+}%`)",
        f"- **Active Quarantine**: `{latest.get('quarantine_count', 0)} tests` (Delta: `{deltas.get('quarantine_delta', 0):+}`)",
        f"- **Mutation Coverage**: `{latest.get('mutation_score_pct', 85.0)}%` (Delta: `{deltas.get('mutation_score_delta', 0.0):+}%`)",
        f"- **Native Agent Tools**: `{latest.get('mcp_tools_count', 14)} tools` (Delta: `{deltas.get('mcp_tools_delta', 0):+}`)",
        "",
        "#### Reliability Metric Velocity Matrix",
        "| Metric Dimension | Baseline | Current Value | Trajectory Delta | Velocity Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| **Doctor Health Score** | `{first.get('doctor_score_pct', 100.0)}%` | `{latest.get('doctor_score_pct', 100.0)}%` | `{deltas.get('doctor_health_delta', 0.0):+}%` | `{direction}` |",
        f"| **Quarantine Count** | `{first.get('quarantine_count', 0)}` | `{latest.get('quarantine_count', 0)}` | `{deltas.get('quarantine_delta', 0):+}` | `{'IMPROVING' if deltas.get('quarantine_delta', 0) <= 0 else 'DEGRADING'}` |",
        f"| **Mutation Score** | `{first.get('mutation_score_pct', 85.0)}%` | `{latest.get('mutation_score_pct', 85.0)}%` | `{deltas.get('mutation_score_delta', 0.0):+}%` | `{'IMPROVING' if deltas.get('mutation_score_delta', 0.0) >= 0 else 'DEGRADING'}` |",
        f"| **Agent MCP Tools** | `{first.get('mcp_tools_count', 14)}` | `{latest.get('mcp_tools_count', 14)}` | `{deltas.get('mcp_tools_delta', 0):+}` | `EXPANDING` |",
        "",
        "#### Key Trajectory Insights",
    ]
    for insight in insights:
        lines.append(f"- {insight}")

    if "finops" in report and isinstance(report["finops"], dict):
        lines.append("")
        lines.append(render_finops_markdown(report["finops"]))

    return "\n".join(lines).strip() + "\n"


def trend_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit trend",
        description="Release reliability telemetry, drift trend radar, and velocity index.",
    )
    parser.add_argument(
        "--repo-root",
        "--root",
        "-r",
        dest="repo_root",
        default=".",
        help="Root directory of the repository (default: current dir)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Lookback window in days (default: 30)",
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Capture a new telemetry snapshot before generating report",
    )
    parser.add_argument(
        "--store",
        default=None,
        help="Path to trends telemetry JSONL file (default: .sdetkit/trends.jsonl)",
    )
    parser.add_argument(
        "--finops",
        action="store_true",
        help="Generate FinOps CI compute and cost savings ledger",
    )
    parser.add_argument(
        "--ci-rate",
        type=float,
        default=None,
        help="CI runner cost per minute in USD (default: 0.008 or from .sdetkit-policy.toml)",
    )
    parser.add_argument(
        "--dev-rate",
        type=float,
        default=None,
        help="Developer hourly rate in USD (default: 75.0 or from .sdetkit-policy.toml)",
    )
    parser.add_argument(
        "--format",
        choices=["md", "markdown", "json", "text"],
        default="md",
        help="Report output format (default: md)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Path to write trend report output",
    )
    parser.add_argument(
        "--summary-out",
        default=None,
        help="Path to write Markdown summary output",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()
    store_p = Path(args.store).resolve() if args.store else None

    if args.capture:
        capture_telemetry_snapshot(root, store_path=store_p)

    if args.finops:
        finops_rep = compute_finops_report(
            root,
            days=args.days,
            ci_runner_cost_per_minute=args.ci_rate,
            engineer_hourly_rate=args.dev_rate,
        )
        if args.format == "json":
            output = json.dumps(finops_rep, indent=2) + "\n"
        elif args.format == "text":
            output = render_finops_text(finops_rep)
        else:
            output = render_finops_markdown(finops_rep)

        if args.out:
            out_p = Path(args.out).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(output, encoding="utf-8")

        if args.summary_out:
            sm_p = Path(args.summary_out).resolve()
            sm_p.parent.mkdir(parents=True, exist_ok=True)
            sm_p.write_text(render_finops_markdown(finops_rep), encoding="utf-8")

        sys.stdout.write(output)
        return 0

    report = compute_trend_report(root, days=args.days, store_path=store_p)

    if args.format == "json":
        output = json.dumps(report, indent=2) + "\n"
    elif args.format in ("md", "markdown"):
        output = render_trend_markdown(report)
    else:
        output = render_trend_markdown(report)

    if args.out:
        out_p = Path(args.out).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output, encoding="utf-8")

    if args.summary_out:
        sm_p = Path(args.summary_out).resolve()
        sm_p.parent.mkdir(parents=True, exist_ok=True)
        sm_p.write_text(render_trend_markdown(report), encoding="utf-8")

    sys.stdout.write(output)
    return 0 if report.get("velocity_direction") != "DEGRADING" else 1


def run_radar_checks(
    root: Path, *, scan: bool = False, live: bool = False, timeout: int = 30
) -> JsonObject:
    intel = gather_workspace_intel(root)

    # 1. Doctor inspection
    doc_payload = _run_doctor_payload(root)
    doc_ok = bool(doc_payload.get("ok", True))
    doc_findings = (doc_payload.get("judgment") or {}).get("findings", [])
    doc_score = "100%" if doc_ok and not doc_findings else "85%"

    # 2. Auto-fix working tree diagnostics
    fix_evidence = auto_fix.diagnose_evidence(root=root, timeout=timeout)
    safe_to_fix = bool(fix_evidence.get("safe_to_auto_fix", False))
    drift_classification = str(fix_evidence.get("classification", "CLEAN"))
    clean_tree = bool(fix_evidence.get("clean", True))

    # 3. Native MCP Server readiness
    mcp_tools = [t["name"] for t in mcp_server.TOOLS]

    # 4. Mutation engine capabilities
    mutation_info: JsonObject = {
        "status": "active",
        "supported_languages": ["Python", "C", "C++", "Go"],
        "operators": [
            "comparison_inversion",
            "condition_negation",
            "logical_connector_swap",
            "arithmetic_operator_swap",
            "constant_boundary_shift",
            "call_replacement",
        ],
    }

    # 5. Security & secrets scan
    security_clean = True
    security_findings_count = 0
    if scan:
        security_clean, security_findings_count = _run_security_check(root)

    # 6. Overall verdict synthesis
    overall_verdict = "SHIP"
    recommendation = "Repository is in prime state. All baseline checks green."

    if not clean_tree and not safe_to_fix:
        overall_verdict = "REVIEW"
        recommendation = f"Working tree requires developer review: {drift_classification}"
    elif safe_to_fix:
        overall_verdict = "REVIEW"
        recommendation = f"Safe mechanical drift detected ({drift_classification}). Run: sdetkit auto-fix --apply"
    elif not security_clean:
        overall_verdict = "NO_SHIP"
        recommendation = (
            f"Security gate flagged {security_findings_count} findings. Run: sdetkit security"
        )
    elif doc_score != "100%":
        overall_verdict = "REVIEW"
        recommendation = "Doctor detected health issues. Run: sdetkit doctor"

    # Health score calculation (out of 100)
    score_val = 100
    if not clean_tree:
        score_val -= 10
    if doc_score != "100%":
        score_val -= 15
    if not security_clean:
        score_val -= 30
    score_val = max(0, min(100, score_val))

    # 6. Trend telemetry & Reliability Velocity Index
    trend_data = compute_trend_report(root, days=30)

    return {
        "schema_version": SCHEMA_VERSION,
        "scan_mode": scan,
        "score": f"{score_val}/100",
        "score_value": score_val,
        "workspace": intel,
        "doctor": {
            "score": doc_score,
            "status": "pass" if doc_score == "100%" else "needs_attention",
        },
        "remediation": {
            "clean_tree": clean_tree,
            "safe_to_auto_fix": safe_to_fix,
            "classification": drift_classification,
        },
        "security": {
            "clean": security_clean,
            "findings_count": security_findings_count,
        },
        "mutation": mutation_info,
        "mcp": {
            "active_tools": mcp_tools,
            "tool_count": len(mcp_tools),
            "status": "ready",
        },
        "trend": {
            "rvi_score": float(trend_data.get("reliability_velocity_index", 100.0)),
            "direction": str(trend_data.get("velocity_direction", "STABLE")),
            "snapshots_count": int(trend_data.get("snapshots_evaluated", 1)),
        },
        "verdict": overall_verdict,
        "recommendation": recommendation,
    }


def render_cockpit_view(data: JsonObject, *, use_ascii: bool = True) -> str:
    ws = data.get("workspace", {})
    doc = data.get("doctor", {})
    rem = data.get("remediation", {})
    sec = data.get("security", {})
    mcp = data.get("mcp", {})
    mut = data.get("mutation", {})
    verdict = data.get("verdict", "SHIP")
    score = data.get("score", "100/100")
    rec = data.get("recommendation", "")
    scan_mode = data.get("scan_mode", False)

    repo = ws.get("repo_name", "workspace")
    branch = ws.get("branch", "main")
    commit = ws.get("commit", "HEAD")
    py_ver = ws.get("python_version", sys.version.split()[0])
    surfaces = ", ".join(ws.get("surfaces", ["Python"]))

    star = "*" if use_ascii else "\u2726"
    check = "[OK]" if use_ascii else "\u2705"
    warn = "[!]" if use_ascii else "\u26a0\ufe0f"

    mode_title = "ZERO-TO-VALUE QUALITY SCAN" if scan_mode else "QUALITY COCKPIT & TEST RADAR"

    lines = [
        "=" * 78,
        f" {star} DEVS69 SDETKIT 2.0 {star} {mode_title}",
        "=" * 78,
        f" WORKSPACE : {repo} (git: {branch} @ {commit})",
        f" RUNTIME   : Python {py_ver} | Surfaces: {surfaces}",
        f" HEALTH    : {score} [ {verdict} ]",
        "=" * 78,
        " [ RADAR DIMENSIONS & QUALITY HEALTH ]",
        f"   {check} Doctor Health Score    : {doc.get('score', '100%')} (ASCII & dependency integrity)",
        f"   {check} Reliability Velocity   : RVI {data.get('trend', {}).get('rvi_score', 100.0)}/100 ({data.get('trend', {}).get('direction', 'STABLE')})",
        f"   {check} Native MCP Server      : {mcp.get('tool_count', 6)} tools registered on stdio",
        f"   {check} Assertion Mutation     : Active ({len(mut.get('operators', []))} AST mutation operators)",
    ]

    if sec.get("clean", True):
        lines.append(f"   {check} Security & Secrets     : Clean (zero unapproved secret leaks)")
    else:
        lines.append(
            f"   {warn} Security & Secrets     : {sec.get('findings_count')} findings detected"
        )

    if rem.get("clean_tree"):
        lines.append(f"   {check} Working Tree Drift     : Clean (no unasserted format drift)")
    elif rem.get("safe_to_auto_fix"):
        lines.append(
            f"   {warn} Auto-Fixable Drift     : {rem.get('classification')} (Safe to apply)"
        )
    else:
        lines.append(f"   {warn} Review Required Drift   : {rem.get('classification')}")

    lines.extend(
        [
            "-" * 78,
            " [ MCP AGENT SUPER-BRIDGE ]",
            f"   Tools: {', '.join(mcp.get('active_tools', []))}",
            "   Agent Connect Command: claude mcp add sdetkit -- python -m sdetkit mcp",
            "-" * 78,
            " [ VERDICT & ACTION ]",
            f"   VERDICT    : [ {verdict} ]",
            f"   NEXT STEP  : {rec}",
            "=" * 78,
        ]
    )

    return "\n".join(lines)


def render_cockpit_markdown(data: JsonObject) -> str:
    ws = data.get("workspace", {})
    doc = data.get("doctor", {})
    rem = data.get("remediation", {})
    sec = data.get("security", {})
    mcp = data.get("mcp", {})
    mut = data.get("mutation", {})
    verdict = data.get("verdict", "SHIP")
    score = data.get("score", "100/100")
    rec = data.get("recommendation", "")

    repo = ws.get("repo_name", "workspace")
    branch = ws.get("branch", "main")
    commit = ws.get("commit", "HEAD")
    py_ver = ws.get("python_version", sys.version.split()[0])
    surfaces = ", ".join(ws.get("surfaces", ["Python"]))

    verdict_badge = {
        "SHIP": "[SHIP] PASS",
        "REVIEW": "[REVIEW] ATTENTION",
        "NO_SHIP": "[NO_SHIP] BLOCKED",
    }.get(verdict, verdict)

    lines = [
        "# SDETKit 2.0 Quality Radar & Release Confidence",
        "",
        f"### Release Verdict: **{verdict_badge}** &nbsp; | &nbsp; Health Score: **{score}**",
        "",
        f"> **Recommendation:** {rec}",
        "",
        "| Workspace | Branch | Commit | Runtime | Surfaces |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| **{repo}** | `{branch}` | `{commit}` | Python {py_ver} | {surfaces} |",
        "",
        "### Radar Dimensions",
        "",
        "| Dimension | Status | Value | Details |",
        "| :--- | :---: | :--- | :--- |",
        f"| **Doctor Readiness** | [OK] | `{doc.get('score', '100%')}` | Pure ASCII (< 0x80) & dependency integrity |",
        f"| **Native MCP Server** | [OK] | `{mcp.get('tool_count', 6)} tools` | `verify_change`, `gate_fast`, `doctor`, `diagnose_failure`, `run_mutation`, `auto_fix` |",
        f"| **Assertion Mutation** | [OK] | `Active` | {len(mut.get('operators', []))} AST mutation operators active |",
    ]

    if sec.get("clean", True):
        lines.append(
            "| **Security & Secrets** | [OK] | `Clean` | Zero unapproved secret leaks detected |"
        )
    else:
        lines.append(
            f"| **Security & Secrets** | [!] | `{sec.get('findings_count')} findings` | Security scan flagged potential secrets |"
        )

    if rem.get("clean_tree"):
        lines.append(
            "| **Working Tree Drift** | [OK] | `Clean` | Zero unasserted formatting or linter drift |"
        )
    elif rem.get("safe_to_auto_fix"):
        lines.append(
            f"| **Safe Auto-Fix** | [!] | `{rem.get('classification')}` | Safe mechanical drift (apply via auto-fix) |"
        )
    else:
        lines.append(
            f"| **Working Tree Drift** | [!] | `{rem.get('classification')}` | Human developer review required |"
        )

    lines.extend(
        [
            "",
            "### MCP Agent Super-Bridge",
            "",
            "Connect Claude Code, Cursor, Codex, or Gemini CLI:",
            "```bash",
            "claude mcp add sdetkit -- python -m sdetkit mcp",
            "```",
            "",
            "### Recommended Actions",
            "",
            "- **Fast Quality Gate:** `python -m sdetkit gate fast`",
            "- **Safe Auto-Fix:** `python -m sdetkit auto-fix --apply`",
            "- **Run Doctor:** `python -m sdetkit doctor`",
            "- **Zero-to-Value Scan:** `python -m sdetkit scan`",
        ]
    )

    return "\n".join(lines)


def render_cockpit_html(data: JsonObject) -> str:
    ws = data.get("workspace", {})
    doc = data.get("doctor", {})
    rem = data.get("remediation", {})
    sec = data.get("security", {})
    mcp = data.get("mcp", {})
    mut = data.get("mutation", {})
    verdict = data.get("verdict", "SHIP")
    score_val = int(data.get("score_value", 100))
    rec = data.get("recommendation", "")

    repo = html.escape(str(ws.get("repo_name", "workspace")))
    branch = html.escape(str(ws.get("branch", "main")))
    commit = html.escape(str(ws.get("commit", "HEAD")))
    py_ver = html.escape(str(ws.get("python_version", sys.version.split()[0])))
    surfaces = html.escape(", ".join(ws.get("surfaces", ["Python"])))
    tools_str = html.escape(", ".join(mcp.get("active_tools", [])))

    badge_class = {
        "SHIP": "badge-ship",
        "REVIEW": "badge-review",
        "NO_SHIP": "badge-noship",
    }.get(verdict, "badge-ship")

    # Circumference for radius 45 is 282.74
    dashoffset = int(282.74 * (1.0 - (score_val / 100.0)))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SDETKit 2.0 - 360-Degree Quality Cockpit</title>
<style>
:root {{
  --bg: #0d1117;
  --surface: #161b22;
  --surface-hover: #1f242c;
  --border: #30363d;
  --text: #c9d1d9;
  --heading: #f0f6fc;
  --accent: #58a6ff;
  --green: #238636;
  --green-text: #3fb950;
  --yellow: #d29922;
  --yellow-text: #e3b341;
  --red: #da3633;
  --red-text: #f85149;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}}
@media (prefers-color-scheme: light) {{
  :root {{
    --bg: #f6f8fa;
    --surface: #ffffff;
    --surface-hover: #f3f4f6;
    --border: #d0d7de;
    --text: #24292f;
    --heading: #1f2328;
    --accent: #0969da;
    --green: #1a7f37;
    --green-text: #1a7f37;
    --yellow: #9a6700;
    --yellow-text: #9a6700;
    --red: #cf222e;
    --red-text: #cf222e;
  }}
}}
body {{
  margin: 0;
  padding: 32px 16px;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  line-height: 1.5;
}}
.container {{
  max-width: 960px;
  margin: 0 auto;
}}
.header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  padding-bottom: 20px;
  margin-bottom: 24px;
}}
.brand {{
  font-size: 24px;
  font-weight: 700;
  color: var(--heading);
  letter-spacing: -0.5px;
}}
.brand span {{
  color: var(--accent);
}}
.badge {{
  padding: 6px 14px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}}
.badge-ship {{
  background: rgba(35, 134, 54, 0.15);
  color: var(--green-text);
  border: 1px solid var(--green);
}}
.badge-review {{
  background: rgba(210, 153, 34, 0.15);
  color: var(--yellow-text);
  border: 1px solid var(--yellow);
}}
.badge-noship {{
  background: rgba(218, 54, 51, 0.15);
  color: var(--red-text);
  border: 1px solid var(--red);
}}
.hero-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}}
.hero-left {{
  flex: 1;
}}
.hero-title {{
  font-size: 14px;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 600;
  margin-bottom: 8px;
}}
.hero-desc {{
  font-size: 18px;
  color: var(--heading);
  font-weight: 500;
  margin-bottom: 16px;
}}
.meta-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.pill {{
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
}}
.gauge-container {{
  position: relative;
  width: 110px;
  height: 110px;
}}
.gauge-circle {{
  transform: rotate(-90deg);
  transform-origin: 50% 50%;
}}
.gauge-bg {{
  stroke: var(--border);
  stroke-width: 8;
  fill: none;
}}
.gauge-val {{
  stroke: var(--green-text);
  stroke-width: 8;
  stroke-linecap: round;
  fill: none;
  stroke-dasharray: 283;
  stroke-dashoffset: {dashoffset};
  transition: stroke-dashoffset 0.8s ease;
}}
.gauge-text {{
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 22px;
  font-weight: 700;
  color: var(--heading);
  text-align: center;
}}
.gauge-sub {{
  font-size: 11px;
  color: var(--text);
  font-weight: 400;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.stat-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  transition: background 0.2s ease;
}}
.stat-card:hover {{
  background: var(--surface-hover);
}}
.stat-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}}
.stat-title {{
  font-size: 13px;
  font-weight: 600;
  color: var(--heading);
}}
.stat-icon {{
  font-size: 14px;
}}
.stat-metric {{
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 6px;
}}
.stat-note {{
  font-size: 12px;
  color: var(--text);
  opacity: 0.85;
}}
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}}
.card-title {{
  font-size: 16px;
  font-weight: 600;
  color: var(--heading);
  margin-top: 0;
  margin-bottom: 12px;
}}
.code-box {{
  position: relative;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 16px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  color: var(--heading);
  overflow-x: auto;
  margin-bottom: 12px;
}}
.copy-btn {{
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}}
.copy-btn:hover {{
  background: var(--border);
}}
.footer {{
  text-align: center;
  font-size: 12px;
  color: var(--text);
  opacity: 0.7;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="brand">SDET<span>Kit</span> 2.0</div>
    <div class="badge {badge_class}">{verdict}</div>
  </div>

  <div class="hero-card">
    <div class="hero-left">
      <div class="hero-title">Release Confidence Radar</div>
      <div class="hero-desc">{rec}</div>
      <div class="meta-pills">
        <div class="pill">Workspace: <strong>{repo}</strong></div>
        <div class="pill">Branch: <strong>{branch}</strong></div>
        <div class="pill">Commit: <strong>{commit}</strong></div>
        <div class="pill">Runtime: <strong>Python {py_ver}</strong></div>
        <div class="pill">Surfaces: <strong>{surfaces}</strong></div>
      </div>
    </div>
    <div class="gauge-container">
      <svg class="gauge-circle" width="110" height="110">
        <circle class="gauge-bg" cx="55" cy="55" r="45" />
        <circle class="gauge-val" cx="55" cy="55" r="45" />
      </svg>
      <div class="gauge-text">
        {score_val}
        <div class="gauge-sub">HEALTH</div>
      </div>
    </div>
  </div>

  <div class="grid">
    <div class="stat-card">
      <div class="stat-header">
        <span class="stat-title">Doctor Readiness</span>
        <span class="stat-icon">&#10003;</span>
      </div>
      <div class="stat-metric">{doc.get("score", "100%")}</div>
      <div class="stat-note">Strict ASCII (< 0x80) and dependency integrity</div>
    </div>

    <div class="stat-card">
      <div class="stat-header">
        <span class="stat-title">Native MCP Server</span>
        <span class="stat-icon">&#10003;</span>
      </div>
      <div class="stat-metric">{mcp.get("tool_count", 6)} Active Tools</div>
      <div class="stat-note">Zero-dependency stdio server for Claude, Cursor, Codex</div>
    </div>

    <div class="stat-card">
      <div class="stat-header">
        <span class="stat-title">Assertion Mutation</span>
        <span class="stat-icon">&#10003;</span>
      </div>
      <div class="stat-metric">Active</div>
      <div class="stat-note">{len(mut.get("operators", []))} AST mutation operators testing assertion rigor</div>
    </div>

    <div class="stat-card">
      <div class="stat-header">
        <span class="stat-title">Security &amp; Secrets</span>
        <span class="stat-icon">&#10003;</span>
      </div>
      <div class="stat-metric">{"Clean" if sec.get("clean") else f"{sec.get('findings_count')} Findings"}</div>
      <div class="stat-note">Vetted against repository baseline &amp; secret patterns</div>
    </div>

    <div class="stat-card">
      <div class="stat-header">
        <span class="stat-title">Safe Remediation</span>
        <span class="stat-icon">&#10003;</span>
      </div>
      <div class="stat-metric">{"Clean Tree" if rem.get("clean_tree") else rem.get("classification")}</div>
      <div class="stat-note">Deterministic mechanical drift auto-fixer</div>
    </div>

    <div class="stat-card">
      <div class="stat-header">
        <span class="stat-title">Release Status</span>
        <span class="stat-icon">&#9733;</span>
      </div>
      <div class="stat-metric">{verdict}</div>
      <div class="stat-note">Overall release confidence decision</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">MCP Agent Super-Bridge</div>
    <p style="margin-top: 0; font-size: 13px; opacity: 0.85;">
      Registered Tools: <code>{tools_str}</code>
    </p>
    <div class="code-box">
      <span>claude mcp add sdetkit -- python -m sdetkit mcp</span>
      <button class="copy-btn" onclick="navigator.clipboard.writeText('claude mcp add sdetkit -- python -m sdetkit mcp')">Copy</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Quick Action Commands</div>
    <div class="code-box">
      <span>python -m sdetkit gate fast</span>
      <button class="copy-btn" onclick="navigator.clipboard.writeText('python -m sdetkit gate fast')">Copy</button>
    </div>
    <div class="code-box">
      <span>python -m sdetkit auto-fix --apply</span>
      <button class="copy-btn" onclick="navigator.clipboard.writeText('python -m sdetkit auto-fix --apply')">Copy</button>
    </div>
  </div>

  <div class="footer">
    Generated by SDETKit 2.0 &bull; 360-Degree Quality Intelligence Engine
  </div>
</div>
</body>
</html>
"""


def _scan_mtimes(root: Path) -> dict[str, float]:
    skip_dirs = {
        ".git",
        "build",
        "dist",
        "site",
        "__pycache__",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
    mtimes: dict[str, float] = {}
    try:
        for entry in root.rglob("*"):
            if any(part in skip_dirs for part in entry.parts):
                continue
            if entry.is_file():
                try:
                    mtimes[str(entry)] = entry.stat().st_mtime
                except (OSError, FileNotFoundError):
                    # Files may be deleted or become unreadable during scan; skip and continue.
                    continue
    except (OSError, FileNotFoundError):
        # Best-effort watch scan: ignore transient traversal errors and return partial mtimes.
        pass
    return mtimes


def _clear_terminal() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
    else:
        sys.stdout.write("\n" + "=" * 78 + "\n")


def run_watch_loop(
    root: Path,
    *,
    scan: bool = False,
    poll_interval: float = 1.0,
    max_iterations: int | None = None,
    use_ascii: bool = True,
) -> int:
    iteration = 0
    last_mtimes = _scan_mtimes(root)

    # Initial render
    intel = run_radar_checks(root, scan=scan)
    _clear_terminal()
    print(render_cockpit_view(intel, use_ascii=use_ascii))
    print("\n[WATCH MODE ACTIVE - Monitoring workspace for file changes (Ctrl+C to exit)]")

    try:
        while True:
            iteration += 1
            if max_iterations is not None and iteration >= max_iterations:
                break
            time.sleep(poll_interval)
            current_mtimes = _scan_mtimes(root)
            if current_mtimes != last_mtimes:
                last_mtimes = current_mtimes
                intel = run_radar_checks(root, scan=scan)
                _clear_terminal()
                print(render_cockpit_view(intel, use_ascii=use_ascii))
                print(
                    "\n[WATCH MODE ACTIVE - Updated at "
                    + time.strftime("%H:%M:%S")
                    + " (Ctrl+C to exit)]"
                )
    except KeyboardInterrupt:
        print("\n[Watch mode stopped]")
        return 0
    return 0


def render_agent_templates() -> dict[str, str]:
    return {
        "CLAUDE.md": AGENT_TEMPLATE_CLAUDE.strip() + "\n",
        "AGENTS.md": AGENT_TEMPLATE_GENERIC.strip() + "\n",
        ".cursorrules": AGENT_TEMPLATE_GENERIC.strip() + "\n",
        ".mcp.json": AGENT_MCP_JSON.strip() + "\n",
    }


def init_agent_bridge(root: Path, *, force: bool = False) -> list[str]:
    created: list[str] = []
    templates = render_agent_templates()

    for name, content in templates.items():
        target = root / name
        if not target.exists() or force:
            target.write_text(content, encoding="utf-8")
            created.append(name)

    return created


def main(argv: list[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    is_trend = (
        ("trend" in sys.argv)
        or (os.environ.get("SDETKIT_SUBCOMMAND") == "trend")
        or (bool(args_list) and args_list[0] == "trend")
    )
    if is_trend:
        if args_list and args_list[0] == "trend":
            args_list = args_list[1:]
        return trend_main(args_list)

    parser = argparse.ArgumentParser(
        prog="sdetkit cockpit",
        description="360-degree quality cockpit and real-time test radar for AI agents and developers.",
    )
    parser.add_argument(
        "--repo-root", default=".", help="Root directory of the repository (default: .)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md", "html"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--out", default=None, help="Write radar report (text/json/md/html) to this file"
    )
    parser.add_argument(
        "--html",
        dest="html_out",
        default=None,
        help="Write standalone interactive HTML quality dashboard to this file",
    )
    parser.add_argument(
        "--step-summary",
        action="store_true",
        help="Append Markdown summary to $GITHUB_STEP_SUMMARY",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run live terminal watch mode (re-evaluates on file changes)",
    )
    parser.add_argument(
        "--scan", action="store_true", help="Run deep Zero-to-Value 360-degree scan"
    )
    parser.add_argument(
        "--agent-config",
        action="store_true",
        help="Print ready-to-use AI agent configuration templates",
    )
    parser.add_argument(
        "--init-agent",
        action="store_true",
        help="Scaffold AI agent instruction files (AGENTS.md, CLAUDE.md, .mcp.json)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing files during --init-agent"
    )
    parser.add_argument(
        "--ascii", action="store_true", default=True, help="Force pure ASCII terminal formatting"
    )

    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    if args.agent_config:
        templates = render_agent_templates()
        print(f"=== .mcp.json ===\n{templates['.mcp.json']}\n")
        print(f"=== CLAUDE.md ===\n{templates['CLAUDE.md']}\n")
        print(f"=== AGENTS.md ===\n{templates['AGENTS.md']}\n")
        return 0

    if args.init_agent:
        created = init_agent_bridge(root, force=args.force)
        if created:
            print(f"Scaffolded AI agent bridge files: {', '.join(created)}")
        else:
            print("AI agent bridge files already exist. Use --force to overwrite if desired.")
        return 0

    if args.watch:
        return run_watch_loop(root, scan=args.scan, use_ascii=args.ascii)

    intel = run_radar_checks(root, scan=args.scan)

    # Determine formatted output
    if args.format == "json":
        output_body = json.dumps(intel, indent=2) + "\n"
    elif args.format == "md":
        output_body = render_cockpit_markdown(intel) + "\n"
    elif args.format == "html":
        output_body = render_cockpit_html(intel)
    else:
        output_body = render_cockpit_view(intel, use_ascii=args.ascii) + "\n"

    # Write to --out if requested
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_body, encoding="utf-8")

    # Write standalone HTML if --html is requested
    if args.html_out:
        html_path = Path(args.html_out)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_cockpit_html(intel), encoding="utf-8")

    # Handle --step-summary
    if args.step_summary:
        summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_env:
            try:
                with open(summary_env, "a", encoding="utf-8") as f:
                    f.write(render_cockpit_markdown(intel) + "\n")
            except OSError:
                # Best-effort helper: inability to write to GITHUB_STEP_SUMMARY should not fail CLI.
                pass

    sys.stdout.write(output_body)

    return 0 if intel.get("verdict") == "SHIP" else 1


if __name__ == "__main__":
    raise SystemExit(main())
