from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, cast


def _run(cli_python: Path, repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(cli_python), "-m", "sdetkit", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _load_json(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    if proc.stdout.strip() == "":
        raise AssertionError(f"expected JSON stdout, got empty output; stderr={proc.stderr!r}")
    return cast(dict[str, Any], json.loads(proc.stdout))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run installed-wheel CLI contract checks.")
    parser.add_argument(
        "--python", required=True, help="Python executable inside the isolated wheel venv."
    )
    parser.add_argument(
        "--repo-root", default=".", help="Repository root containing example assets."
    )
    ns = parser.parse_args(argv)

    cli_python = Path(ns.python)
    repo_root = Path(ns.repo_root).resolve()

    failures: list[str] = []

    def check(name: str, proc: subprocess.CompletedProcess[str]) -> None:
        if proc.returncode != 0:
            failures.append(
                f"{name} failed with rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
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
    if integration.returncode != 1:
        failures.append("integration check should fail the bundled local-smoke profile outside CI")
    else:
        payload = _load_json(integration)
        summary = payload.get("summary", {})
        if summary.get("failed") != 1 or summary.get("passed") is not False:
            failures.append(f"unexpected integration summary: {summary!r}")
        checks = payload.get("checks", [])
        env_checks = [
            item for item in checks if isinstance(item, dict) and item.get("kind") == "env"
        ]
        if not env_checks or env_checks[0].get("name") != "CI":
            failures.append(f"unexpected integration env checks: {env_checks!r}")

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

    if failures:
        sys.stderr.write("\n\n".join(failures) + "\n")
        return 1

    print("installed-wheel contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
