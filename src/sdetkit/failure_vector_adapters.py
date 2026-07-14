from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sdetkit.failure_vector import FailureVector, extract_failure_vector

TS_ERROR = re.compile(r"(?P<path>[\w./-]+\.(?:ts|tsx|js|jsx))\(\d+,\d+\): error (?P<check>TS\d+):")
JS_LOCATION = re.compile(r"(?P<path>[\w./-]+\.(?:ts|tsx|js|jsx)):\d+:\d+\s+error\s+(?P<check>.+)")
JS_TEST = re.compile(
    r"^(?:FAIL|❯)\s+(?P<path>[\w./-]+\.(?:test|spec)\.(?:ts|tsx|js|jsx))",
    re.MULTILINE,
)
GO_LOCATION = re.compile(r"(?P<path>[\w./-]+\.go):\d+(?::\d+)?:\s*(?P<check>.+)")
GO_TEST = re.compile(r"---\s+FAIL:\s+(?P<check>[\w./-]+)")
JAVA_LOCATION = re.compile(
    r"(?P<path>[\w./-]+\.java)(?::\d+|:\[\d+(?:,\d+)?\])(?::\s*(?P<check>.+))?"
)
RUST_LOCATION = re.compile(r"(?:-->\s+|at\s+)?(?P<path>[\w./-]+\.rs):\d+:\d+")
RUST_TEST = re.compile(r"^test\s+(?P<check>[\w:./-]+)\s+\.\.\.\s+FAILED$", re.MULTILINE)
DOTNET_LOCATION = re.compile(
    r"(?P<path>(?:src|tests)[/\\][\w./\\-]+\.(?:cs|fs|vb))"
    r"(?:(?:\(|:line\s+)\d+(?:,\d+)?\)?)",
    re.IGNORECASE,
)
DOTNET_TEST = re.compile(
    r"^\s*Failed\s+(?P<check>.+?)\s+\[\d+(?:\.\d+)?\s*(?:ms|s)\]\s*$",
    re.IGNORECASE | re.MULTILINE,
)
DOTNET_XUNIT_TEST = re.compile(
    r"^\s*\[xUnit\.net[^\]]*\]\s+(?P<check>.+?)\s+\[FAIL\]\s*$",
    re.IGNORECASE | re.MULTILINE,
)
DOTNET_TEST_COMMAND = re.compile(
    r"^(?:Run|\$)\s+(?P<command>dotnet\s+test(?:\s+.+)?)$",
    re.IGNORECASE | re.MULTILINE,
)
DOTNET_PROJECT = re.compile(
    r"(?P<project>[\w./\\-]+\.(?:csproj|fsproj|vbproj))",
    re.IGNORECASE,
)
COMMAND = re.compile(r"^(?:Run|\$)\s+(?P<command>.+)$", re.MULTILINE)
EXIT_CODE = re.compile(r"Process completed with exit code (?P<code>\d+)")
SUPPORTED = frozenset({"auto", "python", "javascript_typescript", "go", "java", "rust", "dotnet"})


@dataclass(frozen=True)
class FailureVectorAdapterResult:
    vector: FailureVector
    ecosystem: str
    tool: str
    confidence: str
    uncertainty: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = self.vector.to_dict()
        payload["adapter"] = {
            "ecosystem": self.ecosystem,
            "tool": self.tool,
            "confidence": self.confidence,
            "uncertainty": list(self.uncertainty),
            "target_code_execution": False,
        }
        return payload


def extract_ci_failure_summary_vector(
    report: Mapping[str, Any],
    *,
    log_url: str | None = None,
    environment: str = "github_actions",
) -> FailureVectorAdapterResult:
    """Convert a read-only full-suite summary artifact into a FailureVector."""

    source = _summary_mapping(report.get("source"))
    first_failure = _summary_mapping(report.get("first_failure"))
    workflow = _summary_text(source.get("workflow")) or "unknown"
    job = _summary_text(source.get("job")) or "unknown"
    command = _summary_text(source.get("command")) or "unknown"
    status = _summary_text(report.get("status")) or "unknown"
    check = _summary_check_name(workflow, job)

    if not first_failure:
        vector = FailureVector(
            check=check,
            command=command,
            exit_code=None,
            failure_class="unknown",
            risk="high",
            scope="unknown",
            reproducible_locally="not_run",
            safe_fix_candidate=False,
            first_failing_line=f"{status}: no failed junit testcase observed",
            affected_files=(),
            log_url=log_url,
            local_repro_command=command if command != "unknown" else None,
            environment=environment,
            headline_signal=f"{check}: unknown",
            actual_failure=status,
            failure_type="unknown",
            failing_command=command,
            failing_test_or_check=check,
            owner_hint=check,
            safe_fix_allowed=False,
        )
        return FailureVectorAdapterResult(
            vector=vector,
            ecosystem="python",
            tool="pytest",
            confidence="low",
            uncertainty=(f"ci_failure_summary_status_{status}",),
        )

    classname = _summary_text(first_failure.get("classname"))
    name = _summary_text(first_failure.get("name"))
    message = _summary_text(first_failure.get("message"))
    text_excerpt = _summary_text(first_failure.get("text_excerpt"))
    path = _junit_classname_to_path(classname)
    node = _pytest_node(path, classname, name)
    first_line = _summary_failure_line(node, message, text_excerpt)
    vector = FailureVector(
        check=check,
        command=command,
        exit_code=None,
        failure_class="test",
        risk="medium",
        scope="pr_owned_only" if path else "unknown",
        reproducible_locally="not_run",
        safe_fix_candidate=False,
        first_failing_line=first_line,
        affected_files=(path,) if path else (),
        log_url=log_url,
        local_repro_command=_pytest_repro_command(path, name),
        environment=environment,
        headline_signal=f"{check}: test",
        actual_failure=message or _first_summary_line(text_excerpt) or first_line,
        failure_type="test",
        failing_command=command,
        failing_test_or_check=node or check,
        owner_hint=path or check,
        safe_fix_allowed=False,
    )
    return FailureVectorAdapterResult(
        vector=vector,
        ecosystem="python",
        tool="pytest",
        confidence="high",
        uncertainty=(),
    )


def _summary_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _summary_text(value: Any) -> str:
    return str(value or "").replace("\r", " ").strip()


def _summary_check_name(workflow: str, job: str) -> str:
    if workflow == "unknown" and job == "unknown":
        return "full_suite"
    return f"{workflow}/{job}"


def _junit_classname_to_path(classname: str) -> str:
    if not classname:
        return ""
    path = classname.replace(".", "/") + ".py"
    if path.startswith(("src/", "tests/")):
        return path
    return ""


def _pytest_node(path: str, classname: str, name: str) -> str:
    if path and name:
        return f"{path}::{name}"
    if name:
        return name
    return classname


def _summary_failure_line(node: str, message: str, text_excerpt: str) -> str:
    detail = message or _first_summary_line(text_excerpt)
    if node and detail:
        return f"FAILED {node} - {detail}"
    if node:
        return f"FAILED {node}"
    return detail or "FAILED unknown junit testcase"


def _first_summary_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _pytest_repro_command(path: str, name: str) -> str | None:
    if path and name:
        return f"PYTHONPATH=src python -m pytest -q {path}::{name} -o addopts="
    return None


def extract_ecosystem_failure_vector(
    log_text: str,
    *,
    ecosystem: str = "auto",
    check: str = "unknown",
    log_url: str | None = None,
    environment: str = "unknown",
) -> FailureVectorAdapterResult:
    """Extract advisory evidence without executing target-repository commands."""

    if ecosystem not in SUPPORTED:
        raise ValueError(f"unsupported ecosystem: {ecosystem}")
    selected = _detect(log_text) if ecosystem == "auto" else ecosystem
    if selected == "python":
        vector = extract_failure_vector(
            log_text,
            check=check,
            log_url=log_url,
            environment=environment,
        )
        known = vector.failure_class != "unknown"
        return FailureVectorAdapterResult(
            vector=vector,
            ecosystem="python",
            tool={"test": "pytest", "type": "mypy", "lint": "ruff"}.get(
                vector.failure_class, "unknown"
            ),
            confidence="high" if known else "low",
            uncertainty=() if known else ("python_tool_not_identified",),
        )
    if selected == "javascript_typescript":
        return _javascript_result(log_text, check, log_url, environment)
    if selected == "go":
        return _go_result(log_text, check, log_url, environment)
    if selected == "java":
        return _java_result(log_text, check, log_url, environment)
    if selected == "rust":
        return _rust_result(log_text, check, log_url, environment)
    if selected == "dotnet":
        return _dotnet_result(log_text, check, log_url, environment)
    return _unknown(log_text, "unknown", check, log_url, environment, "ecosystem_not_identified")


def _detect(log_text: str) -> str:
    lower = log_text.lower()
    if TS_ERROR.search(log_text) or JS_LOCATION.search(log_text) or JS_TEST.search(log_text):
        return "javascript_typescript"
    if any(token in lower for token in ("jest", "vitest", "eslint", "tsc --noemit")):
        return "javascript_typescript"
    if _looks_like_rust(log_text):
        return "rust"
    if GO_LOCATION.search(log_text) or GO_TEST.search(log_text):
        return "go"
    if any(token in lower for token in ("go test", "go vet")):
        return "go"
    if _looks_like_dotnet(log_text):
        return "dotnet"
    if _looks_like_java(log_text):
        return "java"
    if any(token in lower for token in ("pytest", "mypy", "ruff", ".py:")):
        return "python"
    return "unknown"


def _javascript_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> FailureVectorAdapterResult:
    lower = log_text.lower()
    match = TS_ERROR.search(log_text)
    if match:
        return _result(
            log_text, check, log_url, environment, match, "type", "typescript", "npx tsc --noEmit"
        )
    match = JS_LOCATION.search(log_text)
    if match:
        return _result(
            log_text, check, log_url, environment, match, "lint", "eslint", "npx eslint ."
        )
    match = JS_TEST.search(log_text)
    if match or "assertionerror" in lower or "test failed" in lower:
        tool = "vitest" if "vitest" in lower else "jest" if "jest" in lower else "node_test"
        return _result(log_text, check, log_url, environment, match, "test", tool, "npm test")
    return _unknown(
        log_text,
        "javascript_typescript",
        check,
        log_url,
        environment,
        "javascript_failure_not_classified",
    )


def _go_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> FailureVectorAdapterResult:
    lower = log_text.lower()
    location = GO_LOCATION.search(log_text)
    if "go vet" in lower and location:
        return _result(
            log_text, check, log_url, environment, location, "lint", "go_vet", "go vet ./..."
        )
    test = GO_TEST.search(log_text)
    if test or "go test" in lower or "--- fail:" in lower:
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location or test,
            "test",
            "go_test",
            "go test ./...",
        )
    if location:
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location,
            "unknown",
            "go_toolchain",
            "go test ./...",
            ("go_failure_class_not_proven",),
        )
    return _unknown(log_text, "go", check, log_url, environment, "go_failure_not_classified")


def _java_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> FailureVectorAdapterResult:
    lower = log_text.lower()
    location = JAVA_LOCATION.search(log_text)
    if _looks_like_maven_test(lower):
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location,
            "test",
            "maven_test",
            "mvn test",
            ecosystem="java",
        )
    if _looks_like_gradle_test(lower):
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location,
            "test",
            "gradle_test",
            "./gradlew test",
            ecosystem="java",
        )
    if location:
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location,
            "unknown",
            "java_toolchain",
            "mvn test",
            ("java_failure_class_not_proven",),
            ecosystem="java",
        )
    return _unknown(log_text, "java", check, log_url, environment, "java_failure_not_classified")


def _rust_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> FailureVectorAdapterResult:
    lower = log_text.lower()
    location = RUST_LOCATION.search(log_text)
    if _looks_like_cargo_clippy(lower):
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location,
            "lint",
            "cargo_clippy",
            "cargo clippy --all-targets --all-features",
            ecosystem="rust",
        )
    test = RUST_TEST.search(log_text)
    if test or _looks_like_cargo_test(lower):
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location or test,
            "test",
            "cargo_test",
            "cargo test",
            ecosystem="rust",
        )
    if location:
        return _result(
            log_text,
            check,
            log_url,
            environment,
            location,
            "unknown",
            "cargo_toolchain",
            "cargo test",
            ("rust_failure_class_not_proven",),
            ecosystem="rust",
        )
    return _unknown(log_text, "rust", check, log_url, environment, "rust_failure_not_classified")


def _dotnet_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> FailureVectorAdapterResult:
    if not _looks_like_dotnet(log_text):
        return _unknown(
            log_text,
            "dotnet",
            check,
            log_url,
            environment,
            "dotnet_failure_not_classified",
        )

    location = DOTNET_LOCATION.search(log_text)
    test = DOTNET_XUNIT_TEST.search(log_text) or DOTNET_TEST.search(log_text)
    command_match = DOTNET_TEST_COMMAND.search(log_text)
    command = command_match.group("command").strip() if command_match else "dotnet test"
    project_match = DOTNET_PROJECT.search(command)
    project = _normalize_dotnet_path(project_match.group("project")) if project_match else ""
    path = _normalize_dotnet_path(location.group("path")) if location else ""
    test_name = test.group("check").strip() if test else ""
    first_line = test.group(0).strip() if test else _dotnet_first_failure_line(log_text)
    actual_failure = _dotnet_failure_detail(log_text) or first_line
    repro = f"dotnet test {project}" if project else "dotnet test"

    uncertainty = tuple(
        reason
        for present, reason in (
            (bool(project), "dotnet_test_project_not_observed"),
            (bool(test_name), "dotnet_test_name_not_observed"),
            (bool(path), "dotnet_source_path_not_observed"),
        )
        if not present
    )
    vector = FailureVector(
        check=check,
        command=command,
        exit_code=_exit_code(log_text),
        failure_class="test",
        risk="medium",
        scope="unknown",
        reproducible_locally="not_run",
        safe_fix_candidate=False,
        first_failing_line=first_line,
        affected_files=(path,) if path else (),
        log_url=log_url,
        local_repro_command=repro,
        environment=environment,
        headline_signal=f"{check}: test",
        actual_failure=actual_failure,
        failure_type="test",
        failing_command=command,
        failing_test_or_check=test_name or check,
        owner_hint=path or project or check,
        safe_fix_allowed=False,
    )
    return FailureVectorAdapterResult(
        vector=vector,
        ecosystem="dotnet",
        tool="dotnet_test",
        confidence="medium" if uncertainty else "high",
        uncertainty=uncertainty,
    )


def _result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
    match: re.Match[str] | None,
    failure_class: str,
    tool: str,
    repro: str,
    uncertainty: tuple[str, ...] = (),
    ecosystem: str | None = None,
) -> FailureVectorAdapterResult:
    path = match.groupdict().get("path", "") if match else ""
    detail = match.groupdict().get("check", "") if match else ""
    line = match.group(0).strip() if match else _first_failure_line(log_text)
    command_match = COMMAND.search(log_text)
    exit_match = EXIT_CODE.search(log_text)
    command = command_match.group("command").strip() if command_match else repro
    vector = FailureVector(
        check=check,
        command=command,
        exit_code=int(exit_match.group("code")) if exit_match else None,
        failure_class=failure_class,
        risk="high" if failure_class == "unknown" else "medium",
        scope="unknown",
        reproducible_locally="not_run",
        safe_fix_candidate=False,
        first_failing_line=line,
        affected_files=(path,) if path else (),
        log_url=log_url,
        local_repro_command=repro,
        environment=environment,
        headline_signal=f"{check}: {failure_class}",
        actual_failure=line,
        failure_type=failure_class,
        failing_command=command,
        failing_test_or_check=detail or check,
        owner_hint=path or check,
        safe_fix_allowed=False,
    )
    inferred_ecosystem = "go" if tool.startswith("go_") else "javascript_typescript"
    return FailureVectorAdapterResult(
        vector=vector,
        ecosystem=ecosystem or inferred_ecosystem,
        tool=tool,
        confidence="medium" if uncertainty else "high",
        uncertainty=uncertainty,
    )


def _unknown(
    log_text: str,
    ecosystem: str,
    check: str,
    log_url: str | None,
    environment: str,
    uncertainty: str,
) -> FailureVectorAdapterResult:
    vector = extract_failure_vector(
        log_text,
        check=check,
        log_url=log_url,
        environment=environment,
    )
    return FailureVectorAdapterResult(vector, ecosystem, "unknown", "low", (uncertainty,))


def _looks_like_java(log_text: str) -> bool:
    lower = log_text.lower()
    return (
        JAVA_LOCATION.search(log_text) is not None
        or _looks_like_maven_test(lower)
        or _looks_like_gradle_test(lower)
    )


def _looks_like_maven_test(lower: str) -> bool:
    return any(
        token in lower
        for token in (
            "run mvn test",
            "$ mvn test",
            "maven-surefire-plugin",
            "surefire-reports",
            "tests run:",
        )
    )


def _looks_like_gradle_test(lower: str) -> bool:
    return any(
        token in lower
        for token in (
            "run ./gradlew test",
            "$ ./gradlew test",
            "> task :test failed",
            "gradle test executor",
        )
    )


def _looks_like_rust(log_text: str) -> bool:
    lower = log_text.lower()
    return (
        RUST_LOCATION.search(log_text) is not None
        or RUST_TEST.search(log_text) is not None
        or _looks_like_cargo_test(lower)
        or _looks_like_cargo_clippy(lower)
    )


def _looks_like_cargo_test(lower: str) -> bool:
    return any(
        token in lower
        for token in (
            "run cargo test",
            "$ cargo test",
            "test result: failed",
            "running unittests",
            "panicked at",
        )
    )


def _looks_like_cargo_clippy(lower: str) -> bool:
    return any(
        token in lower
        for token in (
            "run cargo clippy",
            "$ cargo clippy",
            "cargo clippy --all-targets --all-features",
            "clippy::",
        )
    )


def _looks_like_dotnet(log_text: str) -> bool:
    lower = log_text.lower()
    return (
        DOTNET_TEST_COMMAND.search(log_text) is not None
        or DOTNET_TEST.search(log_text) is not None
        or DOTNET_XUNIT_TEST.search(log_text) is not None
        or any(
            token in lower
            for token in (
                "test run failed.",
                "failed!  - failed:",
                "microsoft.testplatform",
                "vstest",
                "[xunit.net",
            )
        )
    )


def _normalize_dotnet_path(path: str) -> str:
    return path.replace("\\", "/")


def _dotnet_failure_detail(log_text: str) -> str:
    lines = [line.strip() for line in log_text.splitlines()]
    after_error_message = False
    for line in lines:
        lower = line.lower()
        if lower == "error message:":
            after_error_message = True
            continue
        if after_error_message:
            if not line:
                continue
            if lower in {"stack trace:", "standard output messages:"}:
                break
            return line

    for line in lines:
        lower = line.lower()
        if not line or "process completed with exit code" in lower:
            continue
        if any(
            token in lower
            for token in (
                "assert.",
                "assertion",
                "expected:",
                "actual:",
                "exception",
            )
        ):
            return line
    return ""


def _exit_code(log_text: str) -> int | None:
    match = EXIT_CODE.search(log_text)
    return int(match.group("code")) if match else None


def _dotnet_first_failure_line(log_text: str) -> str:
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if lower.startswith("failed ") or lower in {"test run failed.", "test run failed"}:
            return line
        if lower.startswith("failed!  - failed:"):
            return line
    return lines[0] if lines else "unknown failure"


def _first_failure_line(log_text: str) -> str:
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    for line in lines:
        if any(token in line for token in ("FAIL", "AssertionError", "panic:")):
            return line
    return lines[0] if lines else "unknown failure"
