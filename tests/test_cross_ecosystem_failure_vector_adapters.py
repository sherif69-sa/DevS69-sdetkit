from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.failure_vector_adapters import extract_ecosystem_failure_vector
from sdetkit.safety_gate import evaluate_failure_vector

FIXTURES = Path(__file__).parent / "fixtures" / "ci_failures"


def _fixture(name: str) -> str:
    return (FIXTURES / name / "ci_log.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture", "tool", "failure_class", "affected_file", "repro", "exit_code"),
    [
        ("typescript_tsc", "typescript", "type", "src/app.ts", "npx tsc --noEmit", 2),
        ("eslint", "eslint", "lint", "src/util.ts", "npx eslint .", 1),
        ("jest", "jest", "test", "src/math.test.ts", "npm test", 1),
        (
            "go_test",
            "go_test",
            "test",
            "calculator/calculator_test.go",
            "go test ./...",
            1,
        ),
        ("go_vet", "go_vet", "lint", "internal/logging/logging.go", "go vet ./...", 1),
        (
            "maven_test",
            "maven_test",
            "test",
            "src/test/java/com/example/CalculatorTest.java",
            "mvn test",
            1,
        ),
        (
            "gradle_test",
            "gradle_test",
            "test",
            "src/test/java/com/example/CalculatorTest.java",
            "./gradlew test",
            1,
        ),
        ("cargo_test", "cargo_test", "test", "src/lib.rs", "cargo test", 101),
        (
            "cargo_clippy",
            "cargo_clippy",
            "lint",
            "src/main.rs",
            "cargo clippy --all-targets --all-features",
            101,
        ),
        (
            "dotnet_xunit",
            "dotnet_test",
            "test",
            "tests/Calculator.Tests/CalculatorTests.cs",
            "dotnet test tests/Calculator.Tests/Calculator.Tests.csproj",
            1,
        ),
        (
            "dotnet_nunit_fsharp",
            "dotnet_test",
            "test",
            "tests/Math.Tests/CalculatorTests.fs",
            "dotnet test tests/Math.Tests/Math.Tests.fsproj",
            1,
        ),
        (
            "dotnet_mstest_vb",
            "dotnet_test",
            "test",
            "tests/Legacy.Tests/CalculatorTests.vb",
            "dotnet test tests/Legacy.Tests/Legacy.Tests.vbproj",
            1,
        ),
    ],
)
def test_cross_ecosystem_adapter_extracts_review_first_failure_vectors(
    fixture: str,
    tool: str,
    failure_class: str,
    affected_file: str,
    repro: str,
    exit_code: int,
) -> None:
    result = extract_ecosystem_failure_vector(_fixture(fixture), check=fixture)

    assert result.tool == tool
    assert result.vector.failure_class == failure_class
    assert result.vector.affected_files == (affected_file,)
    assert result.vector.local_repro_command == repro
    assert result.vector.exit_code == exit_code
    assert result.vector.scope == "unknown"
    assert result.vector.safe_fix_candidate is False
    assert result.vector.safe_fix_allowed is False
    assert result.confidence in {"high", "medium"}
    assert result.to_dict()["adapter"]["target_code_execution"] is False

    decision = evaluate_failure_vector(result.vector)
    assert decision.safe_fix_allowed is False
    assert decision.review_first is True
    assert decision.automation_allowed is False
    assert decision.patch_application_allowed is False
    assert decision.merge_authorized is False


def test_adapter_preserves_existing_python_failure_vector_behavior() -> None:
    log = """Run python -m pytest -q
FAILED tests/test_math.py::test_add - assert 3 == 4
Process completed with exit code 1
"""

    result = extract_ecosystem_failure_vector(log, check="pytest")

    assert result.ecosystem == "python"
    assert result.tool == "pytest"
    assert result.vector.failure_class == "test"
    assert result.vector.affected_files == ("tests/test_math.py",)
    assert result.vector.safe_fix_allowed is False


def test_unknown_cross_ecosystem_signal_remains_review_first() -> None:
    result = extract_ecosystem_failure_vector(
        "Build stopped without a structured failure line",
        ecosystem="javascript_typescript",
        check="node-build",
    )

    assert result.tool == "unknown"
    assert result.confidence == "low"
    assert result.uncertainty == ("javascript_failure_not_classified",)
    assert result.vector.failure_class == "unknown"
    assert evaluate_failure_vector(result.vector).review_first is True


def test_unknown_java_signal_remains_review_first() -> None:
    result = extract_ecosystem_failure_vector(
        "Java build stopped without Maven or Gradle test markers",
        ecosystem="java",
        check="java-build",
    )

    assert result.ecosystem == "java"
    assert result.tool == "unknown"
    assert result.confidence == "low"
    assert result.uncertainty == ("java_failure_not_classified",)
    assert result.vector.failure_class == "unknown"
    assert evaluate_failure_vector(result.vector).review_first is True


def test_unknown_rust_signal_remains_review_first() -> None:
    result = extract_ecosystem_failure_vector(
        "Rust build stopped without Cargo test or Clippy markers",
        ecosystem="rust",
        check="rust-build",
    )

    assert result.ecosystem == "rust"
    assert result.tool == "unknown"
    assert result.confidence == "low"
    assert result.uncertainty == ("rust_failure_not_classified",)
    assert result.vector.failure_class == "unknown"
    assert evaluate_failure_vector(result.vector).review_first is True


def test_unknown_dotnet_signal_remains_review_first() -> None:
    result = extract_ecosystem_failure_vector(
        ".NET build stopped without dotnet test evidence",
        ecosystem="dotnet",
        check="dotnet-build",
    )

    assert result.ecosystem == "dotnet"
    assert result.tool == "unknown"
    assert result.confidence == "low"
    assert result.uncertainty == ("dotnet_failure_not_classified",)
    assert result.vector.failure_class == "unknown"
    assert evaluate_failure_vector(result.vector).review_first is True


@pytest.mark.parametrize(
    ("fixture", "expected_test"),
    [
        ("dotnet_xunit", "Calculator.Tests.CalculatorTests.AddsNumbers"),
        ("dotnet_nunit_fsharp", "Math.Tests.CalculatorTests.adds_numbers"),
        ("dotnet_mstest_vb", "Legacy.Tests.CalculatorTests.AddsNumbers"),
    ],
)
def test_dotnet_adapter_preserves_exact_test_identity(
    fixture: str,
    expected_test: str,
) -> None:
    result = extract_ecosystem_failure_vector(_fixture(fixture), check=fixture)

    assert result.ecosystem == "dotnet"
    assert result.tool == "dotnet_test"
    assert result.vector.failing_test_or_check == expected_test
    assert result.vector.actual_failure
    assert result.confidence == "high"
    assert result.uncertainty == ()


def test_cargo_test_is_not_misclassified_as_go_test() -> None:
    result = extract_ecosystem_failure_vector(_fixture("cargo_test"), check="cargo-test")

    assert result.ecosystem == "rust"
    assert result.tool == "cargo_test"
    assert result.vector.local_repro_command == "cargo test"


def test_adapter_rejects_unsupported_ecosystem() -> None:
    with pytest.raises(ValueError, match="unsupported ecosystem"):
        extract_ecosystem_failure_vector("failure", ecosystem="ruby")
