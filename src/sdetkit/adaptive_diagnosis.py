from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.diagnosis.v1"
SEVERITY_SCORE = {"high": 30, "medium": 18, "low": 8, "info": 3}
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}
CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}
SAFE_RUFF_FIXABLE_RULES = {"F401", "I001"}
SAFE_AUTO_FIX_CODES = {"PRE_COMMIT_FORMAT_DRIFT", "RUFF_FIXABLE_LINT"}
RUFF_RULE_RE = re.compile(r"\b([A-Z]\d{3})\b")
ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_.-])(?:/[A-Za-z0-9_@%+=:,./-]+)+")
WIN_PATH_RE = re.compile(r"[A-Za-z]:\\\\[^\s`'\"]+")


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = WIN_PATH_RE.sub("<path>", ABS_PATH_RE.sub("<path>", text))
    text = re.sub(r"secret-[A-Za-z0-9_.-]+", "<redacted>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _safe_list(values: Sequence[Any], limit: int = 6) -> list[str]:
    out: list[str] = []
    for value in values:
        text = _safe(value, 260)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _diag(
    code: str,
    severity: str,
    confidence: str,
    title: str,
    diagnosis: str,
    why: str,
    evidence: Sequence[Any],
    fixes: Sequence[str],
    commands: Sequence[str],
    risk: str,
    signal: str,
    *,
    repeat_count: int = 0,
    files: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "confidence": confidence,
        "title": _safe(title, 160),
        "diagnosis": _safe(diagnosis, 900),
        "why_developers_miss_it": _safe(why, 900),
        "evidence": _safe_list(evidence, 8),
        "recommended_fix": _safe_list(fixes, 8),
        "proof_commands": _safe_list(commands, 8),
        "risk_if_ignored": _safe(risk, 500),
        "learning_signal": _safe(signal, 160),
        "repeat_count": max(0, repeat_count),
        "affected_files": _safe_list(files, 8),
    }


def _file_mentions(text: str) -> list[str]:
    found = re.findall(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.py", text)
    return _safe_list([path for path in found if not path.startswith(("http/", "https/"))], 8)


def _ruff_rule_codes(text: str) -> list[str]:
    codes: list[str] = []
    for code in RUFF_RULE_RE.findall(text):
        if code not in codes:
            codes.append(code)
    return codes[:12]


def _is_safe_ruff_fixable_lint(text: str, codes: Sequence[str]) -> bool:
    lower = text.lower()
    if not codes:
        return False
    if any(code not in SAFE_RUFF_FIXABLE_RULES for code in codes):
        return False
    return (
        "fixable" in lower
        or "[*]" in text
        or "remove unused import" in lower
        or "import block is un-sorted" in lower
    )


def _append_ruff_lint(text: str, files: Sequence[str], diagnoses: list[dict[str, Any]]) -> None:
    codes = _ruff_rule_codes(text)
    if files and _is_safe_ruff_fixable_lint(text, codes):
        targets = " ".join(files)
        rule_text = ", ".join(codes)
        diagnoses.append(
            _diag(
                "RUFF_FIXABLE_LINT",
                "medium",
                "high",
                "Ruff fixable lint can be mechanically remediated",
                f"Ruff reported fixable mechanical lint ({rule_text}) in known files.",
                "Developers often fix the visible import by hand and miss that Ruff can apply this narrow class safely.",
                ["ruff fixable lint", f"ruff_rules={rule_text}", "safe_rules=F401,I001"],
                [
                    "Run ruff check --fix on affected files.",
                    "Run ruff format on affected files.",
                    "Re-run Ruff check and format check.",
                ],
                [
                    f"PYTHONPATH=src python -m ruff check {targets}",
                    f"PYTHONPATH=src python -m ruff format --check {targets}",
                ],
                "The PR stays red for a mechanical lint issue that the autopilot can safely prove.",
                "ruff-fixable-lint",
                files=files,
            )
        )
        return
    _append_static("RUFF_LINT_FAILURE", "Ruff lint contract failed", files, diagnoses)


def _append_local_investigation(
    text: str, files: Sequence[str], diagnoses: list[dict[str, Any]]
) -> bool:
    lower = text.lower()

    if "missing test dependencies" in lower or (
        "modulenotfounderror" in lower
        and any(name in lower for name in ("hypothesis", "yaml", "pytest", "respx", "httpx"))
    ):
        diagnoses.append(
            _diag(
                "MISSING_TEST_DEPENDENCY",
                "medium",
                "high",
                "Test dependency is missing",
                "The test run failed before exercising product behavior because a required test dependency is unavailable.",
                "Developers often chase product code when collection failed because the environment is incomplete.",
                ["missing test dependency"],
                ["Install the declared test requirements and rerun the same focused test command."],
                ["python -m pip install -r requirements-test.txt"],
                "The failure can be misclassified as product logic when the test environment is incomplete.",
                "missing-test-dependency",
                files=files,
            )
        )
        return True

    if (
        "cannot import name 'utc' from 'datetime'" in lower
        or "cannot import name 'utc' from datetime" in lower
    ):
        diagnoses.append(
            _diag(
                "PYTHON_RUNTIME_COMPATIBILITY",
                "high",
                "high",
                "Python runtime compatibility issue detected",
                "The log shows use of datetime.UTC on a Python runtime that does not provide that symbol.",
                "Developers often reproduce on a newer interpreter and miss older supported runtime lanes.",
                ["datetime.UTC import failed"],
                [
                    "Replace the runtime-specific import with a compatibility-safe fallback and rerun supported Python lanes."
                ],
                ["python --version", "python -m pytest -q"],
                "Supported older Python versions can remain broken even when newer CI lanes pass.",
                "python-runtime-compatibility",
                files=files,
            )
        )
        return True

    if "/mnt/c/" in lower and any(
        token in lower
        for token in ("pip", "venv", "site-packages", "keyboardinterrupt", "slow", "stuck")
    ):
        diagnoses.append(
            _diag(
                "LOCAL_ENVIRONMENT_FRICTION",
                "medium",
                "high",
                "Local WSL filesystem friction detected",
                "The log suggests Python packaging or virtualenv work is running from the Windows-mounted filesystem.",
                "Developers often debug package tooling when the real issue is filesystem friction under WSL.",
                ["wsl-mounted-filesystem", "python environment operation"],
                [
                    "Move the active clone or virtualenv to the native WSL filesystem and rerun the same command."
                ],
                ["cp -a /mnt/c/<repo> ~/<repo>", "python -m venv .venv"],
                "Local environment friction can hide the real product signal and waste debugging time.",
                "local-environment-friction",
                files=files,
            )
        )
        return True

    if "takes no arguments" in lower and (
        "init_" in text or "__init__" in text or "test double" in lower or "mock" in lower
    ):
        diagnoses.append(
            _diag(
                "BROKEN_TEST_DOUBLE",
                "medium",
                "high",
                "Test double constructor is broken",
                "The failure appears to happen before product code runs because a local test double cannot be instantiated.",
                "Developers often treat this as product behavior until the traceback shows the fake object failed first.",
                ["test double instantiation failed"],
                ["Fix the test double constructor and rerun the focused test slice."],
                ["python -m pytest -q <focused-test>"],
                "A broken test harness can send the investigation toward the wrong product area.",
                "broken-test-double",
                files=files,
            )
        )
        return True

    if (
        "attributeerror" in lower
        and ("object has no attribute" in lower or "has no attribute" in lower)
        and any(token in lower for token in ("async", "sync", "client", "helper", "parity"))
    ):
        diagnoses.append(
            _diag(
                "MISSING_PUBLIC_API_PARITY",
                "high",
                "high",
                "Missing public API parity detected",
                "A public surface appears to be missing a method or helper that an adjacent sync/async/client surface provides.",
                "Developers often verify one public path and miss that a paired async or helper API is incomplete.",
                ["attribute missing on public API surface"],
                [
                    "Add the missing public API parity and focused regression coverage for both surfaces."
                ],
                ["python -m pytest -q <focused-parity-test>"],
                "Users can hit runtime AttributeError even though the sibling public API works.",
                "missing-public-api-parity",
                files=files,
            )
        )
        return True

    if "rejected" in lower and ("fetch first" in lower or "non-fast-forward" in lower):
        diagnoses.append(
            _diag(
                "GIT_BRANCH_DIVERGED",
                "medium",
                "high",
                "Git branch diverged from remote",
                "The push was rejected because the remote branch contains work not present locally.",
                "Developers often retry the push instead of rebasing onto the updated remote branch.",
                ["push rejected", "fetch first"],
                ["Fetch the remote branch, rebase locally, rerun proof, then push again."],
                ["git fetch origin <branch>", "git rebase origin/<branch>", "git push"],
                "A force push or stale branch can overwrite remote fixes or bot updates.",
                "git-branch-diverged",
                files=files,
            )
        )
        return True

    if "successfully rebased" in lower and "origin/" in lower:
        diagnoses.append(
            _diag(
                "REMOTE_BRANCH_DRIFT",
                "medium",
                "high",
                "Remote branch drift was resolved locally",
                "The local branch had to be rebased on a newer remote branch before pushing.",
                "Bot or remote updates can land between local proof and push.",
                ["remote branch updated", "local rebase succeeded"],
                ["Rerun proof after rebase before pushing."],
                ["python -m pre_commit run -a", "git push"],
                "Proof from before the rebase may no longer describe the pushed branch.",
                "remote-branch-drift",
                files=files,
            )
        )
        return True

    if "product logic failure" in lower or "deterministic product behavior failure" in lower:
        diagnoses.append(
            _diag(
                "PRODUCT_LOGIC_FAILURE",
                "high",
                "medium",
                "Product behavior failure requires review",
                "The log explicitly identifies a deterministic product behavior or contract failure.",
                "Developers often look for environment causes after a real behavior assertion has already identified the failing contract.",
                ["deterministic product behavior failure"],
                [
                    "Reproduce the focused failing behavior and inspect the product contract before broad rewrites."
                ],
                ["PYTHONPATH=src python -m pytest -q <focused-test>"],
                "A real behavior regression can be merged if it is mislabeled as infrastructure noise.",
                "product-logic-failure",
                files=files,
            )
        )
        return True

    return False


def _append_log(text: str, diagnoses: list[dict[str, Any]]) -> None:
    lower = text.lower()
    files = _file_mentions(text)
    handled_local = _append_local_investigation(text, files, diagnoses)
    formatted = _format_count(text)
    if formatted:
        evidence = ["ruff-format modified files", f"reformatted_file_count={formatted}"]
        if "pytest" in lower and ("passed" in lower or "rc=0" in lower):
            evidence.append("pytest evidence appears green")
        diagnoses.append(
            _diag(
                "PRE_COMMIT_FORMAT_DRIFT",
                "medium",
                "high",
                "Formatter drift blocked pre-commit",
                f"ruff-format reformatted {formatted} file(s) during the quality gate.",
                "Developers often see green tests and miss hooks that mutate files.",
                evidence,
                [
                    "Run ruff format on touched files.",
                    "Re-run format check and targeted pytest.",
                ],
                ["PYTHONPATH=src python -m ruff format --check <touched-python-files>"],
                "CI stays red even though product behavior may already be correct.",
                "formatting-drift-after-green-tests",
                files=files,
            )
        )
    if "mypy" in lower and "error:" in lower:
        _append_static("MYPY_TYPE_CONTRACT_DRIFT", "Type contract drift detected", files, diagnoses)
    if "ruff" in lower and ("failed" in lower or "fixable" in lower) and not formatted:
        _append_ruff_lint(text, files, diagnoses)
    if "modulenotfounderror" in lower or "importerror while importing" in lower:
        _append_pytest(
            text,
            "PYTEST_IMPORT_FAILURE",
            "Pytest import or collection failed",
            files,
            diagnoses,
        )
    elif not handled_local and ("assertionerror" in lower or re.search(r"FAILED\s+[^\s]+::", text)):
        _append_pytest(
            text,
            "PYTEST_ASSERTION_FAILURE",
            "Targeted test behavior failed",
            files,
            diagnoses,
        )
    if not diagnoses and text.strip():
        diagnoses.append(
            _diag(
                "UNKNOWN_REVIEW_REQUIRED",
                "medium",
                "medium",
                "Failure needs human review",
                "The provided log contains failure-like text but did not match a known adaptive diagnosis family.",
                "Unknown failures should not be guessed into a safe-fix route.",
                ["unclassified-log-evidence"],
                ["Inspect the first actionable traceback or failing command."],
                ["python -m pre_commit run -a"],
                "Unclassified failures can be unsafe to automate.",
                "unknown-review-required",
                files=files,
            )
        )


def _format_count(text: str) -> int:
    match = re.search(r"(\d+)\s+files?\s+reformatted", text)
    if match:
        return _as_int(match.group(1))
    return 1 if "files were modified by this hook" in text or "file reformatted" in text else 0


def _first_test(text: str) -> str:
    for pattern in (r"FAILED\s+([^\s]+::[^\s]+)", r"(tests/[\w./-]+\.py::[\w\[\]-]+)"):
        match = re.search(pattern, text)
        if match:
            return _safe(match.group(1), 180)
    return "unknown test"


def _append_static(
    code: str, title: str, files: Sequence[str], diagnoses: list[dict[str, Any]]
) -> None:
    diagnoses.append(
        _diag(
            code,
            "medium",
            "medium",
            title,
            f"{title}; inspect the first failing line before broad rewrites.",
            "Static-quality failures are often hidden inside larger gate output.",
            [title],
            ["Fix the first reported contract violation."],
            ["PYTHONPATH=src python -m ruff check <touched-python-files>"],
            "The branch remains blocked at static quality.",
            code.lower().replace("_", "-"),
            files=files,
        )
    )


def _append_pytest(
    text: str,
    code: str,
    title: str,
    files: Sequence[str],
    diagnoses: list[dict[str, Any]],
) -> None:
    test = _first_test(text)
    diagnoses.append(
        _diag(
            code,
            "high",
            "high" if code == "PYTEST_IMPORT_FAILURE" else "medium",
            title,
            f"Pytest reported a failure near {test}; use the first failing test as the fix anchor.",
            "Large CI logs can hide the first useful traceback under repeated summary output.",
            ["pytest failure", f"first_failed_test={test}"],
            ["Reproduce the first failing test only."],
            [f"PYTHONPATH=src python -m pytest -q {test}"],
            "A behavior regression can be merged behind otherwise green checks.",
            "pytest-failure",
            files=files,
        )
    )


def _append_mission(bundle: dict[str, Any], diagnoses: list[dict[str, Any]]) -> None:
    if not bundle:
        return
    decision = str(bundle.get("decision", "")).upper()
    failed = _as_int(bundle.get("failed_step_count"))
    steps = [_as_dict(step) for step in _as_list(bundle.get("steps"))]
    failed_steps = [
        str(step.get("id") or step.get("name") or "unknown")
        for step in steps
        if step.get("status") == "failed" or _as_int(step.get("rc")) != 0
    ]
    if decision == "NO_SHIP" or failed:
        evidence = [f"decision={decision or 'unknown'}", f"failed_step_count={failed}"]
        if failed_steps:
            evidence.append("failed_steps=" + ", ".join(failed_steps[:6]))
        diagnoses.append(
            _diag(
                "MISSION_CONTROL_NO_SHIP",
                "high",
                "high" if failed_steps else "medium",
                "Mission Control marked the run as no-ship",
                "Mission Control found a release-blocking run state across evidence sources.",
                "Developers often inspect one failing command and miss the higher-level decision.",
                evidence,
                ["Start with the first failed Mission Control step."],
                ["PYTHONPATH=src python -m sdetkit mission-control --execute --doctor-cortex"],
                "A no-ship decision can be bypassed if the team only checks local unit tests.",
                "mission-control-no-ship",
            )
        )
    if not _as_list(bundle.get("findings")) and not _as_list(bundle.get("artifacts")):
        diagnoses.append(
            _diag(
                "EVIDENCE_ARTIFACT_MISSING",
                "low",
                "medium",
                "Mission evidence is thin",
                "The Mission Control payload does not expose findings or artifacts that explain the run.",
                "Reviewers need durable artifacts, not only an exit code.",
                ["no findings or artifacts were present in the provided bundle"],
                ["Write a JSON and Markdown evidence bundle for the run."],
                ["PYTHONPATH=src python -m sdetkit mission-control --execute"],
                "Future reviewers lose context needed to diagnose repeated failures.",
                "mission-evidence-gap",
            )
        )


def _doctor_counts(record: dict[str, Any]) -> tuple[int, int] | None:
    cortex = _as_dict(record.get("doctor_cortex"))
    if not cortex or cortex.get("enabled") is False:
        return None
    diagnosis = _as_dict(cortex.get("diagnosis"))
    prescriptions = _as_dict(cortex.get("prescriptions"))
    return (
        _as_int(cortex.get("diagnosis_count", diagnosis.get("diagnosis_count", 0))),
        _as_int(cortex.get("prescription_count", prescriptions.get("prescription_count", 0))),
    )


def _append_history(records: list[dict[str, Any]], diagnoses: list[dict[str, Any]]) -> None:
    if not records:
        diagnoses.append(
            _diag(
                "MISSION_CONTROL_HISTORY_MISSING",
                "low",
                "high",
                "Mission Control history is not available yet",
                "No Mission Control ledger records were available, so recurrence cannot be assessed.",
                "A single run cannot show whether the issue is new, repeated, or worsening.",
                ["ledger_record_count=0"],
                ["Enable Mission Control ledger writes for future runs."],
                ["PYTHONPATH=src python -m sdetkit mission-control --append-ledger"],
                "The kit cannot separate one-time noise from repeated release friction.",
                "mission-history-missing",
            )
        )
        return
    decisions = Counter(str(row.get("decision", "UNKNOWN")).upper() for row in records)
    no_ship = decisions.get("NO_SHIP", 0)
    failed_runs = sum(1 for row in records if _as_int(row.get("failed_step_count")) > 0)
    if no_ship >= 2 or failed_runs >= 2:
        diagnoses.append(_repeated_history(records, no_ship, failed_runs))
    counts = [sample for row in records if (sample := _doctor_counts(row))]
    if len(counts) >= 2:
        _append_doctor_trend(counts[-2], counts[-1], diagnoses)


def _repeated_history(
    records: Sequence[dict[str, Any]], no_ship: int, failed_runs: int
) -> dict[str, Any]:
    return _diag(
        "MISSION_CONTROL_REPEATED_FAILURE_PATTERN",
        "high",
        "high",
        "Repeated release friction detected in history",
        f"History shows {no_ship} NO_SHIP decision(s) and {failed_runs} failed run(s).",
        "Developers usually inspect the latest run; repeated patterns need ledger comparison.",
        [f"ledger_record_count={len(records)}", f"no_ship_count={no_ship}"],
        ["Treat the repeated failing gate as a stabilization task."],
        ["PYTHONPATH=src python -m sdetkit mission-control history"],
        "The same release blocker is likely to return.",
        "repeated-release-friction",
        repeat_count=max(no_ship, failed_runs),
    )


def _append_doctor_trend(
    previous: tuple[int, int], latest: tuple[int, int], diagnoses: list[dict[str, Any]]
) -> None:
    for kind, before, after in (
        ("DIAGNOSIS", previous[0], latest[0]),
        ("PRESCRIPTION", previous[1], latest[1]),
    ):
        if after <= before:
            continue
        noun = kind.lower()
        diagnoses.append(
            _diag(
                f"DOCTOR_CORTEX_{kind}_REGRESSION",
                "medium",
                "high",
                f"Doctor Cortex {noun} count increased",
                f"Doctor Cortex {noun} count increased from {before} to {after}.",
                "A release can look acceptable while diagnostic debt grows across runs.",
                [f"{noun}_delta={after - before}"],
                [f"Inspect the newest Doctor Cortex {noun} output."],
                ["PYTHONPATH=src python -m sdetkit doctor --format json"],
                "Remediation effort can grow quietly until it blocks release.",
                f"doctor-cortex-{noun}-regression",
            )
        )


def _append_adaptive(history: dict[str, Any], diagnoses: list[dict[str, Any]]) -> None:
    if not history:
        return
    runs = _as_int(history.get("run_count", history.get("runs", 0)))
    if runs <= 0:
        diagnoses.append(
            _diag(
                "LEARNING_DB_EMPTY",
                "low",
                "high",
                "Adaptive memory is initialized but empty",
                "Adaptive memory is available but does not contain prior runs.",
                "Developers rarely notice an empty memory database if the file exists.",
                ["adaptive_run_count=0"],
                ["Populate adaptive memory after meaningful runs."],
                ["PYTHONPATH=src python -m sdetkit adaptive history --format operator-json"],
                "Recommendations remain weaker without prior context.",
                "adaptive-memory-empty",
            )
        )
    else:
        diagnoses.append(
            _diag(
                "KNOWN_ADAPTIVE_PATTERN_AVAILABLE",
                "info",
                "medium",
                "Adaptive memory has reusable context",
                "Adaptive memory contains prior context for this investigation.",
                "Developers rarely remember every prior hotspot after many small PRs.",
                [f"adaptive_run_count={runs}"],
                ["Compare current changed files with adaptive history."],
                ["PYTHONPATH=src python -m sdetkit adaptive history --format operator-json"],
                "Prior context may be ignored and investigation work repeated.",
                "adaptive-context",
                repeat_count=runs,
            )
        )


def _risk_score(diagnoses: Sequence[dict[str, Any]]) -> int:
    score = 0
    for item in diagnoses:
        score += SEVERITY_SCORE.get(str(item.get("severity", "info")), 3)
        score += {"high": 5, "medium": 2}.get(str(item.get("confidence", "low")), 0)
        score += min(_as_int(item.get("repeat_count")), 5) * 2
    return min(100, score)


def _rank(item: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        SEVERITY_RANK.get(str(item.get("severity", "info")), 9),
        CONFIDENCE_RANK.get(str(item.get("confidence", "low")), 9),
        -_as_int(item.get("repeat_count")),
        str(item.get("code", "")),
    )


def analyze_evidence(
    *,
    log_text: str = "",
    mission_control: dict[str, Any] | None = None,
    ledger_records: Sequence[dict[str, Any]] | None = None,
    adaptive_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnoses: list[dict[str, Any]] = []
    if log_text:
        _append_log(log_text, diagnoses)
    _append_mission(_as_dict(mission_control), diagnoses)
    _append_history(list(ledger_records or []), diagnoses)
    _append_adaptive(_as_dict(adaptive_history), diagnoses)
    diagnoses = sorted(diagnoses, key=_rank)
    return _payload(diagnoses, _status_for(diagnoses))


def _status_for(diagnoses: Sequence[dict[str, Any]]) -> str:
    if any(item.get("severity") == "high" for item in diagnoses):
        return "needs_fix"
    if any(str(item.get("code", "")) in SAFE_AUTO_FIX_CODES for item in diagnoses):
        return "needs_fix"
    if _risk_score(diagnoses) >= 30:
        return "needs_attention"
    return "monitor" if diagnoses else "clear"


def _payload(diagnoses: list[dict[str, Any]], status: str) -> dict[str, Any]:
    confidence = "low"
    if any(item.get("confidence") == "high" for item in diagnoses):
        confidence = "high"
    elif diagnoses:
        confidence = "medium"
    summary = "No adaptive diagnosis signals were found in the provided evidence."
    if diagnoses:
        verb = (
            "Fix this before release signoff"
            if status == "needs_fix"
            else "Keep collecting evidence"
        )
        summary = f"Primary issue: {diagnoses[0]['title']}. {verb}."
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": status in {"clear", "monitor"},
        "status": status,
        "risk_score": _risk_score(diagnoses),
        "confidence": confidence,
        "summary": _safe(summary, 500),
        "diagnosis_count": len(diagnoses),
        "diagnoses": diagnoses,
        "fix_plan": [
            {
                "code": item["code"],
                "title": item["title"],
                "safe_to_auto_fix": item["code"] in SAFE_AUTO_FIX_CODES,
                "recommended_fix": item["recommended_fix"][:4],
                "proof_commands": item["proof_commands"][:4],
            }
            for item in diagnoses[:5]
        ],
        "learning_updates": [
            {
                "signal": item["learning_signal"],
                "code": item["code"],
                "confidence": item["confidence"],
            }
            for item in diagnoses
        ],
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"status={payload['status']}",
        f"risk_score={payload['risk_score']}",
        f"confidence={payload['confidence']}",
        f"summary={payload['summary']}",
        f"diagnosis_count={payload['diagnosis_count']}",
    ]
    for item in _as_list(payload.get("diagnoses"))[:5]:
        row = _as_dict(item)
        lines.append(
            f"diagnosis={row.get('code')}|{row.get('severity')}|{row.get('confidence')}|{row.get('title')}"
        )
    return "\n".join(_safe(line, 600) for line in lines) + "\n"


def _diagnosis_markdown(row: dict[str, Any]) -> list[str]:
    lines = [
        f"### {row.get('title', 'Untitled diagnosis')}",
        "",
        f"- Code: {row.get('code', 'UNKNOWN')}",
        f"- Severity: {row.get('severity', 'unknown')}",
        f"- Confidence: {row.get('confidence', 'unknown')}",
        f"- Repeat count: {row.get('repeat_count', 0)}",
        "",
        str(row.get("diagnosis", "")),
        "",
        "Why developers miss it:",
        str(row.get("why_developers_miss_it", "")),
        "",
        "Evidence:",
    ]
    lines += [f"- {value}" for value in _as_list(row.get("evidence"))]
    lines += ["", "Recommended fix:"]
    lines += [f"- {value}" for value in _as_list(row.get("recommended_fix"))]
    lines += ["", "Proof commands:"]
    lines += [f"- `{value}`" for value in _as_list(row.get("proof_commands"))]
    lines += ["", f"Risk if ignored: {row.get('risk_if_ignored', '')}", ""]
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adaptive Diagnosis Intelligence",
        "",
        f"- Status: {payload['status']}",
        f"- OK: {str(payload['ok']).lower()}",
        f"- Risk score: {payload['risk_score']}",
        f"- Confidence: {payload['confidence']}",
        f"- Summary: {payload['summary']}",
        "",
        "## Diagnoses",
        "",
    ]
    for item in _as_list(payload.get("diagnoses")):
        lines.extend(_diagnosis_markdown(_as_dict(item)))
    if not _as_list(payload.get("diagnoses")):
        lines.append("- none")
    return "\n".join(_safe(line, 900) if line else "" for line in lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _render(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_format == "md":
        return render_markdown(payload)
    return render_text(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_diagnosis")
    parser.add_argument("--mission-control", default="")
    parser.add_argument("--ledger", default="")
    parser.add_argument("--adaptive-history", default="")
    parser.add_argument("--log", action="append", default=[])
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    parser.add_argument("--out", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv if argv is not None else sys.argv[1:]))
    try:
        log_text = "\n".join(
            Path(path).read_text(encoding="utf-8", errors="replace") for path in args.log
        )
        payload = analyze_evidence(
            log_text=log_text,
            mission_control=_load_json(Path(args.mission_control))
            if args.mission_control
            else None,
            ledger_records=_load_jsonl(Path(args.ledger)) if args.ledger else [],
            adaptive_history=_load_json(Path(args.adaptive_history))
            if args.adaptive_history
            else None,
        )
        rendered = _render(payload, str(args.format))
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
