from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_cmd(parts: list[str], *, fixture_root: Path, repo_root: Path) -> list[str]:
    normalized: list[str] = []
    fixture_root_str = str(fixture_root)
    repo_root_str = str(repo_root)

    for part in parts:
        if part in {fixture_root_str, repo_root_str}:
            normalized.append("<repo>")
            continue
        if part.endswith("/python") or part.endswith("\\python.exe"):
            normalized.append("python")
            continue
        normalized.append(part.replace(fixture_root_str, "<repo>").replace(repo_root_str, "<repo>"))
    return normalized


def project_gate_contract(payload: dict[str, Any], *, fixture_root: Path, repo_root: Path) -> dict[str, Any]:
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


def project_release_contract(payload: dict[str, Any], *, fixture_root: Path, repo_root: Path) -> dict[str, Any]:
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


def project_contract_for_artifact(artifact_name: str, payload: dict[str, Any], *, fixture_root: Path, repo_root: Path) -> dict[str, Any]:
    if artifact_name == "gate-fast.json":
        return project_gate_contract(payload, fixture_root=fixture_root, repo_root=repo_root)
    if artifact_name == "release-preflight.json":
        return project_release_contract(payload, fixture_root=fixture_root, repo_root=repo_root)
    if artifact_name == "doctor.json":
        return project_doctor_contract(payload)
    return payload
