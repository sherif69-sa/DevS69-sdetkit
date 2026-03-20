from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = Path(__file__).with_name("golden")

GOLDEN_CASES = [
    (
        "intelligence_flake_classify",
        [
            "intelligence",
            "flake",
            "classify",
            "--history",
            "examples/kits/intelligence/flake-history.json",
        ],
        0,
    ),
    (
        "integration_topology_check",
        [
            "integration",
            "topology-check",
            "--profile",
            "examples/kits/integration/heterogeneous-topology.json",
        ],
        0,
    ),
    (
        "forensics_compare",
        [
            "forensics",
            "compare",
            "--from",
            "examples/kits/forensics/run-a.json",
            "--to",
            "examples/kits/forensics/run-b.json",
        ],
        0,
    ),
]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _normalize_json(stdout: str) -> str:
    payload = json.loads(stdout)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def test_example_commands_match_committed_goldens() -> None:
    for name, args, expected_rc in GOLDEN_CASES:
        proc = _run(args)
        assert proc.returncode == expected_rc, proc.stderr
        actual = _normalize_json(proc.stdout)
        golden_path = GOLDEN_DIR / f"{name}.json"
        assert actual == golden_path.read_text(encoding="utf-8")
