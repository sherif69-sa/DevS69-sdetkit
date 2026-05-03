from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_text(args: Sequence[str], *, cwd: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return 127, str(exc)
    output = completed.stdout.strip() or completed.stderr.strip()
    return completed.returncode, output


def _git_value(repo: Path, args: Sequence[str], fallback: str) -> str:
    rc, output = _run_text(["git", *args], cwd=repo)
    if rc != 0 or not output:
        return fallback
    return output.splitlines()[0].strip() or fallback


def _git_dirty(repo: Path) -> bool:
    rc, output = _run_text(["git", "status", "--short"], cwd=repo)
    return rc == 0 and bool(output.strip())


def _command_steps() -> list[dict[str, Any]]:
    return [
        {
            "id": "gate_fast",
            "label": "Fast release confidence gate",
            "command": "python -m sdetkit gate fast",
            "status": "ready",
            "tier": "public_stable",
        },
        {
            "id": "gate_release",
            "label": "Strict release confidence gate",
            "command": "python -m sdetkit gate release",
            "status": "ready",
            "tier": "public_stable",
        },
        {
            "id": "doctor",
            "label": "Repository and release-readiness diagnostics",
            "command": "python -m sdetkit doctor",
            "status": "ready",
            "tier": "public_stable",
        },
        {
            "id": "review",
            "label": "Operator review workflow",
            "command": "python -m sdetkit review . --profile release --format operator-json",
            "status": "ready",
            "tier": "public_stable",
        },
        {
            "id": "readiness",
            "label": "Production readiness scorecard",
            "command": "python -m sdetkit readiness",
            "status": "ready",
            "tier": "public_stable",
        },
        {
            "id": "release_room",
            "label": "Release-room plan",
            "command": "python -m sdetkit release-room",
            "status": "planned",
            "tier": "future_public_surface",
        },
    ]


def _artifact(path: Path, label: str, kind: str) -> dict[str, str]:
    return {
        "label": label,
        "kind": kind,
        "path": path.as_posix(),
    }


def build_bundle(repo: Path, out_dir: Path) -> dict[str, Any]:
    repo = repo.resolve()
    out_dir = out_dir.resolve()
    generated_at = _utc_now()
    branch = _git_value(repo, ["branch", "--show-current"], "unknown")
    commit = _git_value(repo, ["rev-parse", "HEAD"], "unknown")
    dirty = _git_dirty(repo)

    steps = _command_steps()
    findings = []
    if dirty:
        findings.append(
            {
                "severity": "warning",
                "code": "WORKTREE_DIRTY",
                "message": "Working tree has uncommitted changes.",
            }
        )

    next_actions = [
        {
            "id": "run_fast_gate",
            "command": "python -m sdetkit gate fast",
            "reason": "Check fast release-confidence feedback first.",
        },
        {
            "id": "run_release_gate",
            "command": "python -m sdetkit gate release",
            "reason": "Run strict release gate before operator signoff.",
        },
        {
            "id": "run_doctor",
            "command": "python -m sdetkit doctor",
            "reason": "Collect deterministic repository diagnostics.",
        },
    ]

    decision = "SHIP_WITH_FINDINGS" if findings else "SHIP"
    risk_band = "medium" if findings else "low"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "ok": True,
        "decision": decision,
        "risk_band": risk_band,
        "repo": {
            "path": repo.as_posix(),
            "branch": branch,
            "commit": commit,
            "dirty": dirty,
        },
        "steps": steps,
        "findings": findings,
        "artifacts": [
            _artifact(out_dir / "mission-control.json", "Mission Control JSON bundle", "json"),
            _artifact(out_dir / "mission-control.md", "Mission Control operator brief", "markdown"),
        ],
        "next_actions": next_actions,
    }


def render_markdown(bundle: dict[str, Any]) -> str:
    repo = bundle["repo"]
    lines = [
        "# Mission Control",
        "",
        f"Generated: {bundle['generated_at_utc']}",
        f"Decision: {bundle['decision']}",
        f"Risk band: {bundle['risk_band']}",
        f"Repository: {repo['path']}",
        f"Branch: {repo['branch']}",
        f"Commit: {repo['commit']}",
        f"Dirty: {str(repo['dirty']).lower()}",
        "",
        "## Steps",
        "",
    ]

    for step in bundle["steps"]:
        lines.append(f"- {step['id']}: {step['status']} - `{step['command']}`")

    lines.extend(["", "## Findings", ""])

    if bundle["findings"]:
        for finding in bundle["findings"]:
            lines.append(f"- {finding['severity']}: {finding['code']} - {finding['message']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Next actions", ""])

    for action in bundle["next_actions"]:
        lines.append(f"- {action['id']}: `{action['command']}`")

    lines.append("")
    return "\n".join(lines)


def write_bundle(bundle: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "mission-control.json"
    md_path = out_dir / "mission-control.md"
    json_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(bundle), encoding="utf-8")
    return json_path, md_path


def _run(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    out_dir = Path(args.out_dir)
    bundle = build_bundle(repo, out_dir)
    json_path, md_path = write_bundle(bundle, out_dir)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(f"decision={bundle['decision']} risk_band={bundle['risk_band']}")
    return 0


def _summarize(args: argparse.Namespace) -> int:
    path = Path(args.bundle)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    print(f"decision={bundle['decision']}")
    print(f"risk_band={bundle['risk_band']}")
    print(f"repo={bundle['repo']['path']}")
    print(f"steps={len(bundle['steps'])}")
    print(f"findings={len(bundle['findings'])}")
    return 0


def _schema(_: argparse.Namespace) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "required_top_level_keys": [
            "schema_version",
            "generated_at_utc",
            "ok",
            "decision",
            "risk_band",
            "repo",
            "steps",
            "findings",
            "artifacts",
            "next_actions",
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit mission-control",
        description="Create a deterministic release-confidence evidence bundle.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Write mission-control.json and mission-control.md")
    run.add_argument("--repo", default=".")
    run.add_argument("--out-dir", default="build/mission-control")
    run.set_defaults(func=_run)

    summarize = sub.add_parser("summarize", help="Summarize a mission-control.json bundle")
    summarize.add_argument("--bundle", required=True)
    summarize.set_defaults(func=_summarize)

    schema = sub.add_parser("schema", help="Print the Mission Control bundle schema summary")
    schema.set_defaults(func=_schema)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
