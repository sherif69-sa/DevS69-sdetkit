from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from shutil import which


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    stdout_log: str
    stderr_log: str
    artifact: str | None


def _run_step(
    *,
    name: str,
    command: list[str],
    out_dir: Path,
    artifact: str | None,
    env: dict[str, str],
) -> StepResult:
    proc = subprocess.run(command, check=False, text=True, capture_output=True, env=env)
    stdout_log = out_dir / f"{name}.stdout.log"
    stderr_log = out_dir / f"{name}.stderr.log"
    stdout_log.write_text(proc.stdout, encoding="utf-8")
    stderr_log.write_text(proc.stderr, encoding="utf-8")
    return StepResult(
        name=name,
        command=command,
        returncode=proc.returncode,
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
        artifact=artifact,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the canonical first-proof lane (gate fast -> gate release -> doctor)."
    )
    parser.add_argument(
        "--python",
        default=None,
        help="Python interpreter used to run `python -m sdetkit ...` commands.",
    )
    parser.add_argument(
        "--out-dir",
        default="build/first-proof",
        help="Directory where first-proof artifacts and logs are written.",
    )
    parser.add_argument(
        "--skip-doctor",
        action="store_true",
        help="Skip `doctor` for environments that only need gate evidence.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when any first-proof step fails.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _python_version_tuple(python_cmd: str) -> tuple[int, int] | None:
    proc = subprocess.run(
        [python_cmd, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if "." not in raw:
        return None
    major_raw, minor_raw = raw.split(".", 1)
    try:
        return int(major_raw), int(minor_raw)
    except ValueError:
        return None


def _resolve_python(explicit: str | None) -> str:
    if explicit:
        return explicit

    candidates: list[str] = []
    for raw in [sys.executable, "python3.13", "python3.12", "python3.11", "python3"]:
        if raw == sys.executable:
            candidates.append(raw)
            continue
        resolved = which(raw)
        if resolved:
            candidates.append(resolved)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        version = _python_version_tuple(candidate)
        if version is None:
            continue
        if version >= (3, 11):
            return candidate

    return sys.executable


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv[1:])
    selected_python = _resolve_python(args.python)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_env = dict(os.environ)
    existing_pythonpath = base_env.get("PYTHONPATH", "")
    repo_src = str(Path("src").resolve())
    if existing_pythonpath:
        base_env["PYTHONPATH"] = f"{repo_src}{os.pathsep}{existing_pythonpath}"
    else:
        base_env["PYTHONPATH"] = repo_src

    steps: list[StepResult] = []
    steps.append(
        _run_step(
            name="gate-fast",
            command=[
                selected_python,
                "-m",
                "sdetkit",
                "gate",
                "fast",
                "--format",
                "json",
                "--stable-json",
                "--out",
                str(out_dir / "gate-fast.json"),
            ],
            out_dir=out_dir,
            artifact=str(out_dir / "gate-fast.json"),
            env=base_env,
        )
    )
    steps.append(
        _run_step(
            name="gate-release",
            command=[
                selected_python,
                "-m",
                "sdetkit",
                "gate",
                "release",
                "--format",
                "json",
                "--out",
                str(out_dir / "release-preflight.json"),
            ],
            out_dir=out_dir,
            artifact=str(out_dir / "release-preflight.json"),
            env=base_env,
        )
    )
    if not args.skip_doctor:
        steps.append(
            _run_step(
                name="doctor",
                command=[
                    selected_python,
                    "-m",
                    "sdetkit",
                    "doctor",
                    "--format",
                    "json",
                    "--out",
                    str(out_dir / "doctor.json"),
                ],
                out_dir=out_dir,
                artifact=str(out_dir / "doctor.json"),
                env=base_env,
            )
        )

    ok = all(step.returncode == 0 for step in steps)
    payload = {
        "ok": ok,
        "decision": "SHIP" if ok else "NO-SHIP",
        "decision_line": f"FIRST_PROOF_DECISION={'SHIP' if ok else 'NO-SHIP'}",
        "strict": bool(args.strict),
        "selected_python": selected_python,
        "steps": [asdict(step) for step in steps],
        "failed_steps": [step.name for step in steps if step.returncode != 0],
    }
    summary_path = out_dir / "first-proof-summary.json"
    summary_path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = "ok" if ok else "failed"
        print(f"first-proof {status}: summary={summary_path}")
        print(payload["decision_line"])
        for step in steps:
            print(f"- {step.name}: rc={step.returncode} artifact={step.artifact}")

    if args.strict and not ok:
        return 1
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main(sys.argv))
