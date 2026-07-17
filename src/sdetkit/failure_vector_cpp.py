from __future__ import annotations

import re
from dataclasses import dataclass

from sdetkit.failure_vector import FailureVector

_EXIT_CODE_RE = re.compile(r"Process completed with exit code (?P<code>\d+)")
_COMMAND_RE = re.compile(
    r"^(?:Run|\$)\s+(?P<command>(?:cmake|ctest|meson|ninja|"
    r"g\+\+|gcc|clang\+\+|clang|cl(?:\.exe)?|link(?:\.exe)?)\b.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_GNU_DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>[^\n:]+?\.(?:cxx|cpp|cc|c|hxx|hpp|hh|h)):"
    r"(?P<line>\d+):(?P<column>\d+):\s*(?:fatal\s+)?error:\s*(?P<message>.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_MSVC_DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?\.(?:cxx|cpp|cc|c|hxx|hpp|hh|h))"
    r"\((?P<line>\d+)(?:,(?P<column>\d+))?\):\s*"
    r"(?:fatal\s+)?error\s+(?P<code>C\d+):\s*(?P<message>.+?)"
    r"(?:\s+\[[^\]]+\])?$",
    re.IGNORECASE | re.MULTILINE,
)
_MSVC_LINK_RE = re.compile(
    r"^(?P<object>[^\n:]+\.obj)\s*:\s*(?:fatal\s+)?error\s+"
    r"(?P<code>LNK\d+):\s*(?P<message>.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_GNU_LINK_RE = re.compile(
    r"^(?P<line>.*(?:undefined reference to|multiple definition of).*)$",
    re.IGNORECASE | re.MULTILINE,
)
_GNU_LINK_OBJECT_RE = re.compile(
    r"(?P<object>(?:CMakeFiles/[^\s:]+\.dir/)?[^\s:]+\.(?:cxx|cpp|cc|c)\.o)"
)
_GTEST_PATH_RE = re.compile(
    r"^(?P<path>[^\n:]+?\.(?:cxx|cpp|cc|c|hxx|hpp|hh|h)):\d+:\s+Failure$",
    re.IGNORECASE | re.MULTILINE,
)
_GTEST_FAILED_RE = re.compile(
    r"^\[\s*FAILED\s*\]\s+(?P<check>[^\n(]+?)(?:\s+\(\d+\s*ms\))?$",
    re.MULTILINE,
)
_CATCH2_PATH_RE = re.compile(
    r"^(?P<path>[^\n:]+?\.(?:cxx|cpp|cc|c|hxx|hpp|hh|h)):\d+:\s+FAILED:$",
    re.IGNORECASE | re.MULTILINE,
)
_CTEST_FAILED_RE = re.compile(
    r"^\s*\d+/\d+\s+Test\s+#\d+:\s+(?P<check>.+?)\s+\.{2,}\*\*\*Failed",
    re.IGNORECASE | re.MULTILINE,
)
_CTEST_SUMMARY_RE = re.compile(
    r"^\s*\d+\s+-\s+(?P<check>.+?)\s+\(Failed\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_PATH_TOKEN_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?[\w./\\-]+\.(?:cxx|cpp|cc|c|hxx|hpp|hh|h))",
    re.IGNORECASE,
)

_IGNORED_PATH_PARTS = {
    ".cache",
    ".git",
    "_build",
    "build",
    "cmakefiles",
    "deps",
    "external",
    "extern",
    "node_modules",
    "out",
    "subprojects",
    "third-party",
    "third_party",
    "vendor",
    "vendors",
    "vcpkg_installed",
}


@dataclass(frozen=True)
class CppFailureVectorResult:
    vector: FailureVector
    tool: str
    confidence: str
    uncertainty: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = self.vector.to_dict()
        payload["adapter"] = {
            "ecosystem": "cpp",
            "tool": self.tool,
            "confidence": self.confidence,
            "uncertainty": list(self.uncertainty),
            "target_code_execution": False,
        }
        return payload


def looks_like_cpp_failure(log_text: str) -> bool:
    lower = log_text.lower()
    return bool(
        _MSVC_DIAGNOSTIC_RE.search(log_text)
        or _GNU_DIAGNOSTIC_RE.search(log_text)
        or _MSVC_LINK_RE.search(log_text)
        or _GNU_LINK_RE.search(log_text)
        or _GTEST_PATH_RE.search(log_text)
        or _CATCH2_PATH_RE.search(log_text)
        or _CTEST_FAILED_RE.search(log_text)
        or any(
            token in lower
            for token in (
                "ctest --",
                "ctest test project",
                "the following tests failed:",
                "collect2: error: ld returned",
                "link : fatal error lnk",
            )
        )
    )


def extract_cpp_failure_vector(
    log_text: str,
    *,
    check: str = "unknown",
    log_url: str | None = None,
    environment: str = "unknown",
) -> CppFailureVectorResult:
    """Normalize saved C++ diagnostics without executing target tools."""

    signal_kinds = _signal_kinds(log_text)
    if len(signal_kinds) > 1:
        return _unknown_result(
            log_text,
            check=check,
            log_url=log_url,
            environment=environment,
            uncertainty=("mixed_cpp_failure_signals",),
            affected_files=_affected_paths(log_text),
            tool="mixed_cpp_toolchain",
        )
    if "test" in signal_kinds:
        return _test_result(log_text, check, log_url, environment)
    if "link" in signal_kinds:
        return _link_result(log_text, check, log_url, environment)
    if "compile" in signal_kinds:
        return _compile_result(log_text, check, log_url, environment)
    return _unknown_result(
        log_text,
        check=check,
        log_url=log_url,
        environment=environment,
        uncertainty=("cpp_failure_not_classified",),
        affected_files=(),
        tool="unknown",
    )


def _signal_kinds(log_text: str) -> set[str]:
    kinds: set[str] = set()
    if _MSVC_DIAGNOSTIC_RE.search(log_text) or _GNU_DIAGNOSTIC_RE.search(log_text):
        kinds.add("compile")
    if _MSVC_LINK_RE.search(log_text) or _GNU_LINK_RE.search(log_text):
        kinds.add("link")
    if _looks_like_test_failure(log_text):
        kinds.add("test")
    return kinds


def _looks_like_test_failure(log_text: str) -> bool:
    lower = log_text.lower()
    return bool(
        _GTEST_PATH_RE.search(log_text)
        or _CATCH2_PATH_RE.search(log_text)
        or _CTEST_FAILED_RE.search(log_text)
        or _CTEST_SUMMARY_RE.search(log_text)
        or "the following tests failed:" in lower
    )


def _compile_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> CppFailureVectorResult:
    msvc = _MSVC_DIAGNOSTIC_RE.search(log_text)
    gnu = _GNU_DIAGNOSTIC_RE.search(log_text)
    match = msvc or gnu
    assert match is not None

    path = _normalize_owned_path(match.group("path"))
    paths = _affected_paths(log_text)
    if path and path not in paths:
        paths = (path, *paths)
    command = _explicit_command(log_text)
    uncertainty: list[str] = []
    if not command:
        uncertainty.append("cpp_repro_command_not_observed")
    if not paths:
        uncertainty.append("cpp_source_path_not_observed")

    if msvc is not None:
        tool = "msvc"
        failure_check = msvc.group("code")
        message = msvc.group("message").strip()
        first_line = msvc.group(0).strip()
    else:
        lower = log_text.lower()
        if "clang++" in lower or "clang " in lower:
            tool = "clang"
        elif "g++" in lower or "gcc " in lower:
            tool = "gcc"
        else:
            tool = "gcc_clang"
            uncertainty.append("cpp_compiler_identity_ambiguous")
        failure_check = "compiler_error"
        message = gnu.group("message").strip() if gnu is not None else "compiler error"
        first_line = gnu.group(0).strip() if gnu is not None else "compiler error"

    return _known_result(
        check=check,
        command=command,
        exit_code=_exit_code(log_text),
        failure_class="compile",
        first_line=first_line,
        actual_failure=message,
        affected_files=paths,
        log_url=log_url,
        environment=environment,
        failing_test_or_check=failure_check,
        owner_hint=paths[0] if paths else check,
        tool=tool,
        uncertainty=tuple(uncertainty),
    )


def _link_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> CppFailureVectorResult:
    msvc = _MSVC_LINK_RE.search(log_text)
    gnu = _GNU_LINK_RE.search(log_text)
    command = _explicit_command(log_text)
    paths = _affected_paths(log_text)
    uncertainty: list[str] = []
    if not command:
        uncertainty.append("cpp_repro_command_not_observed")
    if not paths:
        uncertainty.append("cpp_link_source_path_not_proven")

    if msvc is not None:
        tool = "msvc_linker"
        first_line = msvc.group(0).strip()
        actual_failure = msvc.group("message").strip()
        failure_check = msvc.group("code")
        object_hint = msvc.group("object").strip().replace("\\", "/")
    else:
        tool = "gnu_linker"
        first_line = gnu.group("line").strip() if gnu is not None else "linker failure"
        actual_failure = first_line
        failure_check = "undefined_reference"
        object_match = _GNU_LINK_OBJECT_RE.search(log_text)
        object_hint = object_match.group("object") if object_match else ""

    return _known_result(
        check=check,
        command=command,
        exit_code=_exit_code(log_text),
        failure_class="link",
        first_line=first_line,
        actual_failure=actual_failure,
        affected_files=paths,
        log_url=log_url,
        environment=environment,
        failing_test_or_check=failure_check,
        owner_hint=paths[0] if paths else object_hint or check,
        tool=tool,
        uncertainty=tuple(uncertainty),
    )


def _test_result(
    log_text: str,
    check: str,
    log_url: str | None,
    environment: str,
) -> CppFailureVectorResult:
    lower = log_text.lower()
    command = _explicit_command(log_text)
    paths = _affected_paths(log_text)
    gtest = _GTEST_FAILED_RE.search(log_text)
    catch2 = _CATCH2_PATH_RE.search(log_text)
    ctest = _CTEST_FAILED_RE.search(log_text) or _CTEST_SUMMARY_RE.search(log_text)

    if gtest is not None:
        tool = "ctest_google_test" if "ctest" in lower else "google_test"
        test_name = gtest.group("check").strip()
        path_match = _GTEST_PATH_RE.search(log_text)
        first_line = path_match.group(0).strip() if path_match else gtest.group(0).strip()
    elif catch2 is not None or "test cases:" in lower:
        tool = "ctest_catch2" if "ctest" in lower else "catch2"
        test_name = ctest.group("check").strip() if ctest is not None else check
        first_line = (
            catch2.group(0).strip() if catch2 is not None else _first_failure_line(log_text)
        )
    else:
        tool = "ctest"
        test_name = ctest.group("check").strip() if ctest is not None else check
        first_line = ctest.group(0).strip() if ctest is not None else _first_failure_line(log_text)

    uncertainty: list[str] = []
    if not command:
        uncertainty.append("cpp_repro_command_not_observed")
    if not paths:
        uncertainty.append("cpp_test_source_path_not_observed")
    if test_name == check:
        uncertainty.append("cpp_test_identity_not_observed")

    return _known_result(
        check=check,
        command=command,
        exit_code=_exit_code(log_text),
        failure_class="test",
        first_line=first_line,
        actual_failure=_test_failure_detail(log_text, first_line),
        affected_files=paths,
        log_url=log_url,
        environment=environment,
        failing_test_or_check=test_name,
        owner_hint=paths[0] if paths else test_name,
        tool=tool,
        uncertainty=tuple(uncertainty),
    )


def _known_result(
    *,
    check: str,
    command: str,
    exit_code: int | None,
    failure_class: str,
    first_line: str,
    actual_failure: str,
    affected_files: tuple[str, ...],
    log_url: str | None,
    environment: str,
    failing_test_or_check: str,
    owner_hint: str,
    tool: str,
    uncertainty: tuple[str, ...],
) -> CppFailureVectorResult:
    vector = FailureVector(
        check=check,
        command=command or "unknown",
        exit_code=exit_code,
        failure_class=failure_class,
        risk="medium",
        scope="unknown",
        reproducible_locally="not_run",
        safe_fix_candidate=False,
        first_failing_line=first_line,
        affected_files=affected_files,
        log_url=log_url,
        local_repro_command=command or None,
        environment=environment,
        headline_signal=f"{check}: {failure_class}",
        actual_failure=actual_failure,
        failure_type=failure_class,
        failing_command=command or "unknown",
        failing_test_or_check=failing_test_or_check,
        owner_hint=owner_hint,
        safe_fix_allowed=False,
    )
    return CppFailureVectorResult(
        vector=vector,
        tool=tool,
        confidence="medium" if uncertainty else "high",
        uncertainty=uncertainty,
    )


def _unknown_result(
    log_text: str,
    *,
    check: str,
    log_url: str | None,
    environment: str,
    uncertainty: tuple[str, ...],
    affected_files: tuple[str, ...],
    tool: str,
) -> CppFailureVectorResult:
    command = _explicit_command(log_text)
    first_line = _first_failure_line(log_text)
    vector = FailureVector(
        check=check,
        command=command or "unknown",
        exit_code=_exit_code(log_text),
        failure_class="unknown",
        risk="high",
        scope="unknown",
        reproducible_locally="not_run",
        safe_fix_candidate=False,
        first_failing_line=first_line,
        affected_files=affected_files,
        log_url=log_url,
        local_repro_command=command or None,
        environment=environment,
        headline_signal=f"{check}: unknown",
        actual_failure=first_line,
        failure_type="unknown",
        failing_command=command or "unknown",
        failing_test_or_check=check,
        owner_hint=affected_files[0] if affected_files else check,
        safe_fix_allowed=False,
    )
    return CppFailureVectorResult(vector, tool, "low", uncertainty)


def _explicit_command(log_text: str) -> str:
    match = _COMMAND_RE.search(log_text)
    return match.group("command").strip() if match else ""


def _exit_code(log_text: str) -> int | None:
    match = _EXIT_CODE_RE.search(log_text)
    return int(match.group("code")) if match else None


def _affected_paths(log_text: str) -> tuple[str, ...]:
    paths: list[str] = []
    for match in _PATH_TOKEN_RE.finditer(log_text):
        path = _normalize_owned_path(match.group("path"))
        if path and path not in paths:
            paths.append(path)
    for match in _GNU_LINK_OBJECT_RE.finditer(log_text):
        path = _source_from_object(match.group("object"))
        if path and path not in paths:
            paths.append(path)
    specific_basenames = {path.rsplit("/", 1)[-1] for path in paths if "/" in path}
    return tuple(path for path in paths if "/" in path or path not in specific_basenames)


def _normalize_owned_path(raw_path: str) -> str:
    path = raw_path.strip().strip("\"'").replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    lower_parts = [part.lower() for part in path.split("/") if part]
    if any(part in _IGNORED_PATH_PARTS for part in lower_parts):
        return ""
    if re.match(r"^[A-Za-z]:/", path) or path.startswith("/"):
        for marker in ("/src/", "/tests/", "/include/"):
            if marker in path:
                return marker.strip("/") + "/" + path.split(marker, 1)[1]
        return ""
    return path


def _source_from_object(raw_object: str) -> str:
    normalized = raw_object.replace("\\", "/")
    if ".dir/" in normalized:
        normalized = normalized.split(".dir/", 1)[1]
    if normalized.endswith(".o"):
        normalized = normalized[:-2]
    return _normalize_owned_path(normalized)


def _test_failure_detail(log_text: str, first_line: str) -> str:
    lines = [line.strip() for line in log_text.splitlines()]
    try:
        start = lines.index(first_line.strip())
    except ValueError:
        start = 0
    for line in lines[start + 1 :]:
        if not line:
            continue
        if line.startswith(("[  FAILED  ]", "The following tests FAILED:")):
            continue
        if "Process completed with exit code" in line:
            continue
        return line
    return first_line


def _first_failure_line(log_text: str) -> str:
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if any(
            token in lower
            for token in (
                "error ",
                " error:",
                "failed:",
                "***failed",
                "undefined reference",
                "failure",
            )
        ):
            return line
    return lines[0] if lines else "unknown failure"
