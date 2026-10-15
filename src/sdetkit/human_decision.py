"""Record a person's decision on a decision card.

The record is bound to the card's digest and to the proposed patch's SHA-256,
so it says exactly what was approved or rejected. Before writing it, the card
is re-checked: a card edited after it was built, a patch swapped on disk, or a
proof chain that no longer verifies is refused. Approving never applies the
patch; the record names the command the person runs.

Decisions are appended to RepoMemory, so a surface whose proposals people keep
rejecting is held for review by the patch scorer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import decision_card
from sdetkit.repo_memory import DEFAULT_MEMORY_PATH, append_records
from sdetkit.verdict import build_verdict

SCHEMA_VERSION = "sdetkit.decision_record.v1"
RECORD_JSON = "decision-record.json"
HUMAN_APPROVED = "human_approved"
HUMAN_REJECTED = "human_rejected"

JsonObject = dict[str, Any]


class DecisionRefused(ValueError):
    """The card cannot carry this decision."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()  # noqa: UP017


def _check_card(card: Mapping[str, Any], card_path: Path, decision: str) -> list[str]:
    problems: list[str] = []
    if card.get("schema_version") != decision_card.SCHEMA_VERSION:
        return [f"{card_path.as_posix()} is not a {decision_card.SCHEMA_VERSION} card"]
    if card.get("card_id") != decision_card.card_digest(card):
        problems.append("the card was edited after it was built")
    allowed = [str(option.get("decision")) for option in card.get("options") or []]
    if decision not in allowed:
        problems.append(f"{decision} is not an option on this card (options: {', '.join(allowed)})")
    proposal = card.get("proposal") or {}
    if decision == decision_card.APPROVE and proposal.get("present"):
        patch_path = card_path.parent / str(proposal.get("path"))
        if not patch_path.is_file():
            problems.append(f"the proposed patch {patch_path.as_posix()} is missing")
        elif decision_card.sha256_text(patch_path.read_text(encoding="utf-8")) != proposal.get(
            "sha256"
        ):
            problems.append("the proposed patch changed after the card was built")
        try:
            rebuilt = decision_card.build_decision_card(card_path.parent)
        except ValueError as exc:
            problems.append(str(exc))
        else:
            if not rebuilt["proof"]["chain"].get("ok"):
                problems.append("the protected proof chain no longer verifies")
            elif rebuilt["card_id"] != card.get("card_id"):
                problems.append("the loop artifacts changed after the card was built")
    return problems


def record_decision(
    *,
    card_path: Path,
    decision: str,
    reviewer: str,
    note: str = "",
    out_path: Path | None = None,
    memory_path: Path | None = DEFAULT_MEMORY_PATH,
) -> JsonObject:
    if not reviewer.strip():
        raise DecisionRefused("a decision needs a --reviewer")
    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionRefused(f"cannot read card {card_path.as_posix()}: {exc}") from exc
    if not isinstance(card, dict):
        raise DecisionRefused(f"{card_path.as_posix()} is not a card")
    problems = _check_card(card, card_path, decision)
    if problems:
        raise DecisionRefused("; ".join(problems))

    proposal = card.get("proposal") or {}
    approved = decision == decision_card.APPROVE
    follow_up = decision_card.follow_up(card, decision, card_path.parent)
    next_action = (
        f"{follow_up}, then commit and push so CI proves the fix." if approved else follow_up
    )
    card_verdict = card.get("verdict") or {}
    record: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "card_id": card["card_id"],
        "card_path": card_path.as_posix(),
        "repository": card.get("repository", ""),
        "commit_sha": card.get("commit_sha", ""),
        "patch_sha256": proposal.get("sha256", ""),
        "decision": decision,
        "reviewer": reviewer.strip(),
        "note": note,
        "decided_at": _now(),
        "next_action": next_action,
        # A person's approval does not prove the fix; CI on the pushed commit does.
        "verdict": build_verdict(
            source="diagnose decide",
            decision="REVIEW" if approved else card_verdict.get("decision") or "NOT_RUN",
            reasons=[f"{reviewer.strip()} chose {decision} on card {card['card_id'][:16]}"],
            next_action=next_action,
        ),
        **decision_card.DECISION_BOUNDARY,
    }
    target = out_path or card_path.parent / RECORD_JSON
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record["record_path"] = target.as_posix()

    if memory_path is not None:
        pattern = card.get("pattern") or {}
        append_records(
            memory_path,
            [
                {
                    "schema_version": SCHEMA_VERSION,
                    "loop_decision": HUMAN_APPROVED if approved else HUMAN_REJECTED,
                    "diagnostic_id": pattern.get("diagnostic_id", ""),
                    "plan_classification": pattern.get("plan_classification", ""),
                    "failure_surface": pattern.get("failure_surface", ""),
                    "action": pattern.get("action", ""),
                    "card_id": card["card_id"],
                    "reviewer": reviewer.strip(),
                    "decided_at": record["decided_at"],
                }
            ],
        )
        record["memory"] = memory_path.as_posix()
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit diagnose decide",
        description=(
            "Record a person's decision on a decision card. Nothing is applied: "
            "the record names the command to run."
        ),
    )
    parser.add_argument("--card", required=True, help="decision-card.json from diagnose card/run")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    parser.add_argument("--reviewer", required=True, help="Who is deciding")
    parser.add_argument("--note", default="")
    parser.add_argument("--out", default=None, help="Record path (default: next to the card)")
    parser.add_argument("--memory", default=str(DEFAULT_MEMORY_PATH))
    parser.add_argument("--no-memory", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        record = record_decision(
            card_path=Path(args.card),
            decision=decision_card.APPROVE if args.approve else decision_card.REJECT,
            reviewer=args.reviewer,
            note=args.note,
            out_path=Path(args.out) if args.out else None,
            memory_path=None if args.no_memory else Path(args.memory),
        )
    except DecisionRefused as exc:
        print(f"diagnose decide refused: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(record, indent=2, sort_keys=True))
    else:
        print(f"decision={record['decision']}")
        print(f"record={record['record_path']}")
        print(f"next_action={record['next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
