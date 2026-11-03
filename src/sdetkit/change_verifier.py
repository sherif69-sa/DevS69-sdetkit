"""`sdetkit verify change`: check a change from anyone (a person, an AI agent) by running it.

A change is either a patch file applied on top of a base commit, or a base and a head commit.
The verifier never touches the caller's working tree:

1. clone the repository into a temporary folder and build the change there
2. run the tests on the base and on the change, with the clone's code first on the import path
3. compare the two runs: tests that broke, tests that went missing, tests now skipped
4. read the test files before and after: assertions removed, skip/xfail markers added,
   test or coverage configuration changed
5. write the report, the canonical patch, both JUnit files and an in-toto attestation that
   standard tools (GitHub `actions/attest`, `cosign attest-blob`) can sign

The tests run the change's own code. Run it where you would run that code anyway (CI, a
sandbox); the commands get a reduced environment, without tokens or credentials.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from sdetkit.gates.project_env import resolve_project_python
from sdetkit.isolated_proof_runner import _execution_environment
from sdetkit.verdict import build_verdict
from sdetkit.versioning import tool_version

SCHEMA_VERSION = "sdetkit.change_verification.v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://sherif69-sa.github.io/DevS69-sdetkit/attestations/change-verification/v1"
DEFAULT_OUT_DIR = Path("build") / "sdetkit" / "change-verification"
DEFAULT_TIMEOUT_SECONDS = 900
OUTPUT_TAIL_CHARS = 4000

VERIFIED = "VERIFIED"
REVIEW = "REVIEW"
FAILED = "FAILED"
NOT_RUN = "NOT_RUN"
# The shared verdict for each status; a person still reads what the change means.
_SHARED_DECISION = {VERIFIED: "SHIP", REVIEW: "REVIEW", FAILED: "NO_SHIP", NOT_RUN: "NOT_RUN"}
EXIT_CODES = {VERIFIED: 0, REVIEW: 1, FAILED: 2, NOT_RUN: 2}

# Configuration that decides which tests run and how strictly: a change here can make a
# failing suite pass without fixing anything.
PYTEST_CONFIG_FILES = frozenset({"pytest.ini", "tox.ini", "setup.cfg"})
# Test harness files that can change what runs, but usually change for ordinary reasons.
HARNESS_FILE_NAMES = frozenset({"conftest.py", "noxfile.py"})
HARNESS_PREFIXES = (".github/workflows/",)
_SKIP_WORDS = ("skip", "skipif", "xfail")

JsonObject = dict[str, Any]


class ChangeError(ValueError):
    """The change could not be built (a bad ref, a patch that does not apply)."""


def _git(cwd: Path, *args: str, env: Mapping[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise ChangeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_commit(repo_root: Path, ref: str) -> str:
    try:
        return _git(repo_root, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    except ChangeError:
        raise ChangeError(f"not a commit in {repo_root}: {ref}") from None


def _commit_identity() -> tuple[str, ...]:
    return (
        "-c",
        "user.name=SDETKit Change Verifier",
        "-c",
        "user.email=change-verifier@invalid.local",
    )


def build_change(
    *, repo_root: Path, workspace: Path, base: str, head: str = "", patch_text: str = ""
) -> JsonObject:
    """Clone the repository into `workspace` and leave the change committed there."""

    base_sha = _resolve_commit(repo_root, base)
    head_sha = _resolve_commit(repo_root, head) if head else ""
    environment = _execution_environment()
    _git(repo_root, "clone", "--quiet", "--no-checkout", str(repo_root), str(workspace))
    if head_sha:
        _git(workspace, "checkout", "--quiet", "--detach", head_sha, env=environment)
    else:
        _git(workspace, "checkout", "--quiet", "--detach", base_sha, env=environment)
        patch_file = workspace.parent / "incoming.patch"
        patch_file.write_text(patch_text, encoding="utf-8")
        try:
            _git(
                workspace,
                "apply",
                "--index",
                "--whitespace=nowarn",
                str(patch_file),
                env=environment,
            )
        except ChangeError as exc:
            raise ChangeError(f"the patch does not apply to {base_sha[:12]}: {exc}") from None
        _git(
            workspace,
            *_commit_identity(),
            "commit",
            "--quiet",
            "--no-verify",
            "--allow-empty",
            "-m",
            "change under verification",
            env=environment,
        )
        head_sha = _git(workspace, "rev-parse", "HEAD", env=environment).strip()
    diff = _git(workspace, "diff", "--no-ext-diff", "--binary", base_sha, head_sha, env=environment)
    changed: list[JsonObject] = []
    for line in _git(
        workspace, "diff", "--name-status", "-M", base_sha, head_sha, env=environment
    ).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changed.append({"status": parts[0][:1], "path": parts[-1], "old_path": parts[1]})
    return {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "head_source": "commit" if head else "patch",
        "diff": diff,
        "patch_sha256": _sha256(diff.encode("utf-8")),
        "changed": changed,
    }


# --- what the test files say ------------------------------------------------------------


def _is_test_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return path.endswith(".py") and (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in PurePosixPath(path).parts
    )


def _mentions_skip(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        word = (
            sub.attr
            if isinstance(sub, ast.Attribute)
            else sub.id
            if isinstance(sub, ast.Name)
            else ""
        )
        if word in _SKIP_WORDS:
            return True
    return False


def _assertion_count(node: ast.AST) -> int:
    count = 0
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert):
            # Asserting a constant that is always true checks nothing.
            if not (isinstance(sub.test, ast.Constant) and sub.test.value):
                count += 1
        elif isinstance(sub, ast.Call):
            func = sub.func
            word = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else ""
            )
            if word.startswith("assert") or word in {"raises", "warns", "fail"}:
                count += 1
    return count


def _skips_in_body(node: ast.AST) -> int:
    count = 0
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr in {"skip", "xfail"}:
                count += 1
    return count


def test_facts(source: str) -> dict[str, JsonObject]:
    """{test name: {"assertions": n, "skips": n}} for every test function in a file."""

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return {}
    module_skips = sum(
        1
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
        and _mentions_skip(node.value)
    )
    facts: dict[str, JsonObject] = {}

    def add(func: ast.FunctionDef | ast.AsyncFunctionDef, qualname: str, inherited: int) -> None:
        # The body alone: walking the function itself would count its decorators twice.
        body = ast.Module(body=func.body, type_ignores=[])
        skips = inherited + _skips_in_body(body)
        skips += sum(1 for decorator in func.decorator_list if _mentions_skip(decorator))
        facts[qualname] = {"assertions": _assertion_count(body), "skips": skips}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            add(node, node.name, module_skips)
        elif isinstance(node, ast.ClassDef):
            class_skips = module_skips + sum(
                1 for decorator in node.decorator_list if _mentions_skip(decorator)
            )
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and item.name.startswith("test"):
                    add(item, f"{node.name}.{item.name}", class_skips)
    return facts


def _file_at(workspace: Path, sha: str, path: str) -> str | None:
    try:
        return _git(workspace, "show", f"{sha}:{path}")
    except ChangeError:
        return None


def _finding(code: str, message: str, *, blocking: bool, items: Sequence[str] = ()) -> JsonObject:
    return {"code": code, "message": message, "blocking": blocking, "items": sorted(items)}


def static_findings(workspace: Path, change: Mapping[str, Any]) -> list[JsonObject]:
    """What the diff does to the tests and their configuration, read without running anything."""

    base_sha, head_sha = change["base_sha"], change["head_sha"]
    removed: list[str] = []
    weakened: list[str] = []
    emptied: list[str] = []
    skipped: list[str] = []
    config: list[str] = []
    harness: list[str] = []
    coverage: list[str] = []
    for entry in change["changed"]:
        path, old_path, status = entry["path"], entry["old_path"], entry["status"]
        name = PurePosixPath(path).name
        if _is_test_file(old_path) or _is_test_file(path):
            before = test_facts(_file_at(workspace, base_sha, old_path) or "")
            after = {} if status == "D" else test_facts(_file_at(workspace, head_sha, path) or "")
            for test, facts in sorted(before.items()):
                label = f"{old_path}::{test}"
                if test not in after:
                    removed.append(label)
                    continue
                if after[test]["assertions"] < facts["assertions"]:
                    (emptied if after[test]["assertions"] == 0 else weakened).append(
                        f"{label} ({facts['assertions']} -> {after[test]['assertions']})"
                    )
                if after[test]["skips"] > facts["skips"]:
                    skipped.append(label)
        if name in PYTEST_CONFIG_FILES or (
            name == "pyproject.toml"
            and _pytest_config_changed(workspace, base_sha, head_sha, old_path, path)
        ):
            config.append(path)
        if name in HARNESS_FILE_NAMES or path.startswith(HARNESS_PREFIXES):
            harness.append(path)
        lowered = _coverage_threshold_lowered(workspace, base_sha, head_sha, old_path, path)
        if lowered:
            coverage.append(f"{path} ({lowered})")

    findings: list[JsonObject] = []
    if removed:
        findings.append(
            _finding(
                "tests_removed",
                "Tests that existed before the change are gone.",
                blocking=True,
                items=removed,
            )
        )
    if emptied:
        findings.append(
            _finding(
                "assertions_removed",
                "Tests that checked something before now assert nothing.",
                blocking=True,
                items=emptied,
            )
        )
    if weakened:
        findings.append(
            _finding(
                "assertions_reduced",
                "Tests now make fewer assertions.",
                blocking=True,
                items=weakened,
            )
        )
    if skipped:
        findings.append(
            _finding(
                "skip_added", "Tests gained a skip or xfail marker.", blocking=True, items=skipped
            )
        )
    if config:
        findings.append(
            _finding(
                "test_config_changed",
                "The pytest configuration changed; it decides which tests run and how.",
                blocking=True,
                items=config,
            )
        )
    if coverage:
        findings.append(
            _finding(
                "coverage_threshold_lowered",
                "The minimum coverage went down.",
                blocking=True,
                items=coverage,
            )
        )
    if harness:
        findings.append(
            _finding(
                "test_harness_changed",
                "conftest, nox or CI workflow files changed; read them with the tests.",
                blocking=False,
                items=harness,
            )
        )
    return findings


def _toml_section(text: str | None, *keys: str) -> Any:
    try:
        data: Any = tomllib.loads(text or "")
    except tomllib.TOMLDecodeError:
        return None
    for key in keys:
        data = data.get(key) if isinstance(data, dict) else None
    return data


def _pytest_config_changed(workspace: Path, base: str, head: str, old: str, new: str) -> bool:
    before = _toml_section(_file_at(workspace, base, old), "tool", "pytest")
    after = _toml_section(_file_at(workspace, head, new), "tool", "pytest")
    return bool(before != after)


def _fail_under(name: str, text: str | None) -> float | None:
    if text is None:
        return None
    value: Any = None
    if name == "pyproject.toml":
        value = _toml_section(text, "tool", "coverage", "report", "fail_under")
    elif name in {".coveragerc", "setup.cfg", "tox.ini"}:
        parser = configparser.ConfigParser()
        try:
            parser.read_string(text)
        except configparser.Error:
            return None
        for section in ("report", "coverage:report"):
            if parser.has_option(section, "fail_under"):
                value = parser.get(section, "fail_under")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _coverage_threshold_lowered(workspace: Path, base: str, head: str, old: str, new: str) -> str:
    name = PurePosixPath(new).name
    if name not in {"pyproject.toml", ".coveragerc", "setup.cfg", "tox.ini"}:
        return ""
    before = _fail_under(name, _file_at(workspace, base, old))
    after = _fail_under(name, _file_at(workspace, head, new))
    if before is not None and (after is None or after < before):
        return f"{before:g} -> {'removed' if after is None else f'{after:g}'}"
    return ""


# --- running the tests ------------------------------------------------------------------


def _import_path(workspace: Path) -> str:
    entries = [workspace / "src", workspace] if (workspace / "src").is_dir() else [workspace]
    return os.pathsep.join(str(entry) for entry in entries)


def read_junit(path: Path) -> dict[str, str]:
    """{test id: passed | failed | skipped} from a JUnit XML file."""

    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {}
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        tags = {child.tag for child in case}
        if tags & {"failure", "error"}:
            outcomes[test_id] = "failed"
        elif "skipped" in tags:
            outcomes[test_id] = "skipped"
        else:
            outcomes[test_id] = "passed"
    return outcomes


def run_tests(
    *,
    workspace: Path,
    python: str,
    junit_path: Path,
    test_args: Sequence[str],
    timeout_seconds: int,
) -> JsonObject:
    argv = [
        python,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--junitxml={junit_path}",
        "-o",
        "junit_family=xunit2",
        *test_args,
    ]
    environment = _execution_environment()
    # The clone's code must win over an editable install of the original checkout.
    environment["PYTHONPATH"] = _import_path(workspace)
    try:
        completed = subprocess.run(
            argv,
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        exit_code, timed_out = completed.returncode, False
        output = f"{completed.stdout}\n{completed.stderr}"
    except subprocess.TimeoutExpired as exc:
        exit_code, timed_out = -1, True
        # On a timeout the captured output can arrive as bytes even with text=True.
        output = "\n".join(
            part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part or ""
            for part in (exc.stdout, exc.stderr)
        )
    outcomes = read_junit(junit_path)
    counts = {
        key: sum(1 for value in outcomes.values() if value == key)
        for key in ("passed", "failed", "skipped")
    }
    return {
        "command": " ".join(["python", *argv[1:4], *test_args]),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "pytest_missing": "No module named pytest" in output,
        "counts": counts,
        "outcomes": outcomes,
        "output_tail": output.strip()[-OUTPUT_TAIL_CHARS:],
    }


def _imports_the_clone(workspace: Path, python: str, change: Mapping[str, Any]) -> list[str]:
    """Changed packages the test interpreter would import from somewhere else."""

    tops: set[str] = set()
    for entry in change["changed"]:
        parts = PurePosixPath(entry["path"]).parts
        if not entry["path"].endswith(".py") or _is_test_file(entry["path"]):
            continue
        if parts[0] == "src" and len(parts) > 2:
            tops.add(parts[1])
        elif len(parts) > 1 and (workspace / parts[0] / "__init__.py").is_file():
            tops.add(parts[0])
    elsewhere: list[str] = []
    environment = _execution_environment()
    environment["PYTHONPATH"] = _import_path(workspace)
    for top in sorted(tops):
        probe = (
            "import importlib.util, sys; spec = importlib.util.find_spec(sys.argv[1]); "
            "print(spec.origin if spec and spec.origin else '')"
        )
        completed = subprocess.run(
            [python, "-c", probe, top],
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        origin = completed.stdout.strip()
        if origin and not Path(origin).resolve().is_relative_to(workspace.resolve()):
            elsewhere.append(f"{top} -> {origin}")
    return elsewhere


def compare_runs(base: Mapping[str, Any] | None, head: Mapping[str, Any]) -> JsonObject:
    after: Mapping[str, str] = head["outcomes"]
    before: Mapping[str, str] = base["outcomes"] if base else {}
    return {
        "regressions": sorted(
            t for t, o in after.items() if o == "failed" and before.get(t) == "passed"
        ),
        # New tests, and tests that were skipped before.
        "new_failures": sorted(
            t
            for t, o in after.items()
            if o == "failed" and before.get(t) not in {"passed", "failed"}
        ),
        "still_failing": sorted(
            t for t, o in after.items() if o == "failed" and before.get(t) == "failed"
        ),
        "fixed": sorted(t for t, o in after.items() if o == "passed" and before.get(t) == "failed"),
        "now_skipped": sorted(
            t for t, o in after.items() if o == "skipped" and before.get(t) == "passed"
        ),
        "missing": sorted(t for t in before if t not in after),
    }


# --- the decision -----------------------------------------------------------------------


def decide(
    *,
    head_run: Mapping[str, Any],
    base_run: Mapping[str, Any] | None,
    comparison: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    not_imported: Sequence[str],
) -> tuple[str, list[str]]:
    """The status and the reasons for it, most important first."""

    if head_run["pytest_missing"]:
        return NOT_RUN, ["pytest is not installed in the interpreter that ran the tests"]
    if head_run["timed_out"]:
        return NOT_RUN, ["the tests timed out on the change"]
    if not_imported:
        return NOT_RUN, [
            "the tests would import the changed code from outside the clone: "
            + ", ".join(not_imported)
        ]
    if not head_run["outcomes"]:
        # pytest's last line names the reason: a usage error, an import error, an early exit.
        last_line = (head_run["output_tail"].splitlines() or [""])[-1].strip()
        why = f"pytest exit code {head_run['exit_code']}" + (f": {last_line}" if last_line else "")
        if base_run is not None and base_run["outcomes"]:
            return FAILED, [f"no test ran on the change ({why})"]
        return NOT_RUN, [f"no test ran ({why})"]
    reasons: list[str] = []
    broken = [*comparison["regressions"], *comparison["new_failures"]]
    if base_run is None:
        broken = [t for t, o in head_run["outcomes"].items() if o == "failed"]
    if broken:
        return FAILED, [
            f"{len(broken)} test(s) fail on the change: " + ", ".join(sorted(broken)[:5])
        ]
    if head_run["exit_code"] not in {0, 1}:
        return FAILED, [f"pytest exited with code {head_run['exit_code']} on the change"]
    for finding in findings:
        if finding["blocking"]:
            reasons.append(f"{finding['code']}: {finding['message']}")
    if comparison["now_skipped"]:
        reasons.append(
            f"{len(comparison['now_skipped'])} test(s) passed before and are skipped now"
        )
    if comparison["missing"]:
        reasons.append(f"{len(comparison['missing'])} test(s) ran before and did not run now")
    if comparison["still_failing"]:
        reasons.append(f"{len(comparison['still_failing'])} test(s) failed before and still fail")
    return (
        (REVIEW, reasons)
        if reasons
        else (VERIFIED, ["every test passed and the tests were not weakened"])
    )


def _next_action(status: str) -> str:
    return {
        VERIFIED: "Read the change itself: the tests pass and were not weakened, which says nothing about intent.",
        REVIEW: "Read the findings in change-verification.md before accepting the change.",
        FAILED: "Send the change back: it breaks tests (see change-verification.md).",
        NOT_RUN: "Fix the reason the tests could not run, then verify again.",
    }[status]


def build_attestation(report: Mapping[str, Any], evidence: Mapping[str, str]) -> JsonObject:
    """An in-toto Statement about the change; sign it with your usual attestation tool."""

    subject: list[JsonObject] = [
        {"name": "change.patch", "digest": {"sha256": report["change"]["patch_sha256"]}}
    ]
    if report["change"]["head_source"] == "commit":
        subject.append({"name": "head", "digest": {"gitCommit": report["change"]["head_sha"]}})
    return {
        "_type": STATEMENT_TYPE,
        "subject": subject,
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "verifier": {"name": "sdetkit", "version": report["verifier_version"]},
            "repository": report["repository"],
            "base_commit": report["change"]["base_sha"],
            "head_commit": report["change"]["head_sha"],
            "status": report["status"],
            "reasons": report["reasons"],
            "tests": {
                "command": report["tests"]["head"]["command"],
                "head": report["tests"]["head"]["counts"],
                "base": report["tests"]["base"]["counts"] if report["tests"]["base"] else None,
                **{key: len(value) for key, value in report["tests"]["comparison"].items()},
            },
            "findings": [finding["code"] for finding in report["findings"]],
            "evidence": dict(sorted(evidence.items())),
            "network_isolated": False,
        },
    }


def _render_markdown(report: Mapping[str, Any]) -> str:
    change = report["change"]
    head = report["tests"]["head"]
    base = report["tests"]["base"]
    comparison = report["tests"]["comparison"]
    lines = [
        "# SDETKit change verification",
        "",
        f"- status: `{report['status']}`",
        f"- base: `{change['base_sha'][:12]}`  head: `{change['head_sha'][:12]}` ({change['head_source']})",
        f"- changed files: {len(change['changed'])}",
        f"- tests on the change: {head['counts']['passed']} passed, {head['counts']['failed']} failed, "
        f"{head['counts']['skipped']} skipped",
    ]
    if base:
        lines.append(
            f"- tests on the base: {base['counts']['passed']} passed, {base['counts']['failed']} failed, "
            f"{base['counts']['skipped']} skipped"
        )
    lines += ["", "## Why", ""] + [f"- {reason}" for reason in report["reasons"]]
    lines += ["", "## Next action", "", report["next_action"], ""]
    labels = {
        "regressions": "Passed before, fail now",
        "new_failures": "New tests that fail",
        "fixed": "Failed before, pass now",
        "now_skipped": "Passed before, skipped now",
        "missing": "Ran before, did not run now",
        "still_failing": "Failed before, still fail",
    }
    for key, label in labels.items():
        if comparison[key]:
            lines += [f"## {label}", ""] + [f"- `{item}`" for item in comparison[key][:50]] + [""]
    for finding in report["findings"]:
        marker = "" if finding["blocking"] else " (note)"
        lines += [f"## {finding['code']}{marker}", "", finding["message"], ""]
        lines += [f"- `{item}`" for item in finding["items"][:50]] + [""]
    lines += [
        "## Authority",
        "",
        "This checks that the tests pass and were not weakened. It does not prove the change is",
        "correct or safe, and it applies, merges and dismisses nothing.",
        "",
    ]
    return "\n".join(lines)


_ICONS = {
    VERIFIED: ":white_check_mark:",
    REVIEW: ":warning:",
    FAILED: ":x:",
    NOT_RUN: ":white_circle:",
}
_SUMMARY_LISTS = (
    ("regressions", "Passed before, fail now"),
    ("new_failures", "New tests that fail"),
    ("missing", "Ran before, did not run now"),
    ("now_skipped", "Passed before, skipped now"),
    ("still_failing", "Failed before, still fail"),
    ("fixed", "Failed before, pass now"),
)


def _counts(run: Mapping[str, Any] | None) -> str:
    if not run:
        return "not run"
    counts = run["counts"]
    return f"{counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped"


def render_summary(report: Mapping[str, Any]) -> str:
    """The short Markdown a job summary or pull request comment shows."""

    status = report["status"]
    change = report["change"]
    tests = report["tests"]
    lines = [
        f"### {_ICONS[status]} SDETKit verify change: {status}",
        "",
        f"`{change['base_sha'][:12]}` → `{change['head_sha'][:12]}`, "
        f"{len(change['changed'])} file(s) changed.",
        "",
        "| Run | Tests |",
        "| --- | --- |",
        f"| Base | {_counts(tests['base'])} |",
        f"| Change | {_counts(tests['head'])} |",
        "",
    ]
    lines += [f"- {reason}" for reason in report["reasons"]] + [""]
    blocking = [finding for finding in report["findings"] if finding["blocking"]]
    notes = [finding for finding in report["findings"] if not finding["blocking"]]
    for finding in [*blocking, *notes]:
        marker = " (note)" if not finding["blocking"] else ""
        items = ", ".join(f"`{item}`" for item in finding["items"][:5])
        more = f" and {len(finding['items']) - 5} more" if len(finding["items"]) > 5 else ""
        lines.append(f"- **{finding['code']}**{marker}: {finding['message']} {items}{more}")
    if report["findings"]:
        lines.append("")
    for key, label in _SUMMARY_LISTS:
        items = tests["comparison"][key]
        if items:
            shown = "\n".join(f"- `{item}`" for item in items[:20])
            more = f"\n- and {len(items) - 20} more" if len(items) > 20 else ""
            lines += [
                f"<details><summary>{label} ({len(items)})</summary>",
                "",
                shown + more,
                "",
                "</details>",
                "",
            ]
    lines += [
        f"**Next:** {report['next_action']}",
        "",
        "Passing, unweakened tests say nothing about intent: a person still reads the change. "
        "Nothing was applied, merged or dismissed.",
    ]
    return "\n".join(lines) + "\n"


def _append(path: str | None, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _repository(repo_root: Path) -> str:
    try:
        remote = _git(repo_root, "remote", "get-url", "origin").strip()
    except ChangeError:
        return f"local/{repo_root.resolve().name}"
    trimmed = remote.removesuffix(".git").rstrip("/")
    parts = trimmed.replace(":", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else trimmed


def verify_change(
    *,
    repo_root: Path,
    out_dir: Path = DEFAULT_OUT_DIR,
    base: str = "HEAD",
    head: str = "",
    patch_text: str = "",
    python: str | None = None,
    test_args: Sequence[str] = (),
    run_base: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> JsonObject:
    if bool(head) == bool(patch_text):
        raise ChangeError("give exactly one of --head REF or --patch FILE")
    repo_root = repo_root.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    interpreter = resolve_project_python(repo_root, python).executable
    with tempfile.TemporaryDirectory(prefix="sdetkit-change-") as temp_dir:
        workspace = Path(temp_dir) / "clone"
        change = build_change(
            repo_root=repo_root, workspace=workspace, base=base, head=head, patch_text=patch_text
        )
        findings = static_findings(workspace, change)
        environment = _execution_environment()
        base_run: JsonObject | None = None
        if run_base:
            _git(
                workspace,
                "checkout",
                "--quiet",
                "--force",
                "--detach",
                change["base_sha"],
                env=environment,
            )
            base_run = run_tests(
                workspace=workspace,
                python=interpreter,
                junit_path=Path(temp_dir) / "tests-base.xml",
                test_args=test_args,
                timeout_seconds=timeout_seconds,
            )
            _git(workspace, "clean", "-fdxq", env=environment)
            _git(
                workspace,
                "checkout",
                "--quiet",
                "--force",
                "--detach",
                change["head_sha"],
                env=environment,
            )
        not_imported = _imports_the_clone(workspace, interpreter, change)
        head_run = run_tests(
            workspace=workspace,
            python=interpreter,
            junit_path=Path(temp_dir) / "tests-head.xml",
            test_args=test_args,
            timeout_seconds=timeout_seconds,
        )
        evidence: dict[str, str] = {}
        for name in ("tests-base.xml", "tests-head.xml"):
            source = Path(temp_dir) / name
            if source.is_file():
                shutil.copyfile(source, out_dir / name)
                evidence[name] = _sha256(source.read_bytes())

    comparison = compare_runs(base_run, head_run)
    status, reasons = decide(
        head_run=head_run,
        base_run=base_run,
        comparison=comparison,
        findings=findings,
        not_imported=not_imported,
    )
    patch_path = out_dir / "change.patch"
    patch_path.write_text(change["diff"], encoding="utf-8")
    report: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reasons": reasons,
        "next_action": _next_action(status),
        "repository": _repository(repo_root),
        "verifier_version": tool_version(),
        "change": {key: value for key, value in change.items() if key != "diff"},
        "python": interpreter,
        "tests": {"base": base_run, "head": head_run, "comparison": comparison},
        "findings": findings,
        "real_tree_modified": False,
        "network_isolated": False,
        "verdict": build_verdict(
            source="verify change",
            decision=_SHARED_DECISION[status],
            reasons=reasons,
            next_action=_next_action(status),
        ),
    }
    report_path = out_dir / "change-verification.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = out_dir / "change-verification.md"
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    evidence.update(
        {
            "change.patch": change["patch_sha256"],
            "change-verification.json": _sha256(report_path.read_bytes()),
        }
    )
    attestation = build_attestation(report, evidence)
    (out_dir / "change-verification.intoto.json").write_text(
        json.dumps(attestation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "change-verification.predicate.json").write_text(
        json.dumps(attestation["predicate"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit verify change",
        description=(
            "Verify a change from anyone, an AI agent included: run the tests on the base and on "
            "the change in a temporary clone, check that no test was removed, emptied or skipped, "
            "and write a report and an in-toto attestation. The working tree is never modified."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--patch", help="Unified diff to apply on top of --base")
    source.add_argument("--head", help="Commit or branch holding the change")
    parser.add_argument(
        "--base", default="HEAD", help="Commit the change starts from (default: HEAD)"
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--python", help="Interpreter for the tests (default: the project's own)")
    parser.add_argument(
        "--no-base-run",
        action="store_true",
        help="Run the tests on the change only (faster; every failure then counts against it)",
    )
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--summary-out",
        help="Append a short Markdown summary here (a job summary or pull request comment)",
    )
    parser.add_argument(
        "pytest_args", nargs="*", help="Arguments for pytest after `--`, such as a test path"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    out_dir = Path(args.out_dir)
    try:
        patch_text = Path(args.patch).read_text(encoding="utf-8") if args.patch else ""
        if args.patch and not patch_text.strip():
            raise ChangeError(f"the patch file is empty: {args.patch}")
        report = verify_change(
            repo_root=Path(args.repo_root),
            out_dir=out_dir,
            base=args.base,
            head=args.head or "",
            patch_text=patch_text,
            python=args.python,
            test_args=args.pytest_args,
            run_base=not args.no_base_run,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"verify change error: {exc}", file=sys.stderr)
        _append(
            args.summary_out,
            f"### {_ICONS[NOT_RUN]} SDETKit verify change: {NOT_RUN}\n\n{exc}\n",
        )
        return 2
    _append(args.summary_out, render_summary(report))
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"{report['status']}: {report['reasons'][0] if report['reasons'] else ''}")
        for reason in report["reasons"][1:]:
            print(f"  - {reason}")
        print(f"next: {report['next_action']}")
        print(f"report: {(out_dir / 'change-verification.md').as_posix()}")
        print(f"attestation: {(out_dir / 'change-verification.intoto.json').as_posix()}")
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
