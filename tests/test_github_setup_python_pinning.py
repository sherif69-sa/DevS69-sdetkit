from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

YAML_SEARCH_ROOTS = (
    ROOT / ".github" / "actions",
    ROOT / ".github" / "workflows",
    ROOT / "docs" / "artifacts",
    ROOT / "src" / "sdetkit" / "templates",
    ROOT / "templates",
)

SETUP_PYTHON_ACTION = "actions/setup-python"
INPUT_EXPRESSION_RE = re.compile(r"\${{\s*inputs\.([A-Za-z0-9_-]+)\s*}}")


@dataclass(frozen=True)
class SetupPythonStep:
    path: Path
    step_name: str
    uses: str
    with_block: dict[str, Any]


def _yaml_paths() -> list[Path]:
    paths: list[Path] = []
    for root in YAML_SEARCH_ROOTS:
        if not root.exists():
            continue
        for suffix in ("*.yml", "*.yaml"):
            paths.extend(root.rglob(suffix))
    return sorted(set(paths))


def _load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(text)
    return payload


def _walk(node: Any) -> list[Any]:
    found = [node]
    if isinstance(node, dict):
        for value in node.values():
            found.extend(_walk(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_walk(value))
    return found


def _setup_python_steps(path: Path) -> list[SetupPythonStep]:
    payload = _load_yaml(path)
    steps: list[SetupPythonStep] = []

    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        uses = str(node.get("uses", ""))
        if SETUP_PYTHON_ACTION not in uses:
            continue
        with_block = node.get("with", {})
        if with_block is None:
            with_block = {}
        assert isinstance(with_block, dict), f"{path}: setup-python with block must be a mapping"
        steps.append(
            SetupPythonStep(
                path=path,
                step_name=str(node.get("name", "<unnamed setup-python step>")),
                uses=uses,
                with_block=with_block,
            )
        )

    return steps


def _all_setup_python_steps() -> list[SetupPythonStep]:
    steps: list[SetupPythonStep] = []
    for path in _yaml_paths():
        steps.extend(_setup_python_steps(path))
    return steps


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _action_inputs(path: Path) -> dict[str, Any]:
    payload = _load_yaml(path)
    assert isinstance(payload, dict), f"{path}: action metadata must be a mapping"
    inputs = payload.get("inputs", {})
    assert isinstance(inputs, dict), f"{path}: action inputs must be a mapping"
    return inputs


def _input_default(path: Path, input_name: str) -> str:
    inputs = _action_inputs(path)
    spec = inputs.get(input_name)
    if not isinstance(spec, dict):
        return ""
    value = spec.get("default", "")
    return str(value).strip()


def _input_references(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    return INPUT_EXPRESSION_RE.findall(value)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_every_setup_python_step_has_explicit_version_or_version_file() -> None:
    failures: list[str] = []

    for step in _all_setup_python_steps():
        version = step.with_block.get("python-version")
        version_file = step.with_block.get("python-version-file")
        if _is_non_empty_string(version) or _is_non_empty_string(version_file):
            continue
        failures.append(
            f"{_relative(step.path)}: {step.step_name} uses {step.uses} without "
            "python-version or python-version-file"
        )

    assert failures == []


def test_setup_python_input_expression_versions_have_action_defaults() -> None:
    failures: list[str] = []

    for step in _all_setup_python_steps():
        version = step.with_block.get("python-version")
        for input_name in _input_references(version):
            if ".github/actions/" not in step.path.as_posix():
                continue
            default = _input_default(step.path, input_name)
            if default:
                continue
            failures.append(
                f"{_relative(step.path)}: setup-python uses inputs.{input_name} "
                "without a non-empty default"
            )

    assert failures == []


def test_repo_audit_composite_action_pins_default_python_version() -> None:
    action_path = ROOT / ".github" / "actions" / "repo-audit" / "action.yml"
    inputs = _action_inputs(action_path)

    python_version = inputs.get("python_version")
    assert isinstance(python_version, dict)
    assert python_version.get("default") == "3.12"


def test_repo_audit_composite_action_setup_python_uses_input_default_contract() -> None:
    action_path = ROOT / ".github" / "actions" / "repo-audit" / "action.yml"
    steps = _setup_python_steps(action_path)

    matching = [
        step
        for step in steps
        if step.with_block.get("python-version") == "${{ inputs.python_version }}"
    ]

    assert len(matching) == 1
    assert _input_default(action_path, "python_version") == "3.12"


def test_all_setup_python_actions_are_explicitly_version_pinned() -> None:
    failures: list[str] = []

    for step in _all_setup_python_steps():
        if "@" not in step.uses:
            failures.append(f"{_relative(step.path)}: {step.uses} is not pinned")
            continue
        action, version = step.uses.split("@", 1)
        if action != SETUP_PYTHON_ACTION:
            failures.append(f"{_relative(step.path)}: unexpected action {step.uses}")
            continue
        if not version.strip():
            failures.append(f"{_relative(step.path)}: empty setup-python version")

    assert failures == []


def test_setup_python_guardrail_covers_live_workflows_and_templates() -> None:
    paths = {_relative(step.path) for step in _all_setup_python_steps()}

    required = {
        ".github/actions/repo-audit/action.yml",
        ".github/workflows/ci.yml",
        ".github/workflows/enterprise-gate.yml",
        ".github/workflows/pr-quality-comment.yml",
        ".github/workflows/premium-gate.yml",
        ".github/workflows/quality.yml",
        "src/sdetkit/templates/enterprise_python/.github/workflows/ci.yml",
        "templates/automations/enterprise-next-pass-handoff.yaml",
    }

    missing = sorted(required - paths)
    assert missing == []


def test_guardrail_detects_missing_python_version_in_synthetic_step(tmp_path: Path) -> None:
    workflow = tmp_path / "bad.yml"
    workflow.write_text(
        """
name: bad
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v6
        with:
          cache: pip
""",
        encoding="utf-8",
    )

    steps = _setup_python_steps(workflow)
    assert len(steps) == 1
    step = steps[0]

    assert not _is_non_empty_string(step.with_block.get("python-version"))
    assert not _is_non_empty_string(step.with_block.get("python-version-file"))


def test_guardrail_allows_python_version_file_in_synthetic_step(tmp_path: Path) -> None:
    workflow = tmp_path / "good.yml"
    workflow.write_text(
        """
name: good
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v6
        with:
          python-version-file: .python-version
""",
        encoding="utf-8",
    )

    steps = _setup_python_steps(workflow)
    assert len(steps) == 1
    step = steps[0]

    assert step.with_block["python-version-file"] == ".python-version"


def test_guardrail_detects_missing_action_input_default_in_synthetic_action(
    tmp_path: Path,
) -> None:
    action = tmp_path / "action.yml"
    action.write_text(
        """
name: synthetic
inputs:
  python_version:
    description: Python version
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v6
      with:
        python-version: ${{ inputs.python_version }}
""",
        encoding="utf-8",
    )

    steps = _setup_python_steps(action)
    assert len(steps) == 1

    assert _input_references(steps[0].with_block["python-version"]) == ["python_version"]
    assert _input_default(action, "python_version") == ""


def test_guardrail_allows_action_input_default_in_synthetic_action(tmp_path: Path) -> None:
    action = tmp_path / "action.yml"
    action.write_text(
        """
name: synthetic
inputs:
  python_version:
    description: Python version
    default: "3.12"
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v6
      with:
        python-version: ${{ inputs.python_version }}
""",
        encoding="utf-8",
    )

    steps = _setup_python_steps(action)
    assert len(steps) == 1

    assert _input_references(steps[0].with_block["python-version"]) == ["python_version"]
    assert _input_default(action, "python_version") == "3.12"


def test_no_setup_python_step_depends_on_runner_path_fallback() -> None:
    for step in _all_setup_python_steps():
        version = step.with_block.get("python-version")
        version_file = step.with_block.get("python-version-file")
        assert _is_non_empty_string(version) or _is_non_empty_string(version_file)
