from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run adoption-focused validation suite and emit summary."
    )
    parser.add_argument(
        "--command",
        default=(
            "python -m pytest -q "
            "tests/test_adoption_cli.py "
            "tests/test_adoption_followup_contract.py "
            "tests/test_render_adoption_posture.py "
            "tests/test_adoption_control_loop_artifacts.py "
            "tests/test_fit_cli.py"
        ),
        help="Shell-like command string to execute for validation.",
    )
    parser.add_argument("--out", type=Path, default=Path("build/adoption-validation-summary.json"))
    args = parser.parse_args(argv)

    cmd = shlex.split(args.command)
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    payload: dict[str, Any] = {
        "schema_version": "sdetkit.adoption_validation.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "command": cmd,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout.splitlines()[-40:],
        "stderr_tail": proc.stderr.splitlines()[-40:],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("ADOPTION_VALIDATION=PASS" if payload["ok"] else "ADOPTION_VALIDATION=FAIL")
    print(f"ADOPTION_VALIDATION_SUMMARY={args.out}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
