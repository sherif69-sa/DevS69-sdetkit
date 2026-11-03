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


# Steps that check the setup around the code, not the code: `doctor` and SDETKit's own
# templates, plus the --fix steps that only rewrite files.
SETUP_STEPS = frozenset(
    {"doctor", "doctor_release", "ci_templates", "ruff_fix", "ruff_format_apply"}
)


def failure_rank(step: Mapping[str, Any]) -> int:
    """Which failure to lead with: 0 the code, 1 a setup check, 2 a check that could not run."""

    if step.get("environment_problem"):
        return 2
    return 1 if str(step.get("id") or "") in SETUP_STEPS else 0


def _findings_text(name: str, stdout: str) -> str | None:
    """A failing SDETKit step such as `doctor` prints JSON; its own findings read as a log.

    Fed to the log parsers as-is, the whole document becomes the "first failure", and words
    in it such as "ruff-format" make a setup finding look like a formatting failure.
    """

    try:
        loaded = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(loaded, dict):
        return None
    lines = [
        f"{name}: {item.get('id') or 'check'} ({item.get('severity') or 'unknown'}): "
        f"{item['summary']}"
        for item in loaded.get("next_actions") or []
        if isinstance(item, dict) and item.get("summary")
    ]
    card = loaded.get("next_action")
    if not lines and isinstance(card, dict) and card.get("first_failure"):
        lines.append(f"{name}: {card.get('classification') or 'check'}: {card['first_failure']}")
    return "\n".join(lines) or None


def _ranked_failed_steps(
    payload: Mapping[str, Any], prefix: str = ""
) -> list[tuple[int, str, str]]:
    outputs: list[tuple[int, str, str]] = []
    steps = payload.get("steps")
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict) or step.get("ok", False):
            continue
        name = f"{prefix}{step.get('id') or 'step'}"
        nested = _nested_gate_payload(step)
        inner = _ranked_failed_steps(nested, prefix=f"{name}.") if nested else []
        if inner:
            outputs.extend(inner)
            continue
        stdout = str(step.get("stdout") or "")
        text = "\n".join(
            part
            for part in (_findings_text(name, stdout) or stdout, str(step.get("stderr") or ""))
            if part
        )
        outputs.append(
            (failure_rank(step), name, text or f"{name} failed with exit code {step.get('rc')}")
        )
    return outputs


def failed_step_outputs(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(check name, output) for every failed step, reaching into a nested gate's steps.

    Failures in the code come first, then setup checks, then checks that could not run, so
    the loop leads with the failure worth fixing.
    """

    ranked = sorted(_ranked_failed_steps(payload), key=lambda item: item[0])
    return [(name, text) for _, name, text in ranked]


def write_failed_step_logs(payload: Mapping[str, Any], dest: Path) -> list[Path]:
    """Write each failed step's output to `dest/<check>/output.log` (the folder names the check)."""

    paths: list[Path] = []
    for name, text in failed_step_outputs(payload):
        path = dest / name / "output.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        paths.append(path)
    return paths
