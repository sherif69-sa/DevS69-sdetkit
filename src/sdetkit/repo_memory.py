"""RepoMemory: what this repository's remediation history has proven.

Every `diagnose run` appends its trajectory records here. The memory turns
them into pattern insights the patch scorer already understands:

- a fix pattern verified at least ``min_repeats`` times stops being penalised
  as unproven (``recurring_safe_fix_patterns``);
- a surface whose fixes the verifier blocked, or people rejected
  (``sdetkit diagnose decide --reject``), at least ``min_repeats`` times is held
  for review (``recurring_review_first_surfaces``).

History can make the scorer more or less cautious; it never grants authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.repo_memory.v1"
INSIGHTS_SCHEMA_VERSION = "sdetkit.trajectory_pattern_insights.v1"
DEFAULT_MEMORY_PATH = Path(".sdetkit") / "memory" / "trajectories.jsonl"
DEFAULT_MIN_REPEATS = 2

VERIFIED = "verified_candidate"
BLOCKED = "blocked_review_first"
# A person rejecting a proposal holds its surface for review just as a verifier block does.
HUMAN_REJECTED = "human_rejected"
HELD_FOR_REVIEW = frozenset({BLOCKED, HUMAN_REJECTED})

JsonObject = dict[str, Any]

DECISION_BOUNDARY: dict[str, bool] = {
    "automation_allowed": False,
    "patch_application_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    return str(value or "").strip()


def load_records(path: Path) -> list[JsonObject]:
    """Read the memory; unreadable lines are skipped, a missing file is empty."""

    if not path.is_file():
        return []
    records: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            records.append(loaded)
    return records


def append_records(path: Path, records: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            count += 1
    return count


def _pattern_key(record: Mapping[str, Any]) -> tuple[str, str]:
    classification = _string(record.get("plan_classification")) or _string(
        _as_dict(record.get("diagnosis")).get("failure_class")
    )
    return classification or "unknown", _string(record.get("action")) or "unknown"


def _surface(record: Mapping[str, Any]) -> str:
    return _string(record.get("failure_surface")) or _string(
        _as_dict(record.get("diagnosis")).get("risk_surface")
    )


def build_pattern_insights(
    records: Sequence[Mapping[str, Any]], *, min_repeats: int = DEFAULT_MIN_REPEATS
) -> JsonObject:
    """Pattern insights in the shape `verify score --pattern-insights` reads."""

    verified = Counter(
        _pattern_key(record) for record in records if record.get("loop_decision") == VERIFIED
    )
    blocked = Counter(
        _surface(record) for record in records if record.get("loop_decision") in HELD_FOR_REVIEW
    )
    safe_patterns = [
        {"failure_class": failure_class, "action": action, "verified_count": count}
        for (failure_class, action), count in sorted(verified.items())
        if count >= min_repeats
    ]
    review_surfaces = [
        {"value": surface, "blocked_count": count}
        for surface, count in sorted(blocked.items())
        if surface and count >= min_repeats
    ]
    gates = [_as_dict(record.get("safety_gate")) for record in records]
    gates = [gate for gate in gates if gate]
    return {
        "schema_version": INSIGHTS_SCHEMA_VERSION,
        "record_count": len(records),
        "min_repeats": min_repeats,
        "recurring_safe_fix_patterns": safe_patterns,
        "recurring_review_first_surfaces": review_surfaces,
        "safety_gate_evidence": {
            "collection_status": "collected" if gates else "not_collected",
            "source": "repo_memory",
            "record_count": len(gates),
            "review_first_count": sum(1 for gate in gates if gate.get("review_first")),
            "safe_fix_allowed_count": sum(1 for gate in gates if gate.get("safe_fix_allowed")),
            "reporting_only_count": sum(1 for gate in gates if gate.get("reporting_only")),
            "decision_boundary": dict(DECISION_BOUNDARY),
        },
        **DECISION_BOUNDARY,
    }


def build_profile(
    records: Sequence[Mapping[str, Any]], *, min_repeats: int = DEFAULT_MIN_REPEATS
) -> JsonObject:
    """Summarise the memory for people and for `verify patch --repo-memory-profile`."""

    decisions = Counter(_string(record.get("loop_decision")) or "diagnosed" for record in records)
    classes = Counter(_pattern_key(record)[0] for record in records)
    contracts = [_as_dict(record.get("failure_vector_contract")) for record in records]
    contracts = [contract for contract in contracts if contract]
    insights = build_pattern_insights(records, min_repeats=min_repeats)
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_status": "observed" if records else "empty",
        "record_count": len(records),
        "by_decision": dict(sorted(decisions.items())),
        "by_failure_class": dict(sorted(classes.items())),
        "recurring_safe_fix_patterns": insights["recurring_safe_fix_patterns"],
        "recurring_review_first_surfaces": insights["recurring_review_first_surfaces"],
        "failure_vector_contract_evidence": {
            "collection_status": "collected" if contracts else "not_collected",
            "source": "repo_memory",
            "record_count": len(contracts),
            "authority_boundary_preserved_count": sum(
                1 for contract in contracts if contract.get("authority_boundary_preserved")
            ),
        },
        **DECISION_BOUNDARY,
    }


def query_records(
    records: Sequence[Mapping[str, Any]],
    *,
    failure_class: str = "",
    decision: str = "",
    diagnosis_id: str = "",
    limit: int = 20,
) -> list[JsonObject]:
    matched = [
        dict(record)
        for record in records
        if (not failure_class or _pattern_key(record)[0] == failure_class)
        and (not decision or _string(record.get("loop_decision")) == decision)
        and (not diagnosis_id or _string(record.get("diagnostic_id")) == diagnosis_id)
    ]
    return matched[-limit:] if limit > 0 else matched


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit diagnose memory",
        description="Inspect what this repository's remediation history has proven.",
    )
    parser.add_argument(
        "view",
        nargs="?",
        choices=["profile", "insights", "query"],
        default="profile",
    )
    parser.add_argument("--memory", default=str(DEFAULT_MEMORY_PATH))
    parser.add_argument("--min-repeats", type=int, default=DEFAULT_MIN_REPEATS)
    parser.add_argument("--failure-class", default="")
    parser.add_argument("--decision", default="")
    parser.add_argument("--diagnosis-id", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.min_repeats < 1:
        print("diagnose memory error: --min-repeats must be at least 1", file=sys.stderr)
        return 2
    records = load_records(Path(args.memory))
    if args.view == "insights":
        payload: Any = build_pattern_insights(records, min_repeats=args.min_repeats)
    elif args.view == "query":
        payload = query_records(
            records,
            failure_class=args.failure_class,
            decision=args.decision,
            diagnosis_id=args.diagnosis_id,
            limit=args.limit,
        )
    else:
        payload = build_profile(records, min_repeats=args.min_repeats)

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.view == "query":
        for record in payload:
            print(
                f"{record.get('loop_decision', 'diagnosed')}\t"
                f"{_pattern_key(record)[0]}\t{record.get('diagnostic_id', '')}"
            )
        print(f"matched={len(payload)}")
        return 0
    print(f"memory={args.memory}")
    print(f"records={payload['record_count']}")
    if args.view == "profile":
        for decision, count in payload["by_decision"].items():
            print(f"decision.{decision}={count}")
    for pattern in payload["recurring_safe_fix_patterns"]:
        print(
            f"proven_fix={pattern['failure_class']}/{pattern['action']} "
            f"verified={pattern['verified_count']}"
        )
    for surface in payload["recurring_review_first_surfaces"]:
        print(f"held_for_review={surface['value']} blocked={surface['blocked_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
