from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CANONICAL_LANE_SPEC: tuple[dict[str, Any], ...] = (
    {
        "id": "gate_fast",
        "label": "gate fast",
        "args": [
            "gate",
            "fast",
            "--format",
            "json",
            "--stable-json",
            "--out",
            "build/gate-fast.json",
        ],
        "artifact": "gate-fast.json",
        "rc_file": "gate-fast.rc",
        "expected_rc": 2,
        "expected_ok": False,
        "reason": "Fixture intentionally lacks full repo policy/test wiring so first-run triage is visible.",
    },
    {
        "id": "gate_release",
        "label": "gate release",
        "args": ["gate", "release", "--format", "json", "--out", "build/release-preflight.json"],
        "artifact": "release-preflight.json",
        "rc_file": "release-preflight.rc",
        "expected_rc": 2,
        "expected_ok": False,
        "reason": "Release gate mirrors realistic preflight dependency on doctor+fast and fails truthfully here.",
    },
    {
        "id": "doctor",
        "label": "doctor",
        "args": ["doctor", "--format", "json", "--out", "build/doctor.json"],
        "artifact": "doctor.json",
        "rc_file": "doctor.rc",
        "expected_rc": 0,
        "expected_ok": True,
        "reason": "Doctor runs successfully and returns actionable checks without blocking artifact generation.",
    },
)


def normalize_cmd(parts: list[str], *, fixture_root: Path, repo_root: Path) -> list[str]:
    normalized: list[str] = []
    fixture_root_str = str(fixture_root)
    repo_root_str = str(repo_root)

    for part in parts:
        if part in {fixture_root_str, repo_root_str}:
            normalized.append("<repo>")
            continue
        basename = Path(part).name.lower()
        if re.fullmatch(r"python(\d+(?:\.\d+)*)?(\.exe)?", basename):
            normalized.append("python")
            continue
        normalized.append(part.replace(fixture_root_str, "<repo>").replace(repo_root_str, "<repo>"))
    return normalized


def project_gate_contract(
    payload: dict[str, Any], *, fixture_root: Path, repo_root: Path
) -> dict[str, Any]:
    return {
        "ok": payload["ok"],
        "failed_steps": payload["failed_steps"],
        "profile": payload["profile"],
        "steps": [
            {
                "id": step["id"],
                "ok": step["ok"],
                "rc": step["rc"],
                "cmd": normalize_cmd(step["cmd"], fixture_root=fixture_root, repo_root=repo_root),
            }
            for step in payload["steps"]
        ],
    }


def project_release_contract(
    payload: dict[str, Any], *, fixture_root: Path, repo_root: Path
) -> dict[str, Any]:
    projected = project_gate_contract(payload, fixture_root=fixture_root, repo_root=repo_root)
    projected["dry_run"] = payload["dry_run"]
    return projected


def project_doctor_contract(payload: dict[str, Any]) -> dict[str, Any]:
    quality = dict(payload["quality"])
    quality["failed_check_ids"] = sorted(quality["failed_check_ids"])
    return {
        "ok": payload["ok"],
        "quality": quality,
        "recommendations": payload["recommendations"],
    }


def project_contract_for_artifact(
    artifact_name: str, payload: dict[str, Any], *, fixture_root: Path, repo_root: Path
) -> dict[str, Any]:
    if artifact_name == "gate-fast.json":
        return project_gate_contract(payload, fixture_root=fixture_root, repo_root=repo_root)
    if artifact_name == "release-preflight.json":
        return project_release_contract(payload, fixture_root=fixture_root, repo_root=repo_root)
    if artifact_name == "doctor.json":
        return project_doctor_contract(payload)
    return payload


def build_lane_proof_summary(
    *, fixture_root: Path, repo_root: Path, build_dir: Path
) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    for spec in CANONICAL_LANE_SPEC:
        artifact_path = build_dir / spec["artifact"]
        rc_path = build_dir / spec["rc_file"]
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        observed_rc = int(rc_path.read_text(encoding="utf-8").strip())
        observed_ok = bool(payload.get("ok"))

        commands.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "cmd": ["python", "-m", "sdetkit", *spec["args"]],
                "artifact": f"build/{spec['artifact']}",
                "artifact_contract": project_contract_for_artifact(
                    spec["artifact"], payload, fixture_root=fixture_root, repo_root=repo_root
                ),
                "rc_file": f"build/{spec['rc_file']}",
                "observed_rc": observed_rc,
                "expected_rc": spec["expected_rc"],
                "rc_matches_expected": observed_rc == spec["expected_rc"],
                "observed_ok": observed_ok,
                "expected_ok": spec["expected_ok"],
                "ok_matches_expected": observed_ok is spec["expected_ok"],
                "trust_note": spec["reason"],
            }
        )

    return {
        "lane": "adoption-real-repo-canonical",
        "fixture": "examples/adoption/real-repo",
        "commands": commands,
        "all_expectations_met": all(
            c["rc_matches_expected"] and c["ok_matches_expected"] for c in commands
        ),
        "explanation": "Expected failures in gate fast/release are intentional and preserved as trustworthy first-run triage evidence.",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build canonical real-repo adoption proof summary."
    )
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    summary = build_lane_proof_summary(
        fixture_root=args.fixture_root.resolve(),
        repo_root=args.repo_root.resolve(),
        build_dir=args.build_dir.resolve(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
