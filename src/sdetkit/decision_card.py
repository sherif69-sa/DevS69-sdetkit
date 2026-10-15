"""Decision cards: what the remediation loop found, for a person to decide.

`diagnose run` ends with a decision a person still has to make. The card
collects that decision's evidence from the loop's own artifacts (failure,
SafetyGate, proposed patch, score, proof, verifier, proof chain, memory)
into one reviewable object and a PR comment. The card is identified by the
digest of its content, so a decision recorded against it (see
`sdetkit diagnose decide`) is bound to exactly what the person saw.

A card never applies anything and every authority flag on it is false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit.protected_proof_chain import verify_protected_proof_chain

SCHEMA_VERSION = "sdetkit.decision_card.v1"
COMMENT_MARKER = "<!-- sdetkit:decision-card -->"
CARD_JSON = "decision-card.json"
CARD_MARKDOWN = "decision-card.md"

APPROVE = "approve"
REJECT = "reject"

DECISION_BOUNDARY: dict[str, bool] = {
    "automation_allowed": False,
    "patch_application_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
    "automatic_security_fix_allowed": False,
    "automatic_dismissal_allowed": False,
}

# Proof-chain stages, in the names the chain uses, and the loop artifact for each.
_CHAIN_ARTIFACTS = {
    "diagnostic_job": "job",
    "failure_vector": "failure_vector",
    "safety_gate": "safety_gate",
    "proof_result": "verification_evidence",
    "verifier_result": "verifier_result",
    "patch_score": "patch_score",
    "pr_report": "pr_report",
    "trajectory": "trajectory",
}

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> JsonObject:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def card_digest(card: Mapping[str, Any]) -> str:
    """Digest of everything on the card except its own id."""

    body = {key: value for key, value in card.items() if key != "card_id"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def _artifact(loop_dir: Path, artifacts: Mapping[str, Any], name: str) -> Path | None:
    recorded = _string(artifacts.get(name))
    if not recorded:
        return None
    # Read every artifact from the loop directory itself, wherever the run was started.
    path = loop_dir / Path(recorded).name
    return path if path.is_file() else None


def _artifact_json(loop_dir: Path, artifacts: Mapping[str, Any], name: str) -> JsonObject:
    path = _artifact(loop_dir, artifacts, name)
    return _read_json(path) if path is not None else {}


def _patch_facts(patch_path: Path | None) -> JsonObject:
    if patch_path is None:
        return {"present": False}
    text = patch_path.read_text(encoding="utf-8")
    if not text.strip():
        return {"present": False}
    lines = text.splitlines()
    files = sorted(
        {line[len("+++ b/") :] for line in lines if line.startswith("+++ b/")}
        | {line[len("--- a/") :] for line in lines if line.startswith("--- a/")}
    )
    return {
        "present": True,
        "path": patch_path.name,
        "sha256": sha256_text(text),
        "files": files,
        "additions": sum(
            1 for line in lines if line.startswith("+") and not line.startswith("+++")
        ),
        "deletions": sum(
            1 for line in lines if line.startswith("-") and not line.startswith("---")
        ),
    }


def _chain_facts(
    loop_dir: Path, artifacts: Mapping[str, Any], summary: Mapping[str, Any]
) -> JsonObject:
    manifest_path = _artifact(loop_dir, artifacts, "protected_proof_chain")
    if manifest_path is None:
        return {"present": False, "ok": False}
    stages: dict[str, Path] = {}
    for stage, name in _CHAIN_ARTIFACTS.items():
        path = _artifact(loop_dir, artifacts, name)
        if path is None:
            return {"present": True, "ok": False, "error": f"missing artifact for {stage}"}
        stages[stage] = path
    manifest = _read_json(manifest_path)
    try:
        verification = verify_protected_proof_chain(
            manifest,
            artifacts=stages,
            expected_repository=_string(summary.get("repository")),
            expected_commit_sha=_string(summary.get("commit_sha")),
        )
    except ValueError as exc:
        return {"present": True, "ok": False, "error": str(exc)}
    return {
        "present": True,
        "ok": bool(verification.get("ok")),
        "chain_id": _string(verification.get("chain_id")),
        "mismatches": len(_as_list(verification.get("mismatches"))),
    }


def _pattern(loop_dir: Path, artifacts: Mapping[str, Any], diagnosis_id: str) -> JsonObject:
    """The trajectory record for the candidate, in the keys RepoMemory counts by."""

    path = _artifact(loop_dir, artifacts, "trajectory_jsonl")
    records: list[JsonObject] = []
    if path is not None:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(loaded, dict):
                records.append(loaded)
    chosen = next(
        (record for record in records if _string(record.get("diagnostic_id")) == diagnosis_id),
        records[0] if records else {},
    )
    return {
        "diagnostic_id": _string(chosen.get("diagnostic_id")) or diagnosis_id,
        "plan_classification": _string(chosen.get("plan_classification")),
        "failure_surface": _string(chosen.get("failure_surface")),
        "action": _string(chosen.get("action")),
    }


def _options(
    loop_decision: str, patch: Mapping[str, Any], chain: Mapping[str, Any]
) -> list[JsonObject]:
    approvable = (
        loop_decision == "verified_candidate"
        and bool(patch.get("present"))
        and bool(chain.get("ok"))
    )
    options: list[JsonObject] = []
    if approvable:
        options.append(
            {
                "decision": APPROVE,
                "means": "You accept the proposed patch. You apply it yourself; CI then proves it.",
            }
        )
    options.append(
        {
            "decision": REJECT,
            "means": (
                "You do not accept the proposal. RepoMemory records it, and a surface "
                "rejected repeatedly is held for review."
            ),
        }
    )
    return options


def build_decision_card(loop_dir: Path) -> JsonObject:
    """Build the card from a `diagnose run` output directory."""

    summary = _read_json(loop_dir / "loop.json")
    if not summary:
        raise ValueError(f"{loop_dir.as_posix()} has no loop.json from `sdetkit diagnose run`")
    artifacts = _as_dict(summary.get("artifacts"))
    candidate = _as_dict(summary.get("candidate"))
    bundle = _artifact_json(loop_dir, artifacts, "failure_vector")
    vector = _as_dict(next(iter(_as_list(bundle.get("failure_vectors"))), {}))
    gate = _artifact_json(loop_dir, artifacts, "safety_gate")
    score = _artifact_json(loop_dir, artifacts, "patch_score")
    patch = _patch_facts(_artifact(loop_dir, artifacts, "proposed_patch"))
    chain = _chain_facts(loop_dir, artifacts, summary)
    loop_decision = _string(summary.get("decision"))
    affected = _as_list(vector.get("affected_files"))
    card: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "repository": _string(summary.get("repository")),
        "commit_sha": _string(summary.get("commit_sha")),
        "loop_decision": loop_decision,
        "verdict": _as_dict(summary.get("verdict")),
        "failure": {
            "count": int(summary.get("failure_count") or 0),
            "failure_class": _string(vector.get("failure_class")),
            "first_failure": _string(vector.get("actual_failure"))
            or _string(vector.get("first_failing_line")),
            "affected_file": _string(affected[0]) if affected else "",
            "repro_command": _string(vector.get("local_repro_command")),
        },
        "safety_gate": {
            "safe_fix_allowed": bool(gate.get("safe_fix_allowed")),
            "review_first": bool(gate.get("review_first")),
            "allowed_files": sorted(str(path) for path in _as_list(gate.get("allowed_files"))),
        },
        "proposal": {
            **patch,
            "fix_command": _string(candidate.get("fix_command")),
        },
        "proof": {
            "status": _string(candidate.get("proof_status")) or "not_run",
            "verifier": _string(candidate.get("verifier_status")) or "not_run",
            "patch_score": score.get("score"),
            "risk_flags": sorted(
                _string(_as_dict(flag).get("code")) for flag in _as_list(score.get("risk_flags"))
            ),
            "chain": chain,
        },
        "pattern": _pattern(loop_dir, artifacts, _string(candidate.get("diagnosis_id"))),
        "memory": _as_dict(summary.get("memory")),
        "reasons": [str(reason) for reason in _as_list(summary.get("reasons"))],
        "next_action": _string(summary.get("next_action")),
        "options": _options(loop_decision, patch, chain),
        **DECISION_BOUNDARY,
    }
    card["card_id"] = card_digest(card)
    return card


def follow_up(card: Mapping[str, Any], decision: str, card_dir: Path) -> str:
    """What the person runs after deciding; the patch is named where it actually is."""

    if decision != APPROVE:
        return "Fix the failure by hand."
    patch = (card_dir / str(_as_dict(card.get("proposal")).get("path"))).as_posix()
    return f"git apply --check {patch} && git apply {patch}"


def _yes(value: Any) -> str:
    return "yes" if value else "no"


def render_markdown(card: Mapping[str, Any], *, card_path: str = CARD_JSON) -> str:
    """The card as a PR comment. The marker lets a CI job update one comment in place."""

    verdict = _as_dict(card.get("verdict"))
    failure = _as_dict(card.get("failure"))
    gate = _as_dict(card.get("safety_gate"))
    proposal = _as_dict(card.get("proposal"))
    proof = _as_dict(card.get("proof"))
    chain = _as_dict(proof.get("chain"))
    lines = [
        COMMENT_MARKER,
        f"## SDETKit decision card: `{verdict.get('decision', 'NOT_RUN')}`",
        "",
        f"Loop decision `{card.get('loop_decision', '')}` on `{card.get('commit_sha', '')[:12]}`. "
        "A person decides; SDETKit applies nothing.",
        "",
        "| | |",
        "| --- | --- |",
        f"| Failure | `{failure.get('failure_class') or 'unknown'}`: {failure.get('first_failure') or 'not extracted'} |",
        f"| File | `{failure.get('affected_file') or 'unknown'}` |",
        f"| Reproduce | `{failure.get('repro_command') or 'not known'}` |",
        f"| SafetyGate | safe fix allowed: {_yes(gate.get('safe_fix_allowed'))}; review first: {_yes(gate.get('review_first'))} |",
    ]
    if proposal.get("present"):
        lines += [
            f"| Proposed patch | `{proposal.get('path')}`: {', '.join(proposal.get('files') or [])} "
            f"(+{proposal.get('additions', 0)} -{proposal.get('deletions', 0)}), from `{proposal.get('fix_command', '')}` |",
            f"| Proof | {proof.get('status')}; verifier: `{proof.get('verifier')}`; score {proof.get('patch_score')} |",
            f"| Proof chain | {'verified' if chain.get('ok') else 'not verified'} |",
        ]
    if proof.get("risk_flags"):
        lines.append(f"| Risk flags | {', '.join(f'`{flag}`' for flag in proof['risk_flags'])} |")
    lines += ["", "### Your decision", ""]
    for option in _as_list(card.get("options")):
        item = _as_dict(option)
        lines.append(
            f"- **{item.get('decision')}**: {item.get('means')} "
            f"Record it: `sdetkit diagnose decide --card {card_path} --{item.get('decision')} "
            f"--reviewer <you>`. Then: `{follow_up(card, str(item.get('decision')), Path(card_path).parent)}`"
        )
    reasons = _as_list(card.get("reasons"))
    if reasons:
        lines += ["", "### Why this is not automatic", ""] + [f"- {reason}" for reason in reasons]
    lines += [
        "",
        f"<sub>card `{_string(card.get('card_id'))[:16]}`, every authority flag is false</sub>",
        "",
    ]
    return "\n".join(lines)


def write_decision_card(loop_dir: Path) -> tuple[Path, Path]:
    """Write the card next to the artifacts it describes; a decision re-checks them there."""

    card = build_decision_card(loop_dir)
    json_path = loop_dir / CARD_JSON
    json_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path = loop_dir / CARD_MARKDOWN
    md_path.write_text(render_markdown(card, card_path=json_path.as_posix()), encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit diagnose card",
        description="Build the decision card and PR comment for a `diagnose run` result.",
    )
    parser.add_argument("--loop-dir", default="build/sdetkit/remediation-loop")
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        json_path, md_path = write_decision_card(Path(args.loop_dir))
    except (OSError, ValueError) as exc:
        print(f"diagnose card error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        sys.stdout.write(json_path.read_text(encoding="utf-8"))
    elif args.format == "md":
        sys.stdout.write(md_path.read_text(encoding="utf-8"))
    else:
        card = json.loads(json_path.read_text(encoding="utf-8"))
        print(f"card={json_path.as_posix()}")
        print(f"comment={md_path.as_posix()}")
        print(f"verdict={_as_dict(card.get('verdict')).get('decision', 'NOT_RUN')}")
        print("options=" + ",".join(str(item["decision"]) for item in card["options"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
