from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.sentinel.v1"
EVENT_SCHEMA_VERSION = "sdetkit.adaptive.sentinel.event.v1"
TREND_SCHEMA_VERSION = "sdetkit.adaptive.sentinel.trend_memory.v1"

STATE_RANK = {
    "healthy": 0,
    "watch": 1,
    "warning": 2,
    "critical": 3,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "not_json_object"
    return payload, ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _max_state(*states: str) -> str:
    current = "healthy"
    for state in states:
        if STATE_RANK.get(state, 0) > STATE_RANK.get(current, 0):
            current = state
    return current


PROTECTED_SURFACE_EXCLUDES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".sdetkit/",
    "build/",
    "dist/",
    "htmlcov/",
)


def _is_noise_path(path: str) -> bool:
    return path.startswith(PROTECTED_SURFACE_EXCLUDES)


def _git_changed_paths(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return []

    if result.returncode != 0:
        return []

    paths: list[str] = []
    for raw in result.stdout.splitlines():
        if len(raw) < 4:
            continue
        rel = raw[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1].strip()
        rel = rel.replace("\\", "/")
        if rel and not _is_noise_path(rel):
            paths.append(rel)

    return sorted(set(paths))


def _protected_surface_rule(path: str) -> dict[str, str] | None:
    rel = path.replace("\\", "/")

    if rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml")):
        return {
            "surface": "workflow_automation",
            "risk_band": "critical",
            "reason": "GitHub Actions workflow changes can alter CI, permissions, secrets, and release behavior.",
            "proof_command": "python -m pytest -q tests/test_workflow_alias_regression_guards.py -o addopts=",
        }

    dependency_files = {
        "pyproject.toml",
        "constraints-ci.txt",
        "requirements.txt",
        "requirements-test.txt",
        "requirements-docs.txt",
        ".pre-commit-config.yaml",
    }
    if rel in dependency_files or (rel.startswith("requirements-") and rel.endswith(".txt")):
        return {
            "surface": "dependency_contract",
            "risk_band": "critical",
            "reason": "Dependency and constraint changes can break reproducible installs.",
            "proof_command": "python -m pip install -c constraints-ci.txt -e '.[dev,test]'",
        }

    if rel == "Makefile":
        return {
            "surface": "developer_workflow",
            "risk_band": "warning",
            "reason": "Make targets are operator-facing workflow contracts.",
            "proof_command": "python -m pre_commit run -a",
        }

    if rel.startswith("scripts/release") or rel.startswith("scripts/check_release"):
        return {
            "surface": "release_supply_chain",
            "risk_band": "critical",
            "reason": "Release scripts affect package trust, version gates, and publish readiness.",
            "proof_command": "python -m build",
        }

    security_paths = {
        "src/sdetkit/security.py",
        "src/sdetkit/security_gate.py",
        "src/sdetkit/gates/security_gate.py",
        "src/sdetkit/cli/security.py",
        "tools/security_allowlist.json",
        "tools/security.baseline.json",
    }
    if rel in security_paths or rel.startswith("docs/security"):
        return {
            "surface": "security_posture",
            "risk_band": "critical",
            "reason": "Security surfaces need review-first handling and scanner-noise separation.",
            "proof_command": "python -m sdetkit security check --root . --format json",
        }

    diagnosis_paths = {
        "src/sdetkit/adaptive_sentinel.py",
        "src/sdetkit/adaptive_diagnosis.py",
        "src/sdetkit/adaptive_failure_bundle.py",
        "src/sdetkit/ci_failure_triage.py",
        "src/sdetkit/doctor.py",
        "src/sdetkit/doctor_diagnosis.py",
        "src/sdetkit/doctor_prescriptions.py",
        "src/sdetkit/investigate.py",
        "src/sdetkit/mission_control.py",
        "src/sdetkit/pr_quality_comment.py",
        "tools/maintenance_autopilot.py",
    }
    if rel in diagnosis_paths:
        return {
            "surface": "diagnostic_intelligence",
            "risk_band": "warning",
            "reason": "Diagnosis-engine changes affect operator guidance and evidence routing.",
            "proof_command": "python -m pytest -q tests/test_adaptive_sentinel.py -o addopts=",
        }

    if rel == "src/sdetkit/cli.py" or rel.startswith("src/sdetkit/core/"):
        return {
            "surface": "cli_routing",
            "risk_band": "warning",
            "reason": "CLI routing changes can break public commands and compatibility aliases.",
            "proof_command": "python -m sdetkit --help",
        }

    return None


def _protected_surface_changes(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rel in _git_changed_paths(root):
        rule = _protected_surface_rule(rel)
        if rule is None:
            continue
        rows.append(
            {
                "path": rel,
                "surface": rule["surface"],
                "risk_band": rule["risk_band"],
                "reason": rule["reason"],
                "proof_command": rule["proof_command"],
            }
        )

    return sorted(rows, key=lambda row: (row["surface"], row["path"]))


def _protected_surface_commands(changes: list[dict[str, str]]) -> list[str]:
    commands = [
        "python -m sdetkit adaptive sentinel scan --format json --no-fail",
        "python -m pre_commit run -a",
    ]
    for row in changes:
        command = row.get("proof_command", "")
        if command and command not in commands:
            commands.append(command)
    return commands[:6]


def _inspect_protected_surface_changes(
    changes: list[dict[str, str]],
) -> dict[str, Any] | None:
    if not changes:
        return None

    surfaces = sorted({row["surface"] for row in changes})

    evidence = [f"surfaces={','.join(surfaces)} changed_paths={len(changes)}"]
    evidence.extend(
        f"{row['path']} surface={row['surface']} risk={row['risk_band']}" for row in changes[:12]
    )

    return _finding(
        source="protected_surface_changes",
        title="Protected surface change detected",
        summary=(
            "Adaptive Sentinel detected changes to protected repo surfaces: "
            f"{', '.join(surfaces)}. Treat this as review-first risk evidence."
        ),
        state="warning",
        evidence=evidence,
        commands=_protected_surface_commands(changes),
    )


def _artifact_candidates(root: Path) -> dict[str, list[Path]]:
    return {
        "adaptive_failure_bundle": [
            root / "build/sdetkit/failure-intelligence/failure-intelligence-bundle.json",
            root / "build/pr-quality/failure-intelligence/failure-intelligence-bundle.json",
        ],
        "investigation_failure": [
            root / "build/investigation/failure.json",
        ],
        "doctor_diagnosis": [
            root / "build/doctor-diagnosis.json",
            root / "build/mission-control/doctor-cortex-diagnosis.json",
        ],
        "doctor_prescriptions": [
            root / "build/doctor-prescriptions.json",
            root / "build/mission-control/doctor-cortex-prescriptions.json",
        ],
        "mission_control": [
            root / "build/mission-control/mission-control.json",
        ],
        "quality_verdict": [
            root / ".sdetkit/out/quality-verdict.json",
        ],
    }


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _git_status(root: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "dirty": False,
            "error": str(exc),
            "changed_paths": [],
        }

    if proc.returncode != 0:
        return {
            "available": False,
            "dirty": False,
            "error": proc.stderr.strip()[:300],
            "changed_paths": [],
        }

    changed = [line[3:] for line in proc.stdout.splitlines() if len(line) >= 4]
    return {
        "available": True,
        "dirty": bool(changed),
        "changed_paths": changed[:50],
    }


def _finding(
    *,
    source: str,
    state: str,
    title: str,
    summary: str,
    evidence: list[str] | None = None,
    commands: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "state": state,
        "title": title,
        "summary": summary,
        "evidence": evidence or [],
        "recommended_commands": commands or [],
    }


def _source_record(name: str, path: Path | None, present: bool, error: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "present": present,
        "path": path.as_posix() if path else "",
        "error": error,
    }


def _inspect_failure_bundle(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status", "unknown"))
    primary = str(payload.get("primary_diagnosis_code", "") or "")
    diagnosis_count = int(payload.get("diagnosis_count", 0) or 0)
    review_first = bool(payload.get("review_first", False))
    safe_to_auto_fix = bool(payload.get("safe_to_auto_fix", False))

    if status in {"clear", "monitor"} and diagnosis_count == 0 and not review_first:
        state = "healthy" if status == "clear" else "watch"
        summary = "Adaptive failure bundle is clear."
    elif review_first or primary in {"UNKNOWN", "UNKNOWN_REVIEW_REQUIRED"}:
        state = "critical"
        summary = "Adaptive failure bundle is review-first and must not be automated."
    elif status == "needs_fix":
        state = "warning"
        summary = "Adaptive failure bundle identified a fixable failure path."
    else:
        state = "watch"
        summary = "Adaptive failure bundle should be monitored."

    commands = [
        f"python -m sdetkit doctor --diagnose --failure-bundle {path.as_posix()} --format json",
        "python -m sdetkit mission-control summarize --bundle build/mission-control/mission-control.json",
    ]
    if not safe_to_auto_fix:
        commands.insert(
            0,
            "python -m sdetkit investigate failure --log build/quality.log "
            "--failure-bundle-out-dir build/sdetkit/failure-intelligence --format markdown",
        )

    return _finding(
        source="adaptive_failure_bundle",
        state=state,
        title="Adaptive failure bundle signal",
        summary=summary,
        evidence=[
            f"status={status}",
            f"primary={primary or 'none'}",
            f"diagnosis_count={diagnosis_count}",
            f"review_first={str(review_first).lower()}",
            f"safe_to_auto_fix={str(safe_to_auto_fix).lower()}",
        ],
        commands=commands,
    )


def _inspect_investigation(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    classification = str(payload.get("classification", "") or "")
    if not classification:
        return None

    requires_review = bool(payload.get("requires_human_review", True))
    state = "critical" if classification == "UNKNOWN_REVIEW_REQUIRED" else "warning"
    if not requires_review:
        state = "watch"

    return _finding(
        source="investigation_failure",
        state=state,
        title="Investigation failure signal",
        summary=str(payload.get("summary", "Investigation artifact requires review.")),
        evidence=[
            f"classification={classification}",
            f"requires_human_review={str(requires_review).lower()}",
            f"safe_to_auto_fix={str(payload.get('safe_to_auto_fix', False)).lower()}",
        ],
        commands=_as_list(payload.get("proof_commands"))[:3]
        or ["python -m sdetkit investigate failure --log build/quality.log --format markdown"],
    )


def _inspect_doctor(
    path: Path,
    payload: dict[str, Any],
    *,
    prescriptions: bool = False,
) -> dict[str, Any] | None:
    count_key = "prescription_count" if prescriptions else "diagnosis_count"
    count = int(payload.get(count_key, 0) or 0)
    if count <= 0 and bool(payload.get("ok", True)):
        return None

    noun = "prescription" if prescriptions else "diagnosis"
    return _finding(
        source=f"doctor_{noun}",
        state="warning" if count > 0 else "watch",
        title=f"Doctor Cortex {noun} signal",
        summary=f"Doctor Cortex reported {count} {noun} item(s).",
        evidence=[f"{count_key}={count}", f"path={path.as_posix()}"],
        commands=[
            "python -m sdetkit doctor --diagnose --format json",
            "python -m sdetkit doctor --prescribe --format json",
        ],
    )


def _inspect_mission_control(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    decision = str(payload.get("decision", "") or "")
    failed_step_count = int(payload.get("failed_step_count", 0) or 0)
    findings = _as_list(payload.get("findings"))
    if (
        decision not in {"NO_SHIP", "SHIP_WITH_FINDINGS"}
        and failed_step_count == 0
        and not findings
    ):
        return None

    state = "critical" if decision == "NO_SHIP" or failed_step_count > 0 else "warning"
    return _finding(
        source="mission_control",
        state=state,
        title="Mission Control release signal",
        summary=f"Mission Control decision is {decision or 'unknown'} with {failed_step_count} failed step(s).",
        evidence=[
            f"decision={decision or 'unknown'}",
            f"failed_step_count={failed_step_count}",
            f"finding_count={len(findings)}",
        ],
        commands=[
            f"python -m sdetkit mission-control summarize --bundle {path.as_posix()}",
            "python -m sdetkit mission-control report --bundle build/mission-control/mission-control.json",
        ],
    )


def _inspect_quality_verdict(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    blocking = str(payload.get("blocking_failures", "") or "")
    recommendation = str(
        payload.get("merge_release_recommendation", "") or payload.get("recommendation", "") or ""
    )
    if blocking in {"", "none"} and recommendation in {"", "ready-for-merge-review"}:
        return None

    return _finding(
        source="quality_verdict",
        state="critical" if blocking and blocking != "none" else "warning",
        title="Quality verdict signal",
        summary="Quality verdict is not clean.",
        evidence=[
            f"blocking_failures={blocking or 'unknown'}",
            f"recommendation={recommendation or 'unknown'}",
            f"path={path.as_posix()}",
        ],
        commands=[
            "bash quality.sh cov",
            "python -m sdetkit investigate failure --log build/quality.log --format markdown",
        ],
    )


def _inspect_sources(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for name, candidates in _artifact_candidates(root).items():
        path = _first_existing(candidates)
        if path is None:
            sources.append(_source_record(name, None, False))
            continue

        payload, error = _read_json(path)
        sources.append(_source_record(name, path, payload is not None, error))
        if payload is None:
            findings.append(
                _finding(
                    source=name,
                    state="warning",
                    title="Unreadable sentinel source",
                    summary=f"Sentinel found {name} but could not read it.",
                    evidence=[f"path={path.as_posix()}", f"error={error}"],
                    commands=["Inspect or regenerate the artifact before trusting it."],
                )
            )
            continue

        finding: dict[str, Any] | None = None
        if name == "adaptive_failure_bundle":
            finding = _inspect_failure_bundle(path, payload)
        elif name == "investigation_failure":
            finding = _inspect_investigation(path, payload)
        elif name == "doctor_diagnosis":
            finding = _inspect_doctor(path, payload)
        elif name == "doctor_prescriptions":
            finding = _inspect_doctor(path, payload, prescriptions=True)
        elif name == "mission_control":
            finding = _inspect_mission_control(path, payload)
        elif name == "quality_verdict":
            finding = _inspect_quality_verdict(path, payload)

        if finding is not None:
            findings.append(finding)

    return sources, findings


def _rank_recommendations(findings: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    for finding in sorted(
        findings,
        key=lambda item: STATE_RANK.get(str(item.get("state", "healthy")), 0),
        reverse=True,
    ):
        for command in _as_list(finding.get("recommended_commands")):
            if isinstance(command, str) and command and command not in commands:
                commands.append(command)
            if len(commands) >= 8:
                return commands
    return commands


def _finding_fingerprints(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evidence_prefixes = (
        "primary=",
        "classification=",
        "decision=",
        "blocking_failures=",
        "failed_step_count=",
        "diagnosis_count=",
    )

    for finding in findings:
        item = _as_dict(finding)
        source = str(item.get("source", "unknown"))
        state = str(item.get("state", "healthy"))
        title = str(item.get("title", "Sentinel finding"))
        evidence = [str(row) for row in _as_list(item.get("evidence")) if isinstance(row, str)]

        key = "none"
        for prefix in evidence_prefixes:
            match = next((row for row in evidence if row.startswith(prefix)), "")
            if match:
                key = match
                break

        fingerprint = f"{source}|{key}|{title}"
        rows.append(
            {
                "fingerprint": fingerprint,
                "source": source,
                "state": state,
                "title": title,
                "evidence_key": key,
            }
        )

    return rows


def _read_event_history(path: Path, *, limit: int = 200) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except OSError:
        return []

    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _event_fingerprint_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        for row in _as_list(event.get("finding_fingerprints")):
            item = _as_dict(row)
            fingerprint = str(item.get("fingerprint", ""))
            if fingerprint:
                counts[fingerprint] = counts.get(fingerprint, 0) + 1
    return counts


def _build_trend_memory(
    *,
    previous_events: list[dict[str, Any]],
    current_state: str,
    current_findings: list[dict[str, Any]],
    created_at_utc: str,
) -> dict[str, Any]:
    previous_counts = _event_fingerprint_counts(previous_events)
    recurring: list[dict[str, Any]] = []
    escalated: list[dict[str, Any]] = []

    for finding in current_findings:
        fingerprint = str(finding.get("fingerprint", ""))
        if not fingerprint:
            continue

        previous_count = previous_counts.get(fingerprint, 0)
        recurrence_count = previous_count + 1
        source = str(finding.get("source", "unknown"))
        state = str(finding.get("state", "healthy"))
        evidence_key = str(finding.get("evidence_key", "none"))

        reason = ""
        escalation_state = "watch"
        if "UNKNOWN_REVIEW_REQUIRED" in fingerprint and recurrence_count >= 2:
            reason = "persistent_unknown_review_required"
            escalation_state = "critical"
        elif source == "quality_verdict" and recurrence_count >= 3:
            reason = "quality_regression_loop"
            escalation_state = "critical"
        elif state == "critical" and recurrence_count >= 2:
            reason = "persistent_critical_signal"
            escalation_state = "critical"
        elif recurrence_count >= 3:
            reason = "recurring_failure"
            escalation_state = "warning"

        if not reason:
            continue

        row = {
            "fingerprint": fingerprint,
            "source": source,
            "state": state,
            "evidence_key": evidence_key,
            "recurrence_count": recurrence_count,
            "previous_count": previous_count,
            "reason": reason,
            "trend_state": escalation_state,
        }
        recurring.append(row)
        if escalation_state in {"warning", "critical"}:
            escalated.append(row)

    trend_state = _max_state(*(str(item.get("trend_state", "healthy")) for item in escalated))
    if not escalated:
        trend_state = "healthy"

    max_recurrence = max(
        [int(item.get("recurrence_count", 1) or 1) for item in recurring],
        default=1,
    )
    base = STATE_RANK.get(current_state, 0) * 20
    recurrence_bonus = max(0, max_recurrence - 1) * 15
    critical_bonus = 25 if trend_state == "critical" else 0
    threat_score = min(100, base + recurrence_bonus + critical_bonus)

    if current_state == "healthy" and trend_state == "healthy":
        threat_score = 0

    return {
        "schema_version": TREND_SCHEMA_VERSION,
        "created_at_utc": created_at_utc,
        "current_state": current_state,
        "trend_state": trend_state,
        "threat_score": threat_score,
        "event_count": len(previous_events) + 1,
        "previous_event_count": len(previous_events),
        "current_finding_fingerprint_count": len(current_findings),
        "recurring_finding_count": len(recurring),
        "escalated_finding_count": len(escalated),
        "top_recurring_findings": sorted(
            recurring,
            key=lambda item: (
                int(item.get("recurrence_count", 0) or 0),
                STATE_RANK.get(str(item.get("trend_state", "healthy")), 0),
                str(item.get("source", "")),
            ),
            reverse=True,
        )[:10],
        "escalated_findings": sorted(
            escalated,
            key=lambda item: (
                STATE_RANK.get(str(item.get("trend_state", "healthy")), 0),
                int(item.get("recurrence_count", 0) or 0),
            ),
            reverse=True,
        )[:10],
    }


def render_trend_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adaptive Sentinel Trend Memory",
        "",
        f"- Trend state: **{payload.get('trend_state', 'unknown')}**",
        f"- Threat score: **{payload.get('threat_score', 0)}**",
        f"- Event count: **{payload.get('event_count', 0)}**",
        f"- Recurring findings: **{payload.get('recurring_finding_count', 0)}**",
        f"- Escalated findings: **{payload.get('escalated_finding_count', 0)}**",
        "",
        "## Escalated findings",
    ]
    escalated = _as_list(payload.get("escalated_findings"))
    if not escalated:
        lines.append("- none")
    for row in escalated:
        item = _as_dict(row)
        lines.extend(
            [
                f"- `{item.get('source', 'unknown')}`: "
                f"{item.get('reason', 'recurring')} "
                f"(recurrence={item.get('recurrence_count', 0)}, "
                f"state={item.get('trend_state', 'unknown')})",
                f"  - fingerprint: `{item.get('fingerprint', '')}`",
            ]
        )
    return "\n".join(lines) + "\n"


def build_sentinel_scan(
    *,
    root: str | Path = ".",
    out_dir: str | Path = "build/sdetkit/sentinel",
    event_log: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    out_path = Path(out_dir)
    if not out_path.is_absolute():
        out_path = root_path / out_path

    sources, findings = _inspect_sources(root_path)

    git_status = _git_status(root_path)
    if git_status.get("dirty"):
        findings.append(
            _finding(
                source="git",
                state="watch",
                title="Working tree has local changes",
                summary="Sentinel detected uncommitted work; keep proof tied to the current diff.",
                evidence=[f"changed_paths={len(_as_list(git_status.get('changed_paths')))}"],
                commands=["git status -sb", "git diff --stat"],
            )
        )

    protected_surface_changes = _protected_surface_changes(root_path)
    protected_surface_finding = _inspect_protected_surface_changes(protected_surface_changes)
    if protected_surface_finding is not None:
        findings.append(protected_surface_finding)

    state = _max_state(*(str(item.get("state", "healthy")) for item in findings))
    if not findings:
        findings = [
            _finding(
                source="sentinel",
                state="healthy",
                title="No active sentinel findings",
                summary="No known failure artifacts or degraded repo state were detected.",
                evidence=["no_active_artifact_findings=true"],
                commands=[
                    "bash quality.sh cov",
                    "python -m sdetkit mission-control run --doctor-cortex",
                ],
            )
        ]

    recommendations = _rank_recommendations(findings)
    event_path = (
        Path(event_log)
        if event_log is not None
        else root_path / ".sdetkit/adaptive-sentinel/events.jsonl"
    )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": _utc_now(),
        "root": root_path.as_posix(),
        "state": state,
        "ok": state in {"healthy", "watch"},
        "finding_count": len([item for item in findings if item.get("source") != "sentinel"]),
        "source_count": len(sources),
        "sources": sources,
        "git": git_status,
        "findings": findings,
        "protected_surface_changes": protected_surface_changes,
        "recommendations": recommendations,
        "artifacts": {
            "json": (out_path / "sentinel.json").as_posix(),
            "markdown": (out_path / "sentinel.md").as_posix(),
            "events_jsonl": event_path.as_posix(),
        },
        "automation_allowed_now": False,
        "automation_reason": "Adaptive sentinel is read-only: it watches, classifies, recommends, and records evidence.",
    }

    trend_event_path = Path(str(payload["artifacts"]["events_jsonl"]))
    if not trend_event_path.is_absolute():
        trend_event_path = root_path / trend_event_path

    finding_fingerprints = _finding_fingerprints(findings)
    trend_memory = _build_trend_memory(
        previous_events=_read_event_history(trend_event_path),
        current_state=state,
        current_findings=finding_fingerprints,
        created_at_utc=str(payload["created_at_utc"]),
    )
    payload["trend_memory"] = trend_memory
    payload["trend_state"] = str(trend_memory.get("trend_state", "healthy"))
    payload["threat_score"] = int(trend_memory.get("threat_score", 0) or 0)
    payload["artifacts"]["trend_memory_json"] = (out_path / "trend-memory.json").as_posix()
    payload["artifacts"]["trend_memory_markdown"] = (out_path / "trend-memory.md").as_posix()

    if write:
        _write_json(out_path / "sentinel.json", payload)
        _write_text(out_path / "sentinel.md", render_markdown(payload))
        _write_json(out_path / "trend-memory.json", trend_memory)
        _write_text(out_path / "trend-memory.md", render_trend_markdown(trend_memory))
        if not event_path.is_absolute():
            event_path = root_path / event_path
        _append_jsonl(
            event_path,
            {
                "schema_version": EVENT_SCHEMA_VERSION,
                "created_at_utc": payload["created_at_utc"],
                "state": payload["state"],
                "ok": payload["ok"],
                "finding_count": payload["finding_count"],
                "recommendations": payload["recommendations"][:3],
                "trend_state": payload["trend_state"],
                "threat_score": payload["threat_score"],
                "finding_fingerprints": finding_fingerprints,
                "sentinel_json": payload["artifacts"]["json"],
            },
        )

    return payload


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"state={payload['state']}",
        f"ok={str(payload['ok']).lower()}",
        f"finding_count={payload['finding_count']}",
        f"trend_state={payload.get('trend_state', 'healthy')}",
        f"threat_score={payload.get('threat_score', 0)}",
    ]
    for command in _as_list(payload.get("recommendations"))[:5]:
        lines.append(f"recommendation={command}")
    return "\n".join(lines) + "\n"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adaptive Sentinel",
        "",
        f"- State: **{payload.get('state', 'unknown')}**",
        f"- OK: **{payload.get('ok', False)}**",
        f"- Findings: **{payload.get('finding_count', 0)}**",
        f"- Automation allowed now: **{payload.get('automation_allowed_now', False)}**",
        "",
        "## Findings",
    ]
    for finding in _as_list(payload.get("findings")):
        item = _as_dict(finding)
        lines.extend(
            [
                "",
                f"### {item.get('title', 'Sentinel finding')}",
                f"- source: `{item.get('source', 'unknown')}`",
                f"- state: **{item.get('state', 'unknown')}**",
                f"- summary: {item.get('summary', '')}",
            ]
        )
        evidence = _as_list(item.get("evidence"))
        if evidence:
            lines.append("- evidence:")
            for row in evidence[:6]:
                lines.append(f"  - `{row}`")
    protected = _as_list(payload.get("protected_surface_changes"))
    if protected:
        lines.extend(["", "## Protected surface changes"])
        for row in protected[:8]:
            lines.append(
                "- "
                f"`{row.get('path', '')}` "
                f"surface=`{row.get('surface', 'unknown')}` "
                f"risk=`{row.get('risk_band', 'unknown')}`"
            )

    trend = _as_dict(payload.get("trend_memory"))
    if trend:
        lines.extend(
            [
                "",
                "## Trend memory",
                f"- trend state: **{trend.get('trend_state', 'unknown')}**",
                f"- threat score: **{trend.get('threat_score', 0)}**",
                f"- event count: **{trend.get('event_count', 0)}**",
                f"- recurring findings: **{trend.get('recurring_finding_count', 0)}**",
                f"- escalated findings: **{trend.get('escalated_finding_count', 0)}**",
            ]
        )
        for row in _as_list(trend.get("escalated_findings"))[:5]:
            item = _as_dict(row)
            lines.append(
                f"- escalation: `{item.get('reason', 'recurring')}` "
                f"from `{item.get('source', 'unknown')}` "
                f"(recurrence={item.get('recurrence_count', 0)})"
            )

    lines.extend(["", "## Recommended next commands"])
    for command in _as_list(payload.get("recommendations")):
        lines.append(f"- `{command}`")
    lines.extend(
        [
            "",
            "## Boundary",
            str(payload.get("automation_reason", "")),
        ]
    )
    return "\n".join(lines) + "\n"


def _render(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_format == "md":
        return render_markdown(payload)
    return render_text(payload)


def _scan(args: argparse.Namespace) -> int:
    payload = build_sentinel_scan(
        root=args.root,
        out_dir=args.out_dir,
        event_log=args.event_log or None,
        write=not bool(args.no_write),
    )
    sys.stdout.write(_render(payload, str(args.format)))
    return 0 if bool(payload.get("ok", False)) or bool(args.no_fail) else 1


def _watch(args: argparse.Namespace) -> int:
    iterations = max(1, int(args.iterations))
    last: dict[str, Any] = {}
    for index in range(iterations):
        last = build_sentinel_scan(
            root=args.root,
            out_dir=args.out_dir,
            event_log=args.event_log or None,
            write=not bool(args.no_write),
        )
        if index < iterations - 1:
            time.sleep(max(0.0, float(args.interval_seconds)))
    sys.stdout.write(_render(last, str(args.format)))
    return 0 if bool(last.get("ok", False)) or bool(args.no_fail) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.adaptive_sentinel",
        description="Read-only adaptive sentinel scan/watch loop for repo health signals.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Run one adaptive sentinel scan")
    scan.add_argument("--root", default=".")
    scan.add_argument("--out-dir", default="build/sdetkit/sentinel")
    scan.add_argument("--event-log", default="")
    scan.add_argument("--format", choices=["text", "json", "md"], default="text")
    scan.add_argument("--no-write", action="store_true")
    scan.add_argument("--no-fail", action="store_true")
    scan.set_defaults(func=_scan)

    watch = sub.add_parser("watch", help="Run repeated adaptive sentinel scans")
    watch.add_argument("--root", default=".")
    watch.add_argument("--out-dir", default="build/sdetkit/sentinel")
    watch.add_argument("--event-log", default="")
    watch.add_argument("--interval-seconds", type=float, default=5.0)
    watch.add_argument("--iterations", type=int, default=3)
    watch.add_argument("--format", choices=["text", "json", "md"], default="text")
    watch.add_argument("--no-write", action="store_true")
    watch.add_argument("--no-fail", action="store_true")
    watch.set_defaults(func=_watch)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"adaptive sentinel: error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
