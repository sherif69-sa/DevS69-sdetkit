from __future__ import annotations

import pytest

from sdetkit.failure_vector_cpp import extract_cpp_failure_vector, looks_like_cpp_failure
from sdetkit.safety_gate import evaluate_failure_vector


@pytest.mark.parametrize(
    ("log_text", "tool", "affected_files", "failure_check", "command"),
    [
        (
            """Run cmake --build --preset linux-debug
[1/2] /usr/bin/g++ -Iinclude -c src/engine.cpp
src/engine.cpp:17:9: error: 'missing' was not declared in this scope
Process completed with exit code 1
""",
            "gcc",
            ("src/engine.cpp",),
            "compiler_error",
            "cmake --build --preset linux-debug",
        ),
        (
            """$ clang++ -std=c++20 -Iinclude -c src/widget.cpp
include/widget.hpp:8:5: error: unknown type name 'WidgetState'
Process completed with exit code 1
""",
            "clang",
            ("src/widget.cpp", "include/widget.hpp"),
            "compiler_error",
            "clang++ -std=c++20 -Iinclude -c src/widget.cpp",
        ),
        (
            """Run cmake --build --preset windows-debug
cl /c src\\engine.cpp
D:\\a\\repo\\src\\engine.cpp(31,12): error C2065: 'missing': undeclared identifier [D:\\a\\repo\\build\\app.vcxproj]
Process completed with exit code 1
""",
            "msvc",
            ("src/engine.cpp",),
            "C2065",
            "cmake --build --preset windows-debug",
        ),
    ],
)
def test_cpp_compiler_diagnostics_map_to_review_first_failure_vectors(
    log_text: str,
    tool: str,
    affected_files: tuple[str, ...],
    failure_check: str,
    command: str,
) -> None:
    result = extract_cpp_failure_vector(log_text, check=f"{tool}-build")

    assert result.tool == tool
    assert result.confidence == "high"
    assert result.uncertainty == ()
    assert result.vector.failure_class == "compile"
    assert result.vector.affected_files == affected_files
    assert result.vector.failing_test_or_check == failure_check
    assert result.vector.command == command
    assert result.vector.local_repro_command == command
    assert result.vector.exit_code == 1
    assert result.vector.safe_fix_candidate is False
    assert result.vector.safe_fix_allowed is False

    decision = evaluate_failure_vector(result.vector)
    assert decision.review_first is True
    assert decision.safe_fix_allowed is False
    assert decision.automation_allowed is False
    assert decision.patch_application_allowed is False
    assert decision.merge_authorized is False


def test_cpp_gnu_linker_failure_uses_only_conservative_source_ownership() -> None:
    log_text = """$ cmake --build --preset linux-debug
/usr/bin/ld: CMakeFiles/app.dir/src/main.cpp.o: in function `main':
main.cpp:(.text+0x5): undefined reference to `calculate()'
collect2: error: ld returned 1 exit status
Process completed with exit code 1
"""

    result = extract_cpp_failure_vector(log_text, check="native-link")

    assert result.tool == "gnu_linker"
    assert result.vector.failure_class == "link"
    assert result.vector.affected_files == ("src/main.cpp",)
    assert result.vector.owner_hint == "src/main.cpp"
    assert result.vector.failing_test_or_check == "undefined_reference"
    assert result.vector.first_failing_line == (
        "main.cpp:(.text+0x5): undefined reference to `calculate()'"
    )
    assert result.vector.local_repro_command == "cmake --build --preset linux-debug"
    assert result.confidence == "high"
    assert result.uncertainty == ()


def test_cpp_ctest_google_test_failure_preserves_test_and_source_identity() -> None:
    log_text = """Run ctest --test-dir build --output-on-failure
Test project /home/runner/work/repo/build
1/1 Test #1: calculator_tests ............***Failed    0.01 sec
[ RUN      ] Calculator.Adds
tests/calculator_test.cpp:24: Failure
Expected equality of these values:
[  FAILED  ] Calculator.Adds (0 ms)
The following tests FAILED:
  1 - calculator_tests (Failed)
Process completed with exit code 8
"""

    result = extract_cpp_failure_vector(log_text, check="ctest")

    assert result.tool == "ctest_google_test"
    assert result.vector.failure_class == "test"
    assert result.vector.affected_files == ("tests/calculator_test.cpp",)
    assert result.vector.failing_test_or_check == "Calculator.Adds"
    assert result.vector.actual_failure == "Expected equality of these values:"
    assert result.vector.local_repro_command == "ctest --test-dir build --output-on-failure"
    assert result.vector.exit_code == 8
    assert result.confidence == "high"


def test_cpp_ctest_catch2_failure_preserves_saved_failure_detail() -> None:
    log_text = """$ ctest --preset ci
Test project /repo/build
1/1 Test #1: parser_spec .................***Failed    0.02 sec
tests/parser_spec.cpp:18: FAILED:
  REQUIRE( parse("x") == expected )
test cases: 1 | 1 failed
The following tests FAILED:
  1 - parser_spec (Failed)
Process completed with exit code 8
"""

    result = extract_cpp_failure_vector(log_text, check="ctest")

    assert result.tool == "ctest_catch2"
    assert result.vector.failure_class == "test"
    assert result.vector.affected_files == ("tests/parser_spec.cpp",)
    assert result.vector.failing_test_or_check == "parser_spec"
    assert result.vector.actual_failure == 'REQUIRE( parse("x") == expected )'
    assert result.vector.local_repro_command == "ctest --preset ci"
    assert result.confidence == "high"


def test_cpp_known_failure_without_explicit_command_does_not_invent_repro() -> None:
    log_text = """src/engine.cpp:17:9: error: 'missing' was not declared in this scope
Process completed with exit code 1
"""

    result = extract_cpp_failure_vector(log_text, check="native-build")

    assert result.tool == "gcc_clang"
    assert result.confidence == "medium"
    assert result.uncertainty == (
        "cpp_repro_command_not_observed",
        "cpp_compiler_identity_ambiguous",
    )
    assert result.vector.command == "unknown"
    assert result.vector.local_repro_command is None
    assert result.vector.affected_files == ("src/engine.cpp",)


def test_cpp_mixed_saved_output_remains_low_confidence_and_review_first() -> None:
    log_text = """$ cmake --build build
src/a.cpp:4:2: error: bad compile
main.cpp:(.text+0x5): undefined reference to `x()'
Process completed with exit code 1
"""

    result = extract_cpp_failure_vector(log_text, check="native-build")

    assert result.tool == "mixed_cpp_toolchain"
    assert result.confidence == "low"
    assert result.uncertainty == ("mixed_cpp_failure_signals",)
    assert result.vector.failure_class == "unknown"
    assert result.vector.safe_fix_candidate is False
    assert evaluate_failure_vector(result.vector).review_first is True


def test_cpp_generated_or_vendored_paths_do_not_create_ownership_claims() -> None:
    log_text = """$ g++ -c build/_deps/library/vendor.cpp
build/_deps/library/vendor.cpp:9:2: error: generated dependency failed
Process completed with exit code 1
"""

    result = extract_cpp_failure_vector(log_text, check="native-build")

    assert result.tool == "gcc"
    assert result.vector.affected_files == ()
    assert result.vector.owner_hint == "native-build"
    assert "cpp_source_path_not_observed" in result.uncertainty
    assert result.confidence == "medium"


def test_cpp_adapter_payload_preserves_false_authority() -> None:
    result = extract_cpp_failure_vector(
        """$ clang++ -c src/main.cpp
src/main.cpp:3:1: error: expected expression
Process completed with exit code 1
""",
        check="clang-build",
    )

    payload = result.to_dict()
    adapter = payload["adapter"]
    contract = payload["contract"]

    assert adapter == {
        "ecosystem": "cpp",
        "tool": "clang",
        "confidence": "high",
        "uncertainty": [],
        "target_code_execution": False,
    }
    assert contract["reporting_only"] is True
    assert contract["automation_allowed"] is False
    assert contract["patch_application_allowed"] is False
    assert contract["security_dismissal_allowed"] is False
    assert contract["merge_authorized"] is False
    assert contract["semantic_equivalence_claim"] is False


def test_cpp_detector_requires_structured_failure_evidence() -> None:
    assert looks_like_cpp_failure("src/main.cpp:3:1: error: expected expression") is True
    assert looks_like_cpp_failure("Documentation mentions src/main.cpp and CMake") is False


def test_unknown_cpp_signal_remains_low_confidence() -> None:
    result = extract_cpp_failure_vector(
        "C++ build stopped without a structured compiler, linker, or test signal",
        check="native-build",
    )

    assert result.tool == "unknown"
    assert result.confidence == "low"
    assert result.uncertainty == ("cpp_failure_not_classified",)
    assert result.vector.failure_class == "unknown"
    assert result.vector.local_repro_command is None
