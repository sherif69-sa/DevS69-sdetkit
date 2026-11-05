"""Java tests for `sdetkit verify change`: Maven (Surefire) and Gradle.

Test ids are `<class>::<method>`, the class by its binary name as the JUnit reports give it
(`com.example.CartTest`, a nested class `com.example.CartTest$Empty`), so the change's run, the
base's run and what the test files say compare by one name. A project whose tests do not
compile is reported as `::<project>` (Maven's artifactId, Gradle's project path, `.` for the
root), and each test class the run asked for there as `::<class>`.

Test files are read with a small scanner, as for Go: strings, characters and comments are
blanked, then each method annotated `@Test` (or a JUnit 5 test-like annotation) is followed by
its braces.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from sdetkit.go_tests import write_junit

JsonObject = dict[str, Any]

RUNNERS = ("maven", "gradle")
# Surefire's default includes; Gradle runs every test class, and these are their usual names.
_TEST_CLASS_NAME = re.compile(r"^(?:Test\w*|\w*(?:Test|Tests|TestCase|IT))\.java$")
_BUILD_DIRS = frozenset({"target", "build", ".gradle", "node_modules", ".git"})
_TEST_ANNOTATION = re.compile(
    r"@(?:org\.junit\.(?:jupiter\.(?:api|params)\.)?)?"
    r"(Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b(\s*\([^()]*\))?"
)
_METHOD = re.compile(
    r"\b([A-Za-z_$][\w$]*)\s*\((?:[^()]|\([^()]*\))*\)\s*(?:throws\s+[\w$.,\s]+)?\{"
)
# Statements that look like a method declaration to `_METHOD`.
_KEYWORDS = frozenset({"if", "for", "while", "switch", "catch", "synchronized", "try"})
_CLASS = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)[^{;]*\{")
_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
# JUnit, AssertJ, Hamcrest and Truth assertions, fail(), Mockito's verify() and Java's assert.
_ASSERTION = re.compile(r"(?<![\w$])(?:assert\w*|fail|verify)\s*\(|(?<![\w$.])assert\s")
_ALWAYS_TRUE = re.compile(r"assertTrue\s*\(\s*true\s*\)|assertFalse\s*\(\s*false\s*\)")
_SKIP_ANNOTATION = re.compile(
    r"@(?:\w+\.)*(?:Disabled|Ignore|DisabledIf\w*|EnabledIf\w*|DisabledOn\w*|EnabledOn\w*)\b"
)
_ASSUMPTION = re.compile(r"(?<![\w$])assume\w*\s*\(|(?<![\w$])abort\s*\(")
_EXPECTED = re.compile(r"\bexpected\s*=")
# Stack frames of the test frameworks and the JDK, not of the code under test.
_FRAMEWORK_FRAME = re.compile(
    r"^\s*at (?:org\.junit\.|junit\.|org\.opentest4j\.|org\.apache\.maven\.|org\.gradle\."
    r"|worker\.org\.gradle\.|java\.base/|jdk\.internal\.|sun\.reflect\.|java\.lang\.reflect\."
    r"|java\.util\.|org\.assertj\.core\.(?:internal|error)\.|org\.hamcrest\.|com\.sun\.proxy\.)"
)


def is_java_test_file(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return bool(_TEST_CLASS_NAME.match(parts[-1] if parts else "")) and not (
        _BUILD_DIRS & set(parts[:-1])
    )


def is_java_test_side(path: str) -> bool:
    """A file of the test source set (`src/test/...`): test classes, helpers and resources."""

    return "/src/test/" in f"/{path}"


def is_java_build_file(path: str) -> bool:
    return PurePosixPath(path).name in {"pom.xml", "build.gradle", "build.gradle.kts"}


def detect_java_runner(repo_root: Path) -> str:
    if (repo_root / "pom.xml").is_file():
        return "maven"
    names = ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
    return "gradle" if any((repo_root / name).is_file() for name in names) else ""


# --- reading test files -----------------------------------------------------------------


def mask(source: str) -> str:
    """`source` with the inside of every string, text block, character and comment blanked."""

    out = list(source)
    i, n = 0, len(source)

    def blank(start: int, end: int) -> None:
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        char = source[i]
        if source.startswith("//", i):
            end = source.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = n if end < 0 else end + 2
            blank(i, end)
            i = end
        elif source.startswith('"""', i):
            end = source.find('"""', i + 3)
            end = n if end < 0 else end
            blank(i + 3, end)
            i = end + 3
        elif char in "\"'":
            k = i + 1
            while k < n and source[k] != char and source[k] != "\n":
                k += 2 if source[k] == "\\" else 1
            blank(i + 1, k)
            i = k + 1
        else:
            i += 1
    return "".join(out)


def _closing(masked: str, open_index: int) -> int:
    depth = 0
    for k in range(open_index, len(masked)):
        if masked[k] == "{":
            depth += 1
        elif masked[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _declaration_start(masked: str, index: int) -> int:
    """Where the annotations and modifiers before `index` begin: after the previous member."""

    return max(masked.rfind(char, 0, index) for char in ";{}") + 1


def _classes(masked: str) -> list[tuple[str, int, int, int]]:
    """(name, declaration start, body open, body close) for every class in a file."""

    found: list[tuple[str, int, int, int]] = []
    for match in _CLASS.finditer(masked):
        close = _closing(masked, match.end() - 1)
        if close > 0:
            found.append(
                (match.group(1), _declaration_start(masked, match.start()), match.end() - 1, close)
            )
    return found


def _methods(source: str) -> tuple[list[JsonObject], dict[str, str]]:
    """The test methods of a file, and the bodies of its other methods by name."""

    masked = mask(source)
    classes = _classes(masked)
    tests: list[JsonObject] = []
    seen: set[int] = set()
    for annotation in _TEST_ANNOTATION.finditer(masked):
        method = _METHOD.search(masked, annotation.end())
        if not method or method.start() in seen:
            continue
        seen.add(method.start())
        close = _closing(masked, method.end() - 1)
        if close < 0:
            continue
        start = _declaration_start(masked, annotation.start())
        inside = [c for c in classes if c[2] < method.start() < c[3]]
        class_skips = sum(len(_SKIP_ANNOTATION.findall(masked, c[1], c[2])) for c in inside)
        nested = [name for name, *_ in inside[1:]]
        tests.append(
            {
                "name": ".".join([*nested, method.group(1)]),
                "masked": masked[method.end() - 1 : close + 1],
                "header": masked[start : method.start()],
                "class_skips": class_skips,
                # The signature after the name and the body: what the test is, not what it is called.
                "text": source[method.end(1) : close + 1],
            }
        )
    helpers: dict[str, str] = {}
    for match in _METHOD.finditer(masked):
        name = match.group(1)
        if match.start() in seen or name in helpers or name in _KEYWORDS:
            continue
        close = _closing(masked, match.end() - 1)
        if close > 0:
            helpers[name] = masked[match.end() - 1 : close + 1]
    return tests, helpers


def _assertions(masked_body: str) -> int:
    return len(_ASSERTION.findall(masked_body)) - len(_ALWAYS_TRUE.findall(masked_body))


def java_test_facts(source: str) -> dict[str, JsonObject]:
    """{test name: {"assertions": n, "skips": n}} for every test method in a file; a method of
    a nested class is named `Inner.method`."""

    tests, helpers = _methods(source)
    helper_counts: dict[str, int] = {}

    def with_helpers(body: str, seen: frozenset[str]) -> int:
        count = _assertions(body)
        for name, helper_body in helpers.items():
            if name in seen or not re.search(rf"(?<![\w$.]){re.escape(name)}\s*\(", body):
                continue
            if name not in helper_counts:
                helper_counts[name] = with_helpers(helper_body, seen | {name})
            count += helper_counts[name]
        return count

    return {
        test["name"]: {
            # JUnit 4's @Test(expected = X.class) checks that X is thrown.
            "assertions": with_helpers(test["masked"], frozenset())
            + len(_EXPECTED.findall(test["header"])),
            "skips": len(_SKIP_ANNOTATION.findall(test["header"]))
            + test["class_skips"]
            + len(_ASSUMPTION.findall(test["masked"])),
        }
        for test in tests
    }


def java_test_fingerprints(source: str) -> dict[str, str]:
    tests, _ = _methods(source)
    return {
        test["name"]: hashlib.sha256(" ".join(test["text"].split()).encode("utf-8")).hexdigest()
        for test in tests
    }


def java_class_name(source: str, path: str) -> str:
    """The binary name of a test file's top-level class: its package and file name."""

    match = _PACKAGE.search(mask(source))
    stem = PurePosixPath(path).stem
    return f"{match.group(1)}.{stem}" if match else stem


def java_test_id(source: str, path: str, test: str) -> str:
    """The JUnit id of a test `java_test_facts` names (`Inner.method` for a nested class)."""

    *nested, method = test.split(".")
    return "$".join([java_class_name(source, path), *nested]) + f"::{method}"


# --- build configuration ----------------------------------------------------------------

_POM_PLUGINS = frozenset({"maven-surefire-plugin", "maven-failsafe-plugin", "jacoco-maven-plugin"})
_POM_PROPERTY = re.compile(r"skip|test|surefire|failsafe|jacoco", re.I)
_GRADLE_BLOCK = re.compile(
    r"^[ \t]*(?:tasks\s*\.\s*)?"
    r"(?:test|withType\s*(?:<\s*Test\s*>|\(\s*Test(?:::class(?:\.java)?)?\s*\))"
    r"|named\s*(?:<\s*Test\s*>)?\s*\(\s*[\"']test[\"']\s*\)|jacoco\w*)"
    r"\s*(?:\.\s*configure\s*)?\{",
    re.M,
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def java_test_config(path: str, text: str | None) -> list[str]:
    """What a build file says about running the tests and their coverage: the Surefire,
    Failsafe and JaCoCo plugins and test properties of a pom.xml, the `test`, `withType(Test)`
    and `jacoco*` blocks of a Gradle build script. Two versions compare by this."""

    if not text:
        return []
    if PurePosixPath(path).name == "pom.xml":
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return [text]
        found: list[str] = []
        for element in root.iter():
            name = _local(element.tag) if isinstance(element.tag, str) else ""
            if name == "plugin":
                artifact = next(
                    (c.text or "" for c in element if _local(str(c.tag)) == "artifactId"), ""
                )
                if artifact.strip() in _POM_PLUGINS:
                    found.append(" ".join(ET.tostring(element, encoding="unicode").split()))
            elif name == "properties":
                found += [
                    f"{_local(str(c.tag))}={(c.text or '').strip()}"
                    for c in element
                    if _POM_PROPERTY.search(_local(str(c.tag)))
                ]
        return found
    masked = mask(text)
    blocks: list[str] = []
    for match in _GRADLE_BLOCK.finditer(masked):
        close = _closing(masked, match.end() - 1)
        if close > 0:
            blocks.append(" ".join(text[match.start() : close + 1].split()))
    return blocks


# --- running the tests ------------------------------------------------------------------


def _report_files(workspace: Path, runner: str) -> list[Path]:
    pattern = "surefire-reports" if runner == "maven" else "test-results"
    files: list[Path] = []
    for path in workspace.rglob("TEST-*.xml"):
        parts = path.relative_to(workspace).parts
        if pattern in parts and not {"node_modules", ".git"} & set(parts):
            files.append(path)
    return sorted(files)


def _clean_stack(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not _FRAMEWORK_FRAME.match(line))


def read_java_reports(
    paths: Sequence[Path], names: Mapping[tuple[str, str], str] | None = None
) -> tuple[dict[str, str], dict[str, str]]:
    """({test id: passed | failed | skipped}, {test id: why it failed}) from JUnit XML reports.
    `names` gives the id of a (class, report name) pair where the report's name is not one."""

    outcomes: dict[str, str] = {}
    failures: dict[str, str] = {}
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for case in root.iter("testcase"):
            classname, raw = case.get("classname") or "", case.get("name") or ""
            test_id = (names or {}).get((classname, raw)) or f"{classname}::{_method(raw)}"
            problem = next((c for c in case if c.tag in {"failure", "error"}), None)
            if problem is not None:
                outcomes[test_id] = "failed"
                why = (problem.text or "").strip() or problem.get("message") or ""
                failures[test_id] = _clean_stack(why).strip()
            elif case.find("skipped") is not None:
                outcomes.setdefault(test_id, "skipped")
            else:
                outcomes.setdefault(test_id, "passed")
    return outcomes, failures


def _method(name: str) -> str:
    # Gradle names JUnit 5 tests `method()`.
    return name[:-2] if name.endswith("()") else name


# Gradle's reports name a parameterized or repeated test's runs by their display names alone
# (`[1] 2, 3`), without the method. This init script prints each test's own name with its
# display name, so the ids are the ones Surefire gives: `com.example.CartTest::adds(int)[1]`.
GRADLE_INIT_SCRIPT = r"""allprojects {
    tasks.withType(Test).configureEach {
        afterTest { test, result ->
            println "##sdetkit-test\t${result.resultType}\t${test.className}\t${test.displayName}\t${test.name}"
        }
    }
}
"""
_GRADLE_EVENT = re.compile(r"^##sdetkit-test\t(\w+)\t([^\t]*)\t([^\t]*)\t(.*)$", re.M)
_GRADLE_RESULTS = {"SUCCESS": "passed", "FAILURE": "failed", "SKIPPED": "skipped"}


def read_gradle_events(output: str) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """({test id: outcome}, {(class, report name): test id}) from what the init script printed;
    a report name two tests share maps to neither."""

    outcomes: dict[str, str] = {}
    names: dict[tuple[str, str], str] = {}
    shared: set[tuple[str, str]] = set()
    for result, classname, display, name in _GRADLE_EVENT.findall(output):
        test_id = f"{classname}::{_method(name)}"
        outcomes[test_id] = _GRADLE_RESULTS.get(result, "skipped")
        key = (classname, display)
        if key in names and names[key] != test_id:
            shared.add(key)
        names[key] = test_id
    return outcomes, {key: test_id for key, test_id in names.items() if key not in shared}


# JaCoCo, from the build tool's own repository: the project need not configure it. Its report
# lists every class of the build, loaded by a test or not.
JACOCO_VERSION = "0.8.16"
JACOCO_PLUGIN = f"org.jacoco:jacoco-maven-plugin:{JACOCO_VERSION}"
GRADLE_JACOCO_SCRIPT = f"""
allprojects {{
    pluginManager.withPlugin("java") {{
        apply plugin: "jacoco"
        jacoco {{ toolVersion = "{JACOCO_VERSION}" }}
        tasks.named("jacocoTestReport") {{
            reports {{ xml.required.set(true) }}
        }}
    }}
}}
"""


_ARG_LINE = re.compile(r"<argLine>(.*?)</argLine>", re.S)
# Build tools' own classes: the agent loaded with JAVA_TOOL_OPTIONS also starts in Maven's JVM.
_AGENT_EXCLUDES = "org.apache.maven.*:org.codehaus.*:org.eclipse.aether.*:org.slf4j.*:com.google.*"


def overrides_arg_line(workspace: Path) -> bool:
    """Whether a pom gives surefire an `<argLine>` of its own without the `argLine` property,
    where JaCoCo's prepare-agent puts its agent (`@{argLine}`): the tests then run without it
    and write no coverage, as in jsoup's `<argLine>-Xss640k</argLine>`."""

    for pom in workspace.rglob("pom.xml"):
        if {"node_modules", "target", ".git"} & set(pom.relative_to(workspace).parts):
            continue
        try:
            text = pom.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any("argLine}" not in value for value in _ARG_LINE.findall(text)):
            return True
    return False


def jacoco_agent(
    base: Sequence[str],
    workspace: Path,
    env: Mapping[str, str],
    folder: Path,
    *,
    offline: bool = False,
    isolate: Callable[[list[str]], list[str]] | None = None,
) -> Path | None:
    """JaCoCo's agent jar, copied from Maven's repository (downloaded there the first time)."""

    jar = folder / "org.jacoco.agent-runtime.jar"
    if not jar.is_file():
        argv = [
            *base,
            "-B",
            "-q",
            *(["-o"] if offline else []),
            "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:copy",
            f"-Dartifact=org.jacoco:org.jacoco.agent:{JACOCO_VERSION}:jar:runtime",
            f"-DoutputDirectory={folder}",
            "-Dmdep.stripVersion=true",
        ]
        try:
            subprocess.run(
                isolate(argv) if isolate else argv,
                cwd=workspace,
                env=dict(env),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return None
    return jar if jar.is_file() else None


def jacoco_reports(workspace: Path) -> list[Path]:
    """The JaCoCo XML reports of a run: Maven's `target/site/jacoco/jacoco.xml` and Gradle's
    `build/reports/jacoco/test/jacocoTestReport.xml`, in every module."""

    found = [*workspace.rglob("jacoco.xml"), *workspace.rglob("jacocoTestReport.xml")]
    return sorted(
        path
        for path in found
        if "jacoco" in path.relative_to(workspace).parts[:-1]
        and not {"node_modules", ".git"} & set(path.relative_to(workspace).parts)
    )


_MAVEN_BROKEN = re.compile(
    r"^\[ERROR\] Failed to execute goal \S*maven-compiler-plugin\S* \(\S+\) on project ([\w.-]+)",
    re.M,
)
_MAVEN_COMPILE_ERROR = re.compile(r"^\[ERROR\] (\S+\.java:\[\d+,\d+\].*)$", re.M)
_GRADLE_BROKEN = re.compile(r"^> Task ((?::[\w.-]+)*):compile\w+ FAILED$", re.M)
_GRADLE_COMPILE_ERROR = re.compile(r"^(\S+\.java:\d+: error: .*|e: .*)$", re.M)


def read_build_failures(output: str, runner: str, workspace: Path) -> dict[str, str]:
    """{`::<project>`: the compiler's errors} for each project whose code did not compile."""

    if runner == "maven":
        projects = _MAVEN_BROKEN.findall(output)
        errors = _MAVEN_COMPILE_ERROR.findall(output)
    else:
        projects = [
            path.strip(":").replace(":", "/") or "." for path in _GRADLE_BROKEN.findall(output)
        ]
        errors = _GRADLE_COMPILE_ERROR.findall(output)
    root = f"{workspace.resolve().as_posix()}/"
    why = "\n".join(error.replace(root, "") for error in errors) or "the code did not compile"
    return {f"::{project}": why for project in projects}


def _command(runner: str, workspace: Path, environment: Mapping[str, str]) -> list[str]:
    """The build tool: the project's wrapper when it has one, otherwise the installed tool."""

    wrapper = workspace / ("mvnw" if runner == "maven" else "gradlew")
    if wrapper.is_file():
        return [str(wrapper)] if os.access(wrapper, os.X_OK) else ["sh", str(wrapper)]
    tool = shutil.which("mvn" if runner == "maven" else "gradle", path=environment.get("PATH"))
    return [tool] if tool else []


def java_classes(workspace: Path, paths: Sequence[str]) -> list[str]:
    classes: list[str] = []
    for path in paths:
        try:
            source = (workspace / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            source = ""
        classes.append(java_class_name(source, path))
    return classes


def run_java_tests(
    runner: str,
    *,
    workspace: Path,
    junit_path: Path,
    test_args: Sequence[str],
    timeout_seconds: int,
    environment: Mapping[str, str],
    output_tail_chars: int,
    isolate: Callable[[list[str]], list[str]] | None = None,
    coverage: bool = False,
    fail_fast: bool = False,
) -> JsonObject:
    """Run `mvn test` or `gradle test`; the result has the same shape as a pytest run's.
    Arguments that are `.java` files select their test classes (`-Dtest=` / `--tests`); the
    rest go to the build tool. `isolate` wraps the command, to run it without network access
    (it then runs offline: dependencies must be in the local repository or Gradle's cache).
    `coverage` records JaCoCo coverage and writes its XML reports (see `jacoco_reports`).
    `fail_fast` stops at the first failing test."""

    env = {
        **environment,
        **{key: os.environ[key] for key in ("JAVA_HOME", "GRADLE_USER_HOME") if key in os.environ},
    }
    if isolate:
        # Inside the namespace the user is root, and Java takes its home from the user database:
        # Maven and Gradle get the caller's own (the local repository, settings, Gradle's caches).
        home = env.get("HOME") or str(Path.home())
        env.setdefault("GRADLE_USER_HOME", f"{home}/.gradle")
        env["MAVEN_OPTS"] = f"-Duser.home={home}"
    base = _command(runner, workspace, env)
    # A pom whose argLine leaves out JaCoCo's: the agent goes in by the environment instead,
    # which every test JVM reads whatever the pom says, writing one data file for all modules.
    data_file = junit_path.with_name("jacoco-agent.exec")
    agent = (
        jacoco_agent(
            base, workspace, env, junit_path.parent, offline=bool(isolate), isolate=isolate
        )
        if coverage and runner == "maven" and base and overrides_arg_line(workspace)
        else None
    )
    if agent:
        data_file.unlink(missing_ok=True)
        env["JAVA_TOOL_OPTIONS"] = " ".join(
            part
            for part in (
                env.get("JAVA_TOOL_OPTIONS", ""),
                f"-javaagent:{agent}=destfile={data_file},append=true,excludes={_AGENT_EXCLUDES}",
            )
            if part
        )
    files = [arg for arg in test_args if arg.endswith(".java")]
    classes = java_classes(workspace, files)
    args = [arg for arg in test_args if not arg.endswith(".java")]
    if runner == "maven":
        args = [
            "-B",
            "-Dstyle.color=never",
            "-fae",
            "-Dmaven.test.failure.ignore=true",
            *(["-Dsurefire.skipAfterFailureCount=1"] if fail_fast else []),
            *(["-o"] if isolate else []),
            *args,
            *(
                [f"-Dtest={','.join(classes)}", "-Dsurefire.failIfNoSpecifiedTests=false"]
                if classes
                else []
            ),
            *([f"{JACOCO_PLUGIN}:prepare-agent"] if coverage and not agent else []),
            "test",
            *([f"{JACOCO_PLUGIN}:report"] if coverage else []),
            *([f"-Djacoco.dataFile={data_file}"] if agent else []),
        ]
    else:
        init_script = junit_path.with_name(f"{junit_path.stem}.init.gradle")
        init_script.write_text(
            GRADLE_INIT_SCRIPT + (GRADLE_JACOCO_SCRIPT if coverage else ""), encoding="utf-8"
        )
        args = [
            "test",
            *(["jacocoTestReport"] if coverage else []),
            "--init-script",
            str(init_script),
            "--continue",
            "--console=plain",
            "--no-daemon",
            "--no-build-cache",
            "--no-configuration-cache",
            *(["--fail-fast"] if fail_fast else []),
            *(["--offline"] if isolate else []),
            *args,
            *(arg for name in classes for arg in ("--tests", name)),
        ]
    result: JsonObject = {
        "runner": runner,
        "command": " ".join([PurePosixPath(base[-1]).name if base else runner, *args]),
        "exit_code": 127,
        "timed_out": False,
        "pytest_missing": False,
        "runner_missing": not base,
        "counts": {"passed": 0, "failed": 0, "skipped": 0},
        "outcomes": {},
        "failures": {},
        "output_tail": "",
    }
    if not base:
        result["output_tail"] = f"{'mvn' if runner == 'maven' else 'gradle'} is not installed"
        return result
    # Only this run's reports count, not ones left in the tree.
    for stale in [*_report_files(workspace, runner), *jacoco_reports(workspace)]:
        stale.unlink()
    try:
        argv = [*base, *args]
        completed = subprocess.run(
            isolate(argv) if isolate else argv,
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        result["exit_code"] = completed.returncode
        output = f"{completed.stdout}\n{completed.stderr}"
    except subprocess.TimeoutExpired as exc:
        result.update(exit_code=-1, timed_out=True)
        output = "\n".join(
            part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part or ""
            for part in (exc.stdout, exc.stderr)
        )
    events, names = read_gradle_events(output) if runner == "gradle" else ({}, {})
    outcomes, failures = read_java_reports(_report_files(workspace, runner), names)
    if events:
        outcomes = events
    broken = read_build_failures(output, runner, workspace) if result["exit_code"] else {}
    if broken:
        # The classes the run asked for that never ran did not compile with the rest.
        broken.update(
            {
                f"::{name}": next(iter(broken.values()))
                for name in classes
                if not any(test.startswith(f"{name}::") for test in outcomes)
            }
        )
    for test_id, why in broken.items():
        outcomes[test_id] = "failed"
        failures[test_id] = why
    write_junit(outcomes, junit_path)
    result["outcomes"] = outcomes
    result["failures"] = {
        test: why for test, why in failures.items() if why and outcomes.get(test) == "failed"
    }
    result["counts"] = {
        key: sum(1 for value in outcomes.values() if value == key)
        for key in ("passed", "failed", "skipped")
    }
    tail = output.strip()
    if not outcomes:
        # The build tool ends with its own footer; the reason nothing ran goes last instead.
        tail = f"{tail}\n{_why_nothing_ran(output, runner)}"
    result["output_tail"] = tail[-output_tail_chars:]
    return result


def _why_nothing_ran(output: str, runner: str) -> str:
    lines = output.splitlines()
    if runner == "maven":
        errors = [line[8:].strip() for line in lines if line.startswith("[ERROR] ")]
        if errors and errors[0]:
            return errors[0]
    elif "* What went wrong:" in lines:
        after = lines[lines.index("* What went wrong:") + 1 :]
        if after and after[0].strip():
            return after[0].strip()
    return "no test reports were written"
