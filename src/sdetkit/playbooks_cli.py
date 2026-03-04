from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from importlib import import_module
from pathlib import Path

RECOMMENDED_PLAYBOOKS: list[str] = [
    "onboarding",
    "weekly-review",
    "proof",
    "demo",
    "first-contribution",
    "contributor-funnel",
    "triage-templates",
    "startup-use-case",
    "enterprise-use-case",
    "github-actions-quickstart",
    "gitlab-ci-quickstart",
    "quality-contribution-delta",
    "reliability-evidence-pack",
    "faq-objections",
    "community-activation",
    "external-contribution-push",
    "kpi-audit",
]

CORE_COMMANDS: set[str] = {
    "kv",
    "apiget",
    "cassette-get",
    "doctor",
    "gate",
    "ci",
    "patch",
    "repo",
    "dev",
    "report",
    "maintenance",
    "agent",
    "security",
    "ops",
    "notify",
}

DOC_AND_GOV_COMMANDS: set[str] = {
    "docs-qa",
    "docs-nav",
    "roadmap",
    "policy",
    "evidence",
    "release-narrative",
    "release-readiness-board",
    "trust-signal-upgrade",
}

RESERVED_NAMES: set[str] = (
    {"baseline", "playbooks"} | CORE_COMMANDS | DOC_AND_GOV_COMMANDS | set(RECOMMENDED_PLAYBOOKS)
)

_DAY_PREFIX = re.compile(r"^day\d+_")
_DAY_CLOSEOUT = re.compile(r"^day\d+_(.+_closeout)$")


def _cmd_to_mod(cmd: str) -> str:
    return cmd.replace("-", "_")


def _mod_to_cmd(mod: str) -> str:
    return mod.replace("_", "-")


def _pkg_dir() -> Path:
    import sdetkit

    return Path(sdetkit.__file__).resolve().parent


def _is_legacy_module(mod: str) -> bool:
    if _DAY_PREFIX.match(mod):
        return True
    if mod.endswith("_closeout"):
        return True
    return False


def _discover_legacy_modules(pkg_dir: Path) -> list[str]:
    mods: list[str] = []
    for p in pkg_dir.glob("*.py"):
        if not p.is_file():
            continue
        stem = p.stem
        if stem.startswith("__"):
            continue
        if stem in {"cli", "playbooks_cli"}:
            continue
        if _is_legacy_module(stem):
            mods.append(stem)
    return sorted(mods)


def _alias_for_day_closeout(mod: str) -> str | None:
    m = _DAY_CLOSEOUT.match(mod)
    if not m:
        return None
    alias_mod = m.group(1)
    alias_cmd = _mod_to_cmd(alias_mod)
    if alias_cmd in RESERVED_NAMES:
        return None
    return alias_cmd


def _build_registry(pkg_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    cmd_to_mod: dict[str, str] = {}
    alias_to_canonical: dict[str, str] = {}

    for cmd in RECOMMENDED_PLAYBOOKS:
        mod = _cmd_to_mod(cmd)
        if (pkg_dir / f"{mod}.py").exists():
            cmd_to_mod[cmd] = mod

    for mod in _discover_legacy_modules(pkg_dir):
        canonical = _mod_to_cmd(mod)
        cmd_to_mod[canonical] = mod

        alias = _alias_for_day_closeout(mod)
        if alias and alias not in cmd_to_mod:
            cmd_to_mod[alias] = mod
            alias_to_canonical[alias] = canonical

    return cmd_to_mod, alias_to_canonical


def _list_payload() -> dict[str, object]:
    pkg_dir = _pkg_dir()
    cmd_to_mod, alias_to_canonical = _build_registry(pkg_dir)

    recommended: list[str] = [c for c in RECOMMENDED_PLAYBOOKS if c in cmd_to_mod]

    legacy_canonical: list[str] = []
    for c in cmd_to_mod.keys():
        if c in recommended:
            continue
        if c in alias_to_canonical:
            continue
        if c.startswith("day") or c.endswith("-closeout"):
            legacy_canonical.append(c)
    legacy_canonical = sorted(legacy_canonical)

    all_names = sorted(cmd_to_mod.keys())

    return {
        "recommended": recommended,
        "legacy": legacy_canonical,
        "aliases": dict(sorted(alias_to_canonical.items())),
        "playbooks": all_names,
    }


def _print_text(payload: dict[str, object]) -> None:
    recommended = payload.get("recommended", [])
    legacy = payload.get("legacy", [])
    aliases = payload.get("aliases", {})

    print("Recommended playbooks:")
    if isinstance(recommended, list) and recommended:
        for n in recommended:
            print(f"  {n}")
    else:
        print("  (none)")

    print("")
    print("Legacy bootcamp flows:")
    if isinstance(legacy, list) and legacy:
        for n in legacy:
            print(f"  {n}")
    else:
        print("  (none)")

    if isinstance(aliases, dict) and aliases:
        print("")
        print("Aliases:")
        for a, c in sorted(aliases.items()):
            print(f"  {a} -> {c}")

    print("")
    print("Run: sdetkit playbooks run <name> [-- <args>]")


def _run_playbook(name: str, args: list[str]) -> int:
    pkg_dir = _pkg_dir()
    cmd_to_mod, _alias_to_canonical = _build_registry(pkg_dir)

    mod = cmd_to_mod.get(name)
    if not mod:
        print("playbooks: unknown name", file=sys.stderr)
        return 2

    m = import_module(f"sdetkit.{mod}")
    fn = getattr(m, "main", None)
    if not callable(fn):
        print("playbooks: unknown name", file=sys.stderr)
        return 2

    if args and args[0] == "--":
        args = args[1:]
    return int(fn(list(args)))


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser(prog="sdetkit playbooks")
    sub = p.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("list")
    lp.add_argument("--format", choices=["text", "json"], default="text")

    rp = sub.add_parser("run")
    rp.add_argument("name")
    rp.add_argument("args", nargs=argparse.REMAINDER)

    argv = list(argv)
    if not argv:
        argv = ["list"]
    ns = p.parse_args(list(argv))

    if ns.cmd == "list":
        payload = _list_payload()
        if ns.format == "json":
            sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
            return 0
        _print_text(payload)
        return 0

    if ns.cmd == "run":
        return _run_playbook(str(ns.name), list(ns.args))

    return 2
