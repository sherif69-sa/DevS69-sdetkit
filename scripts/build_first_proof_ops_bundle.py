from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build first-proof operational bundle artifacts.")
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    summary = root / "first-proof-summary.json"

    _run(
        [
            sys.executable,
            "scripts/build_first_proof_health_score.py",
            "--summary",
            str(summary),
            "--out-json",
            str(root / "health-score.json"),
            "--out-md",
            str(root / "health-score.md"),
            "--format",
            "json",
        ]
    )

    _run(
        [
            sys.executable,
            "scripts/doctor_remediate.py",
            "--summary",
            str(summary),
            "--out-json",
            str(root / "doctor-remediate.json"),
            "--out-md",
            str(root / "doctor-remediate.md"),
            "--limit",
            "3",
            "--format",
            "json",
        ]
    )

    _run(
        [
            sys.executable,
            "scripts/operator_onboarding_next.py",
            "--summary",
            str(summary),
            "--out-json",
            "build/onboarding-next.json",
            "--out-md",
            "build/onboarding-next.md",
            "--format",
            "json",
        ]
    )

    _run(
        [
            sys.executable,
            "scripts/check_first_proof_artifact_freshness.py",
            "--artifact-dir",
            str(root),
            "--max-age-hours",
            "48",
            "--out",
            str(root / "artifact-freshness.json"),
            "--format",
            "json",
        ]
    )

    manifest = {
        "ok": True,
        "bundle": "first-proof-ops",
        "artifacts": [
            str(root / "health-score.json"),
            str(root / "doctor-remediate.json"),
            str(root / "artifact-freshness.json"),
            "build/onboarding-next.json",
        ],
    }
    (root / "ops-bundle-manifest.json").write_text(
        __import__("json").dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.format == "json":
        print(__import__("json").dumps(manifest, indent=2, sort_keys=True))
    else:
        print("first-proof-ops-bundle: built health/remediation/onboarding/freshness artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
