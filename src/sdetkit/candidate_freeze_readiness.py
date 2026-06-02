from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.candidate.freeze.readiness.v1"
DEFAULT_OUT = "build/sdetkit/candidate-freeze-readiness.json"

AUTHORITY_BOUNDARY = {
    "automation_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

REQUIRED_EVIDENCE = [
    "issue collision review",
    "local proof feasibility",
    "scoped first PR card",
    "maintenance burden estimate",
    "public API risk review",
    "candidate owner approval",
]


def _load_dict(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _as_bool(payload: dict[str, Any], key: str) -> bool:
    return bool(payload.get(key))


def _as_int(payload: dict[str, Any], key: str) -> int:
    try:
        return int(payload.get(key, 0))
    except (TypeError, ValueError):
        return 0


def _fit_is_promising(repo_fit: dict[str, Any]) -> bool:
    return str(repo_fit.get("fit", "")).strip().lower() == "promising screen"


def _screen_is_valid(repo_fit: dict[str, Any]) -> bool:
    return (
        str(repo_fit.get("status", "")).strip().lower() == "screen only"
        and _as_bool(repo_fit, "screen_only")
        and not _as_bool(repo_fit, "candidate_frozen")
    )


def build_candidate_freeze_readiness(repo_fit: dict[str, Any]) -> dict[str, Any]:
    screen_valid = _screen_is_valid(repo_fit)
    promising = _fit_is_promising(repo_fit)
    missing = list(REQUIRED_EVIDENCE)

    hard_blocks: list[str] = []
    if not screen_valid:
        hard_blocks.append("repo fit input must be screen-only and not already frozen")
    if not promising:
        hard_blocks.append("repo fit screen is not promising enough to advance")

    readiness_score = 0
    if screen_valid:
        readiness_score += 30
    if promising:
        readiness_score += 20
    if _as_int(repo_fit, "score") >= 60:
        readiness_score += 10

    freeze_ready = False
    status = "not ready"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "repo": str(repo_fit.get("repo", "unknown")),
        "commit": str(repo_fit.get("commit", "")),
        "repo_fit_schema": str(repo_fit.get("schema_version", "")),
        "repo_fit": str(repo_fit.get("fit", "")),
        "repo_fit_score": _as_int(repo_fit, "score"),
        "screen_valid": screen_valid,
        "promising_screen": promising,
        "candidate_frozen": False,
        "freeze_ready": freeze_ready,
        "readiness_score": readiness_score,
        "required_evidence": REQUIRED_EVIDENCE,
        "missing_evidence": missing,
        "hard_blocks": hard_blocks,
        "recommended_action": "collect missing evidence before freezing candidate",
        **AUTHORITY_BOUNDARY,
    }


def write_candidate_freeze_readiness_artifact(
    *,
    repo_fit_json: str | Path,
    out: str | Path = DEFAULT_OUT,
) -> dict[str, Any]:
    payload = build_candidate_freeze_readiness(_load_dict(repo_fit_json))
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit candidate-freeze-readiness",
        description="Build read-only candidate freeze readiness evidence.",
    )
    parser.add_argument("--repo-fit-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_candidate_freeze_readiness_artifact(
        repo_fit_json=ns.repo_fit_json,
        out=ns.out,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"readiness_json={ns.out}\n")
        sys.stdout.write(f"repo={payload['repo']}\n")
        sys.stdout.write(f"status={payload['status']}\n")
        sys.stdout.write(f"freeze_ready={str(payload['freeze_ready']).lower()}\n")
        sys.stdout.write(f"candidate_frozen={str(payload['candidate_frozen']).lower()}\n")
        sys.stdout.write(f"automation_allowed={str(payload['automation_allowed']).lower()}\n")
        sys.stdout.write(f"merge_authorized={str(payload['merge_authorized']).lower()}\n")
        sys.stdout.write(
            f"semantic_equivalence_proven={str(payload['semantic_equivalence_proven']).lower()}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
