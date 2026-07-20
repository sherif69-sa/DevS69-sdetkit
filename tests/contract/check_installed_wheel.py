from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, cast


def _run(cli_python: Path, repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("CI", None)
    return subprocess.run(
        [str(cli_python), "-m", "sdetkit", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _load_json(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    if proc.stdout.strip() == "":
        raise AssertionError(f"expected JSON stdout, got empty output; stderr={proc.stderr!r}")
    return cast(dict[str, Any], json.loads(proc.stdout))


def _run_module(
    cli_python: Path,
    cwd: Path,
    module: str,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("CI", None)
    return subprocess.run(
        [str(cli_python), "-m", module, *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _assert_denied(payload: dict[str, Any], failures: list[str], name: str) -> None:
    boundary = payload.get("authority_boundary", payload)
    for key in (
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    ):
        if boundary.get(key) is not False:
            failures.append(f"{name} did not deny {key}: {boundary!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run installed-wheel CLI contract checks.")
    parser.add_argument(
        "--python",
        required=True,
        help="Python executable inside the isolated wheel venv.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing example assets.",
    )
    ns = parser.parse_args(argv)

    cli_python = Path(ns.python).resolve()
    repo_root = Path(ns.repo_root).resolve()

    failures: list[str] = []

    def check(name: str, proc: subprocess.CompletedProcess[str]) -> None:
        if proc.returncode != 0:
            failures.append(
                f"{name} failed with rc={proc.returncode}\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )

    kits = _run(cli_python, repo_root, "kits", "list", "--format", "json")
    check("kits list", kits)
    if kits.returncode == 0:
        payload = _load_json(kits)
        slugs = [item.get("slug") for item in payload.get("kits", []) if isinstance(item, dict)]
        if slugs != ["forensics", "integration", "release", "intelligence"]:
            failures.append(f"kits list returned unexpected slugs: {slugs!r}")

    flake = _run(
        cli_python,
        repo_root,
        "intelligence",
        "flake",
        "classify",
        "--history",
        "examples/kits/intelligence/flake-history.json",
    )
    check("intelligence flake classify", flake)
    if flake.returncode == 0:
        payload = _load_json(flake)
        summary = payload.get("summary", {})
        tests = payload.get("tests", [])
        if summary != {"flaky": 1, "stable_failing": 0, "stable_passing": 1}:
            failures.append(f"unexpected flake summary: {summary!r}")
        if not tests or not isinstance(tests[0], dict) or not tests[0].get("fingerprint"):
            failures.append(
                "flake classification did not expose the expected fingerprinted test record"
            )

    integration = _run(
        cli_python,
        repo_root,
        "integration",
        "check",
        "--profile",
        "examples/kits/integration/profile.json",
    )
    check("integration check", integration)
    if integration.returncode == 0:
        payload = _load_json(integration)
        summary = payload.get("summary", {})
        if (
            summary.get("failed") != 0
            or summary.get("passed") is not True
            or summary.get("total") != 0
        ):
            failures.append(f"unexpected integration summary: {summary!r}")
        if payload.get("checks") != []:
            failures.append(f"unexpected integration checks: {payload.get('checks')!r}")

    compare = _run(
        cli_python,
        repo_root,
        "forensics",
        "compare",
        "--from",
        "examples/kits/forensics/run-a.json",
        "--to",
        "examples/kits/forensics/run-b.json",
    )
    check("forensics compare", compare)
    if compare.returncode == 0:
        payload = _load_json(compare)
        regression = payload.get("regression_summary", {})
        if regression.get("changed_failures") != 1 or regression.get("new_failures") != 1:
            failures.append(f"unexpected forensics regression summary: {regression!r}")

    bundle_path = repo_root / "build" / "installed-wheel-bundle.zip"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = _run(
        cli_python,
        repo_root,
        "forensics",
        "bundle",
        "--run",
        "examples/kits/forensics/run-b.json",
        "--output",
        str(bundle_path),
    )
    check("forensics bundle", bundle)
    if bundle.returncode == 0:
        if not bundle_path.exists():
            failures.append(f"bundle artifact was not created at {bundle_path}")
        else:
            with zipfile.ZipFile(bundle_path) as zf:
                names = sorted(zf.namelist())
            if names != ["manifest.json", "run.json"]:
                failures.append(f"unexpected bundle members: {names!r}")

    with tempfile.TemporaryDirectory(prefix="sdetkit-wheel-dogfood-") as raw_tmp:
        temp_root = Path(raw_tmp)
        fixture = temp_root / "mixed-repo"
        (fixture / "src").mkdir(parents=True)
        (fixture / "tests").mkdir()
        (fixture / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nproject(Fixture)\n",
            encoding="utf-8",
        )
        (fixture / "src" / "main.cpp").write_text(
            "int main() { return 0; }\n",
            encoding="utf-8",
        )
        (fixture / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (fixture / "config.env").write_text(
            "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890\n",
            encoding="utf-8",
        )

        adoption_out = temp_root / "adoption.json"
        adoption = _run(
            cli_python,
            fixture,
            "adoption-surface",
            "--root",
            str(fixture),
            "--out",
            str(adoption_out),
            "--format",
            "text",
        )
        check("installed-wheel adoption surface", adoption)
        if adoption.returncode == 0:
            payload = cast(dict[str, Any], json.loads(adoption_out.read_text(encoding="utf-8")))
            languages = {
                item.get("name")
                for item in payload.get("detected_languages", [])
                if isinstance(item, dict)
            }
            if "cpp" not in languages or "python" not in languages:
                failures.append(f"adoption surface missed fixture languages: {languages!r}")
            _assert_denied(payload, failures, "adoption surface")

        sarif = temp_root / "security.sarif"
        sbom = temp_root / "sbom.cdx.json"
        security = _run(
            cli_python,
            fixture,
            "security",
            "scan",
            "--fail-on",
            "none",
            "--format",
            "sarif",
            "--output",
            str(sarif),
            "--sbom-output",
            str(sbom),
        )
        check("installed-wheel security scan", security)
        if security.returncode == 0 and (not sarif.exists() or not sbom.exists()):
            failures.append("security scan did not create SARIF and SBOM artifacts")

        pytest_log = temp_root / "pytest.log"
        pytest_log.write_text(
            "FAILED tests/test_calc.py::test_add - assert 2 == 3\n"
            "Error: Process completed with exit code 1\n",
            encoding="utf-8",
        )
        triage = _run(
            cli_python,
            fixture,
            "investigate",
            "failure",
            "--log",
            str(pytest_log),
            "--format",
            "json",
        )
        check("installed-wheel pytest triage", triage)
        if triage.returncode == 0:
            payload = _load_json(triage)
            if payload.get("classification") != "PYTEST_ASSERTION_FAILURE":
                failures.append(f"unexpected pytest classification: {payload!r}")
            if payload.get("automation_allowed") is not False:
                failures.append("pytest triage granted automation authority")

        non_cpp = temp_root / "non-cpp"
        non_cpp.mkdir()
        (non_cpp / "README.md").write_text("# No C++ source\n", encoding="utf-8")
        cpp_log = temp_root / "cpp.log"
        cpp_log.write_text(
            "Run g++ -c src/main.cpp\n"
            "src/main.cpp:10:5: error: no matching function for call\n"
            "Error: Process completed with exit code 1\n",
            encoding="utf-8",
        )
        cpp_out = temp_root / "cpp-proof"
        cpp = _run_module(
            cli_python,
            repo_root,
            "sdetkit.cpp_operator_proof",
            "--repo",
            str(non_cpp),
            "--failure-log",
            str(cpp_log),
            "--out-dir",
            str(cpp_out),
            "--check",
            "compile",
            "--format",
            "json",
        )
        if cpp.returncode != 1:
            failures.append(
                f"C++ structured review expected rc=1, got {cpp.returncode}: {cpp.stderr}"
            )
        else:
            payload = _load_json(cpp)
            if payload.get("verification_ok") is not False:
                failures.append(f"C++ proof did not expose failed verification: {payload!r}")
            _assert_denied(payload, failures, "C++ proof")
            if not (cpp_out / "cpp-operator-proof.json").exists():
                failures.append("C++ proof did not retain its structured JSON artifact")

        sha = "a" * 64
        scope = ["sample.py"]

        def inventory(path: str, digest: str) -> dict[str, Any]:
            return {"path": path, "sha256": digest, "size_bytes": 10}

        def artifact(path: str) -> dict[str, str]:
            return {"path": path, "sha256": sha}

        scenarios = {
            "ambiguous": {
                "outcome": "blocked",
                "artifact_path": "build/ambiguous.json",
                "sha256": sha,
                "notes": "blocked",
            },
            "no_op": {
                "outcome": "pass",
                "artifact_path": "build/no-op.json",
                "sha256": sha,
                "notes": "pass",
            },
            "oracle": {
                "outcome": "pass",
                "artifact_path": "build/oracle.json",
                "sha256": sha,
                "notes": "pass",
            },
            "out_of_scope": {
                "outcome": "blocked",
                "artifact_path": "build/out-of-scope.json",
                "sha256": sha,
                "notes": "blocked",
            },
            "rollback": {
                "outcome": "pass",
                "artifact_path": "build/rollback-scenario.json",
                "sha256": sha,
                "notes": "pass",
            },
            "unsafe_patch": {
                "outcome": "pass",
                "artifact_path": "build/unsafe.json",
                "sha256": sha,
                "notes": "must remain blocked",
            },
        }
        evidence = {
            "schema_version": "sdetkit.remediation_research_evidence.v1",
            "candidate_family": "formatter_only",
            "failure_class": "format_drift",
            "source_repository": "fixture/repo",
            "source_commit_sha": "b" * 40,
            "pr_number": 1,
            "pr_owned_scope": scope,
            "before_inventory": [inventory(scope[0], sha)],
            "after_inventory": [inventory(scope[0], "c" * 64)],
            "proposed_diff": {
                "artifact_path": "build/proposed.diff",
                "sha256": sha,
                "files": scope,
                "line_count": 1,
            },
            "focused_proof": {
                "status": "pass",
                "commands": ["format --check"],
                "artifacts": [artifact("build/focused.json")],
                "notes": "pass",
            },
            "full_proof": {
                "status": "pass",
                "commands": ["full proof"],
                "artifacts": [artifact("build/full.json")],
                "notes": "pass",
            },
            "rollback": {
                "strategy": "restore_exact_bytes",
                "verified": True,
                "artifact_path": "build/rollback.json",
                "sha256": sha,
                "restored_inventory_sha256": sha,
                "notes": "pass",
            },
            "reviewer_record": {
                "reviewer_id": "maintainer",
                "reviewed_at": "2026-07-21T00:00:00Z",
                "decision": "accept",
                "notes": "research only",
            },
            "false_authority_count": 0,
            "limitations": ["No patch authority."],
            "scenarios": scenarios,
        }
        evidence_path = temp_root / "remediation-evidence.json"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        remediation = _run_module(
            cli_python,
            repo_root,
            "sdetkit.remediation_research_contract",
            str(evidence_path),
            "--contract-json",
            str(repo_root / "docs/contracts/remediation-research.v1.json"),
            "--format",
            "json",
        )
        if remediation.returncode != 0:
            failures.append(
                f"remediation review report failed with rc={remediation.returncode}: {remediation.stderr}"
            )
        else:
            payload = _load_json(remediation)
            if payload.get("report_status") != "review_required":
                failures.append(f"unsafe remediation scenario was not blocked: {payload!r}")
            reasons = payload.get("readiness_reasons", [])
            if not any(
                str(reason).startswith("scenario_outcome_mismatch:unsafe_patch")
                for reason in reasons
            ):
                failures.append(f"unsafe remediation reason missing: {reasons!r}")
            _assert_denied(payload, failures, "remediation report")

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1

    print("installed-wheel contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
