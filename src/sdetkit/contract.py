from __future__ import annotations

import argparse
import json
from importlib import metadata
from pathlib import Path
from typing import Any

from .review import REVIEW_CONTRACT_VERSION

RUNTIME_CONTRACT_VERSION = "sdetkit.runtime.contract.v1"


def _tool_version() -> str:
    try:
        return metadata.version("sdetkit")
    except metadata.PackageNotFoundError:
        return "0+unknown"


def _public_surface_contract(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "src" / "sdetkit" / "public_command_surface.json"
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _runtime_payload(repo_root: Path) -> dict[str, Any]:
    command_contract = _public_surface_contract(repo_root)
    return {
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "tool": {
            "name": "sdetkit",
            "version": _tool_version(),
        },
        "recommended_install": {
            "pip_git": 'python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"',
            "verify": "python -m sdetkit --help",
        },
        "canonical_first_path": command_contract.get(
            "canonical_first_path",
            [
                "python -m sdetkit gate fast",
                "python -m sdetkit gate release",
                "python -m sdetkit doctor",
            ],
        ),
        "stable_machine_outputs": {
            "review_operator_json": {
                "command": "python -m sdetkit review . --no-workspace --format operator-json",
                "contract_version": REVIEW_CONTRACT_VERSION,
                "notes": "Preferred stable operator-facing parsing surface for CI and automations.",
            }
        },
        "stability_surfaces": {
            "public_command_surface_version": command_contract.get("contract_version"),
            "public_stable_front_door_commands": command_contract.get(
                "public_stable_front_door_commands", []
            ),
            "advanced_supported_next_step": command_contract.get("advanced_supported_next_step"),
        },
        "container_runtime": {
            "dockerfile": "Dockerfile.runtime",
            "default_entrypoint": "sdetkit",
            "example_contract_check": (
                'docker run --rm -v "$PWD":/workspace -w /workspace sdetkit-runtime '
                "contract runtime --format json"
            ),
            "example_review_operator_json": (
                'docker run --rm -v "$PWD":/workspace -w /workspace sdetkit-runtime '
                "review . --no-workspace --format operator-json"
            ),
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"runtime_contract_version: {payload['runtime_contract_version']}",
        f"tool: {payload['tool']['name']}@{payload['tool']['version']}",
        "install:",
        f"  {payload['recommended_install']['pip_git']}",
        f"  {payload['recommended_install']['verify']}",
        "canonical_first_path:",
    ]
    for step in payload.get("canonical_first_path", []):
        lines.append(f"  - {step}")
    review_out = payload["stable_machine_outputs"]["review_operator_json"]
    lines.extend(
        [
            "stable_machine_output:",
            f"  command: {review_out['command']}",
            f"  contract_version: {review_out['contract_version']}",
            "container_runtime:",
            f"  dockerfile: {payload['container_runtime']['dockerfile']}",
            f"  entrypoint: {payload['container_runtime']['default_entrypoint']}",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SDETKit runtime/integration contracts")
    sub = parser.add_subparsers(dest="action", required=True)

    runtime = sub.add_parser(
        "runtime", help="Show adopter-focused install/run integration contract"
    )
    runtime.add_argument("--format", choices=["text", "json"], default="text")
    runtime.add_argument("--repo-root", default=".")

    ns = parser.parse_args(argv)
    if ns.action != "runtime":
        return 2

    payload = _runtime_payload(Path(ns.repo_root).resolve())
    if ns.format == "json":
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))
    else:
        print(_render_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
