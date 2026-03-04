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


def _apply_search_list(xs: list[str], search: str | None) -> list[str]:
    if not search:
        return xs
    s = search.lower()
    return [x for x in xs if s in x.lower()]


def _apply_search_aliases(d: dict[str, str], search: str | None) -> dict[str, str]:
    if not search:
        return d
    s = search.lower()
    return {k: v for k, v in d.items() if (s in k.lower()) or (s in v.lower())}


def _counts(payload: dict[str, object]) -> dict[str, int]:
    out: dict[str, int] = {}
    for k in ["recommended", "legacy", "aliases", "playbooks"]:
        v = payload.get(k)
        if isinstance(v, list):
            out[k] = len(v)
        elif isinstance(v, dict):
            out[k] = len(v)
        else:
            out[k] = 0
    return out


def _list_payload(
    *,
    want_recommended: bool,
    want_legacy: bool,
    want_aliases: bool,
    search: str | None,
) -> dict[str, object]:
    pkg_dir = _pkg_dir()
    cmd_to_mod, alias_to_canonical = _build_registry(pkg_dir)

    recommended = [c for c in RECOMMENDED_PLAYBOOKS if c in cmd_to_mod]
    recommended = _apply_search_list(recommended, search)

    legacy: list[str] = []
    for c in cmd_to_mod.keys():
        if c in recommended:
            continue
        if c in alias_to_canonical:
            continue
        if c.startswith("day") or c.endswith("-closeout"):
            legacy.append(c)
    legacy = sorted(_apply_search_list(legacy, search))

    aliases = _apply_search_aliases(dict(sorted(alias_to_canonical.items())), search)
    all_names = sorted(_apply_search_list(sorted(cmd_to_mod.keys()), search))

    if want_recommended:
        payload: dict[str, object] = {
            "recommended": recommended,
            "legacy": [],
            "aliases": {},
            "playbooks": recommended,
        }
        payload["counts"] = _counts(payload)
        return payload

    if want_legacy:
        payload = {
            "recommended": [],
            "legacy": legacy,
            "aliases": {},
            "playbooks": legacy,
        }
        payload["counts"] = _counts(payload)
        return payload

    if want_aliases:
        alias_names = sorted(list(aliases.keys()))
        payload = {
            "recommended": [],
            "legacy": [],
            "aliases": aliases,
            "playbooks": alias_names,
        }
        payload["counts"] = _counts(payload)
        return payload

    payload = {
        "recommended": recommended,
        "legacy": legacy,
        "aliases": aliases,
        "playbooks": all_names,
    }
    payload["counts"] = _counts(payload)
    return payload


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
        for k, v in sorted(aliases.items()):
            print(f"  {k} -> {v}")
    print("")
    print("Run: sdetkit playbooks run <name>")
    print("Tip: these commands still run directly, e.g. sdetkit <name> --help")


def _cmd_list(ns: argparse.Namespace) -> int:
    payload = _list_payload(
        want_recommended=bool(getattr(ns, "recommended", False)),
        want_legacy=bool(getattr(ns, "legacy", False)),
        want_aliases=bool(getattr(ns, "aliases", False)),
        search=getattr(ns, "search", None),
    )

    fmt = getattr(ns, "format", "text")
    if fmt == "json":
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        return 0

    _print_text(payload)
    return 0


def _cmd_run(ns: argparse.Namespace) -> int:
    pkg_dir = _pkg_dir()
    cmd_to_mod, _alias_to_canonical = _build_registry(pkg_dir)

    name = getattr(ns, "name", "")
    if not isinstance(name, str) or name not in cmd_to_mod:
        sys.stderr.write("playbooks: unknown name\n")
        return 2

    mod_name = cmd_to_mod[name]
    m = import_module(f"sdetkit.{mod_name}")
    fn = getattr(m, "main", None)
    if not callable(fn):
        sys.stderr.write("playbooks: unknown name\n")
        return 2

    args = list(getattr(ns, "args", []) or [])
    if args and args[0] == "--":
        args = args[1:]
    return int(fn(args))


def _selected_playbooks(
    ns: argparse.Namespace,
    all_names: list[str],
    alias_to_canonical: dict[str, str],
) -> list[str]:
    if ns.all:
        return all_names
    if ns.recommended:
        return sorted([n for n in RECOMMENDED_PLAYBOOKS if n in all_names])
    if ns.legacy:
        return [n for n in all_names if n.startswith("day") or n.endswith("-closeout")]
    if ns.aliases:
        return sorted(alias_to_canonical.keys())

    explicit = sorted(set(ns.name or []))
    if explicit:
        return explicit
    return sorted([n for n in RECOMMENDED_PLAYBOOKS if n in all_names])


def _cmd_validate(ns: argparse.Namespace) -> int:
    pkg_dir = _pkg_dir()
    cmd_to_mod, alias_to_canonical = _build_registry(pkg_dir)
    all_names = sorted(cmd_to_mod.keys())
    selected = _selected_playbooks(ns, all_names, alias_to_canonical)

    for name in selected:
        if name not in cmd_to_mod:
            sys.stderr.write("playbooks: unknown name\n")
            return 2

    results: list[dict[str, object]] = []
    failed: list[str] = []
    for name in selected:
        mod_name = cmd_to_mod[name]
        error: str | None = None
        ok = True
        try:
            module = import_module(f"sdetkit.{mod_name}")
            fn = getattr(module, "main", None)
            if not callable(fn):
                ok = False
                error = "missing callable main"
        except Exception as exc:  # pragma: no cover - defensive fallback
            ok = False
            error = str(exc)
        if not ok:
            failed.append(name)
        results.append(
            {
                "name": name,
                "module": mod_name,
                "canonical": alias_to_canonical.get(name, name),
                "ok": ok,
                "error": error,
            }
        )

    payload = {
        "ok": not bool(failed),
        "counts": {"selected": len(selected), "failed": len(failed)},
        "failed": failed,
        "results": results,
    }

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    else:
        sys.stdout.write(f"playbooks validate: {'OK' if payload['ok'] else 'FAIL'}\n")
        for item in results:
            marker = "OK" if item["ok"] else "FAIL"
            sys.stdout.write(f"[{marker}] {item['name']} -> {item['module']}\n")

    return 0 if payload["ok"] else 2


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv:
        argv = ["list"]

    p = argparse.ArgumentParser(prog="sdetkit playbooks")
    sub = p.add_subparsers(dest="cmd", required=True)

    listp = sub.add_parser("list")
    listp.add_argument("--format", choices=["text", "json"], default="text")
    g = listp.add_mutually_exclusive_group()
    g.add_argument("--recommended", action="store_true")
    g.add_argument("--legacy", action="store_true")
    g.add_argument("--aliases", action="store_true")
    listp.add_argument("--search", default=None)
    listp.set_defaults(_handler=_cmd_list)

    runp = sub.add_parser("run")
    runp.add_argument("name")
    runp.add_argument("args", nargs=argparse.REMAINDER)
    runp.set_defaults(_handler=_cmd_run)

    validatep = sub.add_parser("validate")
    validatep.add_argument("--format", choices=["text", "json"], default="text")
    group = validatep.add_mutually_exclusive_group()
    group.add_argument("--recommended", action="store_true")
    group.add_argument("--legacy", action="store_true")
    group.add_argument("--aliases", action="store_true")
    group.add_argument("--all", action="store_true")
    validatep.add_argument("--name", action="append", default=[])
    validatep.set_defaults(_handler=_cmd_validate)

    ns = p.parse_args(argv)
    h = getattr(ns, "_handler", None)
    if not callable(h):
        return 2
    return int(h(ns))
