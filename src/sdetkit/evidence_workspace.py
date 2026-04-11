from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .security import SecurityError, safe_path

WORKSPACE_SCHEMA_VERSION = "sdetkit.evidence.workspace.v1"


def _safe_slug(value: str) -> str:
    out: list[str] = []
    for ch in value.lower():
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "default"


def _stable_json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "workspace_version": 1,
            "runs": [],
            "latest": {},
        }
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("workspace manifest must be a JSON object")
    loaded.setdefault("schema_version", WORKSPACE_SCHEMA_VERSION)
    loaded.setdefault("workspace_version", 1)
    loaded.setdefault("runs", [])
    loaded.setdefault("latest", {})
    return loaded


def load_workspace_manifest(workspace_root: Path) -> dict[str, Any]:
    return _read_manifest(workspace_root / "manifest.json")


def record_workspace_run(
    *,
    workspace_root: Path,
    workflow: str,
    scope: str,
    payload: dict[str, Any],
    artifacts: dict[str, str],
    recommendations: list[str],
) -> dict[str, Any]:
    try:
        workspace_root = safe_path(Path.cwd(), workspace_root.as_posix(), allow_absolute=True)
    except SecurityError as exc:
        raise ValueError(f"workspace root rejected: {exc}") from exc

    workflow_slug = _safe_slug(workflow)
    scope_slug = _safe_slug(scope)
    canonical_payload = _stable_json_text(payload)
    run_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()[:16]

    run_dir = workspace_root / "runs" / workflow_slug / scope_slug / run_hash
    run_dir.mkdir(parents=True, exist_ok=True)

    record_payload = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "workflow": workflow,
        "scope": scope,
        "run_hash": run_hash,
        "payload": payload,
        "artifacts": artifacts,
        "recommendations": recommendations,
    }
    (run_dir / "record.json").write_text(
        json.dumps(record_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    manifest_path = workspace_root / "manifest.json"
    manifest = _read_manifest(manifest_path)
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        runs = []
    normalized_runs: list[dict[str, Any]] = []
    max_run_order = 0
    for idx, item in enumerate(runs):
        if not isinstance(item, dict):
            continue
        run_order = int(item.get("run_order", idx + 1))
        max_run_order = max(max_run_order, run_order)
        normalized = dict(item)
        normalized["run_order"] = run_order
        normalized_runs.append(normalized)
    runs = normalized_runs
    entry = {
        "workflow": workflow,
        "scope": scope,
        "run_hash": run_hash,
        "record_path": run_dir.relative_to(workspace_root).as_posix() + "/record.json",
        "run_order": max_run_order + 1,
    }
    existing = next(
        (
            item
            for item in runs
            if str(item.get("workflow", "")) == workflow
            and str(item.get("scope", "")) == scope
            and str(item.get("run_hash", "")) == run_hash
        ),
        None,
    )
    if existing is None:
        runs.append(entry)
    else:
        entry = {
            "workflow": str(existing.get("workflow", workflow)),
            "scope": str(existing.get("scope", scope)),
            "run_hash": str(existing.get("run_hash", run_hash)),
            "record_path": str(existing.get("record_path", entry["record_path"])),
            "run_order": int(existing.get("run_order", entry["run_order"])),
        }
    runs = sorted(
        runs,
        key=lambda item: (
            str(item.get("workflow", "")),
            str(item.get("scope", "")),
            int(item.get("run_order", 0)),
            str(item.get("run_hash", "")),
        ),
    )

    latest = manifest.get("latest", {})
    if not isinstance(latest, dict):
        latest = {}
    latest[f"{workflow}:{scope}"] = {
        "run_hash": run_hash,
        "record_path": entry["record_path"],
    }

    manifest["runs"] = runs
    manifest["latest"] = {k: latest[k] for k in sorted(latest)}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    latest_dir = workspace_root / "latest" / workflow_slug
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / f"{scope_slug}.json").write_text(
        json.dumps(
            {
                "schema_version": WORKSPACE_SCHEMA_VERSION,
                "workflow": workflow,
                "scope": scope,
                "run_hash": run_hash,
                "record_path": entry["record_path"],
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "workflow": workflow,
        "scope": scope,
        "run_hash": run_hash,
        "record_path": entry["record_path"],
        "workspace_manifest": manifest_path.as_posix(),
    }
