from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True, cwd=cwd
    )


def test_intelligence_flake_impact_and_mutation_policy_contracts() -> None:
    flake = _run(
        "intelligence",
        "flake",
        "classify",
        "--history",
        "examples/kits/intelligence/flake-history.json",
    )
    assert flake.returncode == 0
    flake_json = json.loads(flake.stdout)
    assert flake_json["schema_version"] == "sdetkit.intelligence.flake.v1"
    assert flake_json["tests"][0]["fingerprint"]

    impact = _run(
        "intelligence",
        "impact",
        "summarize",
        "--changed",
        "examples/kits/intelligence/changed-files.txt",
        "--map",
        "examples/kits/intelligence/test-map.json",
    )
    assert impact.returncode == 0
    impact_json = json.loads(impact.stdout)
    assert impact_json["schema_version"] == "sdetkit.intelligence.impact.v1"
    assert impact_json["impacted_tests"] == sorted(impact_json["impacted_tests"])

    policy = _run(
        "intelligence",
        "mutation-policy",
        "--policy",
        "examples/kits/intelligence/mutation-policy.json",
    )
    assert policy.returncode == 0
    policy_json = json.loads(policy.stdout)
    assert policy_json["schema_version"] == "sdetkit.intelligence.mutation-policy.v1"
    assert policy_json["passed"] is True


def test_integration_and_forensics_contracts_and_bundle_determinism(tmp_path: Path) -> None:
    integration = _run("integration", "check", "--profile", "examples/kits/integration/profile.json")
    assert integration.returncode in {0, 1}
    integration_json = json.loads(integration.stdout)
    assert integration_json["schema_version"] == "sdetkit.integration.profile-check.v1"

    compare = _run(
        "forensics",
        "compare",
        "--from",
        "examples/kits/forensics/run-a.json",
        "--to",
        "examples/kits/forensics/run-b.json",
    )
    assert compare.returncode == 0
    cmp_json = json.loads(compare.stdout)
    assert cmp_json["schema_version"] == "sdetkit.forensics.compare.v1"

    out1 = tmp_path / "bundle1.zip"
    out2 = tmp_path / "bundle2.zip"
    cmd = [
        "forensics",
        "bundle",
        "--run",
        "examples/kits/forensics/run-b.json",
        "--output",
    ]
    b1 = _run(*cmd, str(out1))
    b2 = _run(*cmd, str(out2))
    assert b1.returncode == b2.returncode == 0
    assert out1.read_bytes() == out2.read_bytes()

    with zipfile.ZipFile(out1) as zf:
        names = sorted(zf.namelist())
    assert names == ["manifest.json", "run.json"]
