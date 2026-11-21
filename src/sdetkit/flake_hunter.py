"""`sdetkit verify flake` and `sdetkit quarantine`: hunt flaky tests and manage quarantine."""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import uuid
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

    replay_cap_rel: str | None = None
    replay_cmd: str | None = None
    if failed_count > 0:
        try:
            failed_run = next((r for r in run_records if not r.get("passed", True)), None)
            failing_node = (
                (failed_run.get("failed_tests") or [str(target or "all")])[0]
                if failed_run
                else str(target or "all")
            )
            failing_seed = int(failed_run.get("seed", 42)) if failed_run else 42
            resolved_root = root.resolve()
            cap_p = create_replay_capsule(
                resolved_root,
                node_id=failing_node,
                prng_seed=failing_seed,
            )
            replay_cap_rel = str(cap_p.relative_to(resolved_root)).replace("\\", "/")
            replay_cmd = f"sdetkit replay {replay_cap_rel}"
        except Exception as exc:
            # Fallback if capsule generation fails; record none and continue reporting flake metrics
            replay_cap_rel = None
            replay_cmd = f"sdetkit hunt (capsule unavailable: {exc})"

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
        "replay_capsule": replay_cap_rel,
        "replay_cmd": replay_cmd,
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


# =============================================================================
# Chaos Resilience & Flakiness Injection Engine
# =============================================================================

CHAOS_SCHEMA_VERSION = "sdetkit.chaos.v1"
CHAOS_PROFILES = ("latency", "race", "memory", "transient_error", "combined")

_CHAOS_SITECUSTOMIZE_TEMPLATE = """\
# SDETKit Chaos Injection Hook (Runtime Interceptor)
import os
import random
import sys
import time

try:
    _interval_us = int(os.environ.get("SDETKIT_CHAOS_SWITCH_INTERVAL_US", "0"))
    if _interval_us > 0:
        sys.setswitchinterval(_interval_us / 1000000.0)
except (AttributeError, ValueError):
    pass

try:
    _memory_mb = int(os.environ.get("SDETKIT_CHAOS_MEMORY_MB", "0"))
    if _memory_mb > 0:
        _sdetkit_chaos_mem_guard = bytearray(_memory_mb * 1024 * 1024)
except (MemoryError, OverflowError, ValueError):
    pass

try:
    _latency_ms = int(os.environ.get("SDETKIT_CHAOS_LATENCY_MS", "0"))
    _jitter_ms = int(os.environ.get("SDETKIT_CHAOS_JITTER_MS", "0"))
    if _latency_ms > 0:
        _orig_sleep = time.sleep
        def _chaos_sleep(seconds):
            _extra = (_latency_ms + random.uniform(-_jitter_ms, _jitter_ms)) / 1000.0
            if _extra > 0:
                _orig_sleep(_extra)
            _orig_sleep(seconds)
        time.sleep = _chaos_sleep
except (AttributeError, ValueError):
    pass

try:
    _fault_rate = float(os.environ.get("SDETKIT_CHAOS_FAULT_RATE", "0.0"))
    _latency_ms = int(os.environ.get("SDETKIT_CHAOS_LATENCY_MS", "0"))
    _jitter_ms = int(os.environ.get("SDETKIT_CHAOS_JITTER_MS", "0"))
    if _fault_rate > 0.0 or _latency_ms > 0:
        import socket
        _orig_connect = socket.socket.connect
        def _chaos_connect(self, address):
            if _fault_rate > 0.0 and random.random() < _fault_rate:
                raise ConnectionResetError("SDETKit Chaos: injected socket reset")
            if _latency_ms > 0:
                _extra = (_latency_ms + random.uniform(-_jitter_ms, _jitter_ms)) / 1000.0
                if _extra > 0:
                    time.sleep(_extra)
            return _orig_connect(self, address)
        socket.socket.connect = _chaos_connect
except (ImportError, AttributeError, ValueError):
    pass
"""


def _run_command_iteration(
    cmd: Sequence[str],
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
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        dur = time.monotonic() - t0
        return proc.returncode == 0, dur, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        dur = time.monotonic() - t0
        return False, dur, "", "command execution timed out"
    except OSError as err:
        dur = time.monotonic() - t0
        return False, dur, "", f"execution error: {err}"


def inject_chaos(
    root: Path,
    target: str | Path | None = None,
    *,
    profile: str = "combined",
    latency_ms: int = 50,
    jitter_ms: int = 25,
    switch_interval_us: int = 10,
    memory_mb: int = 0,
    fault_rate: float = 0.0,
    runs: int = 3,
    timeout: int = 120,
    command: Sequence[str] | None = None,
) -> JsonObject:
    """Stress-test test execution resilience under injected runtime chaos."""
    resolved_root = root.resolve()
    env = resolve_project_python(resolved_root)
    total_runs = max(1, min(runs, 50))
    target_args: list[str] = [str(target)] if target else []

    norm_profile = profile.strip().lower()
    if norm_profile not in CHAOS_PROFILES:
        norm_profile = "combined"

    active_latency = latency_ms if norm_profile in ("latency", "combined") else 0
    active_jitter = jitter_ms if active_latency > 0 else 0
    active_interval = switch_interval_us if norm_profile in ("race", "combined") else 0
    active_mem = memory_mb if norm_profile in ("memory", "combined") else 0
    active_fault = fault_rate if norm_profile in ("transient_error", "combined") else 0.0

    # 1. Baseline run without chaos
    if command:
        base_passed, base_dur, base_out, base_err = _run_command_iteration(
            command, cwd=resolved_root, timeout=timeout, env_overrides={}
        )
    else:
        base_passed, base_dur, base_out, base_err = _run_single_test_iteration(
            env.executable,
            target_args,
            cwd=resolved_root,
            timeout=timeout,
            env_overrides={},
        )

    # 2. Chaos runs with sitecustomize hook
    durations: list[float] = []
    run_records: list[JsonObject] = []
    passed_count = 0
    failed_count = 0
    detected_failure_modes: list[str] = []

    with tempfile.TemporaryDirectory(prefix="sdetkit_chaos_") as chaos_dir:
        hook_path = Path(chaos_dir) / "sitecustomize.py"
        hook_path.write_text(_CHAOS_SITECUSTOMIZE_TEMPLATE, encoding="utf-8")

        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        chaos_pythonpath = (
            f"{chaos_dir}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else chaos_dir
        )

        chaos_env = {
            "PYTHONPATH": chaos_pythonpath,
            "SDETKIT_CHAOS_SWITCH_INTERVAL_US": str(active_interval),
            "SDETKIT_CHAOS_LATENCY_MS": str(active_latency),
            "SDETKIT_CHAOS_JITTER_MS": str(active_jitter),
            "SDETKIT_CHAOS_MEMORY_MB": str(active_mem),
            "SDETKIT_CHAOS_FAULT_RATE": str(active_fault),
        }

        for iteration in range(1, total_runs + 1):
            if command:
                passed, dur, out, err = _run_command_iteration(
                    command, cwd=resolved_root, timeout=timeout, env_overrides=chaos_env
                )
            else:
                passed, dur, out, err = _run_single_test_iteration(
                    env.executable,
                    target_args,
                    cwd=resolved_root,
                    timeout=timeout,
                    env_overrides=chaos_env,
                )

            durations.append(dur)
            rec: JsonObject = {
                "run": iteration,
                "passed": passed,
                "duration": round(dur, 4),
            }
            if passed:
                passed_count += 1
            else:
                failed_count += 1
                combined_log = f"{out}\n{err}"
                rec["error_snippet"] = (err.strip() or out.strip())[-500:]
                if "timed out" in combined_log.lower():
                    rec["failure_mode"] = "LATENCY_TIMEOUT_SENSITIVITY"
                    if "LATENCY_TIMEOUT_SENSITIVITY" not in detected_failure_modes:
                        detected_failure_modes.append("LATENCY_TIMEOUT_SENSITIVITY")
                elif (
                    "socket reset" in combined_log.lower()
                    or "connectionreset" in combined_log.lower()
                ):
                    rec["failure_mode"] = "UNHANDLED_TRANSIENT_FAULT"
                    if "UNHANDLED_TRANSIENT_FAULT" not in detected_failure_modes:
                        detected_failure_modes.append("UNHANDLED_TRANSIENT_FAULT")
                elif "memoryerror" in combined_log.lower():
                    rec["failure_mode"] = "MEMORY_STARVATION_VULNERABILITY"
                    if "MEMORY_STARVATION_VULNERABILITY" not in detected_failure_modes:
                        detected_failure_modes.append("MEMORY_STARVATION_VULNERABILITY")
                elif active_interval > 0:
                    rec["failure_mode"] = "CONCURRENCY_RACE_DETECTED"
                    if "CONCURRENCY_RACE_DETECTED" not in detected_failure_modes:
                        detected_failure_modes.append("CONCURRENCY_RACE_DETECTED")
                else:
                    rec["failure_mode"] = "CHAOS_FAILURE"
                    if "CHAOS_FAILURE" not in detected_failure_modes:
                        detected_failure_modes.append("CHAOS_FAILURE")
            run_records.append(rec)

    # 3. Compute metrics & policy decision
    resilience_rate = round((passed_count / total_runs) * 100.0, 1) if total_runs > 0 else 0.0
    mean_chaos_dur = round(sum(durations) / len(durations), 4) if durations else 0.0
    dur_overhead_pct = (
        round(((mean_chaos_dur - base_dur) / base_dur) * 100.0, 1) if base_dur > 0.0 else 0.0
    )

    if not base_passed:
        verdict = "BROKEN_BASELINE"
        resilience_score = 0.0
        policy_decision = (
            "Target fails even without chaos injection. Resolve baseline failures first."
        )
    elif resilience_rate == 100.0:
        verdict = "BULLETPROOF"
        resilience_score = 100.0
        policy_decision = (
            "Target is bulletproof: passed all chaos iterations without failure or timeout."
        )
    elif resilience_rate >= 80.0:
        verdict = "RESILIENT"
        resilience_score = resilience_rate
        policy_decision = "Target demonstrated acceptable resilience, but minor flakiness was observed under chaos."
    elif resilience_rate >= 50.0:
        verdict = "VULNERABLE"
        resilience_score = resilience_rate
        policy_decision = "Target is vulnerable: failed half or more runs under simulated environmental turbulence."
    else:
        verdict = "BRITTLE"
        resilience_score = resilience_rate
        policy_decision = (
            "Target collapsed completely under chaos injection. High risk of production flakiness."
        )

    recommendations: list[str] = []
    if "CONCURRENCY_RACE_DETECTED" in detected_failure_modes:
        recommendations.append(
            "Concurrency race detected: verify thread-safety and synchronize shared state."
        )
    if "LATENCY_TIMEOUT_SENSITIVITY" in detected_failure_modes:
        recommendations.append(
            "Latency timeout sensitivity: increase client timeout thresholds or implement adaptive polling."
        )
    if "UNHANDLED_TRANSIENT_FAULT" in detected_failure_modes:
        recommendations.append(
            "Unhandled transient error: implement retry policy with exponential backoff for socket operations."
        )
    if "MEMORY_STARVATION_VULNERABILITY" in detected_failure_modes:
        recommendations.append(
            "Memory starvation vulnerability: reduce peak memory allocations and stream large payloads."
        )
    if not recommendations and verdict != "BULLETPROOF":
        recommendations.append("Stabilize test fixtures and eliminate environmental coupling.")

    replay_cap_rel: str | None = None
    replay_cmd: str | None = None
    if passed_count < total_runs:
        try:
            chaos_prof = {
                "socket_latency_us": active_latency * 1000,
                "thread_preempt_interval_ms": max(1, active_interval // 1000),
                "fault_reset_seq": [1, 2] if active_fault > 0 else [],
            }
            cap_p = create_replay_capsule(
                resolved_root,
                node_id=str(target or "all"),
                prng_seed=42,
                chaos_profile=chaos_prof,
            )
            replay_cap_rel = str(cap_p.relative_to(resolved_root)).replace("\\", "/")
            replay_cmd = f"sdetkit replay {replay_cap_rel}"
        except Exception as exc:
            # Fallback if capsule generation fails; record none and continue reporting chaos metrics
            replay_cap_rel = None
            replay_cmd = f"sdetkit chaos (capsule unavailable: {exc})"

    return {
        "schema_version": CHAOS_SCHEMA_VERSION,
        "target": str(target) if target else (list(command) if command else "all"),
        "profile": norm_profile,
        "verdict": verdict,
        "resilience_score": resilience_score,
        "resilience_rate": resilience_rate,
        "baseline_passed": base_passed,
        "baseline_duration": round(base_dur, 4),
        "mean_chaos_duration": mean_chaos_dur,
        "duration_overhead_pct": dur_overhead_pct,
        "runs_planned": total_runs,
        "passed_runs": passed_count,
        "failed_runs": failed_count,
        "chaos_parameters": {
            "latency_ms": active_latency,
            "jitter_ms": active_jitter,
            "switch_interval_us": active_interval,
            "memory_mb": active_mem,
            "fault_rate": active_fault,
        },
        "detected_failure_modes": detected_failure_modes,
        "policy_decision": policy_decision,
        "recommendations": recommendations,
        "runs": run_records,
        "replay_capsule": replay_cap_rel,
        "replay_cmd": replay_cmd,
    }


def render_chaos_markdown(report: JsonObject) -> str:
    verdict = report.get("verdict", "UNKNOWN")
    score = report.get("resilience_score", 0.0)
    target = report.get("target", "all")
    profile = report.get("profile", "combined")
    planned = report.get("runs_planned", 0)
    passed = report.get("passed_runs", 0)
    failed = report.get("failed_runs", 0)
    base_dur = report.get("baseline_duration", 0.0)
    chaos_dur = report.get("mean_chaos_duration", 0.0)
    overhead = report.get("duration_overhead_pct", 0.0)
    params = report.get("chaos_parameters") or {}
    modes = report.get("detected_failure_modes") or []
    rec = report.get("policy_decision", "")
    actions = report.get("recommendations") or []

    lines = [
        f"### [CHAOS: {verdict} ({score}%)] SDETKit Chaos Resilience & Injection Engine",
        "",
        f"- **Target**: `{target}`",
        f"- **Profile**: `{profile}`",
        f"- **Completed Runs**: {planned} ({passed} passed, {failed} failed)",
        f"- **Parameters**: Latency={params.get('latency_ms', 0)}ms, Jitter={params.get('jitter_ms', 0)}ms, Switch={params.get('switch_interval_us', 0)}us, Mem={params.get('memory_mb', 0)}MB, FaultRate={params.get('fault_rate', 0.0)}",
        f"- **Duration Benchmark**: Baseline `{base_dur}s` -> Chaos `{chaos_dur}s` (`{overhead:+}%` overhead)",
        "",
        f"> **Policy Decision**: {rec}",
        "",
    ]

    if modes:
        lines.append("#### Detected Failure Modes")
        for m in modes:
            lines.append(f"- `{m}`")
        lines.append("")

    if actions:
        lines.append("#### Hardening Recommendations")
        for a in actions:
            lines.append(f"- {a}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def chaos_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit chaos",
        description="Inject controlled chaos (latency, thread races, memory pressure) to stress-test resilience.",
    )
    parser.add_argument(
        "--repo-root", default=".", help="Root directory of the repository (default: current dir)"
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Target test ID or path to execute under chaos (default: all tests)",
    )
    parser.add_argument(
        "--profile",
        choices=["combined", "latency", "race", "memory", "transient_error"],
        default="combined",
        help="Chaos injection profile (default: combined)",
    )
    parser.add_argument(
        "--latency-ms",
        type=int,
        default=50,
        help="Latency delay injected into sleep and socket ops (default: 50ms)",
    )
    parser.add_argument(
        "--jitter-ms",
        type=int,
        default=25,
        help="Random variance applied to latency (default: 25ms)",
    )
    parser.add_argument(
        "--switch-interval-us",
        type=int,
        default=10,
        help="Python thread switch interval in microseconds to force thread interleaving (default: 10us)",
    )
    parser.add_argument(
        "--memory-mb",
        type=int,
        default=0,
        help="Synthetic memory buffer overhead in megabytes (default: 0)",
    )
    parser.add_argument(
        "--fault-rate",
        type=float,
        default=0.0,
        help="Transient fault rate between 0.0 and 1.0 (default: 0.0)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of chaos test iterations (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-run timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--format",
        choices=["md", "json", "text"],
        default="md",
        help="Output format (default: md)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Write JSON report to a file",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Extra arguments passed to test runner",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()

    res = inject_chaos(
        root=root,
        target=args.target,
        profile=args.profile,
        latency_ms=args.latency_ms,
        jitter_ms=args.jitter_ms,
        switch_interval_us=args.switch_interval_us,
        memory_mb=args.memory_mb,
        fault_rate=args.fault_rate,
        runs=args.runs,
        timeout=args.timeout,
    )

    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(res, indent=2))
    elif args.format == "text":
        verdict = res.get("verdict", "UNKNOWN")
        score = res.get("resilience_score", 0.0)
        print(f"verdict={verdict} score={score}% runs={res.get('runs_planned')}")
    else:
        print(render_chaos_markdown(res))

    return 0 if res.get("resilience_score", 0.0) >= 80.0 else 1


GENOME_SCHEMA_VERSION = "sdetkit.flake_genome.v1"

_COMMON_PORTS = {8080, 5000, 3000, 8000, 9000, 8443, 8888, 6379, 5432, 27017, 9092}

REMEDIATION_RECIPES = {
    "GLOBAL_STATE_MUTATION": (
        "Replace direct os.environ or sys.path mutation with pytest's monkeypatch fixture: "
        "`monkeypatch.setenv('KEY', 'VAL')` or `monkeypatch.syspath_prepend(...)`."
    ),
    "ARBITRARY_SLEEP": (
        "Replace hardcoded sleep() with event-driven synchronization or polling loop "
        "(e.g. `threading.Event.wait(timeout)` or `tenacity.retry`)."
    ),
    "UNMOCKED_WALL_CLOCK": (
        "Freeze wall-clock time in assertions using `@pytest.mark.freeze_time`, `freezegun`, "
        "or `monkeypatch.setattr(time, 'time', lambda: 1700000000)`."
    ),
    "UNSEEDED_RANDOMNESS": (
        "Seed pseudo-random generators prior to test execution via `random.seed(42)` "
        "or adopt deterministic property-based testing (Hypothesis)."
    ),
    "PORT_COLLISION": (
        "Bind sockets to ephemeral port 0 (`sock.bind(('127.0.0.1', 0))`) "
        "or use an isolated port fixture instead of hardcoded numbers."
    ),
    "UNBOUNDED_THREAD_SPAWN": (
        "Ensure threads/processes are explicitly daemonized or joined with timeout "
        "to prevent leaked execution across test runs."
    ),
    "TAUTOLOGICAL_ASSERTION": (
        "Replace tautological statements (e.g. constant True/1, or x == x) with meaningful "
        "assertions that verify actual system output, return values, or side-effects."
    ),
    "SWALLOWED_TEST_EXCEPTION": (
        "Replace broad empty except blocks (except Exception: pass) with pytest.raises() "
        "to explicitly verify and assert expected exceptions."
    ),
}


def _is_tautological_assert(node: ast.Assert) -> bool:
    """Check if an assertion is a trivial tautology (e.g. constant True/1, or x == x)."""
    if isinstance(node.test, ast.Constant):
        if node.test.value is True or node.test.value == 1:
            return True
    if isinstance(node.test, ast.Name) and node.test.id == "True":
        return True
    if (
        isinstance(node.test, ast.Compare)
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], (ast.Eq, ast.Is))
    ):
        left = node.test.left
        right = node.test.comparators[0]
        if isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id == right.id:
            return True
        if (
            isinstance(left, ast.Attribute)
            and isinstance(right, ast.Attribute)
            and ast.dump(left) == ast.dump(right)
        ):
            return True
    return False


def _scan_source_tree(tree: ast.AST, rel_path: str) -> list[JsonObject]:
    markers: list[JsonObject] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "sleep") or (
                isinstance(func, ast.Name) and func.id == "sleep"
            ):
                markers.append(
                    {
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "type": "ARBITRARY_SLEEP",
                        "severity": "High",
                        "weight": 25,
                        "message": "Unsynchronized arbitrary sleep call",
                        "recipe": REMEDIATION_RECIPES["ARBITRARY_SLEEP"],
                    }
                )
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in ("now", "utcnow", "today", "time", "monotonic")
            ) or (isinstance(func, ast.Name) and func.id in ("time", "monotonic")):
                markers.append(
                    {
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "type": "UNMOCKED_WALL_CLOCK",
                        "severity": "Medium",
                        "weight": 20,
                        "message": "Unfrozen wall-clock time query",
                        "recipe": REMEDIATION_RECIPES["UNMOCKED_WALL_CLOCK"],
                    }
                )
            elif (
                isinstance(func, ast.Attribute)
                and (
                    (isinstance(func.value, ast.Name) and func.value.id in ("random", "uuid"))
                    or func.attr
                    in (
                        "random",
                        "choice",
                        "randint",
                        "randrange",
                        "sample",
                        "shuffle",
                        "uuid4",
                    )
                )
            ) or (isinstance(func, ast.Name) and func.id in ("randint", "choice", "uuid4")):
                markers.append(
                    {
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "type": "UNSEEDED_RANDOMNESS",
                        "severity": "High",
                        "weight": 25,
                        "message": "Unseeded pseudo-random generator call",
                        "recipe": REMEDIATION_RECIPES["UNSEEDED_RANDOMNESS"],
                    }
                )
            elif isinstance(func, ast.Attribute) and func.attr in ("pop", "clear", "update"):
                if isinstance(func.value, ast.Attribute) and func.value.attr == "environ":
                    markers.append(
                        {
                            "file": rel_path,
                            "line": getattr(node, "lineno", 1),
                            "type": "GLOBAL_STATE_MUTATION",
                            "severity": "Critical",
                            "weight": 35,
                            "message": "Direct os.environ mutation via method without monkeypatch",
                            "recipe": REMEDIATION_RECIPES["GLOBAL_STATE_MUTATION"],
                        }
                    )
            elif isinstance(func, ast.Attribute) and func.attr in ("append", "insert"):
                if isinstance(func.value, ast.Attribute) and func.value.attr == "path":
                    markers.append(
                        {
                            "file": rel_path,
                            "line": getattr(node, "lineno", 1),
                            "type": "GLOBAL_STATE_MUTATION",
                            "severity": "High",
                            "weight": 30,
                            "message": "Direct sys.path modification in test body",
                            "recipe": REMEDIATION_RECIPES["GLOBAL_STATE_MUTATION"],
                        }
                    )
            elif isinstance(func, ast.Attribute) and func.attr in ("Thread", "Process"):
                markers.append(
                    {
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "type": "UNBOUNDED_THREAD_SPAWN",
                        "severity": "Medium",
                        "weight": 20,
                        "message": f"Raw {func.attr} instantiation without managed fixture",
                        "recipe": REMEDIATION_RECIPES["UNBOUNDED_THREAD_SPAWN"],
                    }
                )

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "environ"
                ):
                    markers.append(
                        {
                            "file": rel_path,
                            "line": getattr(node, "lineno", 1),
                            "type": "GLOBAL_STATE_MUTATION",
                            "severity": "Critical",
                            "weight": 35,
                            "message": "Direct os.environ assignment without monkeypatch fixture",
                            "recipe": REMEDIATION_RECIPES["GLOBAL_STATE_MUTATION"],
                        }
                    )

        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "environ"
                ):
                    markers.append(
                        {
                            "file": rel_path,
                            "line": getattr(node, "lineno", 1),
                            "type": "GLOBAL_STATE_MUTATION",
                            "severity": "Critical",
                            "weight": 35,
                            "message": "Direct os.environ deletion without monkeypatch fixture",
                            "recipe": REMEDIATION_RECIPES["GLOBAL_STATE_MUTATION"],
                        }
                    )

        elif isinstance(node, ast.Constant):
            if isinstance(node.value, int) and node.value in _COMMON_PORTS:
                markers.append(
                    {
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "type": "PORT_COLLISION",
                        "severity": "High",
                        "weight": 25,
                        "message": f"Hardcoded network port constant: {node.value}",
                        "recipe": REMEDIATION_RECIPES["PORT_COLLISION"],
                    }
                )
            elif isinstance(node.value, str) and any(f":{p}" in node.value for p in _COMMON_PORTS):
                markers.append(
                    {
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "type": "PORT_COLLISION",
                        "severity": "High",
                        "weight": 25,
                        "message": f"Hardcoded network URL with fixed port: {node.value}",
                        "recipe": REMEDIATION_RECIPES["PORT_COLLISION"],
                    }
                )

        elif isinstance(node, ast.Assert):
            if _is_tautological_assert(node):
                markers.append(
                    {
                        "file": rel_path,
                        "line": getattr(node, "lineno", 1),
                        "type": "TAUTOLOGICAL_ASSERTION",
                        "severity": "Critical",
                        "weight": 35,
                        "message": "Tautological assertion detected (verifies nothing)",
                        "recipe": REMEDIATION_RECIPES["TAUTOLOGICAL_ASSERTION"],
                    }
                )

        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None or (
                    isinstance(handler.type, ast.Name)
                    and handler.type.id in ("Exception", "BaseException")
                ):
                    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                        markers.append(
                            {
                                "file": rel_path,
                                "line": getattr(handler, "lineno", getattr(node, "lineno", 1)),
                                "type": "SWALLOWED_TEST_EXCEPTION",
                                "severity": "Critical",
                                "weight": 35,
                                "message": "Swallowed test exception block (except Exception: pass)",
                                "recipe": REMEDIATION_RECIPES["SWALLOWED_TEST_EXCEPTION"],
                            }
                        )

    return markers


def scan_flake_genome(
    target: Path | str | None = None,
    *,
    root: Path | None = None,
    source_code: str | None = None,
) -> JsonObject:
    """Statically audit test ASTs to classify flake risk and detect concurrency anti-patterns."""
    resolved_root = (root or Path.cwd()).resolve()

    files_to_scan: list[tuple[str, str]] = []

    if source_code is not None:
        files_to_scan.append(("<in-memory>", source_code))
    elif target is not None:
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = resolved_root / target_path
        if target_path.is_file():
            rel = str(
                target_path.relative_to(resolved_root)
                if target_path.is_relative_to(resolved_root)
                else target_path.name
            ).replace("\\", "/")
            files_to_scan.append((rel, target_path.read_text(encoding="utf-8", errors="replace")))
        elif target_path.is_dir():
            for p in sorted(target_path.rglob("test_*.py")):
                if p.is_file():
                    rel = str(p.relative_to(resolved_root)).replace("\\", "/")
                    files_to_scan.append((rel, p.read_text(encoding="utf-8", errors="replace")))
    else:
        tests_dir = resolved_root / "tests"
        if tests_dir.is_dir():
            for p in sorted(tests_dir.rglob("test_*.py")):
                if p.is_file():
                    rel = str(p.relative_to(resolved_root)).replace("\\", "/")
                    files_to_scan.append((rel, p.read_text(encoding="utf-8", errors="replace")))

    all_markers: list[JsonObject] = []
    markers_by_type: dict[str, int] = {}

    for rel_path, code in files_to_scan:
        try:
            tree = ast.parse(code, filename=rel_path)
            file_markers = _scan_source_tree(tree, rel_path)
            all_markers.extend(file_markers)
            for m in file_markers:
                m_type = str(m["type"])
                markers_by_type[m_type] = markers_by_type.get(m_type, 0) + 1
        except SyntaxError as exc:
            all_markers.append(
                {
                    "file": rel_path,
                    "line": exc.lineno or 1,
                    "type": "SYNTAX_ERROR",
                    "severity": "Critical",
                    "weight": 50,
                    "message": f"Syntax error: {exc.msg}",
                    "recipe": "Fix syntax error to restore test parseability.",
                }
            )

    raw_score = sum(int(m.get("weight", 0)) for m in all_markers)
    risk_score = float(min(100, raw_score))

    if risk_score <= 15:
        tier = "PRISTINE"
    elif risk_score <= 35:
        tier = "LOW"
    elif risk_score <= 65:
        tier = "MODERATE"
    elif risk_score <= 85:
        tier = "HIGH"
    else:
        tier = "CRITICAL"

    has_critical = any(m.get("severity") == "Critical" for m in all_markers)
    if risk_score <= 50 and not has_critical:
        verdict = "PASS"
    elif risk_score <= 80 and not has_critical:
        verdict = "NEEDS_REFACTOR"
    else:
        verdict = "REJECT"

    unique_recipes: list[str] = sorted({str(m["recipe"]) for m in all_markers if "recipe" in m})

    return {
        "schema_version": GENOME_SCHEMA_VERSION,
        "target": str(target) if target else "tests",
        "files_scanned": len(files_to_scan),
        "total_markers": len(all_markers),
        "flake_risk_score": risk_score,
        "risk_tier": tier,
        "verdict": verdict,
        "markers_by_type": markers_by_type,
        "markers": all_markers,
        "recipes": unique_recipes,
    }


def render_genome_markdown(report: JsonObject) -> str:
    target = report.get("target", "tests")
    files_cnt = report.get("files_scanned", 0)
    markers_cnt = report.get("total_markers", 0)
    score = report.get("flake_risk_score", 0.0)
    tier = report.get("risk_tier", "PRISTINE")
    verdict = report.get("verdict", "PASS")
    markers = report.get("markers") or []
    recipes = report.get("recipes") or []

    lines = [
        f"### [GENOME RISK: {tier} ({score}/100)] SDETKit Flake Genome & Test Anti-Pattern Analysis",
        "",
        f"- **Target Scanned**: `{target}` (`{files_cnt} test files`, `{markers_cnt} anti-pattern markers`)",
        f"- **Flake Risk Score**: `{score}/100` (`{tier}` Flake Risk)",
        f"- **Verdict**: `{verdict}`",
        "",
        "#### Detected Anti-Pattern Markers",
    ]

    if not markers:
        lines.append(
            "Zero anti-pattern markers detected. Test suite demonstrates pristine determinism.\n"
        )
    else:
        lines.extend(
            [
                "| File:Line | Anti-Pattern | Severity | Description |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for m in markers[:25]:
            fline = f"`{m.get('file')}:{m.get('line')}`"
            mtype = f"`{m.get('type')}`"
            sev = f"**{m.get('severity')}**"
            msg = str(m.get("message", ""))
            lines.append(f"| {fline} | {mtype} | {sev} | {msg} |")
        if len(markers) > 25:
            lines.append(f"\n*... and {len(markers) - 25} additional markers omitted for brevity.*")
        lines.append("")

    if recipes:
        lines.append("#### Prescriptive Auto-Remediation Recipes")
        for r in recipes:
            lines.append(f"- {r}")

    return "\n".join(lines).strip() + "\n"


def genome_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit genome",
        description="Static AST analysis to detect flaky test smells, concurrency anti-patterns, and state leakage.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Target test file or directory to scan (default: tests/)",
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
        "--max-risk",
        type=int,
        default=50,
        help="Maximum allowable flake risk score before failing (default: 50)",
    )
    parser.add_argument(
        "--format",
        choices=["md", "markdown", "json", "text"],
        default="md",
        help="Output report format (default: md)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Path to write JSON report output",
    )
    parser.add_argument(
        "--summary-out",
        default=None,
        help="Path to write Markdown summary output",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()

    report = scan_flake_genome(args.target, root=root)

    if args.out:
        out_p = Path(args.out).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_text = render_genome_markdown(report)
    if args.summary_out:
        sm_p = Path(args.summary_out).resolve()
        sm_p.parent.mkdir(parents=True, exist_ok=True)
        sm_p.write_text(md_text, encoding="utf-8")

    if args.format == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    elif args.format in ("md", "markdown"):
        sys.stdout.write(md_text + "\n")
    else:
        sys.stdout.write(
            f"verdict={report.get('verdict')} risk_score={report.get('flake_risk_score')} "
            f"tier={report.get('risk_tier')} markers={report.get('total_markers')}\n"
        )

    return (
        0
        if report.get("flake_risk_score", 0.0) <= args.max_risk
        and report.get("verdict") != "REJECT"
        else 1
    )


BISECT_SCHEMA_VERSION = "sdetkit.bisect.v1"


def _git_cmd(root: Path, args: Sequence[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            text=True,
            capture_output=True,
            shell=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except OSError:
        # Silently return empty string if git CLI is unavailable or fails
        return ""


def _git_commits(root: Path, good_ref: str | None, bad_ref: str, max_commits: int) -> list[str]:
    if good_ref:
        out = _git_cmd(root, ["rev-list", "--topo-order", "--reverse", f"{good_ref}..{bad_ref}"])
    else:
        out = _git_cmd(root, ["rev-list", f"--max-count={max_commits}", "--reverse", bad_ref])
    commits = [c.strip() for c in out.splitlines() if c.strip()]
    return commits[-max_commits:] if len(commits) > max_commits else commits


def _git_commit_info(root: Path, commit_sha: str) -> dict[str, Any]:
    author = _git_cmd(root, ["log", "-1", "--format=%an <%ae>", commit_sha])
    date = _git_cmd(root, ["log", "-1", "--format=%ai", commit_sha])
    subject = _git_cmd(root, ["log", "-1", "--format=%s", commit_sha])
    files_out = _git_cmd(root, ["show", "--name-only", "--format=", commit_sha])
    changed_files = [f.strip() for f in files_out.splitlines() if f.strip()]
    return {
        "commit": commit_sha[:8],
        "full_sha": commit_sha,
        "author": author or "unknown",
        "date": date or "unknown",
        "message": subject or "unknown",
        "changed_files": changed_files,
    }


def bisect_flaky_test(
    root: Path,
    target: str,
    *,
    good_ref: str | None = None,
    bad_ref: str = "HEAD",
    max_commits: int = 10,
    runs: int = 3,
    timeout: int = 60,
) -> dict[str, Any]:
    resolved_root = root.resolve()
    commits = _git_commits(resolved_root, good_ref, bad_ref, max_commits)

    if not commits:
        hunt = hunt_flakes(resolved_root, target=target, runs=runs, timeout=timeout)
        is_flaky = hunt.get("verdict") == "flaky"
        return {
            "schema_version": BISECT_SCHEMA_VERSION,
            "target": target,
            "good_ref": good_ref or "N/A",
            "bad_ref": bad_ref,
            "verdict": "ATTRIBUTED" if is_flaky else "NOT_REPRODUCED",
            "culprit_commit": {
                "commit": "HEAD",
                "full_sha": "HEAD",
                "author": "Local Working Tree",
                "date": datetime.now(UTC).isoformat(),
                "message": "Local working tree state",
                "changed_files": [],
                "is_direct_test_edit": False,
            },
            "attribution_type": "LOCAL_WORKING_TREE",
            "history": [
                {
                    "commit": "HEAD",
                    "verdict": hunt.get("verdict"),
                    "flake_rate": hunt.get("flake_rate", 0),
                }
            ],
            "recommendation": "Add to quarantine if flakiness persists: `sdetkit quarantine add`",
        }

    low = 0
    high = len(commits) - 1
    eval_history: list[dict[str, Any]] = []
    cache: dict[str, dict[str, Any]] = {}

    def _test_commit(sha: str) -> dict[str, Any]:
        if sha in cache:
            return cache[sha]
        with tempfile.TemporaryDirectory(prefix="sdetkit-bisect-") as temp_dir:
            temp_path = Path(temp_dir) / "wt"
            _git_cmd(
                resolved_root,
                ["worktree", "add", "--detach", str(temp_path), sha],
            )
            if temp_path.exists():
                try:
                    res = hunt_flakes(temp_path, target=target, runs=runs, timeout=timeout)
                finally:
                    _git_cmd(
                        resolved_root,
                        ["worktree", "remove", "--force", str(temp_path)],
                    )
            else:
                res = hunt_flakes(resolved_root, target=target, runs=runs, timeout=timeout)

            outcome = {
                "commit": sha[:8],
                "verdict": res.get("verdict", "clean"),
                "flake_rate": res.get("flake_rate", 0.0),
                "passed_count": res.get("passed_count", 0),
                "failed_count": res.get("failed_count", 0),
            }
            cache[sha] = outcome
            eval_history.append(outcome)
            return outcome

    culprit_sha = commits[high]
    while low <= high:
        mid = (low + high) // 2
        res = _test_commit(commits[mid])
        if res.get("verdict") in ("flaky", "broken", "fail"):
            culprit_sha = commits[mid]
            high = mid - 1
        else:
            low = mid + 1

    info = _git_commit_info(resolved_root, culprit_sha)
    target_clean = target.split("::")[0].replace("\\", "/")
    is_direct = any(target_clean in f.replace("\\", "/") for f in info.get("changed_files", []))
    info["is_direct_test_edit"] = is_direct

    last_eval = cache.get(culprit_sha, {})
    verdict = (
        "ATTRIBUTED"
        if last_eval.get("verdict") in ("flaky", "broken", "fail")
        else "NOT_REPRODUCED"
    )
    attr_type = "DIRECT_TEST_MODIFICATION" if is_direct else "TRANSITIVE_DEPENDENCY_DRIFT"

    return {
        "schema_version": BISECT_SCHEMA_VERSION,
        "target": target,
        "good_ref": good_ref or commits[0][:8],
        "bad_ref": bad_ref,
        "total_commits_scanned": len(commits),
        "commits_evaluated_count": len(eval_history),
        "verdict": verdict,
        "attribution_type": attr_type,
        "culprit_commit": info,
        "history": eval_history,
        "recommendation": (
            f"Commit {info['commit']} by {info['author']} introduced flakiness into "
            f"`{target}` ({attr_type}). Inspect diff or isolate with `sdetkit quarantine add`."
        ),
    }


def render_bisect_markdown(report: Mapping[str, Any]) -> str:
    culprit = report.get("culprit_commit", {})
    history = report.get("history", [])
    lines = [
        "# SDETKit Flake Bisection & Git Blame Attribution",
        "",
        (
            f"**Verdict:** `{report.get('verdict', 'UNKNOWN')}` | "
            f"**Attribution:** `{report.get('attribution_type', 'UNKNOWN')}` | "
            f"**Target:** `{report.get('target', 'N/A')}`"
        ),
        "",
        f"> {report.get('recommendation', '')}",
        "",
        "### Culprit Commit Metadata",
        f"- **Commit:** `{culprit.get('commit', 'HEAD')}` (`{culprit.get('full_sha', 'HEAD')}`)",
        f"- **Author:** {culprit.get('author', 'unknown')}",
        f"- **Date:** {culprit.get('date', 'unknown')}",
        f"- **Subject:** {culprit.get('message', 'unknown')}",
        (
            "- **Modification Type:** "
            f"`{'Direct test file edit' if culprit.get('is_direct_test_edit') else 'Transitive dependency drift'}`"
        ),
        "",
        "### Bisection Progression History",
        "| Step | Commit | Status | Flake Rate | Passed / Total |",
        "|:---:|:---:|:---:|:---:|:---:|",
    ]
    for idx, item in enumerate(history, start=1):
        lines.append(
            f"| {idx} | `{item.get('commit')}` | `{item.get('verdict')}` | "
            f"{item.get('flake_rate', 0.0)}% | {item.get('passed_count', 0)}/{item.get('passed_count', 0) + item.get('failed_count', 0)} |"
        )
    return "\n".join(lines).strip() + "\n"


def bisect_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit bisect",
        description=(
            "Bisect git commit history to pinpoint commit and author introducing test flakiness."
        ),
    )
    parser.add_argument(
        "target",
        help="Target test id or path (e.g. tests/test_api.py::test_case).",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root directory (default: .).")
    parser.add_argument("--good", default=None, help="Known good git commit or ref.")
    parser.add_argument(
        "--bad", default="HEAD", help="Known bad git commit or ref (default: HEAD)."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Flake hunt iterations per commit (default: 3).",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=15,
        help="Maximum commits in range to search (default: 15).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_PER_RUN_TIMEOUT,
        help="Per-run timeout in seconds.",
    )
    parser.add_argument(
        "--format",
        choices=["md", "json", "text"],
        default="md",
        help="Output format.",
    )
    parser.add_argument("--out", help="Path to write JSON output.")
    parser.add_argument("--summary-out", help="Path to write Markdown summary.")

    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()

    report = bisect_flaky_test(
        root,
        args.target,
        good_ref=args.good,
        bad_ref=args.bad,
        max_commits=args.max_commits,
        runs=args.runs,
        timeout=args.timeout,
    )

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.summary_out:
        summary_p = Path(args.summary_out)
        summary_p.parent.mkdir(parents=True, exist_ok=True)
        summary_p.write_text(render_bisect_markdown(report), encoding="utf-8")

    if args.format == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    elif args.format == "text":
        culprit = report.get("culprit_commit", {})
        sys.stdout.write(
            f"verdict={report.get('verdict')} culprit={culprit.get('commit')} "
            f"author={culprit.get('author')} type={report.get('attribution_type')}\n"
        )
    else:
        sys.stdout.write(render_bisect_markdown(report))

    return 0 if report.get("verdict") in ("ATTRIBUTED", "NOT_REPRODUCED") else 1


# =============================================================================
# Frontier 21: Deterministic Replay Capsules (sdetkit replay)
# =============================================================================

CAPSULE_SCHEMA_VERSION = "1.0"
DEFAULT_CAPSULES_DIR = ".sdetkit/capsules"


def create_replay_capsule(
    root: Path,
    *,
    node_id: str,
    prng_seed: int = 42,
    chaos_profile: Mapping[str, Any] | None = None,
    env_overrides: Mapping[str, str] | None = None,
    capsule_id: str | None = None,
) -> Path:
    """Write a portable pure-ASCII JSON capsule for deterministic test failure reproduction."""
    resolved_root = root.resolve()
    capsules_dir = resolved_root / DEFAULT_CAPSULES_DIR
    capsules_dir.mkdir(parents=True, exist_ok=True)

    cid = capsule_id or f"cap_{uuid.uuid4().hex[:8]}"
    if not cid.endswith(".json"):
        capsule_file = capsules_dir / f"{cid}.json"
    else:
        capsule_file = capsules_dir / cid

    rel_path = f"{DEFAULT_CAPSULES_DIR}/{capsule_file.name}"

    default_env = {
        "TZ": "UTC",
        "PYTHONHASHSEED": str(prng_seed),
    }
    if env_overrides:
        default_env.update(env_overrides)

    capsule_data = {
        "schema_version": CAPSULE_SCHEMA_VERSION,
        "node_id": node_id,
        "prng_seed": prng_seed,
        "chaos_profile": dict(chaos_profile or {}),
        "env_overrides": default_env,
        "replay_cmd": f"sdetkit replay {rel_path}",
    }
    capsule_file.write_text(
        json.dumps(capsule_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return capsule_file


def replay_capsule(
    capsule_path: Path | str,
    *,
    root: Path | None = None,
    timeout: int = 60,
) -> JsonObject:
    """Deterministically execute and reproduce a test failure from a replay capsule."""
    resolved_root = (root or Path.cwd()).resolve()
    c_path = Path(capsule_path)
    if not c_path.is_absolute():
        c_path = resolved_root / c_path
    if not c_path.is_file():
        raise OSError(f"replay capsule not found: {capsule_path}")

    try:
        data = json.loads(c_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"malformed replay capsule: {exc}") from None

    if data.get("schema_version") != CAPSULE_SCHEMA_VERSION:
        raise ValueError(f"unsupported replay capsule schema version: {data.get('schema_version')}")

    node_id = data.get("node_id", "")
    seed = int(data.get("prng_seed", 42))
    chaos_prof = data.get("chaos_profile", {})
    env_ov = dict(data.get("env_overrides", {}))

    env_ov.setdefault("PYTHONHASHSEED", str(seed))
    env_ov.setdefault("TZ", "UTC")

    if chaos_prof:
        if "socket_latency_us" in chaos_prof:
            env_ov["SDETKIT_CHAOS_LATENCY_MS"] = str(
                round(chaos_prof["socket_latency_us"] / 1000.0)
            )
        if "thread_preempt_interval_ms" in chaos_prof:
            env_ov["SDETKIT_CHAOS_SWITCH_INTERVAL_US"] = str(
                int(chaos_prof["thread_preempt_interval_ms"] * 1000)
            )
        if "fault_reset_seq" in chaos_prof:
            env_ov["SDETKIT_CHAOS_FAULT_RATE"] = "0.5"

    env = resolve_project_python(resolved_root)
    with tempfile.TemporaryDirectory(prefix="sdetkit_replay_") as tmp_dir:
        if chaos_prof:
            hook_path = Path(tmp_dir) / "sitecustomize.py"
            hook_path.write_text(_CHAOS_SITECUSTOMIZE_TEMPLATE, encoding="utf-8")
            existing_pp = os.environ.get("PYTHONPATH", "")
            env_ov["PYTHONPATH"] = f"{tmp_dir}{os.pathsep}{existing_pp}" if existing_pp else tmp_dir

        target_args = [node_id] if node_id and node_id != "all" else []
        passed, duration, out, err = _run_single_test_iteration(
            env.executable,
            target_args,
            cwd=resolved_root,
            timeout=timeout,
            env_overrides=env_ov,
        )

    verdict = "PASSED" if passed else "REPRODUCED"
    return {
        "schema_version": CAPSULE_SCHEMA_VERSION,
        "verdict": verdict,
        "capsule": str(c_path.name),
        "node_id": node_id,
        "prng_seed": seed,
        "duration_ms": round(duration * 1000.0, 2),
        "reproduced": not passed,
        "output": (f"{out}\n{err}".strip())[-1500:],
    }


def render_replay_markdown(report: JsonObject) -> str:
    """Render structured Markdown report for sdetkit replay."""
    verdict = report.get("verdict", "UNKNOWN")
    repro = report.get("reproduced", False)
    node_id = report.get("node_id", "all")
    seed = report.get("prng_seed", 42)
    dur = report.get("duration_ms", 0.0)
    out = report.get("output", "")

    badge = "[REPRODUCED]" if repro else "[PASSED]"
    lines = [
        f"# {badge} SDETKit Deterministic Replay Capsule",
        "",
        f"- **Verdict**: `{verdict}`",
        f"- **Reproduced**: `{repro}`",
        f"- **Node ID**: `{node_id}`",
        f"- **PRNG Seed**: `{seed}`",
        f"- **Duration**: `{dur} ms`",
        "",
    ]
    if out:
        lines.extend(["### Execution Diagnostics", "```text", out, "```", ""])
    return "\n".join(lines).strip() + "\n"


def render_replay_text(report: JsonObject) -> str:
    """Render concise plain-text summary for sdetkit replay."""
    verdict = report.get("verdict", "UNKNOWN")
    repro = report.get("reproduced", False)
    node_id = report.get("node_id", "all")
    return f"SDETKit Replay: verdict={verdict} reproduced={repro} node={node_id}\n"


def replay_main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for sdetkit replay."""
    parser = argparse.ArgumentParser(
        prog="sdetkit replay",
        description="Deterministically replay a test failure from a portable JSON capsule.",
    )
    parser.add_argument("capsule", help="Path to replay capsule JSON file")
    parser.add_argument("--repo-root", default=".", help="Repository root directory")
    parser.add_argument("--timeout", type=int, default=60, help="Execution timeout in seconds")
    parser.add_argument("--format", choices=["json", "text", "md", "markdown"], default="md")
    parser.add_argument("--out", default=None, help="Output file path")
    parser.add_argument("--summary-out", default=None, help="Summary output file path")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.repo_root).resolve()

    try:
        report = replay_capsule(args.capsule, root=root, timeout=args.timeout)
    except Exception as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    elif args.format == "text":
        output = render_replay_text(report)
    else:
        output = render_replay_markdown(report)

    if args.out:
        out_p = Path(args.out).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output, encoding="utf-8")

    if args.summary_out:
        sm_p = Path(args.summary_out).resolve()
        sm_p.parent.mkdir(parents=True, exist_ok=True)
        with sm_p.open("a", encoding="utf-8") as sf:
            sf.write(render_replay_markdown(report))

    sys.stdout.write(output)
    return 0 if report.get("verdict") in ("PASSED", "REPRODUCED") else 1


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    if os.environ.get("SDETKIT_SUBCOMMAND") == "replay":
        return replay_main(args_list)
    if args_list and args_list[0] == "replay":
        return replay_main(args_list[1:])
    if "replay" in sys.argv:
        return replay_main(args_list)
    if os.environ.get("SDETKIT_SUBCOMMAND") == "bisect":
        return bisect_main(args_list)
    if args_list and args_list[0] == "bisect":
        return bisect_main(args_list[1:])
    if "bisect" in sys.argv:
        return bisect_main(args_list)
    if os.environ.get("SDETKIT_SUBCOMMAND") in ("genome", "flake-genome"):
        return genome_main(args_list)
    if args_list and args_list[0] in ("genome", "flake-genome"):
        return genome_main(args_list[1:])
    if "genome" in sys.argv:
        return genome_main(args_list)
    if os.environ.get("SDETKIT_SUBCOMMAND") == "chaos":
        return chaos_main(args_list)
    if args_list and args_list[0] == "chaos":
        return chaos_main(args_list[1:])
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
