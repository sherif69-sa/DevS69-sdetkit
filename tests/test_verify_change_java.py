"""`sdetkit verify change` on Java tests: Maven (Surefire) and Gradle."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from sdetkit import change_verifier, changed_coverage, java_tests

needs_maven = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("mvn") is None or shutil.which("java") is None,
    reason="needs git, java and mvn",
)
needs_gradle = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("gradle") is None or shutil.which("java") is None,
    reason="needs git, java and gradle",
)
posix_only = pytest.mark.skipif(os.name == "nt", reason="the fake build tool is a shell script")

SOURCE = """\
package com.example.cart;

import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class CartTest {
    @Test
    void adds() {
        assertEquals(1, Cart.add("a").size()); // assertTrue(false) in a comment is not one
        checkTotal(2);
    }

    @Test
    @Disabled("needs a database")
    void disabled() {
        assertNotNull(Cart.load());
    }

    @Test
    void assumes() throws Exception {
        assumeTrue(System.getenv("DB") != null);
        assertEquals(1, Cart.count());
    }

    @Test
    void nothing() {
        String text = "assertEquals(1, 2) and } in a string";
        String block = \"\"\"
            fail("in a text block") }
            \"\"\";
        assertTrue(true);
    }

    @ParameterizedTest
    @ValueSource(ints = {1, 2})
    void positive(int n) {
        assertThat(n).isPositive();
    }

    @org.junit.Test(expected = IllegalStateException.class)
    public void throwsOnEmpty() {
        Cart.checkout();
    }

    private void checkTotal(int want) {
        if (Cart.total() != want) {
            fail("total " + Cart.total());
        }
    }

    @Nested
    @Disabled
    class Empty {
        @Test
        void isEmpty() {
            assertTrue(Cart.isEmpty());
        }
    }
}
"""


def test_the_scanner_counts_assertions_with_helpers_and_skips() -> None:
    assert java_tests.java_test_facts(SOURCE) == {
        "adds": {"assertions": 2, "skips": 0},
        "disabled": {"assertions": 1, "skips": 1},
        "assumes": {"assertions": 1, "skips": 1},
        "nothing": {"assertions": 0, "skips": 0},
        "positive": {"assertions": 1, "skips": 0},
        "throwsOnEmpty": {"assertions": 1, "skips": 0},
        "Empty.isEmpty": {"assertions": 1, "skips": 1},
    }


def test_java_ids_name_the_class_by_package_and_nesting() -> None:
    path = "src/test/java/com/example/cart/CartTest.java"

    assert java_tests.java_class_name(SOURCE, path) == "com.example.cart.CartTest"
    assert java_tests.java_test_id(SOURCE, path, "adds") == "com.example.cart.CartTest::adds"
    assert (
        java_tests.java_test_id(SOURCE, path, "Empty.isEmpty")
        == "com.example.cart.CartTest$Empty::isEmpty"
    )
    assert java_tests.java_class_name("class T {}", "src/test/java/T.java") == "T"


def test_a_renamed_java_test_keeps_its_fingerprint() -> None:
    before = java_tests.java_test_fingerprints(
        "class T {\n    @Test\n    void old() {\n        assertEquals(1, f());\n    }\n}\n"
    )
    after = java_tests.java_test_fingerprints(
        "class T { @Test void renamed() { assertEquals(1, f()); } }"
    )

    assert before["old"] == after["renamed"]


def test_java_test_files_and_the_runner_choice(tmp_path: Path) -> None:
    assert java_tests.is_java_test_file("src/test/java/com/x/CartTest.java")
    assert java_tests.is_java_test_file("core/src/test/java/TestCart.java")
    assert java_tests.is_java_test_file("src/test/java/CartIT.java")
    assert not java_tests.is_java_test_file("src/main/java/com/x/Cart.java")
    assert not java_tests.is_java_test_file("target/generated/CartTest.java")
    assert java_tests.is_java_test_side("core/src/test/resources/cart.json")

    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert change_verifier.resolve_runner(tmp_path) == "maven"
    (tmp_path / "pom.xml").unlink()
    (tmp_path / "settings.gradle.kts").write_text('rootProject.name = "x"\n', encoding="utf-8")
    assert change_verifier.resolve_runner(tmp_path) == "gradle"


SUREFIRE = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.example.CartTest" tests="4">
  <testcase name="adds" classname="com.example.CartTest"/>
  <testcase name="positive(int)[1]" classname="com.example.CartTest">
    <failure message="expected: &lt;1&gt; but was: &lt;2&gt;">org.opentest4j.AssertionFailedError: expected: &lt;1&gt; but was: &lt;2&gt;
\tat org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)
\tat com.example.CartTest.positive(CartTest.java:19)
\tat java.base/java.lang.reflect.Method.invoke(Method.java:568)
</failure>
  </testcase>
  <testcase name="later" classname="com.example.CartTest"><skipped/></testcase>
  <testcase name="crashes()" classname="com.example.CartTest$Empty">
    <error message="boom" type="java.lang.IllegalStateException"/>
  </testcase>
</testsuite>
"""


def test_junit_reports_read_to_class_ids_with_the_test_frames_only(tmp_path: Path) -> None:
    report = tmp_path / "TEST-com.example.CartTest.xml"
    report.write_text(SUREFIRE, encoding="utf-8")

    outcomes, failures = java_tests.read_java_reports([report])

    assert outcomes == {
        "com.example.CartTest::adds": "passed",
        "com.example.CartTest::positive(int)[1]": "failed",
        "com.example.CartTest::later": "skipped",
        "com.example.CartTest$Empty::crashes": "failed",
    }
    assert failures["com.example.CartTest::positive(int)[1]"] == (
        "org.opentest4j.AssertionFailedError: expected: <1> but was: <2>\n"
        "\tat com.example.CartTest.positive(CartTest.java:19)"
    )
    assert failures["com.example.CartTest$Empty::crashes"] == "boom"


def test_gradle_runs_are_named_by_their_method_as_surefire_names_them(tmp_path: Path) -> None:
    output = (
        "> Task :test\n"
        "##sdetkit-test\tSUCCESS\tcom.example.CartTest\tadds()\tadds()\n"
        "##sdetkit-test\tFAILURE\tcom.example.CartTest\t[1] 2\tpositive(int)[1]\n"
        "##sdetkit-test\tSUCCESS\tcom.example.CartTest\t[1] 2\teven(int)[1]\n"
        "##sdetkit-test\tSKIPPED\tcom.example.CartTest$Empty\tisEmpty()\tisEmpty()\n"
    )
    report = tmp_path / "TEST-com.example.CartTest.xml"
    report.write_text(
        '<testsuite><testcase name="adds()" classname="com.example.CartTest">'
        '<failure message="boom">java.lang.AssertionError: boom</failure></testcase>'
        '<testcase name="[1] 2" classname="com.example.CartTest">'
        '<failure message="odd">java.lang.AssertionError: odd</failure></testcase></testsuite>',
        encoding="utf-8",
    )

    outcomes, names = java_tests.read_gradle_events(output)
    _, failures = java_tests.read_java_reports([report], names)

    assert outcomes == {
        "com.example.CartTest::adds": "passed",
        "com.example.CartTest::positive(int)[1]": "failed",
        "com.example.CartTest::even(int)[1]": "passed",
        "com.example.CartTest$Empty::isEmpty": "skipped",
    }
    assert failures["com.example.CartTest::adds"] == "java.lang.AssertionError: boom"
    # `[1] 2` names a run of two methods: its report entry belongs to neither.
    assert not {
        "com.example.CartTest::positive(int)[1]",
        "com.example.CartTest::even(int)[1]",
    } & set(failures)


def test_compile_failures_name_the_project(tmp_path: Path) -> None:
    root = tmp_path.resolve().as_posix()
    maven = (
        f"[ERROR] {root}/src/test/java/com/x/CartTest.java:[9,29] cannot find symbol\n"
        "[ERROR] Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin:3.13.0:"
        "testCompile (default-testCompile) on project cart: Compilation failure\n"
    )
    gradle = (
        f"{root}/core/src/test/java/CartTest.java:9: error: cannot find symbol\n"
        "> Task :core:compileTestJava FAILED\n"
    )

    assert java_tests.read_build_failures(maven, "maven", tmp_path) == {
        "::cart": "src/test/java/com/x/CartTest.java:[9,29] cannot find symbol"
    }
    assert java_tests.read_build_failures(gradle, "gradle", tmp_path) == {
        "::core": "core/src/test/java/CartTest.java:9: error: cannot find symbol"
    }
    assert java_tests.read_build_failures("> Task :compileJava FAILED\n", "gradle", tmp_path) == {
        "::.": "the code did not compile"
    }


POM = """\
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <properties><junit.version>5.10.2</junit.version><java.version>17</java.version></properties>
  <dependencies><dependency><artifactId>guava</artifactId><version>33.0</version></dependency></dependencies>
  <build><plugins><plugin>
    <artifactId>maven-surefire-plugin</artifactId><version>3.2.5</version>
  </plugin></plugins></build>
</project>
"""
GRADLE = """\
dependencies { implementation("com.google.guava:guava:33.0-jre") }
tasks.test {
    useJUnitPlatform()
}
"""


def test_a_build_file_counts_as_test_configuration_only_where_it_runs_the_tests() -> None:
    config = java_tests.java_test_config

    assert config("pom.xml", POM) == config("pom.xml", POM.replace("33.0", "33.1"))
    assert config("pom.xml", POM) == config("pom.xml", POM.replace(">17<", ">21<"))
    assert config("pom.xml", POM) != config(
        "pom.xml",
        POM.replace(
            "<version>3.2.5</version>",
            "<version>3.2.5</version><configuration><skipTests>true</skipTests></configuration>",
        ),
    )
    assert config("pom.xml", POM) != config(
        "pom.xml", POM.replace("<properties>", "<properties><skipTests>true</skipTests>")
    )
    assert config("build.gradle.kts", GRADLE) == config(
        "build.gradle.kts", GRADLE.replace("33.0", "33.1")
    )
    assert config("build.gradle.kts", GRADLE) != config(
        "build.gradle.kts", GRADLE.replace("useJUnitPlatform()", 'exclude("**/CartTest*")')
    )


# --- the build tool's command line, with a fake build tool -------------------------------

FAKE_MVN = """\
#!/bin/sh
printf '%s\\n' "$@" > "$PWD/../argv.txt"
printf '%s' "$MAVEN_OPTS" > "$PWD/../maven_opts.txt"
mkdir -p target/surefire-reports
cat > target/surefire-reports/TEST-com.example.CartTest.xml <<'EOF'
<testsuite><testcase name="adds" classname="com.example.CartTest"/></testsuite>
EOF
"""


@posix_only
def test_test_files_select_their_classes_and_deny_runs_offline(tmp_path: Path) -> None:
    workspace = tmp_path / "clone"
    (workspace / "src/test/java/com/example").mkdir(parents=True)
    (workspace / "src/test/java/com/example/CartTest.java").write_text(
        "package com.example;\nclass CartTest {}\n", encoding="utf-8"
    )
    stale = workspace / "target/surefire-reports/TEST-com.example.OldTest.xml"
    stale.parent.mkdir(parents=True)
    stale.write_text('<testsuite><testcase name="x" classname="Old"/></testsuite>', "utf-8")
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "mvn").write_text(FAKE_MVN, encoding="utf-8")
    (tools / "mvn").chmod((tools / "mvn").stat().st_mode | stat.S_IEXEC)
    wrapped: list[list[str]] = []

    def isolate(argv: list[str]) -> list[str]:
        wrapped.append(argv)
        return argv

    result = java_tests.run_java_tests(
        "maven",
        workspace=workspace,
        junit_path=tmp_path / "junit.xml",
        test_args=["-pl", "core", "src/test/java/com/example/CartTest.java"],
        timeout_seconds=60,
        environment={"PATH": f"{tools}{os.pathsep}{os.environ['PATH']}", "HOME": "/home/me"},
        output_tail_chars=1000,
        isolate=isolate,
    )

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").split("\n")
    assert wrapped and result["exit_code"] == 0
    assert result["outcomes"] == {"com.example.CartTest::adds": "passed"}
    assert "-o" in argv and "-Dtest=com.example.CartTest" in argv
    assert argv[argv.index("-pl") + 1] == "core" and argv[-2] == "test"
    assert (tmp_path / "maven_opts.txt").read_text(encoding="utf-8") == "-Duser.home=/home/me"
    assert result["command"].startswith("mvn -B ")

    java_tests.run_java_tests(
        "maven",
        workspace=workspace,
        junit_path=tmp_path / "junit.xml",
        test_args=[],
        timeout_seconds=60,
        environment={"PATH": f"{tools}{os.pathsep}{os.environ['PATH']}", "HOME": "/home/me"},
        output_tail_chars=1000,
        coverage=True,
    )

    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").split("\n")
    jacoco = java_tests.JACOCO_PLUGIN
    assert argv[-4:-1] == [f"{jacoco}:prepare-agent", "test", f"{jacoco}:report"]


JACOCO = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">
<report name="calc">
  <package name="com/example">
    <class name="com/example/Calc" sourcefilename="Calc.java"/>
    <sourcefile name="Calc.java">
      <line nr="3" mi="3" ci="0" mb="0" cb="0"/>
      <line nr="5" mi="0" ci="4" mb="0" cb="0"/>
      <line nr="9" mi="2" ci="0" mb="2" cb="0"/>
    </sourcefile>
    <sourcefile name="Other.java"><line nr="1" mi="0" ci="1" mb="0" cb="0"/></sourcefile>
  </package>
</report>
"""


def test_jacoco_reports_match_the_changed_files_by_package(tmp_path: Path) -> None:
    report = tmp_path / "target" / "site" / "jacoco" / "jacoco.xml"
    report.parent.mkdir(parents=True)
    report.write_text(JACOCO, encoding="utf-8")
    (tmp_path / "build" / "reports" / "jacoco" / "test").mkdir(parents=True)
    gradle = tmp_path / "build" / "reports" / "jacoco" / "test" / "jacocoTestReport.xml"
    gradle.write_text("<report/>", encoding="utf-8")
    (tmp_path / "jacoco.xml").write_text("<report/>", encoding="utf-8")

    assert java_tests.jacoco_reports(tmp_path) == [gradle, report]
    assert changed_coverage.read_jacoco_xml(
        [report], ["core/src/main/java/com/example/Calc.java", "src/main/java/Calc.java"]
    ) == {"core/src/main/java/com/example/Calc.java": ({3, 5, 9}, {5})}
    assert "jacocoTestReport" in java_tests.GRADLE_JACOCO_SCRIPT
    assert java_tests.JACOCO_VERSION in java_tests.GRADLE_JACOCO_SCRIPT


def test_a_missing_build_tool_is_not_run(tmp_path: Path) -> None:
    result = java_tests.run_java_tests(
        "gradle",
        workspace=tmp_path,
        junit_path=tmp_path / "junit.xml",
        test_args=[],
        timeout_seconds=60,
        environment={"PATH": str(tmp_path)},
        output_tail_chars=1000,
    )

    assert result["runner_missing"] is True
    status, reasons = change_verifier.decide(
        head_run=result, base_run=None, comparison={}, findings=[], not_imported=[]
    )
    assert (status, reasons) == ("NOT_RUN", ["gradle is not installed"])


# --- end to end with Maven and Gradle -----------------------------------------------------
# These download JUnit and the build plugins the first time, so they are network tests.

POM_FILE = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>calc</artifactId>
  <version>1.0</version>
  <properties>
    <maven.compiler.release>17</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>5.10.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>3.2.5</version>
      </plugin>
    </plugins>
  </build>
</project>
"""
GRADLE_FILE = """\
plugins { java }
repositories { mavenCentral() }
dependencies {
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
tasks.test { useJUnitPlatform() }
"""
BUGGY = "package com.example;\n\npublic class Calc {\n    public static int add(int a, int b) { return a - b; }\n}\n"
FIXED = BUGGY.replace("a - b", "a + b")
TEST = """\
package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class CalcTest {
    @Test
    void addsTwo() {
        assertEquals(5, Calc.add(2, 3));
    }

    @Test
    void addsZero() {
        assertEquals(0, Calc.add(0, 0));
    }
}
"""
ZERO = """
    @Test
    void addsZero() {
        assertEquals(0, Calc.add(0, 0));
    }
"""
MAIN = "src/main/java/com/example/Calc.java"
TEST_PATH = "src/test/java/com/example/CalcTest.java"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path, build: dict[str, str], source: str = BUGGY) -> Path:
    repo = tmp_path / "repo"
    files = {**build, MAIN: source, TEST_PATH: TEST, ".gitignore": "target/\nbuild/\n.gradle/\n"}
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _verify(repo: Path, out: Path, files: dict[str, str], **options: Any) -> dict[str, Any]:
    for path, text in files.items():
        (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    diff = _git(repo, "diff", "--cached")
    _git(repo, "reset", "-q", "--hard")
    return change_verifier.verify_change(
        repo_root=repo,
        out_dir=out,
        python=sys.executable,
        patch_text=diff,
        timeout_seconds=600,
        **options,
    )


NEGATIVE = TEST.replace(
    "\n}\n",
    "\n\n    @Test\n    void subtracts() {\n        assertEquals(1, Calc.sub(3, 2));\n    }\n}\n",
)
WITH_SUB = FIXED.replace(
    "\n}\n", "\n    public static int sub(int a, int b) { return a - b; }\n}\n"
)


@pytest.mark.network
@needs_maven
def test_a_maven_fix_is_verified_with_the_tests_that_prove_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"pom.xml": POM_FILE})

    report = _verify(repo, tmp_path / "out", {MAIN: WITH_SUB, TEST_PATH: NEGATIVE})

    assert report["tests"]["runner"] == "maven"
    assert report["status"] == "VERIFIED", report["reasons"]
    assert report["tests"]["comparison"]["fixed"] == ["com.example.CalcTest::addsTwo"]
    # CalcTest does not compile against the code before the change (no Calc.sub): it proves it.
    assert report["tests"]["proof"]["proving"] == [
        "com.example.CalcTest::addsTwo",
        "com.example.CalcTest::addsZero",
        "com.example.CalcTest::subtracts",
    ]
    # JaCoCo, added to the build by the verifier: the tests run both changed lines.
    coverage = report["changed_coverage"]
    assert (coverage["tool"], coverage["changed_lines"], coverage["run_lines"]) == ("JaCoCo", 2, 2)


@pytest.mark.network
@needs_maven
def test_a_maven_regression_fails_and_a_removed_test_is_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"pom.xml": POM_FILE}, source=FIXED)

    regression = _verify(repo, tmp_path / "a", {MAIN: BUGGY})
    removed = _verify(repo, tmp_path / "b", {TEST_PATH: TEST.replace(ZERO, "")})
    untested = _verify(
        repo,
        tmp_path / "c",
        {
            MAIN: FIXED.replace(
                "\n}\n", "\n    public static int mul(int a, int b) { return a * b; }\n}\n"
            )
        },
    )

    assert regression["status"] == "FAILED"
    assert regression["tests"]["comparison"]["regressions"] == ["com.example.CalcTest::addsTwo"]
    assert regression["tests"]["failures"]["com.example.CalcTest::addsTwo"].startswith(
        "org.opentest4j.AssertionFailedError: expected: <5> but was: <-1>"
    )
    assert removed["status"] == "REVIEW"
    assert "tests_removed" in [finding["code"] for finding in removed["findings"]]
    assert removed["tests"]["comparison"]["missing"] == ["com.example.CalcTest::addsZero"]
    assert untested["status"] == "VERIFIED", untested["reasons"]
    assert changed_coverage.not_run_items(untested["changed_coverage"]) == [f"{MAIN}:5"]


POSITIVE = FIXED.replace(
    "\n}\n", "\n    public static boolean positive(int n) { return n > 0; }\n}\n"
)
POSITIVE_TEST = TEST.replace(
    "\n}\n",
    "\n\n    @Test\n    void positive() {\n"
    "        org.junit.jupiter.api.Assertions.assertTrue(Calc.positive(5));\n    }\n}\n",
)


@pytest.mark.network
@needs_maven
def test_maven_mutants_find_the_line_no_test_checks(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"pom.xml": POM_FILE})

    report = _verify(
        repo, tmp_path / "out", {MAIN: POSITIVE, TEST_PATH: POSITIVE_TEST}, mutate=True
    )

    assert report["status"] == "VERIFIED", report["reasons"]
    outcomes = {item["after"]: item["outcome"] for item in report["mutation"]["mutants"]}
    # `a + b` to `a - b` fails addsTwo; nothing tests `positive` at 0 or 1.
    assert outcomes == {
        "public static int add(int a, int b) { return a - b; }": "killed",
        "public static boolean positive(int n) { return n >= 0; }": "survived",
        "public static boolean positive(int n) { return n > 1; }": "survived",
    }


@pytest.mark.network
@needs_gradle
def test_a_gradle_fix_is_verified_and_a_regression_fails(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        {"build.gradle.kts": GRADLE_FILE, "settings.gradle.kts": 'rootProject.name = "calc"\n'},
    )

    fixed = _verify(repo, tmp_path / "a", {MAIN: FIXED})
    broken = _verify(
        repo, tmp_path / "b", {MAIN: FIXED + "class Broken { int x() { return y; } }\n"}
    )

    assert fixed["tests"]["runner"] == "gradle"
    assert fixed["status"] == "VERIFIED", fixed["reasons"]
    assert fixed["tests"]["comparison"]["fixed"] == ["com.example.CalcTest::addsTwo"]
    assert fixed["changed_coverage"]["tool"] == "JaCoCo"
    assert (fixed["changed_coverage"]["changed_lines"], fixed["changed_coverage"]["run_lines"]) == (
        1,
        1,
    )
    assert broken["status"] == "FAILED", broken["reasons"]
    assert "cannot find symbol" in broken["tests"]["failures"]["::."]


def test_a_pom_with_its_own_arg_line_is_found(tmp_path: Path) -> None:
    def pom(arg_line: str) -> str:
        return POM_FILE.replace(
            "<version>3.2.5</version>",
            f"<version>3.2.5</version><configuration><argLine>{arg_line}</argLine></configuration>",
        )

    (tmp_path / "pom.xml").write_text(POM_FILE, encoding="utf-8")
    assert not java_tests.overrides_arg_line(tmp_path)
    (tmp_path / "pom.xml").write_text(pom("@{argLine} -Xss640k"), encoding="utf-8")
    assert not java_tests.overrides_arg_line(tmp_path)
    (tmp_path / "pom.xml").write_text(pom("${argLine} -Xss640k"), encoding="utf-8")
    assert not java_tests.overrides_arg_line(tmp_path)
    # jsoup's: the tests would run without JaCoCo's agent.
    (tmp_path / "pom.xml").write_text(pom("-Xss640k"), encoding="utf-8")
    assert java_tests.overrides_arg_line(tmp_path)
    # A module's pom counts too; one under target/ does not.
    (tmp_path / "pom.xml").write_text(POM_FILE, encoding="utf-8")
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "pom.xml").write_text(pom("-Xss1m"), encoding="utf-8")
    assert java_tests.overrides_arg_line(tmp_path)
    (tmp_path / "core" / "pom.xml").unlink()
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "pom.xml").write_text(pom("-Xss1m"), encoding="utf-8")
    assert not java_tests.overrides_arg_line(tmp_path)


@pytest.mark.network
@needs_maven
def test_coverage_is_measured_when_the_pom_sets_its_own_arg_line(tmp_path: Path) -> None:
    own = POM_FILE.replace(
        "<version>3.2.5</version>",
        "<version>3.2.5</version><configuration><argLine>-Xss1m</argLine></configuration>",
    )
    repo = _repo(tmp_path, {"pom.xml": own})

    report = _verify(repo, tmp_path / "out", {MAIN: WITH_SUB, TEST_PATH: NEGATIVE})

    assert report["status"] == "VERIFIED", report["reasons"]
    coverage = report["changed_coverage"]
    assert (coverage["tool"], coverage["changed_lines"], coverage["run_lines"]) == ("JaCoCo", 2, 2)
