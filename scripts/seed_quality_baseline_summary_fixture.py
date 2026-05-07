from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_SUMMARY: dict[str, Any] = {
    "schema_version": "sdetkit.phase1_baseline.v1",
    "generated_at_utc": "2026-04-19T00:00:00Z",
    "out_dir": "build/phase1-baseline",
    "ok": False,
    "checks": [
        {
            "id": "doctor",
            "ok": False,
            "rc": 1,
            "stdout_log": "build/phase1-baseline/logs/doctor.out.log",
            "stderr_log": "build/phase1-baseline/logs/doctor.err.log",
        },
        {
            "id": "enterprise_contracts",
            "ok": True,
            "rc": 0,
            "stdout_log": "build/phase1-baseline/logs/enterprise_contracts.out.log",
            "stderr_log": "build/phase1-baseline/logs/enterprise_contracts.err.log",
        },
        {
            "id": "primary_docs_map",
            "ok": True,
            "rc": 0,
            "stdout_log": "build/phase1-baseline/logs/primary_docs_map.out.log",
            "stderr_log": "build/phase1-baseline/logs/primary_docs_map.err.log",
        },
        {
            "id": "pytest",
            "ok": False,
            "rc": 1,
            "stdout_log": "build/phase1-baseline/logs/pytest.out.log",
            "stderr_log": "build/phase1-baseline/logs/pytest.err.log",
        },
        {
            "id": "ruff",
            "ok": True,
            "rc": 0,
            "stdout_log": "build/phase1-baseline/logs/ruff.out.log",
            "stderr_log": "build/phase1-baseline/logs/ruff.err.log",
        },
    ],
}


def seed_summary(path: Path, *, force: bool = False) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT_SUMMARY, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary",
        default="build/phase1-baseline/phase1-baseline-summary.json",
        help="Path to the quality baseline summary fixture.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.summary)
    seeded = seed_summary(path, force=bool(args.force))
    print(json.dumps({"ok": True, "seeded": seeded, "summary": path.as_posix()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
