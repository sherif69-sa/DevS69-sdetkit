"""`sdetkit verify flake` and `sdetkit quarantine`: hunt flaky tests and manage quarantine."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sdetkit.gates.project_env import resolve_project_python

JsonObject = dict[str, Any]

DEFAULT_FLAKE_RUNS = 5
DEFAULT_PER_RUN_TIMEOUT = 60

# Regex patterns to detect failure causes and test ids from pytest output
_FAILED_TEST_RE = re.compile(r"FAILED\s+([^\s:]+(?:::[^\s:]+)+)")
_ERROR_TEST_RE = re.compile(r"ERROR\s+([^\s:]+(?:::[^\s:]+)+)")

_RACE_KEYWORDS = (
    "timeout",
    "timed out",
    "deadline",
    "asyncio.exceptions.timeouterror",
    "timeouterror",
    "wait",
    "event not set",
)
_STATE_KEYWORDS = (
    "already exists",
    "duplicate",
    "address in use",
    "fileexistserror",
    "mock not called",
    "singleton",
    "fixture",
)

QUARANTINE_SCHEMA_VERSION = "sdetkit.quarantine.v1"
DEFAULT_QUARANTINE_FILE = ".sdetkit/quarantine.json"
DEFAULT_QUARANTINE_TTL_DAYS = 7


def _classify_cause(output: str) -> str:
    lower = output.lower()
    if any(k in lower for k in _RACE_KEYWORDS):
        return "TIMING_RACE"
    if any(k in lower for k in _STATE_KEYWORDS):
        return "STATE_POLLUTION"
    return "UNKNOWN"


def _extract_failures(stdout: str, stderr: str) -> list[str]:
    combined = f"{stdout}\n{stderr}"
    found: list[str] = []
    for match in _FAILED_TEST_RE.finditer(combined):
        test_id = match.group(1).strip()
        if test_id not in found:
            found.append(test_id)
    for match in _ERROR_TEST_RE.finditer(combined):
        test_id = match.group(1).strip()
        if test_id not in found:
            found.append(test_id)
    return found


def _compute_stats(durations: list[float]) -> dict[str, float]:
    if not durations:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "stddev": 0.0}
    n = len(durations)
    mean_val = sum(durations) / n
    variance = sum((x - mean_val) ** 2 for x in durations) / n if n > 1 else 0.0
    return {
        "min": round(min(durations), 4),
        "max": round(max(durations), 4),
        "mean": round(mean_val, 4),
        "stddev": round(math.sqrt(variance), 4),
    }


def _run_single_test_iteration(
    executable: str,
    args: list[str],
    *,
    cwd: Path,
    timeout: int,
    env_overrides: Mapping[str, str] | None = None,
) -> tuple[bool, float, str, str]:
    env = {
        k: v for k, v in os.environ.items() if k not in ("PYTEST_ADDOPTS", "PYTEST_XDIST_WORKER")
    }
    if env_overrides:
        env.update(env_overrides)

    cmd = [executable, "-m", "pytest", "-o", "addopts=", "-q", "--tb=short", *args]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        duration = time.monotonic() - t0
        return proc.returncode == 0, duration, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return False, duration, "", "test execution timed out"
    except OSError as err:
        duration = time.monotonic() - t0
        return False, duration, "", f"execution error: {err}"


def hunt_flakes(
    root: Path,
    target: str | Path | None = None,
    *,
    runs: int = DEFAULT_FLAKE_RUNS,
    shuffle: bool = True,
    seed: int | None = None,
    timeout: int = DEFAULT_PER_RUN_TIMEOUT,
    max_seconds: float | None = None,
    fail_fast: bool = False,
    extra_args: Sequence[str] = (),
) -> JsonObject:
    """Stress-test test targets over multiple iterations to detect and prove non-determinism."""

    target_args: list[str] = []
    if target:
        target_str = str(target)
        target_args.append(target_str)
    if extra_args:
        target_args.extend(extra_args)

    env = resolve_project_python(root)
    total_runs = max(2, min(runs, 100))
    rng = random.Random(seed if seed is not None else 42)

    durations: list[float] = []
    run_records: list[JsonObject] = []
    all_failing_tests: set[str] = set()
    start_time = time.monotonic()

    passed_count = 0
    failed_count = 0

    for iteration in range(1, total_runs + 1):
        if max_seconds is not None and (time.monotonic() - start_time) > max_seconds:
            break

        current_seed = rng.randint(1, 1_000_000) if shuffle else (seed or 0)
        iter_env = {"PYTHONHASHSEED": str(current_seed)}

        passed, duration, out, err = _run_single_test_iteration(
            env.executable,
            target_args,
            cwd=root,
            timeout=timeout,
            env_overrides=iter_env,
        )
        durations.append(duration)

        failed_tests = _extract_failures(out, err)
        record: JsonObject = {
            "run": iteration,
            "passed": passed,
            "duration": round(duration, 4),
            "seed": current_seed,
            "failed_tests": failed_tests,
        }

        if passed:
            passed_count += 1
        else:
            failed_count += 1
            cause = _classify_cause(f"{out}\n{err}")
            record["cause"] = cause
            record["error_snippet"] = (err.strip() or out.strip())[-500:]
            all_failing_tests.update(failed_tests)

        run_records.append(record)

        if fail_fast and failed_count > 0 and passed_count > 0:
            break

    completed = len(run_records)
    if completed == 0:
        return {
            "ok": True,
            "verdict": "not_run",
            "reason": "no runs completed within time limit",
            "runs_planned": total_runs,
            "runs_completed": 0,
            "passed_runs": 0,
            "failed_runs": 0,
            "flake_rate": 0.0,
            "duration_stats": _compute_stats([]),
            "flaky_tests": [],
            "failures": [],
            "reasons": ["no runs completed"],
        }

    # If it failed some runs and passed other runs: PROVEN FLAKY!
    if passed_count > 0 and failed_count > 0:
        verdict = "flaky"
        ok = False
        flaky_tests = sorted(all_failing_tests) or [str(target or "test suite")]
        flake_rate = round((failed_count / completed) * 100.0, 1)
        reasons = [
            f"test non-determinism proven: {failed_count}/{completed} runs failed ({flake_rate}% flake rate)"
        ]
    elif failed_count == completed:
        verdict = "broken"
        ok = False
        flaky_tests = []
        flake_rate = 100.0
        reasons = [f"test consistently broken: failed all {completed} runs"]
    else:
        verdict = "deterministic"
        ok = True
        flaky_tests = []
        flake_rate = 0.0
        reasons = [f"deterministic: passed all {completed} runs"]

    return {
        "ok": ok,
        "verdict": verdict,
        "target": str(target) if target else "all",
        "runs_planned": total_runs,
        "runs_completed": completed,
        "passed_runs": passed_count,
        "failed_runs": failed_count,
        "flake_rate": flake_rate,
        "duration_stats": _compute_stats(durations),
        "flaky_tests": flaky_tests,
        "failures": [r for r in run_records if not r.get("passed", True)],
        "runs": run_records,
        "reasons": reasons,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    verdict = payload.get("verdict", "unknown")
    completed = payload.get("runs_completed", 0)
    passed = payload.get("passed_runs", 0)
    failed = payload.get("failed_runs", 0)
    rate = payload.get("flake_rate", 0.0)
    stats = payload.get("duration_stats", {})
    target = payload.get("target", "all")

    if verdict == "deterministic":
        badge = "DETERMINISTIC PASS"
        symbol = "[OK]"
    elif verdict == "flaky":
        badge = "FLAKY (PROVEN NON-DETERMINISTIC)"
        symbol = "[FLAKE]"
    elif verdict == "broken":
        badge = "BROKEN (100% FAILURE)"
        symbol = "[FAIL]"
    else:
        badge = "NOT RUN"
        symbol = "[SKIP]"

    lines: list[str] = [
        f"### {symbol} Flake Hunter: {badge}",
        "",
        f"- **Target:** `{target}`",
        f"- **Completed Runs:** {completed} ({passed} passed, {failed} failed)",
        f"- **Flake Rate:** {rate}%",
        f"- **Duration:** min={stats.get('min', 0)}s, max={stats.get('max', 0)}s, mean={stats.get('mean', 0)}s, stddev={stats.get('stddev', 0)}s",
        "",
    ]

    flaky_tests = payload.get("flaky_tests", [])
    if flaky_tests:
        lines.append("#### Flaky Tests Detected")
        for test in flaky_tests:
            lines.append(f"- ` {test} `")
        lines.append("")

    failures = payload.get("failures", [])
    if failures:
        lines.append("#### Failure Log Details")
        for failure in failures[:5]:
            run_no = failure.get("run")
            cause = failure.get("cause", "UNKNOWN")
            snippet = failure.get("error_snippet", "").strip()
            lines.append(f"- **Run #{run_no}** (cause: `{cause}`):")
            if snippet:
                lines.append(f"  ```text\n  {snippet[:200]}\n  ```")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


# =============================================================================
# Automated Test Quarantine & Flake Graduation Matrix Engine
# =============================================================================


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _calculate_expires_at(ttl_days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=ttl_days)).isoformat()


def _is_expired(expires_at: str) -> bool:
    try:
        clean = expires_at.replace("Z", "+00:00")
        exp = datetime.fromisoformat(clean)
        return datetime.now(UTC) > exp
    except (ValueError, TypeError):
        return False


def _days_remaining(expires_at: str) -> float:
    try:
        clean = expires_at.replace("Z", "+00:00")
        exp = datetime.fromisoformat(clean)
        delta = exp - datetime.now(UTC)
        return round(max(0.0, delta.total_seconds() / 86400.0), 1)
    except (ValueError, TypeError):
        return 0.0


def _resolve_manifest_path(root: Path, manifest_path: Path | str | None = None) -> Path:
    if manifest_path is not None:
        p = Path(manifest_path)
        return p if p.is_absolute() else (root / p)
    return root / DEFAULT_QUARANTINE_FILE


def load_quarantine(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        return {
            "schema_version": QUARANTINE_SCHEMA_VERSION,
            "updated_at": _iso_now(),
            "records": {},
        }
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {
                "schema_version": QUARANTINE_SCHEMA_VERSION,
                "updated_at": _iso_now(),
                "records": {},
            }
        data.setdefault("records", {})
        data.setdefault("schema_version", QUARANTINE_SCHEMA_VERSION)
        return data
    except (json.JSONDecodeError, OSError):
        return {
            "schema_version": QUARANTINE_SCHEMA_VERSION,
            "updated_at": _iso_now(),
            "records": {},
        }


def save_quarantine(manifest_path: Path, data: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _iso_now()
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_to_quarantine(
    root: Path,
    test_id: str,
    *,
    reason: str = "",
    ttl_days: int = DEFAULT_QUARANTINE_TTL_DAYS,
    owner: str = "",
    issue_url: str = "",
    classification: str = "UNKNOWN",
    manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    target_manifest = _resolve_manifest_path(root, manifest_path)
    data = load_quarantine(target_manifest)
    records: dict[str, Any] = data.setdefault("records", {})

    clean_id = test_id.strip()
    file_part = clean_id.split("::")[0].replace("\\", "/")

    # Check test existence on disk
    file_exists = (root / file_part).is_file()
    now_iso = _iso_now()
    expires_iso = _calculate_expires_at(ttl_days)

    entry = {
        "test_id": clean_id,
        "reason": reason or "Flaky test isolated from blocking build",
        "classification": classification,
        "owner": owner or "unassigned",
        "issue_url": issue_url or "",
        "created_at": now_iso,
        "expires_at": expires_iso,
        "ttl_days": ttl_days,
        "status": "active",
        "file_exists": file_exists,
        "history": [
            {
                "timestamp": now_iso,
                "action": "quarantined",
                "reason": reason,
                "owner": owner,
            }
        ],
    }

    records[clean_id] = entry
    save_quarantine(target_manifest, data)

    return {
        "ok": True,
        "action": "add",
        "test_id": clean_id,
        "status": "active",
        "expires_at": expires_iso,
        "ttl_days": ttl_days,
        "file_exists": file_exists,
        "manifest_path": str(target_manifest),
    }


def list_quarantine(
    root: Path,
    *,
    manifest_path: Path | str | None = None,
    status_filter: str | None = None,
) -> dict[str, Any]:
    target_manifest = _resolve_manifest_path(root, manifest_path)
    data = load_quarantine(target_manifest)
    records: dict[str, Any] = data.get("records", {})

    active_records = []
    expired_records = []
    graduated_records = []

    for _, entry in sorted(records.items()):
        current_status = entry.get("status", "active")
        exp_at = entry.get("expires_at", "")
        if current_status == "active" and _is_expired(exp_at):
            current_status = "expired"

        entry_copy = dict(entry)
        entry_copy["status"] = current_status
        entry_copy["days_remaining"] = (
            _days_remaining(exp_at) if current_status == "active" else 0.0
        )

        if current_status == "active":
            active_records.append(entry_copy)
        elif current_status == "expired":
            expired_records.append(entry_copy)
        elif current_status == "graduated":
            graduated_records.append(entry_copy)

    all_list = active_records + expired_records + graduated_records
    if status_filter:
        flt = status_filter.lower().strip()
        all_list = [r for r in all_list if r.get("status") == flt]

    return {
        "schema_version": QUARANTINE_SCHEMA_VERSION,
        "manifest_path": str(target_manifest),
        "total_count": len(records),
        "active_count": len(active_records),
        "expired_count": len(expired_records),
        "graduated_count": len(graduated_records),
        "records": all_list,
    }


def audit_quarantine(
    root: Path,
    *,
    manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    target_manifest = _resolve_manifest_path(root, manifest_path)
    data = load_quarantine(target_manifest)
    records: dict[str, Any] = data.get("records", {})

    active_count = 0
    expired_tests: list[str] = []
    zombie_tests: list[str] = []
    healthy_tests: list[str] = []

    for test_id, entry in sorted(records.items()):
        current_status = entry.get("status", "active")
        if current_status != "active":
            continue

        active_count += 1
        exp_at = entry.get("expires_at", "")
        if _is_expired(exp_at):
            expired_tests.append(test_id)

        file_part = test_id.split("::")[0].replace("\\", "/")
        file_path = root / file_part
        if not file_path.is_file():
            zombie_tests.append(test_id)
        elif "::" in test_id:
            symbol = test_id.split("::")[-1]
            clean_symbol = symbol.split("[")[0].strip()
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                if clean_symbol not in content:
                    zombie_tests.append(test_id)
            except OSError:
                zombie_tests.append(test_id)

        if test_id not in expired_tests and test_id not in zombie_tests:
            healthy_tests.append(test_id)

    # Health score: 100 - (15 * expired) - (20 * zombie)
    score = 100 - (15 * len(expired_tests)) - (20 * len(zombie_tests))
    health_score = max(0, min(100, score))

    verdict = "HEALTHY"
    if health_score < 60:
        verdict = "DEGRADED"
    elif health_score < 90:
        verdict = "ATTENTION_NEEDED"

    recommendations: list[str] = []
    if expired_tests:
        recommendations.append(
            f"{len(expired_tests)} test(s) have expired TTLs. Review, graduate, or renew their quarantine."
        )
    if zombie_tests:
        recommendations.append(
            f"{len(zombie_tests)} quarantined test(s) no longer exist in repository files (zombies). Clean up manifest."
        )
    if not expired_tests and not zombie_tests:
        recommendations.append(
            "Quarantine manifest is healthy. All active quarantines are within TTL limits."
        )

    return {
        "schema_version": QUARANTINE_SCHEMA_VERSION,
        "manifest_path": str(target_manifest),
        "health_score": health_score,
        "verdict": verdict,
        "active_quarantined_count": active_count,
        "expired_count": len(expired_tests),
        "expired_tests": expired_tests,
        "zombie_count": len(zombie_tests),
        "zombie_tests": zombie_tests,
        "healthy_count": len(healthy_tests),
        "healthy_tests": healthy_tests,
        "recommendations": recommendations,
    }


def filter_quarantine(
    root: Path,
    *,
    manifest_path: Path | str | None = None,
    mode: str = "k",
) -> dict[str, Any]:
    target_manifest = _resolve_manifest_path(root, manifest_path)
    data = load_quarantine(target_manifest)
    records: dict[str, Any] = data.get("records", {})

    active_ids = [
        test_id
        for test_id, entry in records.items()
        if entry.get("status") == "active" and not _is_expired(entry.get("expires_at", ""))
    ]

    if not active_ids:
        return {
            "schema_version": QUARANTINE_SCHEMA_VERSION,
            "active_count": 0,
            "active_tests": [],
            "pytest_args": "",
            "mode": mode,
        }

    if mode == "ignore":
        files = sorted({tid.split("::")[0].replace("\\", "/") for tid in active_ids})
        pytest_args = " ".join(f"--ignore={f}" for f in files)
    else:
        # Default -k filter: exclude function names
        tokens = []
        for tid in sorted(active_ids):
            func_name = tid.split("::")[-1]
            clean_func = func_name.split("[")[0].strip()
            if clean_func and clean_func not in tokens:
                tokens.append(clean_func)
        expr = " and ".join(f"not {t}" for t in tokens)
        pytest_args = f'-k "{expr}"' if expr else ""

    return {
        "schema_version": QUARANTINE_SCHEMA_VERSION,
        "active_count": len(active_ids),
        "active_tests": sorted(active_ids),
        "pytest_args": pytest_args,
        "mode": mode,
    }


def shadow_run_quarantine(
    root: Path,
    *,
    manifest_path: Path | str | None = None,
    timeout: int = 180,
    extra_args: Sequence[str] | None = None,
) -> dict[str, Any]:
    filter_res = filter_quarantine(root, manifest_path=manifest_path)
    active_tests = filter_res.get("active_tests") or []

    if not active_tests:
        return {
            "ok": True,
            "executed": False,
            "active_count": 0,
            "message": "No active quarantined tests to shadow-run.",
            "returncode": 0,
        }

    env = resolve_project_python(root)
    cmd = [
        env.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        *(list(extra_args) if extra_args else []),
        *active_tests,
    ]

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        duration = round(time.monotonic() - t0, 3)
        return {
            "ok": True,  # Shadow mode always passes overall to not block CI
            "executed": True,
            "test_returncode": proc.returncode,
            "test_passed": proc.returncode == 0,
            "duration_seconds": duration,
            "tests_run_count": len(active_tests),
            "command": " ".join(cmd),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "message": (
                f"Shadow run executed {len(active_tests)} quarantined test(s) in {duration}s "
                f"(test_rc={proc.returncode}). CI is not blocked."
            ),
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {
            "ok": True,
            "executed": False,
            "error": str(exc),
            "message": f"Shadow run encountered an error: {exc}. Non-blocking.",
        }


def graduate_test(
    root: Path,
    test_id: str,
    *,
    runs: int = 10,
    manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    target_manifest = _resolve_manifest_path(root, manifest_path)
    data = load_quarantine(target_manifest)
    records: dict[str, Any] = data.get("records", {})

    clean_id = test_id.strip()
    if clean_id not in records:
        return {
            "ok": False,
            "graduated": False,
            "error": f"Test '{clean_id}' is not present in quarantine manifest.",
            "test_id": clean_id,
        }

    flake_result = hunt_flakes(
        root=root,
        target=clean_id,
        runs=runs,
        shuffle=True,
        fail_fast=True,
    )

    passed_all = (
        flake_result.get("flake_rate", 100.0) == 0.0
        and flake_result.get("passed_runs", 0) == flake_result.get("runs_completed", 0)
        and flake_result.get("runs_completed", 0) >= runs
    )

    now_iso = _iso_now()
    if passed_all:
        records[clean_id]["status"] = "graduated"
        records[clean_id]["graduated_at"] = now_iso
        records[clean_id].setdefault("history", []).append(
            {
                "timestamp": now_iso,
                "action": "graduated",
                "runs_verified": runs,
                "flake_rate": 0.0,
            }
        )
        save_quarantine(target_manifest, data)
        return {
            "ok": True,
            "graduated": True,
            "test_id": clean_id,
            "runs_verified": runs,
            "message": (
                f"SUCCESS: Test '{clean_id}' passed {runs}/{runs} iterations "
                f"and is GRADUATED from quarantine!"
            ),
            "details": flake_result,
        }
    else:
        return {
            "ok": True,
            "graduated": False,
            "test_id": clean_id,
            "runs_verified": runs,
            "runs_passed": flake_result.get("passed_runs", 0),
            "runs_failed": flake_result.get("failed_runs", 0),
            "flake_rate": flake_result.get("flake_rate", 100.0),
            "message": (
                f"FAILED: Test '{clean_id}' failed graduation check "
                f"({flake_result.get('failed_runs', 0)} failed). Test remains quarantined."
            ),
            "details": flake_result,
        }


def render_quarantine_list_markdown(payload: dict[str, Any]) -> str:
    total = payload.get("total_count", 0)
    active = payload.get("active_count", 0)
    expired = payload.get("expired_count", 0)
    graduated = payload.get("graduated_count", 0)
    records = payload.get("records", [])

    lines = [
        "### SDETKit Test Quarantine Manifest",
        "",
        f"- **Active Quarantined**: `{active}`",
        f"- **Expired (Action Needed)**: `{expired}`",
        f"- **Graduated**: `{graduated}`",
        f"- **Total**: `{total}`",
        "",
    ]
    if records:
        lines.append("| Status | Test ID | Remaining | Owner | Reason |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for r in records:
            st = str(r.get("status", "active")).upper()
            tid = r.get("test_id", "")
            rem = f"{r.get('days_remaining', 0.0)}d" if st == "ACTIVE" else "-"
            own = r.get("owner", "unassigned")
            rsn = r.get("reason", "")
            lines.append(f"| `{st}` | `{tid}` | {rem} | `{own}` | {rsn} |")
    else:
        lines.append("_No quarantined tests found in manifest._")
    return "\n".join(lines).strip() + "\n"


def render_quarantine_audit_markdown(payload: dict[str, Any]) -> str:
    score = payload.get("health_score", 100)
    verdict = payload.get("verdict", "HEALTHY")
    lines = [
        f"### SDETKit Quarantine Audit: {verdict} ({score}/100)",
        "",
        f"- **Active Quarantined**: `{payload.get('active_quarantined_count', 0)}`",
        f"- **Expired TTLs**: `{payload.get('expired_count', 0)}`",
        f"- **Zombie Tests**: `{payload.get('zombie_count', 0)}`",
        f"- **Healthy Active**: `{payload.get('healthy_count', 0)}`",
        "",
    ]
    recs = payload.get("recommendations", [])
    if recs:
        lines.append("**Recommendations**:")
        for r in recs:
            lines.append(f"- {r}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def quarantine_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit quarantine",
        description="Manage test quarantine, TTL expirations, shadow test runs, and flake graduation.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=False)

    # add
    p_add = sub.add_parser("add", help="Add a test to quarantine")
    p_add.add_argument("test_id", help="Test ID (e.g. tests/test_api.py::test_case)")
    p_add.add_argument("--reason", default="", help="Reason for quarantining")
    p_add.add_argument("--ttl", type=int, default=DEFAULT_QUARANTINE_TTL_DAYS, help="TTL in days")
    p_add.add_argument("--owner", default="", help="Responsible engineer / team handle")
    p_add.add_argument("--issue", default="", help="Tracking issue URL")
    p_add.add_argument("--classification", default="UNKNOWN", help="Failure cause classification")
    p_add.add_argument("--manifest", default=None, help="Custom quarantine manifest path")
    p_add.add_argument("--repo-root", default=".", help="Repository root directory")

    # list
    p_list = sub.add_parser("list", help="List quarantined tests")
    p_list.add_argument("--manifest", default=None, help="Custom quarantine manifest path")
    p_list.add_argument("--repo-root", default=".", help="Repository root directory")
    p_list.add_argument("--status", default=None, choices=["active", "expired", "graduated"])
    p_list.add_argument("--format", default="text", choices=["text", "json", "md"])

    # audit
    p_audit = sub.add_parser(
        "audit", help="Audit quarantine manifest health and flag expired/zombies"
    )
    p_audit.add_argument("--manifest", default=None, help="Custom quarantine manifest path")
    p_audit.add_argument("--repo-root", default=".", help="Repository root directory")
    p_audit.add_argument("--format", default="text", choices=["text", "json", "md"])

    # filter
    p_filter = sub.add_parser("filter", help="Emit pytest exclusion argument string")
    p_filter.add_argument("--manifest", default=None, help="Custom quarantine manifest path")
    p_filter.add_argument("--repo-root", default=".", help="Repository root directory")
    p_filter.add_argument("--mode", default="k", choices=["k", "ignore"])

    # shadow-run
    p_shadow = sub.add_parser("shadow-run", help="Run quarantined tests in advisory shadow mode")
    p_shadow.add_argument("--manifest", default=None, help="Custom quarantine manifest path")
    p_shadow.add_argument("--repo-root", default=".", help="Repository root directory")
    p_shadow.add_argument("--timeout", type=int, default=180, help="Per-run timeout in seconds")
    p_shadow.add_argument("--format", default="text", choices=["text", "json", "md"])

    # graduate
    p_grad = sub.add_parser(
        "graduate", help="Re-verify stability and graduate test from quarantine"
    )
    p_grad.add_argument("test_id", help="Test ID to graduate")
    p_grad.add_argument("--runs", type=int, default=10, help="Number of verification iterations")
    p_grad.add_argument("--manifest", default=None, help="Custom quarantine manifest path")
    p_grad.add_argument("--repo-root", default=".", help="Repository root directory")
    p_grad.add_argument("--format", default="text", choices=["text", "json", "md"])

    args = parser.parse_args(argv)
    if not args.subcommand:
        parser.print_help()
        return 0
    root = Path(args.repo_root).resolve()

    if args.subcommand == "add":
        res = add_to_quarantine(
            root,
            args.test_id,
            reason=args.reason,
            ttl_days=args.ttl,
            owner=args.owner,
            issue_url=args.issue,
            classification=args.classification,
            manifest_path=args.manifest,
        )
        print(f"Quarantined {args.test_id} (TTL: {args.ttl}d, expires: {res['expires_at']})")
        return 0

    if args.subcommand == "list":
        res = list_quarantine(root, manifest_path=args.manifest, status_filter=args.status)
        if args.format == "json":
            print(json.dumps(res, indent=2))
        else:
            print(render_quarantine_list_markdown(res))
        return 0

    if args.subcommand in ("audit", "check"):
        res = audit_quarantine(root, manifest_path=args.manifest)
        if args.format == "json":
            print(json.dumps(res, indent=2))
        else:
            print(render_quarantine_audit_markdown(res))
        return 0 if res.get("health_score", 100) >= 60 else 1

    if args.subcommand == "filter":
        res = filter_quarantine(root, manifest_path=args.manifest, mode=args.mode)
        args_str = res.get("pytest_args", "")
        if args_str:
            print(args_str)
        return 0

    if args.subcommand in ("shadow-run", "shadow_run"):
        res = shadow_run_quarantine(root, manifest_path=args.manifest, timeout=args.timeout)
        if args.format == "json":
            print(json.dumps(res, indent=2))
        else:
            print(res.get("message", "Shadow run completed."))
        return 0

    if args.subcommand == "graduate":
        res = graduate_test(root, args.test_id, runs=args.runs, manifest_path=args.manifest)
        if args.format == "json":
            print(json.dumps(res, indent=2))
        else:
            print(res.get("message", ""))
        return 0 if res.get("graduated", False) else 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    if args_list and args_list[0] == "quarantine":
        args_list = args_list[1:]
        return quarantine_main(args_list)
    if "quarantine" in sys.argv:
        return quarantine_main(args_list)
    if args_list and args_list[0] in {
        "add",
        "list",
        "audit",
        "check",
        "filter",
        "shadow-run",
        "shadow_run",
        "graduate",
    }:
        return quarantine_main(args_list)

    parser = argparse.ArgumentParser(
        prog="sdetkit verify flake",
        description="Hunt flaky tests, prove test non-determinism, and measure duration variance.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target test path or test id (e.g. tests/test_api.py::test_case)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_FLAKE_RUNS,
        help=f"Number of test iterations to execute (default: {DEFAULT_FLAKE_RUNS})",
    )
    parser.add_argument(
        "--no-shuffle",
        action="store_true",
        help="Disable execution order / hash seed randomization",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Fixed seed for reproducible test shuffling",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_PER_RUN_TIMEOUT,
        help=f"Per-run timeout in seconds (default: {DEFAULT_PER_RUN_TIMEOUT})",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Maximum total runtime budget in seconds",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first non-deterministic pass/fail split",
    )
    parser.add_argument(
        "--format",
        choices=["md", "json", "text"],
        default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Write JSON payload to a file",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Extra arguments passed to test runner",
    )

    args = parser.parse_args(args_list)
    root = Path(args.repo_root).resolve()

    payload = hunt_flakes(
        root=root,
        target=args.target,
        runs=args.runs,
        shuffle=not args.no_shuffle,
        seed=args.seed,
        timeout=args.timeout,
        max_seconds=args.max_seconds,
        fail_fast=args.fail_fast,
        extra_args=args.extra_args,
    )

    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    elif args.format == "text":
        verdict = payload.get("verdict", "unknown")
        rate = payload.get("flake_rate", 0.0)
        print(f"verdict={verdict} flake_rate={rate}% runs={payload.get('runs_completed')}")
    else:
        print(render_markdown(payload))

    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
