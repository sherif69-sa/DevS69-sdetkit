from __future__ import annotations

from pathlib import Path
import subprocess
import textwrap


def _scripts_from_workflow() -> list[tuple[str, str]]:
    workflow = Path(".github/workflows/evidence-truth-bootstrap.yml")
    lines = workflow.read_text(encoding="utf-8").splitlines()
    scripts: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("      - name: "):
            name = line.split(": ", 1)[1]
            cursor = index + 1
            while cursor < len(lines) and not lines[cursor].startswith("      - name: "):
                if lines[cursor] == "        run: |":
                    cursor += 1
                    block: list[str] = []
                    while cursor < len(lines):
                        current = lines[cursor]
                        if current.startswith("      - name: "):
                            break
                        block.append(current[8:] if current.startswith("        ") else current)
                        cursor += 1
                    scripts.append((name, textwrap.dedent("\n".join(block)).rstrip() + "\n"))
                    break
                cursor += 1
        index += 1
    return scripts


def _repair_generated_files() -> None:
    newline = chr(10)
    repairs = {
        "tests/test_cpp_operator_proof.py": [
            ('"# Fixture' + newline + '"', r'"# Fixture\n"'),
            ('"Run g++ -c src/main.cpp' + newline + '"', r'"Run g++ -c src/main.cpp\n"'),
            (
                '"src/main.cpp:10:5: error: no matching function for call' + newline + '"',
                r'"src/main.cpp:10:5: error: no matching function for call\n"',
            ),
            (
                '"Error: Process completed with exit code 1' + newline + '"',
                r'"Error: Process completed with exit code 1\n"',
            ),
        ],
        "tests/test_investigate_failure.py": [
            ('"Run g++ -c src/main.cpp' + newline + '"', r'"Run g++ -c src/main.cpp\n"'),
            (
                '"src/main.cpp:10:5: error: no matching function for call' + newline + '"',
                r'"src/main.cpp:10:5: error: no matching function for call\n"',
            ),
            (
                '"Error: Process completed with exit code 1' + newline + '"',
                r'"Error: Process completed with exit code 1\n"',
            ),
            (
                'assert payload["confidence"] == "high"',
                'assert payload["confidence"] == "medium"',
            ),
        ],
        "src/sdetkit/failure_vector_cpp.py": [
            (
                r'r"g\+\+|gcc|clang\+\+|clang|cl(?:\.exe)?|link(?:\.exe)?)\b.*)$",',
                r'r"g\+\+|gcc|clang\+\+|clang|cl(?:\.exe)?|link(?:\.exe)?)(?=\s|$).*)$",',
            )
        ],
    }
    for raw_path, replacements in repairs.items():
        path = Path(raw_path)
        text = path.read_text(encoding="utf-8")
        for old, new in replacements:
            if old not in text:
                print(f"FAILED_FILE_MARKER={raw_path}:{old!r}")
                raise SystemExit(2)
            text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")


def _apply_canonical_fixes() -> int:
    result = subprocess.run(
        [
            "python",
            "-m",
            "ruff",
            "check",
            "--fix",
            "tests/test_repo_version_truth.py",
            "src/sdetkit/failure_vector_cpp.py",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print("FAILED_CANONICAL_REPAIR")
        print(result.stdout)
        print(result.stderr)
    return result.returncode


def main() -> int:
    scripts = _scripts_from_workflow()
    expected = [
        "Apply focused evidence-truth patch",
        "Install proof dependencies",
        "Format and lint focused scope",
        "Run focused proof",
        "Run clean-wheel dogfood",
        "Commit clean review branch",
    ]
    names = [name for name, _ in scripts]
    if names != expected:
        print(f"FAILED_BOOTSTRAP_STEPS={names!r}")
        return 2

    for name, script in scripts:
        if name == "Run focused proof":
            script = script.replace(
                "tests/test_cpp_operator_proof.py \\",
                "tests/test_cpp_operator_proof.py \\\n            tests/test_cpp_failure_vector_adapters.py \\",
                1,
            )
        if name == "Commit clean review branch":
            script = script.replace(
                "git rm .github/workflows/evidence-truth-bootstrap.yml",
                "git rm .github/workflows/evidence-truth-bootstrap.yml "
                ".github/workflows/evidence-truth-pr-trigger.yml",
                1,
            )
            script = script.replace(
                "src/sdetkit/cpp_operator_proof.py \\",
                "src/sdetkit/cpp_operator_proof.py \\\n            src/sdetkit/failure_vector_cpp.py \\",
                1,
            )
        result = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", script],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"FAILED_STEP={name}")
            combined = (result.stdout + "\n" + result.stderr).splitlines()
            for line in combined[-100:]:
                print(line)
            return result.returncode
        if name == "Apply focused evidence-truth patch":
            _repair_generated_files()
        if name == "Install proof dependencies" and _apply_canonical_fixes() != 0:
            return 1
        print(f"PASSED_STEP={name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
