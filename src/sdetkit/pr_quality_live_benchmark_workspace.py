from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pr_quality_live_benchmark_workspace.v1"
DEFAULT_FIXTURES_DIR = Path("tests") / "fixtures" / "remediation_benchmark"
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "live-benchmark" / "repositories"
MANIFEST_JSON = "workspace-manifest.json"
MANIFEST_MD = "workspace-manifest.md"

JsonObject = dict[str, Any]

SCENARIO_SETUP: tuple[tuple[str, str, str | None, str], ...] = (
    ("live_oracle_git_grounded.json", "oracle", None, "src/sdetkit/example.py"),
    (
        "live_inventory_claim_mismatch.json",
        "mismatch",
        None,
        "src/sdetkit/unplanned.py",
    ),
    (
        "live_proof_mutation.json",
        "mutation",
        "claimed_write",
        "src/sdetkit/example.py",
    ),
    (
        "live_network_boundary_required.json",
        "network",
        None,
        "src/sdetkit/example.py",
    ),
    (
        "live_unclaimed_write.json",
        "unclaimed",
        "unclaimed_write",
        "src/sdetkit/example.py",
    ),
    (
        "live_evidence_shadow.json",
        "shadow",
        "evidence_shadow",
        "src/sdetkit/example.py",
    ),
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )


def _read_scenario_type(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")

    scenario_type = str(payload.get("scenario_type") or "").strip()
    if not scenario_type:
        raise ValueError(f"scenario_type is required in {path}")
    return scenario_type


def _runtime_hook_script(hook_mode: str) -> str:
    if hook_mode == "claimed_write":
        return (
            "from pathlib import Path\n"
            'Path("src/sdetkit/example.py").write_text('
            '"VALUE = 99\\n", encoding="utf-8")\n'
        )

    if hook_mode == "unclaimed_write":
        return (
            "from pathlib import Path\n"
            'Path("src/sdetkit/injected.py").write_text('
            '"INJECTED = True\\n", encoding="utf-8")\n'
        )

    if hook_mode == "evidence_shadow":
        return (
            "import json\n"
            "from pathlib import Path\n"
            'root = Path("build") / "-".join(("isolated", "proof", "runner"))\n'
            'name = "-".join(("verification", "evidence")) + ".json"\n'
            "target = root / name\n"
            "target.parent.mkdir(parents=True, exist_ok=True)\n"
            'target.write_text(json.dumps({"status": "passed"}) + "\\n", encoding="utf-8")\n'
        )

    raise ValueError(f"unsupported hook mode: {hook_mode}")


def _initialize_repository(root: Path, *, hook_mode: str | None) -> None:
    if root.exists():
        shutil.rmtree(root)

    source = root / "src" / "sdetkit"
    tests = root / "tests"
    source.mkdir(parents=True)
    tests.mkdir()

    (source / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tests / "test_placeholder.py").write_text(
        "def test_placeholder() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    if hook_mode:
        tools = root / "tools"
        tools.mkdir()
        (tools / "runtime_hook.py").write_text(
            _runtime_hook_script(hook_mode),
            encoding="utf-8",
        )
        (root / ".pre-commit-config.yaml").write_text(
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: runtime-guard-probe\n"
            "        name: runtime guard probe\n"
            "        entry: python tools/runtime_hook.py\n"
            "        language: system\n"
            "        pass_filenames: false\n"
            "        always_run: true\n",
            encoding="utf-8",
        )

    _git(root, "init", "--quiet")
    _git(root, "config", "user.name", "PR Quality Live Benchmark")
    _git(root, "config", "user.email", "pr-quality-live-benchmark@invalid.local")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "baseline")


def _apply_candidate_change(root: Path, *, changed_path: str) -> None:
    target = root / changed_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 2\n", encoding="utf-8")


def prepare_live_benchmark_workspaces(
    *,
    out_dir: Path,
    fixtures_dir: Path = DEFAULT_FIXTURES_DIR,
) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios: list[JsonObject] = []

    for fixture_name, repo_name, hook_mode, changed_path in SCENARIO_SETUP:
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.exists():
            raise ValueError(f"missing live benchmark fixture: {fixture_path}")

        repo_root = out_dir / repo_name
        _initialize_repository(repo_root, hook_mode=hook_mode)
        _apply_candidate_change(repo_root, changed_path=changed_path)

        scenarios.append(
            {
                "fixture_path": fixture_path.as_posix(),
                "repo_name": repo_name,
                "repo_root": repo_root.as_posix(),
                "scenario_type": _read_scenario_type(fixture_path),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "boundary": {
            "writes_limited_to_output_directory": True,
            "source_checkout_code_modified": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def render_markdown(manifest: JsonObject) -> str:
    boundary = manifest["boundary"]
    lines = [
        "# PR Quality live benchmark workspace manifest",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Scenarios prepared: `{manifest['scenario_count']}`",
        "",
        "## Scenario repositories",
        "",
    ]

    for scenario in manifest["scenarios"]:
        lines.append(
            f"- `{scenario['scenario_type']}`: "
            f"repo=`{scenario['repo_name']}`, fixture=`{scenario['fixture_path']}`"
        )

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "- Writes limited to output directory: "
                f"`{str(boundary['writes_limited_to_output_directory']).lower()}`"
            ),
            (
                "- Source checkout code modified: "
                f"`{str(boundary['source_checkout_code_modified']).lower()}`"
            ),
            f"- Automation allowed: `{str(boundary['automation_allowed']).lower()}`",
            f"- Merge authorized: `{str(boundary['merge_authorized']).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(boundary['semantic_equivalence_proven']).lower()}`"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(manifest: JsonObject, *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / MANIFEST_JSON
    markdown_path = out_dir / MANIFEST_MD
    json_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(manifest), encoding="utf-8")
    return {
        "workspace_manifest_json": json_path.as_posix(),
        "workspace_manifest_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_live_benchmark_workspace")
    parser.add_argument("--fixtures-dir", type=Path, default=DEFAULT_FIXTURES_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        manifest = prepare_live_benchmark_workspaces(
            out_dir=args.out_dir,
            fixtures_dir=args.fixtures_dir,
        )
        artifacts = write_manifest(manifest, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": manifest["status"],
                    "scenario_count": manifest["scenario_count"],
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
