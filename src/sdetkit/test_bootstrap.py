from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_TEST_MODULES: tuple[str, ...] = ("httpx", "yaml", "hypothesis", "pre_commit")
MIN_TEST_PYTHON: tuple[int, int] = (3, 11)
TEST_BOOTSTRAP_REMEDIATION = "python -m pip install -r requirements-test.txt"

SCHEMA_VERSION = "sdetkit.polyglot_matrix.v1"

_EXCLUDED_DIRS: set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "site",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def missing_modules(modules: Sequence[str] = REQUIRED_TEST_MODULES) -> list[str]:
    return sorted(name for name in modules if importlib.util.find_spec(name) is None)


def build_test_bootstrap_report() -> dict[str, object]:
    version = sys.version_info
    if hasattr(version, "major") and hasattr(version, "minor"):
        current = (int(version.major), int(version.minor))
    else:
        current = (int(version[0]), int(version[1]))
    missing = missing_modules()
    return {
        "ok": current >= MIN_TEST_PYTHON and not missing,
        "python": {
            "current": platform.python_version(),
            "required": f"{MIN_TEST_PYTHON[0]}.{MIN_TEST_PYTHON[1]}+",
            "supported": current >= MIN_TEST_PYTHON,
        },
        "dependencies": {
            "required_modules": list(REQUIRED_TEST_MODULES),
            "missing_modules": missing,
            "all_present": not missing,
        },
        "remediation": TEST_BOOTSTRAP_REMEDIATION,
    }


def _parse_junit(junit_path: Path) -> dict[str, int]:
    if not junit_path.is_file():
        return {"passed": 0, "failed": 0, "skipped": 0, "total": 0}
    try:
        tree = ET.parse(junit_path)
        root = tree.getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        tests = 0
        failures = 0
        errors = 0
        skipped = 0
        for suite in suites:
            tests += int(suite.attrib.get("tests", 0))
            failures += int(suite.attrib.get("failures", 0))
            errors += int(suite.attrib.get("errors", 0))
            skipped += int(suite.attrib.get("skipped", 0))
        failed = failures + errors
        passed = max(0, tests - failed - skipped)
        return {"passed": passed, "failed": failed, "skipped": skipped, "total": tests}
    except Exception:
        return {"passed": 0, "failed": 0, "skipped": 0, "total": 0}


def discover_polyglot_projects(root: Path, max_depth: int = 3) -> list[dict[str, str]]:
    projects: list[dict[str, str]] = []
    root = root.resolve()

    for current_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS and not d.startswith(".")]
        rel = Path(current_dir).relative_to(root)
        if len(rel.parts) > max_depth:
            dirs.clear()
            continue

        rel_str = "." if rel == Path(".") else str(rel).replace("\\", "/")
        p_dir = Path(current_dir)

        if any(
            f in files
            for f in (
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "requirements.txt",
                "pytest.ini",
            )
        ):
            if (
                (p_dir / "tests").is_dir()
                or any(f.startswith("test_") or f.endswith("_test.py") for f in files)
                or (p_dir / "pytest.ini").is_file()
                or (p_dir / "pyproject.toml").is_file()
            ):
                projects.append({"folder": rel_str, "language": "python", "runner": "pytest"})

        if "go.mod" in files:
            projects.append({"folder": rel_str, "language": "go", "runner": "go"})

        if "package.json" in files:
            try:
                from sdetkit.js_tests import detect_runner

                runner = detect_runner(p_dir)
                if runner:
                    projects.append({"folder": rel_str, "language": "javascript", "runner": runner})
            except (OSError, ValueError, TypeError, json.JSONDecodeError, ImportError):
                # Skip unparseable package.json or missing runner dependencies.
                pass

        if any(f in files for f in ("pom.xml", "build.gradle", "build.gradle.kts")):
            try:
                from sdetkit.java_tests import detect_java_runner

                runner = detect_java_runner(p_dir)
                if runner:
                    projects.append({"folder": rel_str, "language": "java", "runner": runner})
            except (OSError, ValueError, TypeError, ImportError):
                # Skip malformed build descriptors or missing runner dependencies.
                pass

    return projects


def _run_python_project(
    project_dir: Path,
    junit_path: Path,
    test_args: Sequence[str],
    timeout: int,
    fail_fast: bool = False,
) -> dict[str, Any]:
    python_bin = sys.executable
    args = [
        python_bin,
        "-m",
        "pytest",
        "-q",
        "--junitxml",
        str(junit_path),
        "-o",
        "junit_family=xunit2",
        *(["-x"] if fail_fast else []),
        *test_args,
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        str(project_dir / "src")
        + os.pathsep
        + str(project_dir)
        + os.pathsep
        + env.get("PYTHONPATH", "")
    )
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            args,
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        dur = round(time.perf_counter() - start, 3)
        counts = _parse_junit(junit_path)
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return {
            "exit_code": proc.returncode,
            "duration_seconds": dur,
            "counts": counts,
            "output_tail": output[-2000:] if len(output) > 2000 else output,
            "runner_missing": False,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        dur = round(time.perf_counter() - start, 3)
        out = (
            (exc.stdout or b"").decode("utf-8", errors="replace")
            + "\n"
            + (exc.stderr or b"").decode("utf-8", errors="replace")
        )
        return {
            "exit_code": -1,
            "duration_seconds": dur,
            "counts": _parse_junit(junit_path),
            "output_tail": f"Test run timed out after {timeout}s\n{out[-1000:]}",
            "runner_missing": False,
            "timed_out": True,
        }
    except Exception as exc:
        dur = round(time.perf_counter() - start, 3)
        return {
            "exit_code": 1,
            "duration_seconds": dur,
            "counts": {"passed": 0, "failed": 1, "skipped": 0, "total": 1},
            "output_tail": str(exc),
            "runner_missing": False,
            "timed_out": False,
        }


def _run_go_project(
    project_dir: Path,
    junit_path: Path,
    test_args: Sequence[str],
    timeout: int,
    fail_fast: bool = False,
) -> dict[str, Any]:
    from sdetkit.go_tests import run_go_tests

    start = time.perf_counter()
    res = run_go_tests(
        workspace=project_dir,
        junit_path=junit_path,
        test_args=test_args or ["./..."],
        timeout_seconds=timeout,
        environment=os.environ,
        output_tail_chars=2000,
        fail_fast=fail_fast,
    )
    dur = round(time.perf_counter() - start, 3)
    counts = res.get("counts", {})
    passed = int(counts.get("passed", 0))
    failed = int(counts.get("failed", 0))
    skipped = int(counts.get("skipped", 0))
    return {
        "exit_code": int(res.get("exit_code", 1)),
        "duration_seconds": dur,
        "counts": {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": passed + failed + skipped,
        },
        "output_tail": str(res.get("output_tail", "")),
        "runner_missing": bool(res.get("runner_missing", False)),
        "timed_out": bool(res.get("timed_out", False)),
    }


def _run_js_project(
    runner: str,
    project_dir: Path,
    junit_path: Path,
    test_args: Sequence[str],
    timeout: int,
    fail_fast: bool = False,
) -> dict[str, Any]:
    from sdetkit.js_tests import run_js_tests

    start = time.perf_counter()
    res = run_js_tests(
        runner,
        workspace=project_dir,
        junit_path=junit_path,
        test_args=test_args,
        timeout_seconds=timeout,
        environment=os.environ,
        output_tail_chars=2000,
        fail_fast=fail_fast,
    )
    dur = round(time.perf_counter() - start, 3)
    counts = res.get("counts", {})
    passed = int(counts.get("passed", 0))
    failed = int(counts.get("failed", 0))
    skipped = int(counts.get("skipped", 0))
    return {
        "exit_code": int(res.get("exit_code", 1)),
        "duration_seconds": dur,
        "counts": {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": passed + failed + skipped,
        },
        "output_tail": str(res.get("output_tail", "")),
        "runner_missing": bool(res.get("runner_missing", False)),
        "timed_out": bool(res.get("timed_out", False)),
    }


def _run_java_project(
    runner: str,
    project_dir: Path,
    junit_path: Path,
    test_args: Sequence[str],
    timeout: int,
    fail_fast: bool = False,
) -> dict[str, Any]:
    from sdetkit.java_tests import run_java_tests

    start = time.perf_counter()
    res = run_java_tests(
        runner,
        workspace=project_dir,
        junit_path=junit_path,
        test_args=test_args,
        timeout_seconds=timeout,
        environment=os.environ,
        output_tail_chars=2000,
        fail_fast=fail_fast,
    )
    dur = round(time.perf_counter() - start, 3)
    counts = res.get("counts", {})
    passed = int(counts.get("passed", 0))
    failed = int(counts.get("failed", 0))
    skipped = int(counts.get("skipped", 0))
    return {
        "exit_code": int(res.get("exit_code", 1)),
        "duration_seconds": dur,
        "counts": {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": passed + failed + skipped,
        },
        "output_tail": str(res.get("output_tail", "")),
        "runner_missing": bool(res.get("runner_missing", False)),
        "timed_out": bool(res.get("timed_out", False)),
    }


def run_polyglot_matrix(
    root: Path,
    targets: Sequence[str] = (),
    languages: Sequence[str] | None = None,
    fail_fast: bool = False,
    timeout_seconds: int = 120,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    discovered = discover_polyglot_projects(root)

    if targets:
        target_set = {t.rstrip("/\\") for t in targets}
        filtered: list[dict[str, str]] = []
        for p in discovered:
            folder = p["folder"]
            if folder in target_set or any(folder.startswith(t) for t in target_set):
                filtered.append(p)
        discovered = filtered

    if languages:
        lang_set = {lang.strip().lower() for lang in languages}
        discovered = [p for p in discovered if p["language"].lower() in lang_set]

    matrix: list[dict[str, Any]] = []
    totals = {"projects": 0, "passed": 0, "failed": 0, "skipped": 0, "total": 0}

    temp_dir: str | None = None
    if output_dir is None:
        import tempfile

        temp_dir = tempfile.mkdtemp(prefix="sdetkit-polyglot-")
        base_junit_dir = Path(temp_dir)
    else:
        base_junit_dir = output_dir
        base_junit_dir.mkdir(parents=True, exist_ok=True)

    try:
        for idx, proj in enumerate(discovered):
            folder = proj["folder"]
            lang = proj["language"]
            runner = proj["runner"]
            project_dir = root if folder == "." else (root / folder)
            junit_path = base_junit_dir / f"junit_{idx}_{runner}.xml"

            if lang == "python":
                run_res = _run_python_project(
                    project_dir, junit_path, (), timeout_seconds, fail_fast
                )
            elif lang == "go":
                run_res = _run_go_project(project_dir, junit_path, (), timeout_seconds, fail_fast)
            elif lang == "javascript":
                run_res = _run_js_project(
                    runner, project_dir, junit_path, (), timeout_seconds, fail_fast
                )
            elif lang == "java":
                run_res = _run_java_project(
                    runner, project_dir, junit_path, (), timeout_seconds, fail_fast
                )
            else:
                run_res = {
                    "exit_code": 1,
                    "duration_seconds": 0.0,
                    "counts": {"passed": 0, "failed": 0, "skipped": 0, "total": 0},
                    "output_tail": f"Unsupported language: {lang}",
                    "runner_missing": True,
                    "timed_out": False,
                }

            counts = run_res.get("counts", {})
            p_passed = int(counts.get("passed", 0))
            p_failed = int(counts.get("failed", 0))
            p_skipped = int(counts.get("skipped", 0))
            p_total = int(counts.get("total", 0))

            if run_res.get("runner_missing"):
                status = "UNAVAILABLE"
            elif run_res.get("timed_out"):
                status = "TIMED_OUT"
            elif run_res.get("exit_code") != 0:
                status = "FAILED"
            elif p_total == 0:
                status = "NO_TESTS"
            else:
                status = "PASSED"

            matrix_item = {
                "folder": folder,
                "language": lang,
                "runner": runner,
                "status": status,
                "exit_code": run_res.get("exit_code", 0),
                "duration_seconds": run_res.get("duration_seconds", 0.0),
                "passed": p_passed,
                "failed": p_failed,
                "skipped": p_skipped,
                "total": p_total,
                "output_tail": run_res.get("output_tail", ""),
            }
            matrix.append(matrix_item)

            totals["projects"] += 1
            totals["passed"] += p_passed
            totals["failed"] += p_failed
            totals["skipped"] += p_skipped
            totals["total"] += p_total

            if fail_fast and status in ("FAILED", "TIMED_OUT"):
                break
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    has_failures = any(m["status"] in ("FAILED", "TIMED_OUT") for m in matrix)
    has_passes = any(m["status"] == "PASSED" for m in matrix)

    if has_failures:
        verdict = "FAIL"
    elif has_passes:
        verdict = "PASS"
    else:
        verdict = "NO_TESTS"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "verdict": verdict,
        "totals": totals,
        "matrix": matrix,
    }


def render_polyglot_markdown(report: Mapping[str, Any]) -> str:
    verdict = report.get("verdict", "UNKNOWN")
    totals = report.get("totals", {})
    matrix = report.get("matrix", [])

    lines = [
        "# SDETKit Polyglot Test Matrix Radar",
        "",
        (
            f"**Verdict:** `{verdict}` | **Projects:** {totals.get('projects', 0)} | "
            f"**Total Tests:** {totals.get('total', 0)} | "
            f"**Passed:** {totals.get('passed', 0)} | "
            f"**Failed:** {totals.get('failed', 0)} | "
            f"**Skipped:** {totals.get('skipped', 0)}"
        ),
        "",
        "### Execution Matrix",
        "",
        ("| Project | Language | Runner | Passed | Failed | Skipped | Total | Duration | Status |"),
        "|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for item in matrix:
        lines.append(
            f"| `{item.get('folder', '.')}` | {item.get('language')} | "
            f"`{item.get('runner')}` | {item.get('passed', 0)} | "
            f"{item.get('failed', 0)} | {item.get('skipped', 0)} | "
            f"{item.get('total', 0)} | {item.get('duration_seconds', 0.0):.2f}s | "
            f"**{item.get('status')}** |"
        )

    failures = [
        item for item in matrix if item.get("status") in ("FAILED", "TIMED_OUT", "UNAVAILABLE")
    ]
    if failures:
        lines.extend(["", "### Project Diagnostics", ""])
        for item in failures:
            lines.extend(
                [
                    (
                        f"#### `{item.get('folder')}` ({item.get('language')} / "
                        f"{item.get('runner')}) - {item.get('status')}"
                    ),
                    "```",
                    item.get("output_tail", "").strip() or "(no output captured)",
                    "```",
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def polyglot_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit polyglot",
        description=(
            "Execute unified polyglot test runner matrix across Python, Go, JS/TS, "
            "and Java projects."
        ),
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Specific target directories or projects to run (default: discover from root).",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root directory to inspect (default: .).",
    )
    parser.add_argument(
        "--languages",
        help="Comma-separated languages to filter (e.g. python,go,javascript,java).",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop test execution on first failing project.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds per runner (default: 120).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument("--out", help="Path to write JSON matrix report.")
    parser.add_argument("--summary-out", help="Path to write Markdown summary report.")

    raw = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] in ("polyglot", "test-runner"):
        raw = raw[1:]
    args = parser.parse_args(raw)
    root_path = Path(args.root).resolve()
    langs = (
        [lang.strip() for lang in args.languages.split(",") if lang.strip()]
        if args.languages
        else None
    )

    report = run_polyglot_matrix(
        root=root_path,
        targets=args.targets,
        languages=langs,
        fail_fast=args.fail_fast,
        timeout_seconds=args.timeout,
    )

    md = render_polyglot_markdown(report)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.summary_out:
        summary_path = Path(args.summary_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(md, encoding="utf-8")

    if args.format == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    elif args.format == "md":
        sys.stdout.write(md)
    else:
        sys.stdout.write(md)

    return 0 if report.get("verdict") in ("PASS", "NO_TESTS") else 1


main = polyglot_main
