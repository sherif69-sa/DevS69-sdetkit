from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_MANIFEST_PATH = "docs/roadmap/manifest.json"
_SDETKIT_SRC = "src/sdetkit"
_CONTRACT_SCRIPTS_DIR = "scripts"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit upgrade-hub",
        description=(
            "Deep-dig the roadmap manifest and surface a single consolidated upgrade hub "
            "for high-load repositories."
        ),
    )
    parser.add_argument("--root", default=".", help="Repository root containing docs/roadmap.")
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Number of high-signal hidden feature lanes to include.",
    )
    return parser


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / _MANIFEST_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _discover_closeout_modules(root: Path) -> list[str]:
    src = root / _SDETKIT_SRC
    if not src.exists():
        return []
    return sorted(path.stem for path in src.glob("*closeout*.py") if path.is_file())


def _discover_contract_scripts(root: Path) -> list[str]:
    scripts = root / _CONTRACT_SCRIPTS_DIR
    if not scripts.exists():
        return []
    return sorted(path.name for path in scripts.glob("check_*contract*.py") if path.is_file())


def _discover_cli_visibility() -> dict[str, Any]:
    # Lazy import to avoid module-import cycles at import time.
    from . import cli

    parser, _ = cli._build_root_parser(show_hidden_commands=True)

    def _choices(parser: argparse.ArgumentParser) -> set[str]:
        for action in parser._actions:
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                return set(choices.keys())
        return set()

    all_choices = _choices(parser)
    hidden = sorted(name for name in all_choices if cli._is_hidden_cmd(name))
    visible = sorted(name for name in all_choices if not cli._is_hidden_cmd(name))

    return {
        "visible_count": len(visible),
        "all_count": len(all_choices),
        "hidden_count": len(hidden),
        "hidden_commands_sample": hidden[:15],
        "visible_commands_sample": visible[:15],
    }


def _discover_playbook_coverage() -> dict[str, Any]:
    from . import playbooks_cli

    cmd_to_mod, _ = playbooks_cli._build_registry(playbooks_cli._pkg_dir())
    promoted = sorted(
        cmd
        for cmd in cmd_to_mod
        if not cmd.startswith('')
        and not cmd.startswith("impact")
        and "_closeout" not in cmd
        and "-closeout-" not in cmd
    )
    recommended = sorted(playbooks_cli.RECOMMENDED_PLAYBOOKS)
    recommended_missing = sorted(cmd for cmd in recommended if cmd not in promoted)
    return {
        "promoted_playbooks": promoted,
        "promoted_playbooks_count": len(promoted),
        "recommended_count": len(recommended),
        "recommended_missing": recommended_missing,
        "promoted_sample": promoted[:20],
    }


def build_upgrade_hub_summary(root: str = ".", *, top: int = 8) -> dict[str, Any]:
    base = Path(root)
    data = _load_manifest(base)
    alignment = data.get("closeout_alignment", {})
    entries_raw = alignment.get("entries", []) if isinstance(alignment, dict) else []
    entries = [item for item in entries_raw if isinstance(item, dict)]

    lanes = Counter()
    hidden_candidates: list[dict[str, Any]] = []
    for item in entries:
        lane = item.get("lane")
        if isinstance(lane, str) and lane:
            lanes[lane] += 1

        contracts = int(item.get("contract_scripts", 0) or 0)
        tests = int(item.get("tests_referencing_module", 0) or 0)
        if contracts >= 2 or tests >= 2:
            hidden_candidates.append(
                {
                    "id": item.get("id"),
                    "lane": lane,
                    "module": item.get("module"),
                    "contract_scripts": contracts,
                    "tests_referencing_module": tests,
                }
            )

    hidden_candidates.sort(
        key=lambda item: (
            item["contract_scripts"],
            item["tests_referencing_module"],
            str(item["lane"]),
        ),
        reverse=True,
    )
    top_candidates = hidden_candidates[: max(1, top)]
    closeout_modules = _discover_closeout_modules(base)
    contract_scripts = _discover_contract_scripts(base)
    cli_visibility = _discover_cli_visibility()
    playbooks_coverage = _discover_playbook_coverage()

    module_by_lane: dict[str, list[str]] = {}
    for item in entries:
        lane = item.get("lane")
        module = item.get("module")
        if not isinstance(lane, str) or not lane:
            continue
        if not isinstance(module, str) or not module:
            continue
        module_by_lane.setdefault(lane, []).append(module)

    recommended_set = set(playbooks_coverage["promoted_playbooks"])
    integration_opportunities: list[dict[str, Any]] = []
    for lane, modules in sorted(module_by_lane.items()):
        cmd_name = lane.replace("_", "-")
        if cmd_name in recommended_set:
            continue
        if len(modules) < 2:
            continue
        integration_opportunities.append(
            {
                "lane": lane,
                "candidate_playbook_name": cmd_name,
                "module_count": len(modules),
                "modules_sample": modules[:5],
            }
        )
    integration_opportunities.sort(key=lambda item: item["module_count"], reverse=True)

    return {
        "name": "upgrade-hub",
        "manifest": _MANIFEST_PATH,
        "total_closeout_entries": len(entries),
        "repo_inventory": {
            "closeout_modules": len(closeout_modules),
            "contract_scripts": len(contract_scripts),
        },
        "cli_visibility": cli_visibility,
        "playbooks_coverage": playbooks_coverage,
        "lane_distribution": dict(sorted(lanes.items())),
        "high_signal_hidden_features": top_candidates,
        "integration_opportunities": integration_opportunities[: max(1, top)],
        "actions": {
            "roadmap_manifest": "python -m sdetkit roadmap manifest --format json",
            "playbooks_catalog": "python -m sdetkit playbooks list --recommended --format json",
            "show_hidden_commands": "python -m sdetkit --help --show-hidden",
            "upgrade_hub_json": "python -m sdetkit upgrade-hub --format json --top 15",
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Upgrade hub report",
        f"Manifest: {payload['manifest']}",
        f"Total closeout entries: {payload['total_closeout_entries']}",
        "Inventory: closeout_modules={closeout_modules} contract_scripts={contract_scripts}".format(
            closeout_modules=payload["repo_inventory"]["closeout_modules"],
            contract_scripts=payload["repo_inventory"]["contract_scripts"],
        ),
        "CLI visibility: visible={visible_count} all={all_count} hidden={hidden_count}".format(
            visible_count=payload["cli_visibility"]["visible_count"],
            all_count=payload["cli_visibility"]["all_count"],
            hidden_count=payload["cli_visibility"]["hidden_count"],
        ),
        "",
        "Lane distribution:",
    ]
    for lane, count in payload["lane_distribution"].items():
        lines.append(f"- {lane}: {count}")
    lines.extend(["", "High-signal hidden features:"])
    for item in payload["high_signal_hidden_features"]:
        lines.append(
            "- id={id} lane={lane} module={module} contracts={contract_scripts} tests={tests}".format(
                id=item.get("id"),
                lane=item.get("lane"),
                module=item.get("module"),
                contract_scripts=item.get("contract_scripts"),
                tests=item.get("tests_referencing_module"),
            )
        )
    lines.extend(["", "Integration opportunities:"])
    for item in payload["integration_opportunities"]:
        lines.append(
            "- lane={lane} candidate={candidate} modules={count}".format(
                lane=item["lane"],
                candidate=item["candidate_playbook_name"],
                count=item["module_count"],
            )
        )
    lines.extend(["", "Actions:"])
    for _, cmd in payload["actions"].items():
        lines.append(f"- {cmd}")
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Upgrade hub report",
        "",
        f"- Manifest: `{payload['manifest']}`",
        f"- Total closeout entries: **{payload['total_closeout_entries']}**",
        (
            "- Inventory: closeout_modules={closeout_modules}, contract_scripts={contract_scripts}".format(
                closeout_modules=payload["repo_inventory"]["closeout_modules"],
                contract_scripts=payload["repo_inventory"]["contract_scripts"],
            )
        ),
        (
            "- CLI visibility: visible={visible_count}, all={all_count}, hidden={hidden_count}".format(
                visible_count=payload["cli_visibility"]["visible_count"],
                all_count=payload["cli_visibility"]["all_count"],
                hidden_count=payload["cli_visibility"]["hidden_count"],
            )
        ),
        "",
        "## Lane distribution",
        "",
    ]
    for lane, count in payload["lane_distribution"].items():
        lines.append(f"- `{lane}`: {count}")
    lines.extend(["", "## High-signal hidden features", ""])
    for item in payload["high_signal_hidden_features"]:
        lines.append(
            "- `id={id}` `{lane}` `{module}` contracts={contract_scripts} tests={tests}".format(
                id=item.get("id"),
                lane=item.get("lane"),
                module=item.get("module"),
                contract_scripts=item.get("contract_scripts"),
                tests=item.get("tests_referencing_module"),
            )
        )
    lines.extend(["", "## Integration opportunities", ""])
    for item in payload["integration_opportunities"]:
        lines.append(
            "- `{lane}` -> candidate `{candidate}` (`{count}` modules)".format(
                lane=item["lane"],
                candidate=item["candidate_playbook_name"],
                count=item["module_count"],
            )
        )
    lines.extend(["", "## Actions", ""])
    for _, cmd in payload["actions"].items():
        lines.append(f"- `{cmd}`")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    payload = build_upgrade_hub_summary(args.root, top=args.top)

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.format == "markdown":
        print(_render_markdown(payload), end="")
        return 0
    print(_render_text(payload), end="")
    return 0
