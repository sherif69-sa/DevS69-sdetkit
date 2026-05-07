from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sdetkit._datetime import UTC

SCHEMA_VERSION = "sdetkit.adaptive_diagnosis.memory.v1"
RECORD_SCHEMA_VERSION = "sdetkit.adaptive_diagnosis.learning_record.v1"
SAFE_FIX_ROLLUP_SCHEMA_VERSION = "sdetkit.adaptive_safe_fix.rollup.v1"
LEARN_SUMMARY_SCHEMA_VERSION = "sdetkit.adaptive.learn.summary.v1"
SOURCE_SCHEMA_VERSION = "sdetkit.adaptive.diagnosis.v1"
ACTIONABLE_STATUSES = {"needs_attention", "needs_fix"}
CONFIDENCE_SCORE = {"low": 1, "medium": 2, "high": 3}
SCORE_CONFIDENCE = {1: "low", 2: "medium", 3: "high"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return 0


def _first(values: Any) -> str:
    for value in _as_list(values):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _prefixed_csv(values: Any, prefix: str) -> list[str]:
    for value in _as_list(values):
        text = str(value or "").strip()
        if text.startswith(prefix):
            return [item for item in text.removeprefix(prefix).split(",") if item]
    return []


def _lane_for_code(code: str, signal: str = "") -> str:
    haystack = f"{code} {signal}".lower()
    if any(token in haystack for token in ("ruff", "mypy", "format", "lint", "coverage")):
        return "quality"
    if any(token in haystack for token in ("pytest", "test", "fixture", "snapshot", "flake")):
        return "test"
    if any(token in haystack for token in ("package", "dependency", "install", "wheel", "build")):
        return "dependency"
    if any(token in haystack for token in ("security", "cve", "ghsa", "secret")):
        return "security"
    if any(token in haystack for token in ("release", "mission", "version", "tag")):
        return "release"
    if any(token in haystack for token in ("docs", "markdown", "mkdocs", "link")):
        return "docs"
    if any(token in haystack for token in ("git", "branch", "remote")):
        return "source-control"
    if any(token in haystack for token in ("network", "timeout", "api", "tls", "dns")):
        return "environment"
    return "unknown"


def _bounded_confidence(base: str, delta: int) -> str:
    score = CONFIDENCE_SCORE.get(str(base or "medium"), 2) + delta
    return SCORE_CONFIDENCE[min(3, max(1, score))]


def _optional_bool_from_flags(*, positive: bool = False, negative: bool = False) -> bool | None:
    if positive and negative:
        raise ValueError("outcome flags are mutually exclusive")
    if positive:
        return True
    if negative:
        return False
    return None


def _record_hash(parts: dict[str, Any]) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_diagnosis(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    if payload.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ValueError(f"unsupported adaptive diagnosis schema in {path}")
    return payload


def build_safe_fix_learning_record(
    *,
    plan: dict[str, Any],
    remediation_result: dict[str, Any] | None = None,
    commit_result: dict[str, Any] | None = None,
    learned_at_utc: str | None = None,
) -> dict[str, Any]:
    remediation = _as_dict(remediation_result)
    commit = _as_dict(commit_result)
    affected_files = [str(value) for value in _as_list(plan.get("affected_files"))]
    identity = {
        "source": "adaptive_safe_fix",
        "source_code": plan.get("source_code", "UNKNOWN"),
        "fix_type": plan.get("fix_type", "unknown"),
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", False)),
        "remediation_status": remediation.get("status", "not_attempted"),
        "commit_pushed": bool(commit.get("pushed", False)),
    }
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": _record_hash(identity),
        "learned_at_utc": learned_at_utc or _timestamp(),
        "source": "adaptive_safe_fix",
        "source_schema_version": str(plan.get("schema_version", "")),
        "source_status": str(plan.get("source_status", "unknown")),
        "source_confidence": str(plan.get("confidence", "unknown")),
        "source_risk_score": 0,
        "code": str(plan.get("source_code", "UNKNOWN")),
        "signal": f"safe-fix-{plan.get('fix_type', 'unknown')}",
        "severity": "info",
        "confidence": str(plan.get("confidence", "unknown")),
        "title": f"Safe fix outcome for {plan.get('fix_type', 'unknown')}",
        "recommended_fix": _first(plan.get("commands")),
        "proof_command": _first(plan.get("proof_commands")),
        "risk_if_ignored": str(plan.get("reason", "")),
        "repeat_count": 0,
        "affected_files": affected_files,
        "fix_type": str(plan.get("fix_type", "unknown")),
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", False)),
        "requires_human_review": bool(plan.get("requires_human_review", True)),
        "affected_file_count": len(affected_files),
        "remediation_attempted": bool(remediation.get("attempted", False)),
        "remediation_ok": bool(remediation.get("ok", False)),
        "remediation_status": str(remediation.get("status", "not_attempted")),
        "remediation_command_count": _as_int(remediation.get("command_count")),
        "commit_attempted": bool(commit.get("attempted", False)),
        "commit_ok": bool(commit.get("ok", False)),
        "commit_pushed": bool(commit.get("pushed", False)),
        "commit_reason": str(commit.get("reason", "")),
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def build_safe_fix_memory_rollup(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    safe_fix_records = 0

    for record in records:
        row = _as_dict(record)
        if row.get("source") != "adaptive_safe_fix":
            continue

        safe_fix_records += 1
        fix_type = str(row.get("fix_type", "unknown"))
        code = str(row.get("code", "UNKNOWN"))
        key = (fix_type, code)
        group = groups.setdefault(
            key,
            {
                "fix_type": fix_type,
                "code": code,
                "records": 0,
                "affected_file_count": 0,
                "remediation_attempts": 0,
                "remediation_successes": 0,
                "commit_attempts": 0,
                "commit_pushes": 0,
                "latest_record_id": "",
                "latest_learned_at_utc": "",
                "latest_remediation_status": "unknown",
                "latest_commit_reason": "",
            },
        )

        group["records"] += 1
        group["affected_file_count"] += _as_int(row.get("affected_file_count"))
        if bool(row.get("remediation_attempted", False)):
            group["remediation_attempts"] += 1
        if bool(row.get("remediation_ok", False)):
            group["remediation_successes"] += 1
        if bool(row.get("commit_attempted", False)):
            group["commit_attempts"] += 1
        if bool(row.get("commit_pushed", False)):
            group["commit_pushes"] += 1
        group["latest_record_id"] = str(row.get("record_id", ""))
        group["latest_learned_at_utc"] = str(row.get("learned_at_utc", ""))
        group["latest_remediation_status"] = str(row.get("remediation_status", "unknown"))
        group["latest_commit_reason"] = str(row.get("commit_reason", ""))

    ordered_groups = []
    for group in sorted(groups.values(), key=lambda item: (item["fix_type"], item["code"])):
        group["remediation_success_rate"] = _rate(
            _as_int(group["remediation_successes"]), _as_int(group["remediation_attempts"])
        )
        group["commit_push_rate"] = _rate(
            _as_int(group["commit_pushes"]), _as_int(group["commit_attempts"])
        )
        ordered_groups.append(group)

    return {
        "schema_version": SAFE_FIX_ROLLUP_SCHEMA_VERSION,
        "ok": True,
        "source": "adaptive_safe_fix_memory",
        "input_records": len(records),
        "safe_fix_records": safe_fix_records,
        "group_count": len(ordered_groups),
        "groups": ordered_groups,
    }


def safe_fix_rollup_from_db(db_path: Path) -> dict[str, Any]:
    return build_safe_fix_memory_rollup(_read_jsonl(db_path))


def build_learning_records(
    payload: dict[str, Any],
    *,
    include_monitor: bool = False,
    learned_at_utc: str | None = None,
    proof_passed: bool | None = None,
    fix_accepted: bool | None = None,
    false_positive: bool = False,
) -> list[dict[str, Any]]:
    status = str(payload.get("status", "unknown"))
    if status not in ACTIONABLE_STATUSES and not include_monitor:
        return []

    learned_at = learned_at_utc or _timestamp()
    records: list[dict[str, Any]] = []
    for diagnosis in _as_list(payload.get("diagnoses")):
        row = _as_dict(diagnosis)
        code = str(row.get("code", "UNKNOWN")).strip() or "UNKNOWN"
        signal = str(row.get("learning_signal", "")).strip() or code.lower()
        identity = {
            "source_status": status,
            "code": code,
            "signal": signal,
            "title": row.get("title", ""),
            "recommended_fix": _first(row.get("recommended_fix")),
            "proof_command": _first(row.get("proof_commands")),
            "proof_passed": proof_passed,
            "fix_accepted": fix_accepted,
            "false_positive": false_positive,
        }
        records.append(
            {
                "schema_version": RECORD_SCHEMA_VERSION,
                "record_id": _record_hash(identity),
                "learned_at_utc": learned_at,
                "source": "adaptive_diagnosis",
                "source_schema_version": str(payload.get("schema_version", "")),
                "source_status": status,
                "source_confidence": str(payload.get("confidence", "unknown")),
                "source_risk_score": _as_int(payload.get("risk_score")),
                "code": code,
                "signal": signal,
                "severity": str(row.get("severity", "unknown")),
                "confidence": str(row.get("confidence", "unknown")),
                "title": str(row.get("title", "")),
                "recommended_fix": _first(row.get("recommended_fix")),
                "proof_command": _first(row.get("proof_commands")),
                "risk_if_ignored": str(row.get("risk_if_ignored", "")),
                "repeat_count": _as_int(row.get("repeat_count")),
                "recurrence_count": _as_int(row.get("repeat_count")),
                "affected_files": [str(value) for value in _as_list(row.get("affected_files"))],
                "matched_signals": _prefixed_csv(row.get("evidence"), "matched_failure_signals="),
                "candidate_scenarios": _prefixed_csv(row.get("evidence"), "candidate_scenarios="),
                "selected_primary_diagnosis": len(records) == 0,
                "recommended_checks": [
                    str(value) for value in _as_list(row.get("recommended_fix"))[:4]
                ],
                "proof_commands": [str(value) for value in _as_list(row.get("proof_commands"))[:4]],
                "proof_passed": proof_passed,
                "fix_accepted": fix_accepted,
                "false_positive": false_positive,
                "lane": _lane_for_code(code, signal),
            }
        )
    return records


def _calibration_for_scenario(row: dict[str, Any]) -> dict[str, Any]:
    records = _as_int(row.get("records"))
    recurrence_count = _as_int(row.get("recurrence_count"))
    false_positive_count = _as_int(row.get("false_positive_count"))
    proof_passed_count = _as_int(row.get("proof_passed_count"))
    fix_accepted_count = _as_int(row.get("fix_accepted_count"))
    matched_signal_count = _as_int(row.get("matched_signal_count"))
    candidate_scenario_count = _as_int(row.get("candidate_scenario_count"))

    confidence_delta = 0
    risk_delta = 0
    actions: list[str] = []
    reasons: list[str] = []

    if false_positive_count:
        confidence_delta -= 2
        risk_delta -= min(20, false_positive_count * 8)
        actions.append("demote")
        reasons.append("operator marked false positive")
    if proof_passed_count or fix_accepted_count:
        confidence_delta += 1 + min(1, proof_passed_count + fix_accepted_count - 1)
        actions.append("promote")
        reasons.append("proof or accepted fix confirmed recommendation")
    if recurrence_count >= 3:
        risk_delta += min(30, recurrence_count * 3)
        actions.append("increase_risk")
        reasons.append("recurrence crossed promotion threshold")
    if records and matched_signal_count == 0 and candidate_scenario_count == 0:
        confidence_delta -= 1
        actions.append("lower_confidence")
        reasons.append("evidence is thin: no matched signals or candidate scenarios")

    if not actions:
        actions.append("observe")
        reasons.append("not enough outcome evidence to promote or demote")

    if "demote" in actions:
        primary_action = "demote"
    elif "promote" in actions and "increase_risk" in actions:
        primary_action = "promote_and_increase_risk"
    elif "promote" in actions:
        primary_action = "promote"
    elif "increase_risk" in actions:
        primary_action = "increase_risk"
    elif "lower_confidence" in actions:
        primary_action = "lower_confidence"
    else:
        primary_action = "observe"

    base_confidence = str(row.get("base_confidence", "medium"))
    return {
        "primary_action": primary_action,
        "actions": actions,
        "base_confidence": base_confidence,
        "calibrated_confidence": _bounded_confidence(base_confidence, confidence_delta),
        "confidence_delta": confidence_delta,
        "risk_delta": risk_delta,
        "reasons": reasons,
    }


def summarize_learning_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    scenario_groups: dict[str, dict[str, Any]] = {}
    lane_groups: dict[str, dict[str, Any]] = {}
    diagnosis_records = 0

    for record in records:
        row = _as_dict(record)
        if row.get("source") != "adaptive_diagnosis":
            continue
        diagnosis_records += 1
        code = str(row.get("code", "UNKNOWN"))
        signal = str(row.get("signal", ""))
        lane = str(row.get("lane") or _lane_for_code(code, signal))
        repeat_count = _as_int(row.get("recurrence_count", row.get("repeat_count")))
        false_positive = bool(row.get("false_positive", False))
        proof_passed = row.get("proof_passed")
        fix_accepted = row.get("fix_accepted")

        scenario = scenario_groups.setdefault(
            code,
            {
                "code": code,
                "lane": lane,
                "records": 0,
                "recurrence_count": 0,
                "false_positive_count": 0,
                "proof_passed_count": 0,
                "fix_accepted_count": 0,
                "proof_failed_count": 0,
                "fix_rejected_count": 0,
                "matched_signal_count": 0,
                "candidate_scenario_count": 0,
                "base_confidence": str(row.get("confidence", "medium")),
                "latest_record_id": "",
                "latest_learned_at_utc": "",
                "sample_signal": signal,
                "sample_proof_command": str(row.get("proof_command", "")),
            },
        )
        scenario["records"] += 1
        scenario["recurrence_count"] += repeat_count
        scenario["matched_signal_count"] += len(_as_list(row.get("matched_signals")))
        scenario["candidate_scenario_count"] += len(_as_list(row.get("candidate_scenarios")))
        if false_positive:
            scenario["false_positive_count"] += 1
        if proof_passed is True:
            scenario["proof_passed_count"] += 1
        elif proof_passed is False:
            scenario["proof_failed_count"] += 1
        if fix_accepted is True:
            scenario["fix_accepted_count"] += 1
        elif fix_accepted is False:
            scenario["fix_rejected_count"] += 1
        scenario["latest_record_id"] = str(row.get("record_id", ""))
        scenario["latest_learned_at_utc"] = str(row.get("learned_at_utc", ""))

        lane_group = lane_groups.setdefault(
            lane,
            {
                "lane": lane,
                "records": 0,
                "recurrence_count": 0,
                "false_positive_count": 0,
                "proof_unknown_count": 0,
                "scenario_codes": set(),
            },
        )
        lane_group["records"] += 1
        lane_group["recurrence_count"] += repeat_count
        if false_positive:
            lane_group["false_positive_count"] += 1
        if proof_passed is None:
            lane_group["proof_unknown_count"] += 1
        lane_group["scenario_codes"].add(code)

    for scenario in scenario_groups.values():
        scenario["calibration"] = _calibration_for_scenario(scenario)

    top_recurring = sorted(
        scenario_groups.values(),
        key=lambda item: (
            -_as_int(item["recurrence_count"]),
            -_as_int(item["records"]),
            item["code"],
        ),
    )[:10]

    weakest_lanes = []
    for lane_group in lane_groups.values():
        scenario_codes = sorted(lane_group.pop("scenario_codes"))
        lane_group["scenario_count"] = len(scenario_codes)
        lane_group["scenario_codes"] = scenario_codes[:8]
        lane_group["weakness_score"] = (
            _as_int(lane_group["records"])
            + _as_int(lane_group["recurrence_count"])
            + _as_int(lane_group["proof_unknown_count"])
            + _as_int(lane_group["false_positive_count"]) * 2
        )
        weakest_lanes.append(lane_group)
    weakest_lanes.sort(
        key=lambda item: (-_as_int(item["weakness_score"]), -_as_int(item["records"]), item["lane"])
    )

    return {
        "schema_version": LEARN_SUMMARY_SCHEMA_VERSION,
        "ok": True,
        "source": "adaptive_diagnosis_learning",
        "input_records": len(records),
        "diagnosis_records": diagnosis_records,
        "scenario_count": len(scenario_groups),
        "lane_count": len(weakest_lanes),
        "top_recurring_scenarios": top_recurring,
        "weakest_lanes": weakest_lanes[:10],
        "calibration_summary": {
            "promote": sum(
                1
                for item in scenario_groups.values()
                if "promote" in _as_dict(item.get("calibration")).get("actions", [])
            ),
            "demote": sum(
                1
                for item in scenario_groups.values()
                if "demote" in _as_dict(item.get("calibration")).get("actions", [])
            ),
            "increase_risk": sum(
                1
                for item in scenario_groups.values()
                if "increase_risk" in _as_dict(item.get("calibration")).get("actions", [])
            ),
            "lower_confidence": sum(
                1
                for item in scenario_groups.values()
                if "lower_confidence" in _as_dict(item.get("calibration")).get("actions", [])
            ),
        },
    }


def learning_summary_from_db(db_path: Path) -> dict[str, Any]:
    summary = summarize_learning_records(_read_jsonl(db_path))
    summary["db_path"] = db_path.as_posix()
    return summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def append_learning_records(db_path: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = {str(row.get("record_id", "")) for row in _read_jsonl(db_path)}
    appended = 0
    with db_path.open("a", encoding="utf-8") as fh:
        for record in records:
            record_id = str(record.get("record_id", ""))
            if not record_id or record_id in existing_ids:
                continue
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            existing_ids.add(record_id)
            appended += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "db_path": db_path.as_posix(),
        "input_records": len(records),
        "appended_records": appended,
        "total_records": len(existing_ids),
    }


def learn_from_diagnosis(
    diagnosis_path: Path,
    db_path: Path,
    *,
    include_monitor: bool = False,
    learned_at_utc: str | None = None,
    proof_passed: bool | None = None,
    fix_accepted: bool | None = None,
    false_positive: bool = False,
) -> dict[str, Any]:
    payload = load_diagnosis(diagnosis_path)
    records = build_learning_records(
        payload,
        include_monitor=include_monitor,
        learned_at_utc=learned_at_utc,
        proof_passed=proof_passed,
        fix_accepted=fix_accepted,
        false_positive=false_positive,
    )
    summary = append_learning_records(db_path, records)
    summary["source_path"] = diagnosis_path.as_posix()
    summary["source_status"] = str(payload.get("status", "unknown"))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_diagnosis_memory")
    parser.add_argument("diagnosis_json")
    parser.add_argument("--db", default=".sdetkit/adaptive-diagnosis-memory.jsonl")
    parser.add_argument("--include-monitor", action="store_true")
    parser.add_argument("--proof-passed", action="store_true")
    parser.add_argument("--proof-failed", action="store_true")
    parser.add_argument("--fix-accepted", action="store_true")
    parser.add_argument("--fix-rejected", action="store_true")
    parser.add_argument("--false-positive", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def build_summarize_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_diagnosis_memory summarize")
    parser.add_argument("--db", default=".sdetkit/adaptive-diagnosis-memory.jsonl")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def _print_summary(summary: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print(f"adaptive learning db: {summary.get('db_path', '')}")
    print(f"diagnosis records: {summary['diagnosis_records']}")
    print(f"scenario count: {summary['scenario_count']}")
    print(f"lane count: {summary['lane_count']}")
    for lane in _as_list(summary.get("weakest_lanes"))[:5]:
        row = _as_dict(lane)
        print(
            "weak lane: "
            f"{row.get('lane')} records={row.get('records')} "
            f"recurrence={row.get('recurrence_count')} score={row.get('weakness_score')}"
        )


def _main_summarize(argv: list[str]) -> int:
    args = build_summarize_parser().parse_args(argv)
    try:
        summary = learning_summary_from_db(Path(args.db))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2
    _print_summary(summary, str(args.format))
    return 0


def main(argv: list[str] | None = None) -> int:
    arg_list = list(sys.argv[1:] if argv is None else argv)
    if arg_list and arg_list[0] == "summarize":
        return _main_summarize(arg_list[1:])

    args = build_parser().parse_args(arg_list)
    try:
        summary = learn_from_diagnosis(
            Path(args.diagnosis_json),
            Path(args.db),
            include_monitor=bool(args.include_monitor),
            proof_passed=_optional_bool_from_flags(
                positive=bool(args.proof_passed), negative=bool(args.proof_failed)
            ),
            fix_accepted=_optional_bool_from_flags(
                positive=bool(args.fix_accepted), negative=bool(args.fix_rejected)
            ),
            false_positive=bool(args.false_positive),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"adaptive diagnosis learning db: {summary['db_path']}")
        print(f"source status: {summary['source_status']}")
        print(f"appended records: {summary['appended_records']}/{summary['input_records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
