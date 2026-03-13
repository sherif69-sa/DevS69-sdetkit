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


def test_intelligence_contracts_and_failure_fingerprinting() -> None:
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
    assert flake_json["tests"][0]["next_step"]

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

    fingerprint = _run(
        "intelligence",
        "failure-fingerprint",
        "--failures",
        "examples/kits/intelligence/failures.json",
    )
    assert fingerprint.returncode == 0
    fingerprint_json = json.loads(fingerprint.stdout)
    assert fingerprint_json["schema_version"] == "sdetkit.intelligence.failure-fingerprint.v1"
    assert fingerprint_json["summary"]["with_nondeterminism_hints"] >= 1


def test_intelligence_failure_mode_invalid_failures_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad-failures.json"
    bad.write_text('{"oops": []}', encoding="utf-8")
    proc = _run("intelligence", "failure-fingerprint", "--failures", str(bad))
    assert proc.returncode == 2
    assert "intelligence error" in proc.stderr


def test_integration_and_forensics_contracts_and_bundle_determinism(tmp_path: Path) -> None:
    integration = _run(
        "integration", "check", "--profile", "examples/kits/integration/profile.json"
    )
    assert integration.returncode in {0, 1}
    integration_json = json.loads(integration.stdout)
    assert integration_json["schema_version"] == "sdetkit.integration.profile-check.v1"
    assert integration_json["summary"]["next_step"]

    cassette = tmp_path / "cassette.json"
    cassette.write_text(
        json.dumps(
            {
                "version": 1,
                "interactions": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "https://example.com/ping",
                            "body_b64": "",
                            "headers": [],
                        },
                        "response": {"status_code": 200, "headers": [], "body_b64": ""},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cval = _run("integration", "cassette-validate", "--cassette", str(cassette))
    assert cval.returncode == 0
    cval_json = json.loads(cval.stdout)
    assert cval_json["schema_version"] == "sdetkit.integration.cassette-validate.v1"

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
    assert "regression_summary" in cmp_json

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

    diff_same = _run(
        "forensics", "bundle-diff", "--from-bundle", str(out1), "--to-bundle", str(out2)
    )
    assert diff_same.returncode == 0
    diff_same_json = json.loads(diff_same.stdout)
    assert diff_same_json["schema_version"] == "sdetkit.forensics.bundle-diff.v1"
    assert diff_same_json["summary"]["passed"] is True


def test_forensics_compare_fail_on_warn_exit_code() -> None:
    proc = _run(
        "forensics",
        "compare",
        "--from",
        "examples/kits/forensics/run-a.json",
        "--to",
        "examples/kits/forensics/run-b.json",
        "--fail-on",
        "warn",
    )
    assert proc.returncode == 1


def test_forensics_bundle_include_tracks_manifest_and_sanitizes_names(tmp_path: Path) -> None:
    nested = tmp_path / "logs" / "session.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("failure details", encoding="utf-8")

    output = tmp_path / "bundle.zip"
    proc = _run(
        "forensics",
        "bundle",
        "--run",
        "examples/kits/forensics/run-b.json",
        "--output",
        str(output),
        "--include",
        str(nested),
        str(tmp_path / "missing.log"),
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    extras = payload["manifest"]["extras"]
    assert len(extras) == 2
    included = [entry for entry in extras if entry["status"] == "included"]
    missing = [entry for entry in extras if entry["status"] == "missing"]
    assert len(included) == 1
    assert len(missing) == 1
    assert included[0]["stored"].startswith("extras/")
    assert "/" not in included[0]["stored"].removeprefix("extras/")
    assert missing[0]["stored"] is None

    with zipfile.ZipFile(output) as zf:
        assert included[0]["stored"] in zf.namelist()


def test_release_alias_backward_compatibility() -> None:
    direct = _run("gate", "fast")
    via_release = _run("release", "gate", "fast")
    assert direct.returncode == via_release.returncode
