from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import re
import sqlite3
import subprocess
import urllib.parse
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SEVERITY_WEIGHT = {
    "critical": 20,
    "high": 12,
    "medium": 7,
    "low": 3,
    "warn": 6,
    "info": 1,
    "unknown": 5,
}

SEVERITY_RANK = {
    "critical": 6,
    "high": 5,
    "medium": 4,
    "warn": 3,
    "low": 2,
    "info": 1,
    "unknown": 0,
}

REQUIRED_ARTIFACTS = (
    "doctor.json",
    "maintenance.json",
    "security-check.json",
)

RECOMMENDATION_CATALOG: dict[str, tuple[str, str]] = {
    "doctor": (
        "Stabilize developer workflows by enforcing doctor recommendations in CI.",
        "Add a CI required check for doctor threshold and fix unstable project hygiene.",
    ),
    "maintenance": (
        "Maintenance checks are failing and may degrade release confidence.",
        "Prioritize failed maintenance checks by severity and blast radius.",
    ),
    "security": (
        "Security findings are present in control-plane inputs.",
        "Address high/critical vulnerabilities before enabling broad rollout.",
    ),
    "engine:artifact-integrity": (
        "Gate artifacts are incomplete or unreadable.",
        "Regenerate gate outputs and block release until artifact integrity is green.",
    ),
    "engine:step-failures": (
        "Premium gate step failure markers found.",
        "Inspect corresponding step logs and rerun premium gate after remediation.",
    ),
    "engine:determinism": (
        "Signal regeneration produced non-deterministic counts.",
        "Investigate unstable data sources and enforce deterministic ordering.",
    ),
    "security:SEC_SECRET_PATTERN": (
        "Potential secret exposure detected.",
        "Rotate credentials, scrub history, and enforce secret scanning pre-commit.",
    ),
    "security:SEC_SUBPROCESS_SHELL_TRUE": (
        "Subprocess shell invocation risk detected.",
        "Replace shell=True with shell=False or structured argument invocation.",
    ),
    "security:SEC_REQUESTS_NO_TIMEOUT": (
        "Network calls without timeout threaten reliability.",
        "Add explicit timeout and retry policy with breaker guardrails.",
    ),
    "security:SEC_YAML_LOAD": (
        "Unsafe yaml.load usage detected.",
        "Replace yaml.load with yaml.safe_load where behavior allows.",
    ),
}


@dataclass(frozen=True)
class Signal:
    source: str
    category: str
    severity: str
    message: str
    fingerprint: str


@dataclass(frozen=True)
class StepStatus:
    name: str
    ok: bool
    log_path: str
    details: str
    warnings_count: int


@dataclass(frozen=True)
class SourceResult:
    source: str
    warnings: list[Signal]
    recommendations: list[Signal]
    checks: list[Signal]


@dataclass(frozen=True)
class AutoFixResult:
    rule_id: str
    path: str
    status: str
    message: str


@dataclass(frozen=True)
class FixPlanItem:
    rule_id: str
    path: str
    priority: str
    reason: str
    suggested_edit: str


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_severity(raw: str) -> str:
    key = raw.lower().strip() if raw else "unknown"
    return key if key in SEVERITY_WEIGHT else "unknown"


def _fingerprint(parts: Iterable[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _make_signal(source: str, category: str, severity: str, message: str) -> Signal:
    sev = _normalize_severity(severity)
    msg = _safe_text(message) or "unspecified"
    return Signal(source, category, sev, msg, _fingerprint((source, category, sev, msg)))


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_doctor(payload: dict[str, Any]) -> SourceResult:
    warnings: list[Signal] = []
    recommendations: list[Signal] = []
    checks: list[Signal] = []

    node = payload.get("checks")
    if isinstance(node, dict):
        for name, item in node.items():
            if not isinstance(item, dict) or item.get("ok", True):
                continue
            warnings.append(
                _make_signal(
                    "doctor",
                    _safe_text(name) or "check",
                    _safe_text(item.get("severity", "unknown")),
                    _safe_text(item.get("message", "failed check")),
                )
            )

    for rec in payload.get("recommendations", []):
        recommendations.append(_make_signal("doctor", "recommendation", "info", _safe_text(rec)))

    if isinstance(payload.get("score"), int) and payload["score"] < 70:
        checks.append(
            _make_signal(
                "doctor", "score-threshold", "warn", f"doctor score low: {payload['score']}%"
            )
        )

    return SourceResult("doctor", warnings, recommendations, checks)


def _parse_maintenance(payload: dict[str, Any]) -> SourceResult:
    warnings: list[Signal] = []
    recommendations: list[Signal] = []
    checks: list[Signal] = []

    for item in payload.get("checks", []):
        if not isinstance(item, dict) or item.get("ok", True):
            continue
        warnings.append(
            _make_signal(
                "maintenance",
                _safe_text(item.get("name", "unknown")),
                _safe_text(item.get("severity", "unknown")),
                _safe_text(item.get("summary", "failed check")),
            )
        )

    for rec in payload.get("recommendations", []):
        recommendations.append(
            _make_signal("maintenance", "recommendation", "info", _safe_text(rec))
        )

    if isinstance(payload.get("score"), int) and payload["score"] < 70:
        checks.append(
            _make_signal(
                "maintenance",
                "score-threshold",
                "warn",
                f"maintenance score low: {payload['score']}%",
            )
        )

    return SourceResult("maintenance", warnings, recommendations, checks)


def _parse_security(payload: dict[str, Any]) -> SourceResult:
    warnings: list[Signal] = []
    checks: list[Signal] = []

    for item in payload.get("findings", []):
        if not isinstance(item, dict):
            continue
        rule = _safe_text(item.get("rule_id") or item.get("rule") or "finding")
        path = _safe_text(item.get("path"))
        line = _safe_text(item.get("line"))
        msg = " ".join(x for x in [rule, path, f"line={line}" if line else ""] if x)
        warnings.append(
            _make_signal("security", rule, _safe_text(item.get("severity", "unknown")), msg)
        )

    totals = payload.get("totals")
    if isinstance(totals, dict):
        if int(totals.get("critical", 0)) > 0:
            checks.append(
                _make_signal(
                    "security",
                    "critical-findings",
                    "critical",
                    f"critical findings: {totals.get('critical', 0)}",
                )
            )
        if int(totals.get("high", 0)) > 0:
            checks.append(
                _make_signal(
                    "security", "high-findings", "high", f"high findings: {totals.get('high', 0)}"
                )
            )

    return SourceResult("security", warnings, [], checks)


def _scan_step_logs(out_dir: Path) -> list[StepStatus]:
    statuses: list[StepStatus] = []
    for log in sorted(out_dir.glob("premium-gate.*.log")):
        text = log.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        failed = "error: step failed" in low or "traceback" in low
        wc = low.count("warning") + low.count("⚠️")
        details = (
            "failure markers found in log"
            if failed
            else (f"contains warning output ({wc})" if wc > 0 else "ok")
        )
        statuses.append(
            StepStatus(
                log.name.removeprefix("premium-gate.").removesuffix(".log"),
                not failed,
                str(log),
                details,
                wc,
            )
        )
    return statuses


def _dedupe(signals: list[Signal]) -> list[Signal]:
    seen: set[str] = set()
    out: list[Signal] = []
    for s in signals:
        if s.fingerprint in seen:
            continue
        seen.add(s.fingerprint)
        out.append(s)
    return out


def _rank(signals: list[Signal]) -> list[Signal]:
    return sorted(
        signals, key=lambda s: (-SEVERITY_RANK.get(s.severity, 0), s.source, s.category, s.message)
    )


def _score(warnings: list[Signal], checks: list[Signal], steps: list[StepStatus]) -> int:
    penalty = sum(
        SEVERITY_WEIGHT.get(s.severity, SEVERITY_WEIGHT["unknown"]) for s in [*warnings, *checks]
    )
    penalty += sum(14 for st in steps if not st.ok)
    penalty += sum(2 for st in steps if st.ok and st.warnings_count > 0)
    return max(0, 100 - min(99, penalty))


def _required_artifacts(out_dir: Path) -> tuple[dict[str, bool], list[Signal]]:
    status: dict[str, bool] = {}
    checks: list[Signal] = []
    for name in REQUIRED_ARTIFACTS:
        ok = (out_dir / name).exists()
        status[name] = ok
        if not ok:
            checks.append(_make_signal("engine", "required-artifact", "warn", f"missing {name}"))
    return status, checks


def _source_digest(out_dir: Path) -> str:
    chunks: list[str] = []
    for name in REQUIRED_ARTIFACTS:
        p = out_dir / name
        chunks.append(
            f"{name}:{hashlib.sha256(p.read_bytes()).hexdigest()}"
            if p.exists()
            else f"{name}:missing"
        )
    for log in sorted(out_dir.glob("premium-gate.*.log")):
        chunks.append(f"{log.name}:{hashlib.sha256(log.read_bytes()).hexdigest()}")
    return hashlib.sha256("|".join(chunks).encode("utf-8")).hexdigest()


def _knowledge_recommendations(
    warnings: list[Signal], checks: list[Signal], steps: list[StepStatus]
) -> list[Signal]:
    recs: list[Signal] = []
    for s in [*warnings, *checks]:
        key = f"{s.source}:{s.category}"
        if key in RECOMMENDATION_CATALOG:
            a, b = RECOMMENDATION_CATALOG[key]
            recs.append(_make_signal("engine", "playbook", s.severity, f"{a} {b}"))
        elif s.source in RECOMMENDATION_CATALOG:
            a, b = RECOMMENDATION_CATALOG[s.source]
            recs.append(_make_signal("engine", "playbook", s.severity, f"{a} {b}"))

    if any(not st.ok for st in steps):
        a, b = RECOMMENDATION_CATALOG["engine:step-failures"]
        recs.append(_make_signal("engine", "step-failures", "high", f"{a} {b}"))
    if checks:
        a, b = RECOMMENDATION_CATALOG["engine:artifact-integrity"]
        recs.append(_make_signal("engine", "artifact-integrity", "high", f"{a} {b}"))

    high_sec = [
        w for w in warnings if w.source == "security" and w.severity in {"high", "critical"}
    ]
    if high_sec:
        a, b = RECOMMENDATION_CATALOG["security"]
        recs.append(_make_signal("engine", "security-priority", "high", f"{a} {b}"))

    return _rank(_dedupe(recs))


def _autofix_timeout(text: str) -> tuple[str, bool]:
    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        call = match.group(0)
        if "timeout=" in call:
            return call
        changed = True
        return call[:-1] + ", timeout=10)"

    pattern = re.compile(r"requests\.(?:get|post|put|delete|patch|head|options)\([^\n\)]*\)")
    return pattern.sub(repl, text), changed


def _autofix_shell_true(text: str) -> tuple[str, bool]:
    new = text.replace("shell=True", "shell=False")
    return new, new != text


def _autofix_yaml_load(text: str) -> tuple[str, bool]:
    new = text.replace("yaml.load(", "yaml.safe_load(")
    return new, new != text


def _apply_autofix_for_finding(root: Path, finding: dict[str, Any]) -> AutoFixResult:
    rule = _safe_text(finding.get("rule_id") or finding.get("rule") or "")
    rel_path = _safe_text(finding.get("path"))
    if not rel_path:
        return AutoFixResult(rule, "", "skipped", "no file path in finding")

    target = (root / rel_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return AutoFixResult(rule, rel_path, "skipped", "path escapes fix root")

    if not target.exists() or not target.is_file():
        return AutoFixResult(rule, rel_path, "skipped", "target file missing")

    text = target.read_text(encoding="utf-8", errors="replace")
    patched = text
    changed = False

    if rule == "SEC_REQUESTS_NO_TIMEOUT":
        patched, changed = _autofix_timeout(text)
    elif rule == "SEC_SUBPROCESS_SHELL_TRUE":
        patched, changed = _autofix_shell_true(text)
    elif rule in {"SEC_YAML_LOAD", "SEC_YAML_UNSAFE_LOAD"}:
        patched, changed = _autofix_yaml_load(text)
    else:
        return AutoFixResult(rule, rel_path, "manual", "no safe auto-fix handler for this rule")

    if not changed:
        return AutoFixResult(rule, rel_path, "manual", "auto-fix handler found no editable pattern")

    target.write_text(patched, encoding="utf-8")
    return AutoFixResult(rule, rel_path, "fixed", "applied safe auto-fix")


def _build_fix_plan_item(result: AutoFixResult) -> FixPlanItem:
    rule = result.rule_id or "UNKNOWN"
    base_reason = result.message if result.message else "manual intervention required"
    if rule == "SEC_SECRET_PATTERN":
        edit = "Rotate leaked secret, remove hardcoded token, and add environment/secret manager reference."
        priority = "critical"
    elif rule == "SEC_SUBPROCESS_SHELL_TRUE":
        edit = "Replace shell invocation with argument list and shell=False; validate escaping and command boundaries."
        priority = "high"
    elif rule == "SEC_REQUESTS_NO_TIMEOUT":
        edit = "Add explicit timeout and retry policy to requests call; verify caller handles timeout exceptions."
        priority = "high"
    elif rule in {"SEC_YAML_LOAD", "SEC_YAML_UNSAFE_LOAD"}:
        edit = "Replace yaml.load with yaml.safe_load and validate schema/shape of parsed data."
        priority = "high"
    else:
        edit = "Follow engine playbook recommendation for this rule and create a focused patch with tests."
        priority = "medium"
    return FixPlanItem(
        rule_id=rule, path=result.path, priority=priority, reason=base_reason, suggested_edit=edit
    )


def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS insights_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                commit_sha TEXT,
                score INTEGER NOT NULL,
                warnings_count INTEGER NOT NULL,
                recommendations_count INTEGER NOT NULL,
                checks_count INTEGER NOT NULL,
                source_digest TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guidelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commit_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                commit_sha TEXT NOT NULL,
                message TEXT NOT NULL,
                changed_files_json TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT ''
            )
            """
        )


def _git_commit_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def persist_insights(payload: dict[str, Any], db_path: Path, commit_sha: str | None = None) -> int:
    _init_db(db_path)
    resolved_sha = _safe_text(commit_sha) or _git_commit_sha()
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO insights_runs (
                commit_sha, score, warnings_count, recommendations_count, checks_count, source_digest, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_sha,
                int(payload.get("score", 0)),
                int(payload.get("counts", {}).get("warnings", 0)),
                int(payload.get("counts", {}).get("recommendations", 0)),
                int(payload.get("counts", {}).get("engine_checks", 0)),
                _safe_text(payload.get("source_digest")),
                json.dumps(payload, sort_keys=True),
            ),
        )
        return int(cur.lastrowid or 0)


def add_guideline(
    db_path: Path, title: str, body: str, tags: list[str], source: str = "manual"
) -> int:
    _init_db(db_path)
    clean_tags = ",".join(sorted({_safe_text(tag) for tag in tags if _safe_text(tag)}))
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO guidelines (title, body, tags, source) VALUES (?, ?, ?, ?)",
            (_safe_text(title), _safe_text(body), clean_tags, _safe_text(source) or "manual"),
        )
        return int(cur.lastrowid or 0)


def update_guideline(
    db_path: Path, guideline_id: int, title: str, body: str, tags: list[str], active: bool = True
) -> bool:
    _init_db(db_path)
    clean_tags = ",".join(sorted({_safe_text(tag) for tag in tags if _safe_text(tag)}))
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE guidelines
            SET title = ?, body = ?, tags = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (_safe_text(title), _safe_text(body), clean_tags, 1 if active else 0, guideline_id),
        )
        return cur.rowcount > 0


def list_guidelines(
    db_path: Path, active_only: bool = True, limit: int = 100
) -> list[dict[str, Any]]:
    _init_db(db_path)
    query = "SELECT id, created_at, updated_at, title, body, tags, source, active FROM guidelines"
    params: tuple[Any, ...] = ()
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
    params = (max(1, min(limit, 500)),)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": int(row[0]),
            "created_at": row[1],
            "updated_at": row[2],
            "title": row[3],
            "body": row[4],
            "tags": [x for x in _safe_text(row[5]).split(",") if x],
            "source": row[6],
            "active": bool(row[7]),
        }
        for row in rows
    ]


def record_commit_learning(
    db_path: Path, commit_sha: str, message: str, changed_files: list[str], summary: str = ""
) -> int:
    _init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO commit_learning (commit_sha, message, changed_files_json, summary)
            VALUES (?, ?, ?, ?)
            """,
            (
                _safe_text(commit_sha) or "unknown",
                _safe_text(message) or "no message",
                json.dumps(sorted({_safe_text(x) for x in changed_files if _safe_text(x)})),
                _safe_text(summary),
            ),
        )
        return int(cur.lastrowid or 0)


def _autolearn_from_payload(db_path: Path, payload: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    for rec in payload.get("recommendations", []):
        if not isinstance(rec, dict):
            continue
        title = f"{_safe_text(rec.get('source'))}:{_safe_text(rec.get('category'))}"
        body = _safe_text(rec.get("message"))
        if not title or not body:
            continue
        ids.append(
            add_guideline(
                db_path, title, body, ["auto", _safe_text(rec.get("severity"))], source="engine"
            )
        )
    return ids


class _InsightsHandler(http.server.BaseHTTPRequestHandler):
    db_path: Path
    out_dir: Path
    server_version = "sdetkit-premium-insights/1.0"

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_payload(self) -> dict[str, Any]:
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"ok": True})
            return
        if parsed.path == "/guidelines":
            q = urllib.parse.parse_qs(parsed.query)
            active = q.get("active", ["1"])[0] != "0"
            limit = int(q.get("limit", ["100"])[0])
            self._json(
                200, {"guidelines": list_guidelines(self.db_path, active_only=active, limit=limit)}
            )
            return
        if parsed.path == "/analyze":
            payload = collect_signals(self.out_dir)
            run_id = persist_insights(payload, self.db_path)
            self._json(200, {"run_id": run_id, "payload": payload})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        body = self._read_payload()
        if parsed.path == "/guidelines":
            guideline_id = add_guideline(
                self.db_path,
                _safe_text(body.get("title")),
                _safe_text(body.get("body")),
                body.get("tags", []) if isinstance(body.get("tags"), list) else [],
                source=_safe_text(body.get("source")) or "manual",
            )
            self._json(201, {"id": guideline_id})
            return
        if parsed.path == "/learn-commit":
            learning_id = record_commit_learning(
                self.db_path,
                _safe_text(body.get("commit_sha")) or _git_commit_sha(),
                _safe_text(body.get("message")),
                body.get("changed_files", [])
                if isinstance(body.get("changed_files"), list)
                else [],
                summary=_safe_text(body.get("summary")),
            )
            self._json(201, {"id": learning_id})
            return
        self._json(404, {"error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 2 and parts[0] == "guidelines" and parts[1].isdigit():
            body = self._read_payload()
            ok = update_guideline(
                self.db_path,
                int(parts[1]),
                _safe_text(body.get("title")),
                _safe_text(body.get("body")),
                body.get("tags", []) if isinstance(body.get("tags"), list) else [],
                active=bool(body.get("active", True)),
            )
            self._json(200 if ok else 404, {"ok": ok})
            return
        self._json(404, {"error": "not found"})


def serve_insights_api(host: str, port: int, out_dir: Path, db_path: Path) -> None:
    _InsightsHandler.db_path = db_path
    _InsightsHandler.out_dir = out_dir
    _init_db(db_path)
    server = http.server.ThreadingHTTPServer((host, port), _InsightsHandler)
    server.serve_forever()


def run_autofix(out_dir: Path, fix_root: Path) -> list[AutoFixResult]:
    security_payload = _load_json(out_dir / "security-check.json")
    if not security_payload:
        return [AutoFixResult("", "", "skipped", "security-check.json missing or invalid")]

    results: list[AutoFixResult] = []
    for finding in security_payload.get("findings", []):
        if isinstance(finding, dict):
            results.append(_apply_autofix_for_finding(fix_root, finding))
    return results


def collect_signals(out_dir: Path) -> dict[str, Any]:
    warnings: list[Signal] = []
    recommendations: list[Signal] = []
    checks: list[Signal] = []

    sources = {
        "doctor": (out_dir / "doctor.json", _parse_doctor),
        "maintenance": (out_dir / "maintenance.json", _parse_maintenance),
        "security": (out_dir / "security-check.json", _parse_security),
    }

    for source, (path, parser) in sources.items():
        payload = _load_json(path)
        if payload is None:
            checks.append(
                _make_signal(
                    "engine", f"{source}_artifact", "warn", f"{path.name} missing or invalid"
                )
            )
            continue
        parsed = parser(payload)
        warnings.extend(parsed.warnings)
        recommendations.extend(parsed.recommendations)
        checks.extend(parsed.checks)

    required, required_checks = _required_artifacts(out_dir)
    checks.extend(required_checks)

    steps = _scan_step_logs(out_dir)
    if not steps:
        checks.append(_make_signal("engine", "step-logs", "warn", "no premium step logs found"))

    warnings = _rank(_dedupe(warnings))
    checks = _rank(_dedupe(checks))

    recommendations.extend(_knowledge_recommendations(warnings, checks, steps))
    recommendations = _rank(_dedupe(recommendations))

    hotspots: dict[str, int] = {}
    for w in warnings:
        hotspots[w.source] = hotspots.get(w.source, 0) + 1

    return {
        "ok": not warnings and not checks and all(st.ok for st in steps),
        "score": _score(warnings, checks, steps),
        "warnings": [asdict(s) for s in warnings],
        "recommendations": [asdict(s) for s in recommendations],
        "engine_checks": [asdict(s) for s in checks],
        "step_status": [asdict(s) for s in steps],
        "required_artifacts": required,
        "hotspots": hotspots,
        "source_digest": _source_digest(out_dir),
        "counts": {
            "warnings": len(warnings),
            "recommendations": len(recommendations),
            "engine_checks": len(checks),
            "steps": len(steps),
        },
        "five_heads": {
            "head_1_ingest": "artifact + log loading and normalization",
            "head_2_analyze": "severity weighting, ranking, hotspots, and score",
            "head_3_autofix": "safe rule-based automatic remediation",
            "head_4_plan": "manual follow-up plan with exact suggested edits",
            "head_5_trust": "determinism check + source digest + minimum-score gating",
        },
    }


def _apply_learned_guideline_actions(payload: dict[str, Any], db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return payload

    guidelines = list_guidelines(db_path, active_only=True, limit=10000)
    if not guidelines:
        return payload

    warnings = payload.get("warnings", [])
    rec_signals: list[Signal] = []
    for item in payload.get("recommendations", []):
        if not isinstance(item, dict):
            continue
        rec_signals.append(
            _make_signal(
                _safe_text(item.get("source")) or "engine",
                _safe_text(item.get("category")) or "recommendation",
                _safe_text(item.get("severity")) or "info",
                _safe_text(item.get("message")),
            )
        )

    action_plan = list(payload.get("manual_fix_plan", []))

    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        key = f"{_safe_text(warning.get('source'))}:{_safe_text(warning.get('category'))}"
        severity = _safe_text(warning.get("severity")) or "warn"
        for guideline in guidelines:
            title = _safe_text(guideline.get("title"))
            tags = (
                set(guideline.get("tags", [])) if isinstance(guideline.get("tags"), list) else set()
            )
            if title != key and key not in tags and severity not in tags:
                continue
            body = _safe_text(guideline.get("body"))
            if not body:
                continue
            rec_signals.append(
                _make_signal(
                    "engine",
                    "learned-guideline",
                    severity,
                    f"Apply learned guideline '{title}': {body}",
                )
            )
            action_plan.append(
                {
                    "rule_id": key or "LEARNED",
                    "path": _safe_text(warning.get("message")),
                    "priority": severity,
                    "reason": "Learned guideline match",
                    "suggested_edit": body,
                }
            )

    out = dict(payload)
    deduped = _rank(_dedupe(rec_signals))
    out["recommendations"] = [asdict(s) for s in deduped]
    if action_plan:
        out["manual_fix_plan"] = action_plan
    out["counts"] = {**out.get("counts", {}), "recommendations": len(out["recommendations"])}
    return out


def _apply_double_check(payload: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    if payload["counts"] == second["counts"] and payload.get("source_digest") == second.get(
        "source_digest"
    ):
        return payload
    out = dict(payload)
    checks = list(out["engine_checks"])
    checks.append(
        asdict(
            _make_signal(
                "engine",
                "determinism",
                "warn",
                "non-deterministic signal counts or digest between two reads",
            )
        )
    )
    out["engine_checks"] = checks
    out["counts"] = {**out["counts"], "engine_checks": len(checks)}
    out["ok"] = False
    return out


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"premium gate intelligence score: {payload['score']}%",
        "connector status: unified check graph assembled",
        f"source digest: {payload.get('source_digest', 'n/a')[:16]}",
    ]
    if payload["ok"]:
        lines.append("✅ no active warnings detected")

    if payload.get("hotspots"):
        lines.append("risk hotspots:")
        for source, count in sorted(payload["hotspots"].items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"- {source}: {count}")

    if payload["step_status"]:
        lines.append("step status:")
        for st in payload["step_status"][:30]:
            icon = "✅" if st["ok"] else "❌"
            lines.append(f"- {icon} {st['name']} ({st['details']})")

    if payload["engine_checks"]:
        lines.append("engine double-checks:")
        for item in payload["engine_checks"][:30]:
            lines.append(f"- ⚠️ {item['category']}: {item['message']}")

    if payload["warnings"]:
        lines.append("active warnings:")
        for item in payload["warnings"][:30]:
            lines.append(
                f"- ⚠️ {item['source']}:{item['category']} [{item['severity']}] {item['message']}"
            )

    if payload["recommendations"]:
        lines.append("top recommendations:")
        for item in payload["recommendations"][:30]:
            lines.append(
                f"- 💡 {item['source']}:{item['category']} [{item['severity']}] {item['message']}"
            )

    if payload.get("manual_fix_plan"):
        lines.append("manual follow-up plan:")
        for item in payload["manual_fix_plan"][:20]:
            lines.append(
                f"- 🔧 {item['priority']} {item['rule_id']} {item['path']}: {item['suggested_edit']}"
            )

    return "\n".join(lines)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# premium gate brain report",
        f"- score: **{payload['score']}%**",
        f"- source digest: `{payload.get('source_digest', 'n/a')[:16]}`",
        "",
        "## five heads",
    ]
    for key, val in payload.get("five_heads", {}).items():
        lines.append(f"- **{key}**: {val}")
    lines.append("")
    lines.append("## warnings")
    if payload.get("warnings"):
        for item in payload["warnings"][:30]:
            lines.append(
                f"- ⚠️ `{item['source']}:{item['category']}` ({item['severity']}): {item['message']}"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## recommendations")
    if payload.get("recommendations"):
        for item in payload["recommendations"][:30]:
            lines.append(
                f"- 💡 `{item['source']}:{item['category']}` ({item['severity']}): {item['message']}"
            )
    else:
        lines.append("- none")
    if payload.get("manual_fix_plan"):
        lines.append("")
        lines.append("## manual fix plan")
        for item in payload["manual_fix_plan"][:20]:
            lines.append(
                f"- 🔧 `{item['priority']}` `{item['rule_id']}` `{item['path']}` — {item['suggested_edit']}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit-premium-gate-engine")
    parser.add_argument("--out-dir", default=".sdetkit/out")
    parser.add_argument("--db-path", default=".sdetkit/out/premium-insights.db")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--double-check", action="store_true")
    parser.add_argument("--min-score", type=int, default=None)
    parser.add_argument("--auto-fix", action="store_true")
    parser.add_argument("--fix-root", default=".")
    parser.add_argument("--learn-db", action="store_true")
    parser.add_argument("--learn-commit", action="store_true")
    parser.add_argument("--serve-api", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8799)
    ns = parser.parse_args(argv)

    out_dir = Path(ns.out_dir)
    db_path = Path(ns.db_path)

    if ns.serve_api:
        serve_insights_api(str(ns.host), int(ns.port), out_dir, db_path)
        return 0

    payload = collect_signals(out_dir)
    payload = _apply_learned_guideline_actions(payload, db_path)

    if ns.double_check:
        payload = _apply_double_check(payload, collect_signals(out_dir))

    if ns.auto_fix:
        fixes = run_autofix(out_dir, Path(ns.fix_root))
        payload = dict(payload)
        payload["auto_fix_results"] = [asdict(x) for x in fixes]
        manual_plan = [
            asdict(_build_fix_plan_item(item))
            for item in fixes
            if item.status in {"manual", "skipped"}
        ]
        if manual_plan:
            payload["manual_fix_plan"] = manual_plan
        if any(x.status in {"manual", "skipped"} for x in fixes):
            payload.setdefault("recommendations", []).append(
                asdict(
                    _make_signal(
                        "engine",
                        "manual-followup",
                        "high",
                        "Auto-fix could not resolve all findings. Follow engine playbook recommendations and patch files manually.",
                    )
                )
            )

    if ns.json_output:
        Path(ns.json_output).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if ns.learn_db:
        persist_insights(payload, db_path)
        _autolearn_from_payload(db_path, payload)

    if ns.learn_commit:
        sha = _git_commit_sha()
        commit_message = ""
        changed_files: list[str] = []
        try:
            msg = subprocess.run(
                ["git", "log", "-1", "--pretty=%s"], check=True, capture_output=True, text=True
            )
            commit_message = msg.stdout.strip()
            files = subprocess.run(
                ["git", "show", "--name-only", "--pretty=", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            changed_files = [line.strip() for line in files.stdout.splitlines() if line.strip()]
        except Exception:
            commit_message = "unknown"
        record_commit_learning(
            db_path, sha, commit_message, changed_files, summary=f"score={payload.get('score', 0)}"
        )

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif ns.format == "markdown":
        print(render_markdown(payload))
    else:
        print(render_text(payload))

    if ns.min_score is not None and payload["score"] < ns.min_score:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
