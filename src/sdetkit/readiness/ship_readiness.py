from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _extract_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    start = text.find("{")
    if start == -1:
        return {}
    candidate = text[start:]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_command(
    command: str,
    *,
    root: Path,
    timeout_sec: int,
    retries: int,
    retry_delay_sec: float,
    log_path: Path | None,
) -> dict[str, Any]:
    argv = shlex.split(command)
    if argv and argv[0] == "python":
        argv[0] = sys.executable

    env = dict(os.environ)
    src_path = str(root / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )

    attempts = 0
    result: dict[str, Any] = {}
    stdout = ""
    stderr = ""
    while attempts <= retries:
        attempts += 1
        try:
            proc = subprocess.run(
                argv,
                cwd=str(root),
                shell=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout_sec,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            error_kind = "none" if proc.returncode == 0 else "command_failed"
            result = {
                "command": command,
                "return_code": proc.returncode,
                "ok": proc.returncode == 0,
                "error_kind": error_kind,
                "parsed_json": _extract_json(proc.stdout),
            }
        except subprocess.TimeoutExpired as exc:
            result = {
                "command": command,
                "return_code": 124,
                "ok": False,
                "error": f"timeout after {timeout_sec}s",
                "error_kind": "timeout",
                "parsed_json": {},
            }
            stdout = ""
            stderr = str(exc)

        should_retry = (not result["ok"]) and result["error_kind"] in {"timeout"}
        if should_retry and attempts <= retries:
            time.sleep(retry_delay_sec)
            continue
        break
    result["attempts"] = attempts

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "\n".join(
                [
                    f"$ {command}",
                    f"return_code: {result['return_code']}",
                    "",
                    "stdout:",
                    stdout.rstrip(),
                    "",
                    "stderr:",
                    stderr.rstrip(),
                    "",
                ]
            ),
            encoding="utf-8",
        )

    return result


def _build_release_contract(results: list[dict[str, Any]]) -> dict[str, Any]:
    catalog = {row["id"]: row for row in results}
    gate_fast_ok = catalog.get("gate_fast", {}).get("ok", False)
    gate_release_ok = catalog.get("gate_release", {}).get("ok", False)
    doctor_ok = catalog.get("doctor", {}).get("ok", False)
    release_readiness_ok = catalog.get("release_readiness", {}).get("ok", False)

    all_green = all(row["ok"] for row in results)
    blockers: list[str] = []
    blocker_catalog: list[dict[str, Any]] = []
    for row in results:
        if not row["ok"]:
            blockers.append(row["id"])
            blocker_catalog.append(
                {
                    "id": row["id"],
                    "error_kind": row.get("error_kind", "unknown"),
                    "attempts": row.get("attempts", 1),
                    "return_code": row.get("return_code", -1),
                }
            )

    decision = "go" if all_green else "no-go"
    return {
        "gate_fast_ok": gate_fast_ok,
        "gate_release_ok": gate_release_ok,
        "doctor_ok": doctor_ok,
        "release_readiness_ok": release_readiness_ok,
        "all_green": all_green,
        "decision": decision,
        "blockers": blockers,
        "blocker_catalog": blocker_catalog,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit ship-readiness",
        description="Run an end-to-end ship readiness sequence and emit one release contract.",
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=Path("build/ship-readiness"))
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--retries", type=int, default=1, help="Retries for transient failures.")
    parser.add_argument(
        "--retry-delay-sec",
        type=float,
        default=1.0,
        help="Delay between retry attempts.",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--release-dry-run",
        action="store_true",
        help="Run gate release with --dry-run (useful for local premerge rehearsal lanes).",
    )
    parser.add_argument(
        "--include-enterprise",
        action="store_true",
        help="Also execute enterprise-assessment and include it in go/no-go contract.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    gate_release_cmd = "python -m sdetkit gate release --format json"
    if args.release_dry_run:
        gate_release_cmd += " --dry-run"
    commands = [
        ("gate_fast", "python -m sdetkit gate fast --format json --stable-json"),
        ("gate_release", gate_release_cmd),
        ("doctor", "python -m sdetkit doctor --format json"),
        ("release_readiness", "python -m sdetkit release-readiness --format json"),
    ]
    if args.include_enterprise:
        commands.append(
            ("enterprise_assessment", "python -m sdetkit enterprise-assessment --format json")
        )

    results: list[dict[str, Any]] = []
    for idx, (run_id, cmd) in enumerate(commands, start=1):
        result = _run_command(
            cmd,
            root=args.root,
            timeout_sec=args.timeout_sec,
            retries=max(0, args.retries),
            retry_delay_sec=max(0.0, args.retry_delay_sec),
            log_path=args.out_dir / "logs" / f"{idx:02d}-{run_id}.log",
        )
        result["id"] = run_id
        results.append(result)

    contract = _build_release_contract(results)
    payload = {
        "contract": {
            "schema_version": "sdetkit.ship_readiness.v1",
            "generated_at_utc": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        },
        "summary": contract,
        "runs": results,
    }
    (args.out_dir / "ship-readiness-summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print("ship-readiness")
        print(f"decision: {payload['summary']['decision']}")
        print(f"all_green: {payload['summary']['all_green']}")
        print(f"blockers: {', '.join(payload['summary']['blockers']) or 'none'}")

    if args.strict and not payload["summary"]["all_green"]:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
