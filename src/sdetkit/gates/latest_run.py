"""The most recent gate run, kept so `diagnose run` can pick up where a failing gate left off.

`gate fast` and `gate release` save their full result (each step's stdout and stderr
included) to `.sdetkit/runs/gate-latest.json` under the repository root. `diagnose run`
with no `--log` reads it and turns every failed step into a log file, so "the gate failed"
leads straight to "here is why and what would fix it" without saving logs by hand.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

LATEST_RUN_PATH = Path(".sdetkit/runs/gate-latest.json")
SCHEMA_VERSION = "sdetkit.gate_run.v1"


def record_latest_run(root: Path, payload: Mapping[str, Any]) -> Path | None:
    """Save a gate result as the latest run. Never fails the gate itself."""

    path = root / LATEST_RUN_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"schema_version": SCHEMA_VERSION, **payload}
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return None
    return path


def load_latest_run(root: Path) -> dict[str, Any] | None:
    path = root / LATEST_RUN_PATH
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _nested_gate_payload(step: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        loaded = json.loads(str(step.get("stdout") or ""))
    except ValueError:
        return None
    if isinstance(loaded, dict) and isinstance(loaded.get("steps"), list):
        return loaded
    return None


def failed_step_outputs(payload: Mapping[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """(check name, output) for every failed step, reaching into a nested gate's steps."""

    outputs: list[tuple[str, str]] = []
    steps = payload.get("steps")
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict) or step.get("ok", False):
            continue
        name = f"{prefix}{step.get('id') or 'step'}"
        nested = _nested_gate_payload(step)
        inner = failed_step_outputs(nested, prefix=f"{name}.") if nested else []
        if inner:
            outputs.extend(inner)
            continue
        text = "\n".join(
            part for part in (str(step.get("stdout") or ""), str(step.get("stderr") or "")) if part
        )
        outputs.append((name, text or f"{name} failed with exit code {step.get('rc')}"))
    return outputs


def write_failed_step_logs(payload: Mapping[str, Any], dest: Path) -> list[Path]:
    """Write each failed step's output to `dest/<check>/output.log` (the folder names the check)."""

    paths: list[Path] = []
    for name, text in failed_step_outputs(payload):
        path = dest / name / "output.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        paths.append(path)
    return paths
