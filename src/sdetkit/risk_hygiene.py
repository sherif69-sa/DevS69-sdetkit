from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

_GENERATED_PREFIXES = (
    ".sdetkit/",
    "build/",
    "site/",
    ".pytest_cache/",
    "__pycache__/",
    ".mypy_cache/",
    ".ruff_cache/",
)


def _norm(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def is_generated_artifact_path(path: str) -> bool:
    p = _norm(path)
    if not p or p == "repo":
        return False
    if any(p == pref.rstrip("/") or p.startswith(pref) for pref in _GENERATED_PREFIXES):
        return True
    if p.endswith(".db") or p.endswith(".sqlite") or p.endswith(".sqlite3"):
        return True
    if "coverage" in p or p.endswith(".coverage"):
        return True
    if "release-room" in p and (p.endswith(".json") or p.endswith(".txt")):
        return True
    return False


def tracked_paths(root: Path) -> set[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"], check=False, text=True, capture_output=True
        )
    except OSError:
        return set()
    if proc.returncode != 0:
        return set()
    return {_norm(line) for line in proc.stdout.splitlines() if line.strip()}


def classify_risks(root: Path, risks: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = tracked_paths(root)
    source: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    reasons: dict[str, int] = {}
    for risk in risks:
        f = str(risk.get("file", "repo"))
        if not is_generated_artifact_path(f):
            source.append(risk)
            continue
        nf = _norm(f)
        signal = str(risk.get("signal", "")).lower()
        title = str(risk.get("title", "")).lower()
        tracked_generated = nf in tracked
        release_package = (
            "release" in signal or "package" in signal or "release" in title or "package" in title
        )
        entry = dict(risk)
        entry["generated_artifact"] = True
        entry["tracked_generated_artifact"] = tracked_generated
        generated.append(entry)
        if tracked_generated or release_package:
            source.append(entry)
        else:
            suppressed.append(entry)
            reasons["untracked_generated_artifact"] = (
                reasons.get("untracked_generated_artifact", 0) + 1
            )
    return {
        "source_risks": source,
        "generated_artifact_risks": generated,
        "suppressed_risks": suppressed,
        "suppression_reasons": reasons,
        "workspace_noise_detected": bool(generated),
        "risk_hygiene_summary": {
            "total_risks": len(risks),
            "source_risks": len(source),
            "generated_artifact_risks": len(generated),
            "suppressed_risks": len(suppressed),
        },
    }
