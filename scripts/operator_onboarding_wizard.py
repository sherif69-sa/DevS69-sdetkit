from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run_canonical(repo_root: Path, python_bin: str) -> list[dict[str, Any]]:
    commands = [
        ("gate_fast", [python_bin, "-m", "sdetkit", "gate", "fast", "--format", "json", "--out", "build/gate-fast.json"]),
        (
            "gate_release",
            [
                python_bin,
                "-m",
                "sdetkit",
                "gate",
                "release",
                "--format",
                "json",
                "--out",
                "build/release-preflight.json",
            ],
        ),
        ("doctor", [python_bin, "-m", "sdetkit", "doctor", "--format", "json", "--out", "build/doctor.json"]),
    ]
    results: list[dict[str, Any]] = []
    for step_id, cmd in commands:
        proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True)
        results.append({"id": step_id, "cmd": cmd, "rc": proc.returncode})
    return results


def _load_artifact(path: Path) -> tuple[str, bool | None, list[str]]:
    if not path.exists():
        return "missing", None, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "invalid-json", None, []
    ok = payload.get("ok")
    failed_steps = payload.get("failed_steps")
    return (
        "present",
        ok if isinstance(ok, bool) else None,
        list(failed_steps) if isinstance(failed_steps, list) else [],
    )


def _build_summary(repo_root: Path) -> dict[str, Any]:
    artifact_map = {
        "gate_fast": repo_root / "build" / "gate-fast.json",
        "gate_release": repo_root / "build" / "release-preflight.json",
        "doctor": repo_root / "build" / "doctor.json",
    }
    checks: dict[str, dict[str, Any]] = {}
    actions: list[str] = []
    for key, path in artifact_map.items():
        state, ok, failed_steps = _load_artifact(path)
        checks[key] = {"path": str(path.relative_to(repo_root)), "state": state, "ok": ok, "failed_steps": failed_steps}
        if state != "present":
            actions.append(f"Run canonical step for {key}: missing artifact.")
        elif ok is False:
            actions.append(f"Triage {key}: inspect failed_steps in {path.name}.")
    overall_ready = all(item["ok"] is True for item in checks.values())
    if overall_ready:
        actions.append("Canonical onboarding path is green.")
    return {"schema_version": "1", "overall_ready": overall_ready, "checks": checks, "actions": actions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/operator_onboarding_wizard.py")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out", default=".sdetkit/out/operator-onboarding-summary.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(argv)

    repo_root = Path(ns.repo_root).resolve()
    run_results = _run_canonical(repo_root, ns.python) if ns.run else []
    summary = _build_summary(repo_root)
    summary["run_results"] = run_results
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if ns.format == "json":
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"operator-onboarding: {'READY' if summary['overall_ready'] else 'NOT_READY'}")
        for action in summary["actions"]:
            print(f"- {action}")
    return 0 if summary["overall_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
