from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

from .atomicio import canonical_json_dumps
from .security import SecurityError, safe_path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fingerprint(test_id: str, message: str) -> str:
    return hashlib.sha256(f"{test_id}\n{message}".encode()).hexdigest()[:16]


def _cmd_flake_classify(history_path: Path, rerun_threshold: int) -> dict[str, Any]:
    data = _load_json(history_path)
    if not isinstance(data, dict) or not isinstance(data.get("tests"), list):
        raise ValueError("history must be an object with a tests array")
    out: list[dict[str, Any]] = []
    for item in data["tests"]:
        if not isinstance(item, dict):
            continue
        test_id = str(item.get("id", ""))
        outcomes = [str(x) for x in item.get("outcomes", []) if isinstance(x, str)]
        if not test_id or not outcomes:
            continue
        failures = sum(1 for x in outcomes if x == "failed")
        passes = sum(1 for x in outcomes if x == "passed")
        flaky = failures > 0 and passes > 0 and len(outcomes) >= rerun_threshold
        classification = "flaky" if flaky else ("stable-failing" if failures else "stable-passing")
        message = f"{classification}:{','.join(outcomes)}"
        if classification == "flaky":
            signal = "nondeterministic-rerun"
            next_step = "Quarantine test and capture deterministic seed/fixture isolation evidence."
        elif classification == "stable-failing":
            signal = "consistent-regression"
            next_step = "Treat as product regression and escalate to release decision gate."
        else:
            signal = "stable"
            next_step = "Keep in baseline suite."

        out.append(
            {
                "test_id": test_id,
                "classification": classification,
                "signal": signal,
                "next_step": next_step,
                "runs": len(outcomes),
                "failures": failures,
                "passes": passes,
                "fingerprint": _fingerprint(test_id, message),
            }
        )
    out.sort(key=lambda x: (x["classification"], x["test_id"], x["fingerprint"]))
    return {
        "schema_version": "sdetkit.intelligence.flake.v1",
        "tests": out,
        "summary": {
            "flaky": sum(1 for x in out if x["classification"] == "flaky"),
            "stable_failing": sum(1 for x in out if x["classification"] == "stable-failing"),
            "stable_passing": sum(1 for x in out if x["classification"] == "stable-passing"),
        },
    }


def _cmd_capture_env(seed: int | None) -> dict[str, Any]:
    chosen_seed = seed if seed is not None else int(os.environ.get("SDETKIT_SEED", "1337"))
    rng = random.Random(chosen_seed)
    sampled = {
        k: os.environ.get(k, "")
        for k in sorted(["CI", "GITHUB_REF", "GITHUB_SHA", "PYTHONHASHSEED", "TZ"])  # deterministic
    }
    return {
        "schema_version": "sdetkit.intelligence.env-capture.v1",
        "seed": chosen_seed,
        "derived_seed": rng.randint(0, 10_000_000),
        "environment": sampled,
    }


def _cmd_impact(changed_path: Path, testmap_path: Path) -> dict[str, Any]:
    changed = [
        line.strip()
        for line in changed_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    mapping = _load_json(testmap_path)
    if not isinstance(mapping, dict):
        raise ValueError("test map must be a json object")
    impacted: set[str] = set()
    reasons: list[dict[str, str]] = []
    for file_path in sorted(changed):
        tests = mapping.get(file_path, [])
        if isinstance(tests, list):
            for test_id in sorted(str(x) for x in tests):
                impacted.add(test_id)
                reasons.append({"changed_file": file_path, "test_id": test_id})
    reasons.sort(key=lambda x: (x["test_id"], x["changed_file"]))
    return {
        "schema_version": "sdetkit.intelligence.impact.v1",
        "changed_files": sorted(changed),
        "impacted_tests": sorted(impacted),
        "mapping_hits": reasons,
    }


def _cmd_mutation_policy(policy_path: Path) -> dict[str, Any]:
    policy = _load_json(policy_path)
    if not isinstance(policy, dict):
        raise ValueError("policy file must be a json object")
    threshold = float(policy.get("minimum_score", 0))
    score = float(policy.get("observed_score", 0))
    owners = policy.get("owners", [])
    owner_ok = isinstance(owners, list) and len(owners) > 0
    justification = str(policy.get("justification", "")).strip()
    passed = score >= threshold and owner_ok and bool(justification)
    return {
        "schema_version": "sdetkit.intelligence.mutation-policy.v1",
        "passed": passed,
        "threshold": threshold,
        "observed_score": score,
        "owner_count": len(owners) if isinstance(owners, list) else 0,
        "has_justification": bool(justification),
    }


def _cmd_failure_fingerprint(failures_path: Path) -> dict[str, Any]:
    doc = _load_json(failures_path)
    if not isinstance(doc, dict) or not isinstance(doc.get("failures"), list):
        raise ValueError("failures file must contain a failures array")

    fingerprints: list[dict[str, Any]] = []
    for item in doc["failures"]:
        if not isinstance(item, dict):
            continue
        test_id = str(item.get("test_id", "")).strip()
        message = str(item.get("message", "")).strip()
        fixture_scope = str(item.get("fixture_scope", "unknown")).strip() or "unknown"
        if not test_id or not message:
            continue

        msg_lower = message.lower()
        nondeterminism_hints: list[str] = []
        if any(token in msg_lower for token in ["timeout", "timed out", "deadline exceeded"]):
            nondeterminism_hints.append("timing-sensitive")
        if any(token in msg_lower for token in ["connection reset", "econnreset", "network"]):
            nondeterminism_hints.append("network-sensitive")
        if any(token in msg_lower for token in ["random", "seed", "nondetermin"]):
            nondeterminism_hints.append("seed-sensitive")
        if fixture_scope in {"session", "module"}:
            nondeterminism_hints.append("shared-fixture-scope")

        fingerprints.append(
            {
                "test_id": test_id,
                "fixture_scope": fixture_scope,
                "fingerprint": _fingerprint(test_id, message),
                "nondeterminism_hints": sorted(set(nondeterminism_hints)),
            }
        )

    fingerprints.sort(key=lambda item: (item["test_id"], item["fingerprint"]))
    return {
        "schema_version": "sdetkit.intelligence.failure-fingerprint.v1",
        "failures": fingerprints,
        "summary": {
            "total": len(fingerprints),
            "with_nondeterminism_hints": sum(
                1 for item in fingerprints if item["nondeterminism_hints"]
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit intelligence", description="Test Intelligence Kit"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    flake = sub.add_parser("flake", help="Flake classification from rerun history")
    flake_sub = flake.add_subparsers(dest="subcmd", required=True)
    classify = flake_sub.add_parser("classify")
    classify.add_argument("--history", required=True)
    classify.add_argument("--rerun-threshold", type=int, default=2)

    cap = sub.add_parser("capture-env", help="Deterministic seed/environment capture")
    cap.add_argument("--seed", type=int, default=None)

    impact = sub.add_parser("impact", help="Changed-scope impacted test summary")
    impact_sub = impact.add_subparsers(dest="subcmd", required=True)
    summarize = impact_sub.add_parser("summarize")
    summarize.add_argument("--changed", required=True)
    summarize.add_argument("--map", required=True, dest="test_map")

    mut = sub.add_parser("mutation-policy", help="Mutation governance evaluation")
    mut.add_argument("--policy", required=True)

    fp = sub.add_parser(
        "failure-fingerprint",
        help="Stable failure fingerprinting with nondeterminism heuristics",
    )
    fp.add_argument("--failures", required=True)

    ns = parser.parse_args(argv)
    try:
        if ns.cmd == "flake" and ns.subcmd == "classify":
            payload = _cmd_flake_classify(
                safe_path(Path.cwd(), ns.history, allow_absolute=True), max(ns.rerun_threshold, 1)
            )
        elif ns.cmd == "capture-env":
            payload = _cmd_capture_env(ns.seed)
        elif ns.cmd == "impact" and ns.subcmd == "summarize":
            payload = _cmd_impact(
                safe_path(Path.cwd(), ns.changed, allow_absolute=True),
                safe_path(Path.cwd(), ns.test_map, allow_absolute=True),
            )
        elif ns.cmd == "failure-fingerprint":
            payload = _cmd_failure_fingerprint(
                safe_path(Path.cwd(), ns.failures, allow_absolute=True)
            )
        else:
            payload = _cmd_mutation_policy(safe_path(Path.cwd(), ns.policy, allow_absolute=True))
    except (ValueError, OSError, SecurityError) as exc:
        sys.stderr.write(f"intelligence error: {exc}\n")
        return 2

    sys.stdout.write(canonical_json_dumps(payload))
    if payload.get("passed") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
