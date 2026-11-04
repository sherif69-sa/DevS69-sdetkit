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
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from sdetkit.changed_coverage import (
    changed_lines,
    coverage_line,
    coverage_rcfile,
    not_measured,
    not_run_items,
    read_coverage_json,
    read_go_profile,
    read_istanbul_json,
    read_jacoco_xml,
    read_lcov,
    summarize,
    write_test_contexts_plugin,
)
from sdetkit.changed_mutation import (
    DEFAULT_MAX_MUTANTS,
    Mutant,
    mutate_changed_lines,
    mutation_line,
    survivor_items,
)
from sdetkit.gates.project_env import resolve_project_python
from sdetkit.go_tests import _module_path as go_module_path
from sdetkit.go_tests import (
    dependent_test_packages,
    go_package_args,
    go_test_facts,
    go_test_fingerprints,
    is_go_test_file,
    package_dir,
    run_go_tests,
    test_dependencies,
)
from sdetkit.isolated_proof_runner import _execution_environment
from sdetkit.java_tests import RUNNERS as JAVA_RUNNERS
from sdetkit.java_tests import (
    detect_java_runner,
    is_java_build_file,
    is_java_test_file,
    is_java_test_side,
    jacoco_reports,
    java_test_config,
    java_test_facts,
    java_test_fingerprints,
    java_test_id,
    run_java_tests,
)
from sdetkit.js_tests import (
    RUNNERS,
    coverage_unavailable,
    detect_runner,
    is_js_config_file,
    is_js_test_file,
    js_test_facts,
    js_test_fingerprints,
    link_node_modules,
    package_test_config,
    run_js_tests,
)
from sdetkit.network_boundary import (
    PROOF_EXECUTION_ALLOWED,
    assess_network_boundary,
    build_loopback_isolated_argv,
    unavailable_reason,
)
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
RUNNER_CHOICES = ("auto", "pytest", *RUNNERS, "go", *JAVA_RUNNERS)
# A repository with any of these is a Python project: `auto` runs pytest there.
_PYTHON_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", "tox.ini")

JsonObject = dict[str, Any]


# Wraps a command so it runs without network access (see `--network deny`).
Isolate = Callable[[list[str]], list[str]]


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


def pull_request_change(repo_root: Path, number: int, remote: str = "origin") -> tuple[str, str]:
    """(base, head) of pull request `number` on `remote` (GitHub's `refs/pull/<n>/head`): the
    head as fetched now, and the base where it left the remote's default branch, as "Files
    changed" shows it. The head is kept as `refs/sdetkit/pull/<n>`; the working tree, the
    branches and the index are not touched."""

    if number < 1:
        raise ChangeError("--pr takes a pull request number")
    local = f"refs/sdetkit/pull/{number}"
    _git(repo_root, "fetch", "--quiet", "--no-tags", remote, f"+refs/pull/{number}/head:{local}")
    head = _git(repo_root, "rev-parse", local).strip()
    try:
        default = _git(repo_root, "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD").strip()
    except ChangeError:
        default = f"{remote}/main"
    branch = default.split("/", 1)[1] if "/" in default else default
    # The base branch as it is on the remote now, so the merge base is the PR's own.
    _git(
        repo_root,
        "fetch",
        "--quiet",
        "--no-tags",
        remote,
        f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}",
    )
    base = _git(repo_root, "merge-base", f"refs/remotes/{remote}/{branch}", head).strip()
    return base, head


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


def working_tree_patch(repo_root: Path) -> str:
    """The uncommitted change (staged, unstaged and untracked files) as a patch on HEAD.

    It is built in a throwaway index, so the repository's own index is never touched; files the
    repository ignores stay out, as they would from a commit.
    """

    with tempfile.TemporaryDirectory(prefix="sdetkit-index-") as temp_dir:
        environment = {**os.environ, "GIT_INDEX_FILE": str(Path(temp_dir) / "index")}
        _git(repo_root, "read-tree", "HEAD", env=environment)
        _git(repo_root, "add", "-A", env=environment)
        return _git(repo_root, "diff", "--cached", "--binary", "HEAD", env=environment)


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
    # Assertions moved into a helper in the same file still check the test's result.
    helpers = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("test")
    }
    helper_counts: dict[str, int] = {}

    def with_helpers(body: ast.Module, seen: frozenset[str]) -> int:
        count = _assertion_count(body)
        for sub in ast.walk(body):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                name = sub.func.id
                if name in helpers and name not in seen:
                    if name not in helper_counts:
                        helper_body = ast.Module(body=helpers[name].body, type_ignores=[])
                        helper_counts[name] = with_helpers(helper_body, seen | {name})
                    count += helper_counts[name]
        return count

    def add(func: ast.FunctionDef | ast.AsyncFunctionDef, qualname: str, inherited: int) -> None:
        # The body alone: walking the function itself would count its decorators twice.
        body = ast.Module(body=func.body, type_ignores=[])
        skips = inherited + _skips_in_body(body)
        skips += sum(1 for decorator in func.decorator_list if _mentions_skip(decorator))
        facts[qualname] = {"assertions": with_helpers(body, frozenset()), "skips": skips}

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


def test_fingerprints(source: str) -> dict[str, str]:
    """{test name: fingerprint of its arguments, decorators and body}, line numbers aside.

    Two tests with the same fingerprint check the same thing: a test that disappears while one
    with its fingerprint appears was renamed or moved, not removed.
    """

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return {}

    def fingerprint(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        parts = [ast.dump(func.args), *map(ast.dump, func.decorator_list)]
        parts += [ast.dump(statement) for statement in func.body]
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    prints: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            prints[node.name] = fingerprint(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and item.name.startswith("test"):
                    prints[f"{node.name}.{item.name}"] = fingerprint(item)
    return prints


def _test_junit_id(path: str, test: str) -> str:
    """The JUnit id of a test function, as `junit_id` gives it for its node id."""

    return junit_id(f"{path}::{test.replace('.', '::')}")


def _test_readers(
    path: str,
) -> tuple[Callable[[str], dict[str, JsonObject]], Callable[[str], dict[str, str]]]:
    if is_js_test_file(path):
        return js_test_facts, js_test_fingerprints
    if is_go_test_file(path):
        return go_test_facts, go_test_fingerprints
    if is_java_test_file(path):
        return java_test_facts, java_test_fingerprints
    return test_facts, test_fingerprints


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
    # Tests gone from a file and tests new in one, by fingerprint, to tell a rename from a removal.
    gone: list[tuple[str, str, str]] = []
    added: dict[str, list[tuple[str, str]]] = {}
    weakened: list[str] = []
    emptied: list[str] = []
    skipped: list[str] = []
    only: list[str] = []
    config: list[str] = []
    harness: list[str] = []
    coverage: list[str] = []
    for entry in change["changed"]:
        path, old_path, status = entry["path"], entry["old_path"], entry["status"]
        name = PurePosixPath(path).name
        if any(
            check(file)
            for check in (_is_test_file, is_js_test_file, is_go_test_file, is_java_test_file)
            for file in (old_path, path)
        ):
            facts_of, prints_of = _test_readers(path)
            before = facts_of(_file_at(workspace, base_sha, old_path) or "")
            after = {} if status == "D" else facts_of(_file_at(workspace, head_sha, path) or "")
            before_prints = prints_of(_file_at(workspace, base_sha, old_path) or "")
            after_prints = (
                {} if status == "D" else prints_of(_file_at(workspace, head_sha, path) or "")
            )
            # `.only` on any test, new or old, stops the rest of its file from running.
            only += [
                f"{path}::{test}"
                for test, facts in sorted(after.items())
                if facts.get("only") and not before.get(test, {}).get("only")
            ]
            for test in sorted(set(after_prints) - set(before_prints)):
                added.setdefault(after_prints[test], []).append((path, test))
            for test, facts in sorted(before.items()):
                label = f"{old_path}::{test}"
                if test not in after:
                    gone.append((old_path, test, before_prints.get(test, "")))
                    continue
                if after[test]["assertions"] < facts["assertions"]:
                    (emptied if after[test]["assertions"] == 0 else weakened).append(
                        f"{label} ({facts['assertions']} -> {after[test]['assertions']})"
                    )
                if after[test]["skips"] > facts["skips"]:
                    skipped.append(label)
        if (
            name in PYTEST_CONFIG_FILES
            or is_js_config_file(path)
            or (
                name == "pyproject.toml"
                and _pytest_config_changed(workspace, base_sha, head_sha, old_path, path)
            )
            or (
                name == "package.json"
                and package_test_config(_file_at(workspace, base_sha, old_path))
                != package_test_config(_file_at(workspace, head_sha, path))
            )
            or (
                is_java_build_file(path)
                and java_test_config(old_path, _file_at(workspace, base_sha, old_path))
                != java_test_config(path, _file_at(workspace, head_sha, path))
            )
        ):
            config.append(path)
        if name in HARNESS_FILE_NAMES or path.startswith(HARNESS_PREFIXES):
            harness.append(path)
        lowered = _coverage_threshold_lowered(workspace, base_sha, head_sha, old_path, path)
        if lowered:
            coverage.append(f"{path} ({lowered})")

    renamed: list[JsonObject] = []
    for old_path, test, fingerprint in gone:
        twins = added.get(fingerprint) if fingerprint else None
        if twins:
            new_path, new_test = twins.pop(0)
            renamed.append(
                {
                    "from": f"{old_path}::{test}",
                    "to": f"{new_path}::{new_test}",
                    "junit_id": f"{old_path}::{test}"
                    if is_js_test_file(old_path)
                    else f"{package_dir(old_path)}::{test}"
                    if is_go_test_file(old_path)
                    else java_test_id(_file_at(workspace, base_sha, old_path) or "", old_path, test)
                    if is_java_test_file(old_path)
                    else _test_junit_id(old_path, test),
                }
            )
        else:
            removed.append(f"{old_path}::{test}")

    findings: list[JsonObject] = []
    if renamed:
        note = _finding(
            "tests_renamed",
            "Tests were renamed or moved with their bodies unchanged; they still run.",
            blocking=False,
            items=[f"{item['from']} -> {item['to']}" for item in renamed],
        )
        note["renamed"] = renamed
        findings.append(note)
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
    if only:
        findings.append(
            _finding(
                "only_added",
                "Tests gained `.only`, so the other tests in their file stop running.",
                blocking=True,
                items=only,
            )
        )
    if config:
        findings.append(
            _finding(
                "test_config_changed",
                "The test configuration changed (pytest, vitest or jest); it decides which "
                "tests run and how.",
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


def read_junit_failures(path: Path) -> dict[str, str]:
    """{test id: the failure's text} for the failed tests in a JUnit XML file."""

    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {}
    failures: dict[str, str] = {}
    for case in root.iter("testcase"):
        for tag in ("failure", "error"):
            element = case.find(tag)
            if element is not None:
                why = (element.text or element.get("message") or "").strip()
                if why:
                    failures[f"{case.get('classname', '')}::{case.get('name', '')}"] = why
                break
    return failures


# Stack frames of the test runners and of node itself: they say nothing about the change.
_RUNNER_FRAME = re.compile(r"^\s*at .*(?:node_modules[/\\]|node:internal|\(node:|\(<anonymous>\))")


def clean_failure(text: str, workspace: Path) -> str:
    """A failure's text without the runners' own stack frames and with the clone's paths made
    relative, so it reads as it would in the repository."""

    roots = {f"{workspace.as_posix()}/", f"{workspace.resolve().as_posix()}/"}
    lines = []
    for line in text.splitlines():
        if _RUNNER_FRAME.match(line):
            continue
        for root in roots:
            line = line.replace(f"file://{root}", "").replace(root, "")
        lines.append(line)
    return "\n".join(lines).strip()


# How much of each failing test's message a report keeps (the end, where the error is), and for
# how many tests.
FAILURE_CHARS = 1500
MAX_FAILURES = 20


def keep_failures(failures: Mapping[str, str], tests: Sequence[str]) -> dict[str, str]:
    """The messages of `tests` that have one, the first MAX_FAILURES, each cut to its end."""

    kept: dict[str, str] = {}
    for test in tests:
        why = failures.get(test, "").strip()
        if why and len(kept) < MAX_FAILURES:
            kept[test] = why if len(why) <= FAILURE_CHARS else "..." + why[-FAILURE_CHARS:]
    return kept


def run_tests(
    *,
    workspace: Path,
    python: str,
    junit_path: Path,
    test_args: Sequence[str],
    timeout_seconds: int,
    isolate: Isolate | None = None,
    coverage_rc: Path | None = None,
    no_cov: bool = False,
    plugin_dir: Path | None = None,
) -> JsonObject:
    """Run pytest; with `coverage_rc`, under coverage.py with that configuration (and, with
    `no_cov`, pytest-cov's own coverage off, so it does not take the measurement over). With
    `plugin_dir`, the plugin there records which test ran each line (see
    `write_test_contexts_plugin`)."""

    covered = [python, "-m", "coverage", "run", f"--rcfile={coverage_rc}"] if coverage_rc else []
    argv = [
        *(covered or [python]),
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--junitxml={junit_path}",
        "-o",
        "junit_family=xunit2",
        *(["--no-cov"] if no_cov else []),
        *(["-p", write_test_contexts_plugin(plugin_dir)] if plugin_dir else []),
        *test_args,
    ]
    # A report left by an earlier run (the last mutant's) must not be read as this one's.
    junit_path.unlink(missing_ok=True)
    environment = _execution_environment()
    # The clone's code must win over an editable install of the original checkout.
    environment["PYTHONPATH"] = _import_path(workspace) + (
        f"{os.pathsep}{plugin_dir}" if plugin_dir else ""
    )
    try:
        completed = subprocess.run(
            isolate(argv) if isolate else argv,
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
        "runner": "pytest",
        "command": " ".join(["python", "-m", "pytest", "-q", *test_args]),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "pytest_missing": "No module named pytest" in output,
        "runner_missing": "No module named pytest" in output,
        "counts": counts,
        "outcomes": outcomes,
        "failures": read_junit_failures(junit_path),
        "output_tail": output.strip()[-OUTPUT_TAIL_CHARS:],
    }


def _importable(python: str, module: str) -> bool:
    completed = subprocess.run(
        [python, "-I", "-c", f"import {module}"],
        capture_output=True,
        timeout=60,
        check=False,
        shell=False,
    )
    return completed.returncode == 0


_JS_SOURCE = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")


def _source_file(runner: str) -> Callable[[str], bool]:
    """Whether a changed file is code the tests should run: not a test, its data or vendored."""

    def keep(path: str) -> bool:
        parts = PurePosixPath(path).parts
        if {"testdata", "vendor", "node_modules"} & set(parts):
            return False
        if runner == "go":
            return path.endswith(".go") and not is_go_test_file(path)
        if runner in JAVA_RUNNERS:
            return (
                path.endswith(".java")
                and not is_java_test_file(path)
                and not is_java_test_side(path)
            )
        if runner in RUNNERS:
            return (
                path.endswith(_JS_SOURCE)
                and not path.endswith((".d.ts", ".d.mts", ".d.cts"))
                and not is_js_test_file(path)
                and not is_js_config_file(path)
            )
        return (
            path.endswith(".py") and not _is_test_file(path) and parts[-1] not in HARNESS_FILE_NAMES
        )

    return keep


def read_python_coverage(
    workspace: Path,
    python: str,
    rcfile: Path,
    measured_dir: Path,
    contexts: dict[str, dict[int, set[str]]] | None = None,
) -> dict[str, tuple[set[int], set[int]]]:
    """Combine the run's coverage data and read it. A probe file runs in a measured directory
    first, so there is data even when no test reached any of them (every changed line then
    reads as not run instead of not measured). With `contexts`, also which tests ran each
    line."""

    probe = measured_dir / "_sdetkit_coverage_probe.py"
    out = rcfile.with_name("coverage.json")
    try:
        probe.write_text("", encoding="utf-8")
        report = ["json", "-o", str(out), *(["--show-contexts"] if contexts is not None else [])]
        for args in (["run", str(probe)], ["combine"], report):
            # -I: the clone's own modules (one named `coverage`, say) are not imported here.
            subprocess.run(
                [python, "-I", "-m", "coverage", *args, f"--rcfile={rcfile}"],
                cwd=workspace,
                env=_execution_environment(),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
                shell=False,
            )
    finally:
        probe.unlink(missing_ok=True)
    measured = read_coverage_json(out, workspace, contexts)
    measured.pop(probe.relative_to(workspace.resolve()).as_posix(), None)
    return measured


def budget_timeout(timeout: int, max_seconds: float | None, elapsed: float) -> tuple[int, bool]:
    """A mutant run's timeout under a time budget, and whether the budget cut it short: what
    is left of the budget when that is less than `timeout`, and at least a second. Without a
    budget, `timeout` as it is: a run it ends hung, which counts as caught."""

    if max_seconds is None:
        return timeout, False
    left = max(1, int(max_seconds - elapsed))
    return (left, True) if left < timeout else (timeout, False)


# Past this many tests running a line, the whole command is as quick to run as a selection.
MAX_SELECTED_TESTS = 200


def tests_for_line(
    contexts: Mapping[str, Mapping[int, set[str]]], path: str, line: int
) -> list[str] | None:
    """The pytest node ids of the tests that ran `path:line`, or None when every test must run:
    the line ran outside a test too (at import, during collection, in a fixture shared from
    before), is not known, or ran in more tests than a selection saves."""

    names = (contexts.get(path) or {}).get(line)
    if not names or "" in names or len(names) > MAX_SELECTED_TESTS:
        return None
    return sorted(names)


def _options(workspace: Path, test_args: Sequence[str]) -> list[str]:
    """`test_args` without the tests they name (paths and node ids), to run other tests."""

    return [
        arg
        for arg in test_args
        if arg.startswith("-") or not ("::" in arg or (workspace / arg).exists())
    ]


BASE_MODES = ("targeted", "full", "none")
NETWORK_MODES = ("allow", "deny")
# Past this many tests to re-run on the base, a full base run is as cheap and simpler.
MAX_TARGETED = 500


def _clean(workspace: Path) -> None:
    # node_modules holds the links to the repository's installed packages (see js_tests).
    _git(workspace, "clean", "-fdxq", "-e", "/node_modules", env=_execution_environment())


def _checkout(workspace: Path, sha: str) -> None:
    _git(workspace, "checkout", "--quiet", "--force", "--detach", sha, env=_execution_environment())
    _clean(workspace)


def junit_id(nodeid: str) -> str:
    """The id pytest's JUnit report gives a test node id (`classname::name`)."""

    # pytest's junitxml.mangle_test_address: parameters stay with the name, the path is dotted.
    path, bracket, params = nodeid.partition("[")
    names = path.split("::")
    names[0] = re.sub(r"\.py$", "", names[0].replace("/", "."))
    names[-1] += bracket + params
    return f"{'.'.join(names[:-1])}::{names[-1]}"


def collect_ids(
    *,
    workspace: Path,
    python: str,
    test_args: Sequence[str],
    timeout_seconds: int,
    isolate: Isolate | None = None,
) -> tuple[list[str], str]:
    """The node ids pytest collects in the workspace, and its output (for errors)."""

    environment = _execution_environment()
    environment["PYTHONPATH"] = _import_path(workspace)
    argv = [python, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *test_args]
    completed = subprocess.run(
        isolate(argv) if isolate else argv,
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        shell=False,
    )
    ids = [line.strip() for line in completed.stdout.splitlines() if "::" in line]
    return ids, f"{completed.stdout}\n{completed.stderr}"


def targeted_base_run(
    *,
    workspace: Path,
    python: str,
    junit_path: Path,
    test_args: Sequence[str],
    head_run: Mapping[str, Any],
    timeout_seconds: int,
    isolate: Isolate | None = None,
) -> JsonObject:
    """What the base needs to explain the change's run, without running the whole suite again.

    Collecting the base finds the tests that no longer run; re-running on the base only the tests
    that failed or were skipped on the change tells a regression from a failure that was already
    there. Every other collected test is recorded as "collected": it is known to exist on the
    base, its outcome there was not needed.
    """

    collected, output = collect_ids(
        workspace=workspace,
        python=python,
        test_args=test_args,
        timeout_seconds=timeout_seconds,
        isolate=isolate,
    )
    by_junit = {junit_id(nodeid): nodeid for nodeid in collected}
    targets = sorted(
        by_junit[test]
        for test, outcome in head_run["outcomes"].items()
        if outcome in {"failed", "skipped"} and test in by_junit
    )
    if len(targets) > MAX_TARGETED:
        return run_tests(
            workspace=workspace,
            python=python,
            junit_path=junit_path,
            test_args=test_args,
            timeout_seconds=timeout_seconds,
            isolate=isolate,
        )
    if targets:
        run = run_tests(
            workspace=workspace,
            python=python,
            junit_path=junit_path,
            test_args=targets,
            timeout_seconds=timeout_seconds,
            isolate=isolate,
        )
    else:
        run = {
            "runner": "pytest",
            "command": " ".join(["python", "-m", "pytest", "--collect-only", "-q", *test_args]),
            "exit_code": 0,
            "timed_out": False,
            "pytest_missing": "No module named pytest" in output,
            "runner_missing": "No module named pytest" in output,
            "counts": {"passed": 0, "failed": 0, "skipped": 0},
            "outcomes": {},
            "failures": {},
            "output_tail": output.strip()[-OUTPUT_TAIL_CHARS:],
        }
    run["outcomes"] = {**{test: "collected" for test in by_junit}, **run["outcomes"]}
    return {**run, "mode": "targeted", "collected": len(collected), "rerun": len(targets)}


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


def _test_side_paths(change: Mapping[str, Any]) -> list[str]:
    """The change's files on the tests' side: test modules, their helpers and data, conftest."""

    paths: list[str] = []
    for entry in change["changed"]:
        path = PurePosixPath(entry["path"])
        if entry["status"] == "D":
            continue
        if (
            _is_test_file(entry["path"])
            or is_js_test_file(entry["path"])
            or is_go_test_file(entry["path"])
            or is_java_test_file(entry["path"])
            or is_java_test_side(entry["path"])
            or path.name == "conftest.py"
            or "tests" in path.parts
            or "testdata" in path.parts
        ):
            paths.append(entry["path"])
    return sorted(paths)


def _is_test_module(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def proving_tests(proof_run: Mapping[str, Any], head_run: Mapping[str, Any]) -> JsonObject:
    """Which of the change's tests fail on the code before it and pass on the change.

    `proof_run` ran the change's tests against the base code. A test module that did not even
    import there (it needs something the change adds) fails as a whole: pytest reports it as
    one error named after the module.
    """

    before: Mapping[str, str] = proof_run["outcomes"]
    after: Mapping[str, str] = head_run["outcomes"]
    broken_modules = {test.split("::", 1)[1] for test, o in before.items() if test.startswith("::")}

    def failed_before(test: str) -> bool:
        module = test.split("::", 1)[0]
        if before.get(test) == "failed":
            return True
        return any(module == m or module.startswith(f"{m}.") for m in broken_modules)

    ran = [t for t, o in after.items() if o == "passed" and (t in before or failed_before(t))]
    return {
        "proving": sorted(t for t in ran if failed_before(t)),
        "not_proving": sorted(t for t in ran if before.get(t) == "passed"),
    }


def coverage_findings(coverage: Mapping[str, Any]) -> list[JsonObject]:
    """Changed code no test runs: a note, or a blocking finding below the minimum."""

    findings: list[JsonObject] = []
    minimum = float(coverage.get("minimum") or 0)
    percent = coverage.get("percent")
    below = percent is not None and percent < minimum
    if not_run_items(coverage):
        findings.append(
            _finding(
                "changed_lines_not_run",
                "Changed lines of code that no test runs."
                + (f" {percent:g}% of them run; the minimum is {minimum:g}%." if below else ""),
                blocking=below,
                items=not_run_items(coverage),
            )
        )
    if coverage.get("unmeasured"):
        findings.append(
            _finding(
                "changed_files_not_measured",
                "Changed files no test loaded: none of their changed lines ran.",
                blocking=False,
                items=coverage["unmeasured"],
            )
        )
    if minimum and not coverage.get("measured"):
        findings.append(
            _finding(
                "changed_lines_not_measured",
                "A minimum changed-line coverage is set, but it could not be measured: "
                f"{coverage.get('reason')}.",
                blocking=True,
            )
        )
    return findings


def mutation_findings(mutation: Mapping[str, Any] | None) -> list[JsonObject]:
    """Changed lines no test checks: a note, or a blocking finding below the minimum score."""

    if not mutation:
        return []
    findings: list[JsonObject] = []
    minimum = float(mutation.get("minimum") or 0)
    score = mutation.get("score")
    below = score is not None and score < minimum
    if survivor_items(mutation):
        findings.append(
            _finding(
                "changed_lines_not_checked",
                "The tests still pass with these changed lines altered, so no test checks what "
                "they do."
                + (
                    f" The tests catch {score:g}% of the mutants; the minimum is {minimum:g}%."
                    if below
                    else ""
                ),
                blocking=below,
                items=survivor_items(mutation),
            )
        )
    if minimum and not mutation.get("ran"):
        findings.append(
            _finding(
                "changed_lines_not_mutated",
                "A minimum mutation score is set, but the mutants could not run: "
                f"{mutation.get('reason')}.",
                blocking=True,
            )
        )
    return findings


# --- the decision -----------------------------------------------------------------------


def broken_tests(
    head_run: Mapping[str, Any], base_run: Mapping[str, Any] | None, comparison: Mapping[str, Any]
) -> list[str]:
    """The tests the change breaks: every failure when there is no base run to compare with."""

    if base_run is None:
        return sorted(t for t, o in head_run["outcomes"].items() if o == "failed")
    return sorted([*comparison["regressions"], *comparison["new_failures"]])


def decide(
    *,
    head_run: Mapping[str, Any],
    base_run: Mapping[str, Any] | None,
    comparison: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    not_imported: Sequence[str],
) -> tuple[str, list[str]]:
    """The status and the reasons for it, most important first."""

    runner = head_run.get("runner", "pytest")
    if head_run.get("runner_missing") or head_run["pytest_missing"]:
        if runner in RUNNERS:
            return NOT_RUN, [
                f"{runner} is not installed in the repository: install its packages (npm ci)"
            ]
        if runner != "pytest":
            return NOT_RUN, [head_run["output_tail"] or f"{runner} is not installed"]
        return NOT_RUN, ["pytest is not installed in the interpreter that ran the tests"]
    if head_run["timed_out"]:
        return NOT_RUN, ["the tests timed out on the change"]
    if not_imported:
        return NOT_RUN, [
            "the tests would import the changed code from outside the clone: "
            + ", ".join(not_imported)
        ]
    if not head_run["outcomes"]:
        # The runner's last line names the reason: a usage error, an import error, an early exit.
        last_line = (head_run["output_tail"].splitlines() or [""])[-1].strip()
        why = f"{runner} exit code {head_run['exit_code']}" + (
            f": {last_line}" if last_line else ""
        )
        if base_run is not None and base_run["outcomes"]:
            return FAILED, [f"no test ran on the change ({why})"]
        return NOT_RUN, [f"no test ran ({why})"]
    reasons: list[str] = []
    broken = broken_tests(head_run, base_run, comparison)
    if broken:
        return FAILED, [
            f"{len(broken)} test(s) fail on the change: " + ", ".join(sorted(broken)[:5])
        ]
    if head_run["exit_code"] not in {0, 1}:
        return FAILED, [f"{runner} exited with code {head_run['exit_code']} on the change"]
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


def _shown(items: Sequence[str], limit: int = 3) -> str:
    return ", ".join(items[:limit]) + (
        f" and {len(items) - limit} more" if len(items) > limit else ""
    )


def _next_action(status: str, findings: Sequence[Mapping[str, Any]] = ()) -> str:
    """What to do next. When the tests pass, also where they fall short: the changed lines no
    test runs and those no test checks, so whoever made the change (an agent, say) can add the
    tests they need."""

    action = {
        VERIFIED: "Read the change itself: the tests pass and were not weakened, which says nothing about intent.",
        REVIEW: "Read the findings in change-verification.md before accepting the change.",
        FAILED: "Send the change back: it breaks tests (see change-verification.md).",
        NOT_RUN: "Fix the reason the tests could not run, then verify again.",
    }[status]
    if status not in {VERIFIED, REVIEW}:
        return action
    items = {finding["code"]: list(finding.get("items") or []) for finding in findings}
    gaps: list[str] = []
    if items.get("changed_lines_not_run"):
        gaps.append(f"the changed lines no test runs ({_shown(items['changed_lines_not_run'])})")
    if items.get("changed_lines_not_checked"):
        # `path:line: before → after`: one line can have several surviving mutants.
        lines = list(
            dict.fromkeys(item.split(": ", 1)[0] for item in items["changed_lines_not_checked"])
        )
        gaps.append(f"the changed lines no test checks ({_shown(lines)})")
    return f"{action} Then add tests for {' and '.join(gaps)}." if gaps else action


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
                "base_mode": report["tests"].get("base_mode", "full"),
                **{key: len(value) for key, value in report["tests"]["comparison"].items()},
                "proving": len((report["tests"].get("proof") or {}).get("proving", [])),
                "not_proving": len((report["tests"].get("proof") or {}).get("not_proving", [])),
            },
            "findings": [finding["code"] for finding in report["findings"]],
            "changed_lines": {
                key: (report.get("changed_coverage") or {}).get(key)
                for key in ("measured", "changed_lines", "run_lines", "percent", "minimum")
            },
            "mutation": (
                {
                    key: report["mutation"].get(key)
                    for key in (
                        "ran",
                        "killed",
                        "survived",
                        "timed_out",
                        "not_built",
                        "score",
                        "minimum",
                        "not_started",
                        "unfinished",
                    )
                }
                if report.get("mutation")
                else None
            ),
            "evidence": dict(sorted(evidence.items())),
            "network_isolated": report.get("network_isolated") is True,
        },
    }


def _proof_line(proof: Mapping[str, Any] | None) -> str:
    """Whether the change's own tests show what it does, in one sentence (empty when none ran)."""

    if not proof or not proof.get("run"):
        return ""
    proving, not_proving = len(proof["proving"]), len(proof["not_proving"])
    total = proving + not_proving
    if not total:
        return "**Proof:** no test in the changed test files passed on the change, so they prove nothing yet."
    if not proving:
        return (
            f"**Proof:** none of the {total} passing test(s) in the changed test files fail on the code "
            "before the change; they do not show what it does."
        )
    return (
        f"**Proof:** {proving} of the {total} passing test(s) in the changed test files fail on the "
        "code before the change and pass with it."
    )


def _render_markdown(report: Mapping[str, Any]) -> str:
    change = report["change"]
    head = report["tests"]["head"]
    base = report["tests"]["base"]
    comparison = report["tests"]["comparison"]
    proof = report["tests"].get("proof")
    lines = [
        "# SDETKit change verification",
        "",
        f"- status: `{report['status']}`",
        f"- base: `{change['base_sha'][:12]}`  head: `{change['head_sha'][:12]}` ({change['head_source']})",
        f"- changed files: {len(change['changed'])}",
        f"- tests on the change: {_counts(head)}",
    ]
    if base:
        lines.append(f"- tests on the base: {_counts(base)}")
    if _proof_line(proof):
        lines += ["", _proof_line(proof)]
    if coverage_line(report.get("changed_coverage")):
        lines += ["", coverage_line(report.get("changed_coverage"))]
    if mutation_line(report.get("mutation")):
        lines += ["", mutation_line(report.get("mutation"))]
    lines += ["", "## Why", ""] + [f"- {reason}" for reason in report["reasons"]]
    lines += ["", "## Next action", "", report["next_action"], ""]
    if proof and proof["proving"]:
        lines += ["## Tests that prove the change", ""]
        lines += [f"- `{item}`" for item in proof["proving"][:50]] + [""]
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
    failures = report["tests"].get("failures") or {}
    if failures:
        lines += ["## Why they fail", ""]
        for test, why in failures.items():
            lines += [f"### `{test}`", "", _fenced(why), ""]
    lines += [
        "## Authority",
        "",
        "This checks that the tests pass and were not weakened. It does not prove the change is",
        "correct or safe, and it applies, merges and dismisses nothing.",
        "",
    ]
    return "\n".join(lines)


def _fenced(text: str) -> str:
    """`text` in a code block whose fence no line of it can close."""

    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}text\n{text}\n{fence}"


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
    text = f"{counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped"
    if run.get("mode") == "targeted":
        return f"{run['collected']} collected, {run['rerun']} re-run ({text})"
    return text


def render_summary(report: Mapping[str, Any]) -> str:
    """The short Markdown a job summary or pull request comment shows."""

    status = report["status"]
    change = report["change"]
    tests = report["tests"]
    lines = [
        f"### {_ICONS[status]} SDETKit verify change: {status}",
        "",
        f"`{change['base_sha'][:12]}` → `{change['head_sha'][:12]}`, {len(change['changed'])} file(s) changed.",
        "",
        "| Run | Tests |",
        "| --- | --- |",
        f"| Base | {_counts(tests['base'])} |",
        f"| Change | {_counts(tests['head'])} |",
        "",
    ]
    proof = tests.get("proof")
    if _proof_line(proof):
        lines += [_proof_line(proof), ""]
    if coverage_line(report.get("changed_coverage")):
        lines += [coverage_line(report.get("changed_coverage")), ""]
    if mutation_line(report.get("mutation")):
        lines += [mutation_line(report.get("mutation")), ""]
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
    lists = [(tests["comparison"][key], label) for key, label in _SUMMARY_LISTS]
    if proof:
        lists.append((proof["proving"], "Fail before the change, pass with it"))
    for items, label in lists:
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
    failures = list((tests.get("failures") or {}).items())
    if failures:
        shown = "\n\n".join(f"`{test}`\n\n{_fenced(why)}" for test, why in failures[:5])
        more = (
            f"\n\nand {len(failures) - 5} more in change-verification.md"
            if len(failures) > 5
            else ""
        )
        lines += [
            f"<details><summary>Why they fail ({len(failures)})</summary>",
            "",
            shown + more,
            "",
            "</details>",
            "",
        ]
    lines += [f"**Next:** {report['next_action']}", "", _SUMMARY_FOOTER]
    return "\n".join(lines) + "\n"


_SUMMARY_FOOTER = (
    "Passing, unweakened tests say nothing about intent: a person still reads the change. "
    "Nothing was applied, merged or dismissed."
)


# GitHub shows at most 10 annotations of each level per step.
MAX_ANNOTATIONS = 10


def _command_data(text: str) -> str:
    """A workflow command's message: a line break would end it, `%` starts an escape."""

    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _command_property(text: str) -> str:
    return _command_data(text).replace(":", "%3A").replace(",", "%2C")


def _runs(lines: Sequence[int]) -> list[tuple[int, int]]:
    """(first, last) of each run of consecutive line numbers."""

    runs: list[tuple[int, int]] = []
    for line in sorted(set(lines)):
        if runs and line == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], line)
        else:
            runs.append((line, line))
    return runs


def github_annotations(report: Mapping[str, Any]) -> list[str]:
    """GitHub workflow commands that mark, on the pull request's diff, each changed line no
    test checks (a warning: its surviving mutants) and each run of changed lines no test runs
    (a notice). Paths are the repository's, as the diff names them; the code quoted from the
    change is escaped, so it cannot end the command or start another."""

    commands: list[str] = []
    survivors: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for item in (report.get("mutation") or {}).get("mutants", []):
        if item["outcome"] == "survived":
            survivors.setdefault((item["path"], item["line"]), []).append(item)
    for (path, line), items in sorted(survivors.items())[:MAX_ANNOTATIONS]:
        edits = " or ".join(f"`{item['after']}`" for item in items)
        hints = "; ".join(dict.fromkeys(str(item["hint"]) for item in items if item.get("hint")))
        commands.append(
            f"::warning file={_command_property(path)},line={line},"
            f"title={_command_property('No test checks this line')}::"
            + _command_data(
                f"Every test still passes with this line changed to {edits}, so no test checks "
                "what it does. Add a test that fails on that change"
                + (f": {hints}." if hints else ".")
            )
        )
    runs = [
        (item["path"], first, last)
        for item in (report.get("changed_coverage") or {}).get("files", [])
        for first, last in _runs(item["not_run"])
    ]
    for path, first, last in runs[:MAX_ANNOTATIONS]:
        what = f"line {first}" if first == last else f"lines {first}-{last}"
        commands.append(
            f"::notice file={_command_property(path)},line={first},endLine={last},"
            f"title={_command_property('No test runs this code')}::"
            + _command_data(f"No test runs changed {what} of this file.")
        )
    return commands


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


def resolve_runner(repo_root: Path, runner: str = "auto") -> str:
    """The test runner `auto` means: pytest in a Python project, else what package.json uses,
    else go test with a go.mod, else Maven with a pom.xml or Gradle with a Gradle build."""

    if runner not in RUNNER_CHOICES:
        raise ChangeError(f"unknown test runner: {runner}")
    if runner != "auto":
        return runner
    if any((repo_root / marker).is_file() for marker in _PYTHON_MARKERS):
        return "pytest"
    if detect_runner(repo_root):
        return detect_runner(repo_root)
    if (repo_root / "go.mod").is_file():
        return "go"
    return detect_java_runner(repo_root) or "pytest"


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
    base_mode: str = "targeted",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    runner: str = "auto",
    network: str = "allow",
    min_changed_coverage: float = 0.0,
    measure_coverage: bool = True,
    mutate: bool = False,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    min_mutation_score: float = 0.0,
    max_mutation_seconds: float | None = None,
) -> JsonObject:
    """`base_mode`: "targeted" (collect the base, re-run there what failed or skipped on the
    change), "full" (run the whole suite on the base too) or "none". `runner`: "auto", "pytest",
    "vitest", "jest", "node", "go", "maven" or "gradle"; only pytest has a collection step, so "targeted" runs the
    whole suite on the base for the others. `network`: "allow", or "deny" to run every command
    that executes the repository's code in a network namespace of its own (Linux, unprivileged
    user namespaces): only its own loopback is reachable. "deny" where that is not available is
    an error, not a run with the network. `min_changed_coverage`: below this percentage of
    changed code lines run by the tests, the change needs review (0, the default, only reports
    it); `measure_coverage` False skips the measurement. `mutate`: alter the changed lines the
    tests run, one operator or constant at a time (at most `max_mutants` times), and run the
    tests on each, to find the lines no test checks; `min_mutation_score` (which turns it on) is
    the share of mutants the tests must catch for the change not to need review."""

    if bool(head) == bool(patch_text):
        raise ChangeError("give exactly one of --head REF or --patch FILE")
    if base_mode not in BASE_MODES:
        raise ChangeError(f"unknown base run mode: {base_mode}")
    if network not in NETWORK_MODES:
        raise ChangeError(f"unknown network mode: {network}")
    if not 0 <= min_changed_coverage <= 100:
        raise ChangeError("--min-changed-coverage is a percentage, from 0 to 100")
    if max_mutants < 1:
        raise ChangeError("--max-mutants must be at least 1")
    if max_mutation_seconds is not None and max_mutation_seconds <= 0:
        raise ChangeError("--max-mutation-seconds must be more than 0")
    if not 0 <= min_mutation_score <= 100:
        raise ChangeError("--min-mutation-score is a percentage, from 0 to 100")
    mutate = mutate or min_mutation_score > 0
    isolate: Isolate | None = None
    boundary: JsonObject = {}
    if network == "deny":
        boundary = assess_network_boundary(require_network_isolation=True)
        if boundary.get(PROOF_EXECUTION_ALLOWED) is not True:
            raise ChangeError(
                "--network deny needs a network namespace, which is not available here: "
                + unavailable_reason(boundary)
            )

        def isolated(argv: list[str]) -> list[str]:
            return build_loopback_isolated_argv(boundary, argv)

        isolate = isolated
    base_mode = base_mode if run_base else "none"
    repo_root = repo_root.resolve()
    runner = resolve_runner(repo_root, runner)
    if runner != "pytest" and base_mode == "targeted":
        base_mode = "full"
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
        proof_run: JsonObject | None = None
        proof_modules: list[str] = []

        # Which changed lines of code the tests run, measured on the change's run.
        changed = changed_lines(change["diff"], _source_file(runner))
        coverage_rc: Path | None = None
        go_profile: Path | None = None
        js_coverage: Path | None = None
        java_coverage = False
        measured_dirs: list[Path] = []
        why_not = ""
        if not measure_coverage:
            why_not = "turned off with --no-coverage"
        elif changed and runner in JAVA_RUNNERS:
            java_coverage = True
        elif changed and runner in RUNNERS:
            why_not = coverage_unavailable(runner, repo_root)
            js_coverage = None if why_not else Path(temp_dir) / "js-coverage"
        elif changed and runner == "go":
            go_profile = Path(temp_dir) / "go.cover"
        elif changed and _importable(interpreter, "coverage"):
            coverage_rc = Path(temp_dir) / "coveragerc"
            measured_dirs = sorted({(workspace / path).parent.resolve() for path in changed})
            coverage_rcfile(coverage_rc, Path(temp_dir) / ".coverage", measured_dirs)
        elif changed:
            why_not = "coverage.py is not installed in the interpreter that runs the tests"
        no_cov = coverage_rc is not None and _importable(interpreter, "pytest_cov")
        # Which test ran each changed line, so a mutant of it re-runs those tests only.
        plugin_dir = Path(temp_dir) / "plugins" if mutate else None
        contexts: dict[str, dict[int, set[str]]] | None = {} if mutate else None

        def run(
            name: str,
            args: Sequence[str],
            *,
            cover: bool = False,
            fail_fast: bool = False,
            timeout: int = timeout_seconds,
            related: Sequence[str] = (),
        ) -> JsonObject:
            if runner == "go":
                return run_go_tests(
                    workspace=workspace,
                    junit_path=Path(temp_dir) / name,
                    test_args=args,
                    timeout_seconds=timeout,
                    environment=environment,
                    output_tail_chars=OUTPUT_TAIL_CHARS,
                    isolate=isolate,
                    cover_profile=go_profile if cover else None,
                    fail_fast=fail_fast,
                )
            if runner in JAVA_RUNNERS:
                return run_java_tests(
                    runner,
                    workspace=workspace,
                    junit_path=Path(temp_dir) / name,
                    test_args=args,
                    timeout_seconds=timeout,
                    environment=environment,
                    output_tail_chars=OUTPUT_TAIL_CHARS,
                    isolate=isolate,
                    coverage=cover and java_coverage,
                    fail_fast=fail_fast,
                )
            if runner == "pytest":
                return run_tests(
                    workspace=workspace,
                    python=interpreter,
                    junit_path=Path(temp_dir) / name,
                    test_args=["-x", *args] if fail_fast else args,
                    timeout_seconds=timeout,
                    isolate=isolate,
                    coverage_rc=coverage_rc if cover else None,
                    no_cov=cover and no_cov,
                    plugin_dir=plugin_dir if cover and coverage_rc else None,
                )
            return run_js_tests(
                runner,
                workspace=workspace,
                junit_path=Path(temp_dir) / name,
                test_args=args,
                timeout_seconds=timeout,
                environment=environment,
                output_tail_chars=OUTPUT_TAIL_CHARS,
                isolate=isolate,
                coverage_dir=js_coverage if cover else None,
                coverage_files=sorted(changed),
                fail_fast=fail_fast,
                related=related,
            )

        if runner in RUNNERS:
            link_node_modules(repo_root, workspace)
        # The change first, then the clone moves to the base for everything compared with it.
        _checkout(workspace, change["head_sha"])
        not_imported = (
            _imports_the_clone(workspace, interpreter, change) if runner == "pytest" else []
        )
        started = time.monotonic()
        head_run = run("tests-head.xml", test_args, cover=True)
        head_seconds = time.monotonic() - started
        measured: dict[str, tuple[set[int], set[int]]] | None = None
        tool = ""
        if coverage_rc is not None:
            tool = "coverage.py"
            measured = read_python_coverage(
                workspace, interpreter, coverage_rc, measured_dirs[0], contexts
            )
        elif go_profile is not None:
            tool = "go test -coverprofile"
            profile = go_profile.read_text(encoding="utf-8") if go_profile.is_file() else ""
            measured = read_go_profile(profile, go_module_path(workspace))
        elif js_coverage is not None:
            tool = f"{runner} (V8)"
            measured = (
                read_lcov(js_coverage / "lcov.info", workspace)
                if runner == "node"
                else read_istanbul_json(js_coverage / "coverage-final.json", workspace)
            )
        elif java_coverage:
            tool = "JaCoCo"
            measured = read_jacoco_xml(jacoco_reports(workspace), changed)
        if measured:
            coverage = summarize(changed, measured, tool=tool, minimum=min_changed_coverage)
        elif measured is not None:
            # No data at all (the build failed, the runner stopped early): no line is known
            # to have run or not.
            coverage = not_measured(f"{tool} wrote no coverage data", minimum=min_changed_coverage)
        elif why_not:
            coverage = not_measured(why_not, minimum=min_changed_coverage)
        else:
            # The change touches no source code: nothing to measure.
            coverage = summarize({}, {}, tool="", minimum=min_changed_coverage)
        mutation: JsonObject | None = None
        if mutate:
            # Only the changed lines the tests run: a mutant of one no test runs survives.
            ran = (
                {
                    path: [n for n in lines if n in measured[path][1]]
                    for path, lines in changed.items()
                    if path in measured
                }
                if measured
                else changed
            )
            # A mutant that hangs the tests counts as caught once it takes twice the change's run.
            mutant_timeout = min(timeout_seconds, int(head_seconds * 2) + 30)

            # go test: the packages whose test binaries are built from the mutated package.
            go_binaries = (
                test_dependencies(workspace, environment)
                if runner == "go" and not any(not arg.startswith("-") for arg in test_args)
                else None
            )

            mutation_started = time.monotonic()

            def mutant_timeouts() -> tuple[int, bool]:
                return budget_timeout(
                    mutant_timeout, max_mutation_seconds, time.monotonic() - mutation_started
                )

            def run_mutant(mutant: Mutant) -> JsonObject:
                # pytest re-runs only the tests that ran the mutated line, when that is known;
                # jest and vitest the test files that import the mutated file, and go test the
                # packages built from it, unless the command names its tests itself (a
                # selection of its own to respect).
                tests = tests_for_line(contexts or {}, mutant.path, mutant.line)
                if go_binaries:
                    tests = dependent_test_packages(go_binaries, mutant.path) or None
                related = (
                    [mutant.path]
                    if runner in {"jest", "vitest"}
                    and _options(workspace, test_args) == list(test_args)
                    else []
                )
                args = [*_options(workspace, test_args), *tests] if tests else list(test_args)
                timeout, cut = mutant_timeouts()
                result = run(
                    "tests-mutant.xml", args, fail_fast=True, timeout=timeout, related=related
                )
                if (tests or related) and not result["outcomes"]:
                    # The selection did not resolve (another root directory, no test file
                    # imports the file, say): run them all.
                    tests = None
                    timeout, cut = mutant_timeouts()
                    result = run("tests-mutant.xml", test_args, fail_fast=True, timeout=timeout)
                elif related:
                    tests = sorted(result["outcomes"])
                result["selected"] = len(tests) if tests else None
                # Stopped by the budget's end, not by a hang: it tells nothing either way.
                result["unfinished"] = bool(result.get("timed_out") and cut)
                return result

            mutation = mutate_changed_lines(
                workspace=workspace,
                lines=ran,
                head_run=head_run,
                run=run_mutant,
                max_mutants=max_mutants,
                minimum=min_mutation_score,
                max_seconds=max_mutation_seconds,
            )
        if base_mode != "none":
            _checkout(workspace, change["base_sha"])
            if base_mode == "full":
                base_run = run("tests-base.xml", test_args)
            else:
                base_run = targeted_base_run(
                    workspace=workspace,
                    python=interpreter,
                    junit_path=Path(temp_dir) / "tests-base.xml",
                    test_args=test_args,
                    head_run=head_run,
                    timeout_seconds=timeout_seconds,
                    isolate=isolate,
                )
            _clean(workspace)
            test_side = _test_side_paths(change)
            proof_modules = [
                path
                for path in test_side
                if _is_test_module(path)
                or is_js_test_file(path)
                or is_go_test_file(path)
                or is_java_test_file(path)
            ]
            if proof_modules:
                # The change's tests against the code before it: a test that fails here and
                # passes on the change shows that the change does what the test checks.
                _git(workspace, "checkout", change["head_sha"], "--", *test_side, env=environment)
                # go test takes packages, not files: the changed test files' packages run.
                proof_args = go_package_args(proof_modules) if runner == "go" else proof_modules
                proof_run = run("tests-proof.xml", proof_args)
        evidence: dict[str, str] = {}
        for name in ("tests-base.xml", "tests-proof.xml", "tests-head.xml"):
            source = Path(temp_dir) / name
            if source.is_file():
                shutil.copyfile(source, out_dir / name)
                evidence[name] = _sha256(source.read_bytes())

    comparison = compare_runs(base_run, head_run)
    # A renamed test ran before under its old name; it is not missing.
    renamed_ids = [item["junit_id"] for finding in findings for item in finding.get("renamed", [])]
    comparison["missing"] = [
        test
        for test in comparison["missing"]
        # Parametrized ids (`[...]`, Java's `(...)`) and Go subtests (`/...`) go with their test.
        if not any(
            test == old or test.startswith((f"{old}[", f"{old}/", f"{old}(")) for old in renamed_ids
        )
    ]
    proof: JsonObject = {"files": proof_modules, "run": proof_run, "proving": [], "not_proving": []}
    if proof_run is not None:
        proof.update(proving_tests(proof_run, head_run))
        if proof["not_proving"] and not proof["proving"]:
            findings.append(
                _finding(
                    "tests_do_not_prove_the_change",
                    "No test in the changed test files fails on the code before the change, "
                    "so they do not show what it does (expected for a pure refactor).",
                    blocking=False,
                    items=proof["not_proving"],
                )
            )
    findings += coverage_findings(coverage)
    findings += mutation_findings(mutation)
    status, reasons = decide(
        head_run=head_run,
        base_run=base_run,
        comparison=comparison,
        findings=findings,
        not_imported=not_imported,
    )
    # Why the broken tests fail, so whoever made the change can fix it without running them.
    runs = [run_result for run_result in (base_run, proof_run, head_run) if run_result]
    for run_result in runs:
        run_result["failures"] = {
            test: clean_failure(why, workspace)
            for test, why in run_result.get("failures", {}).items()
        }
    failures = (
        keep_failures(head_run["failures"], broken_tests(head_run, base_run, comparison))
        if status == FAILED
        else {}
    )
    for run_result in runs:
        run_result["failures"] = keep_failures(
            run_result["failures"], sorted(run_result["failures"])
        )
    patch_path = out_dir / "change.patch"
    patch_path.write_text(change["diff"], encoding="utf-8")
    report: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reasons": reasons,
        "next_action": _next_action(status, findings),
        "repository": _repository(repo_root),
        "verifier_version": tool_version(),
        "change": {key: value for key, value in change.items() if key != "diff"},
        "python": interpreter,
        "tests": {
            "runner": runner,
            "base": base_run,
            "base_mode": base_mode,
            "head": head_run,
            "comparison": comparison,
            "proof": proof,
            "failures": failures,
        },
        "findings": findings,
        "changed_coverage": coverage,
        "mutation": mutation,
        "real_tree_modified": False,
        "network_isolated": isolate is not None,
        "network": {
            "mode": network,
            "backend": boundary.get("backend", ""),
            "loopback": "own" if isolate is not None else "host",
        },
        "verdict": build_verdict(
            source="verify change",
            decision=_SHARED_DECISION[status],
            reasons=reasons,
            next_action=_next_action(status, findings),
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
    source.add_argument(
        "--working-tree",
        action="store_true",
        help="Verify the uncommitted change, untracked files included, against HEAD",
    )
    source.add_argument(
        "--pr",
        type=int,
        metavar="NUMBER",
        help=(
            "Verify a GitHub pull request: its head from origin's refs/pull/NUMBER/head, from "
            "where it left the default branch (a --base given instead is used as it is)"
        ),
    )
    parser.add_argument(
        "--base", default="HEAD", help="Commit the change starts from (default: HEAD)"
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--python", help="Interpreter for the tests (default: the project's own)")
    parser.add_argument(
        "--base-run",
        choices=BASE_MODES,
        default="targeted",
        help=(
            "What runs on the base: targeted (collect it, re-run what failed or was skipped on the "
            "change; default), full (the whole suite again), none"
        ),
    )
    parser.add_argument(
        "--no-base-run",
        action="store_true",
        help="Same as --base-run none: every failure then counts against the change",
    )
    parser.add_argument(
        "--runner",
        choices=RUNNER_CHOICES,
        default="auto",
        help=(
            "Test runner: pytest, vitest, jest, node (node --test), go (go test), maven or "
            "gradle; auto (default) uses pytest in a Python project, otherwise what "
            "package.json uses, otherwise go test where there is a go.mod, otherwise Maven or "
            "Gradle"
        ),
    )
    parser.add_argument(
        "--network",
        choices=NETWORK_MODES,
        default="allow",
        help=(
            "deny: run the tests in a network namespace of their own (Linux), so the change's "
            "code reaches nothing but its own loopback; an error where that is not available"
        ),
    )
    parser.add_argument(
        "--min-changed-coverage",
        type=float,
        default=0.0,
        metavar="PERCENT",
        help=(
            "Below this share of changed code lines run by the tests the change needs review "
            "(default 0: report it only). Measured for pytest (coverage.py), go test, jest, vitest, "
            "node --test, Maven and Gradle (JaCoCo)"
        ),
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Do not measure which changed lines the tests run",
    )
    parser.add_argument(
        "--mutate",
        action="store_true",
        help=(
            "Also alter the changed lines the tests run, one operator or constant at a time, and "
            "run the tests on each mutant: a mutant no test fails on shows a line no test checks"
        ),
    )
    parser.add_argument(
        "--max-mutants",
        type=int,
        default=DEFAULT_MAX_MUTANTS,
        metavar="N",
        help=f"At most this many mutants, spread over the changed lines (default {DEFAULT_MAX_MUTANTS})",
    )
    parser.add_argument(
        "--max-mutation-seconds",
        type=float,
        default=None,
        metavar="SECONDS",
        help=(
            "Start no further mutant once this many seconds have gone, and stop a running one "
            "when they run out; the report says how many did not run or finish. Default: no limit"
        ),
    )
    parser.add_argument(
        "--min-mutation-score",
        type=float,
        default=0.0,
        metavar="PERCENT",
        help=(
            "Below this share of mutants caught by the tests the change needs review (turns "
            "--mutate on; default 0: report the survivors only)"
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--github-annotations",
        action="store_true",
        help=(
            "Print GitHub workflow commands that mark the changed lines no test checks or runs "
            "on the pull request's diff (with --format text)"
        ),
    )
    parser.add_argument(
        "--summary-out",
        help="Append a short Markdown summary here (a job summary or pull request comment)",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Arguments for the test runner after `--`, such as a test path",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.github_annotations and args.format == "json":
        parser.error("--github-annotations prints to the output, which --format json holds")
    out_dir = Path(args.out_dir)
    try:
        patch_text = Path(args.patch).read_text(encoding="utf-8") if args.patch else ""
        if args.patch and not patch_text.strip():
            raise ChangeError(f"the patch file is empty: {args.patch}")
        if args.working_tree:
            if args.base != "HEAD":
                raise ChangeError("--working-tree verifies the uncommitted change against HEAD")
            patch_text = working_tree_patch(Path(args.repo_root))
            if not patch_text.strip():
                raise ChangeError("there is no uncommitted change to verify")
        base, head = args.base, args.head or ""
        if args.pr is not None:
            pr_base, head = pull_request_change(Path(args.repo_root), args.pr)
            base = pr_base if args.base == "HEAD" else args.base
        report = verify_change(
            repo_root=Path(args.repo_root),
            out_dir=out_dir,
            base=base,
            head=head,
            patch_text=patch_text,
            python=args.python,
            test_args=args.pytest_args,
            run_base=not args.no_base_run,
            base_mode=args.base_run,
            timeout_seconds=args.timeout_seconds,
            runner=args.runner,
            network=args.network,
            min_changed_coverage=args.min_changed_coverage,
            measure_coverage=not args.no_coverage,
            mutate=args.mutate,
            max_mutants=args.max_mutants,
            max_mutation_seconds=args.max_mutation_seconds,
            min_mutation_score=args.min_mutation_score,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"verify change error: {exc}", file=sys.stderr)
        _append(
            args.summary_out,
            f"### {_ICONS[NOT_RUN]} SDETKit verify change: {NOT_RUN}\n\n{exc}\n",
        )
        return 2
    _append(args.summary_out, render_summary(report))
    if args.github_annotations:
        for command in github_annotations(report):
            print(command)
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
