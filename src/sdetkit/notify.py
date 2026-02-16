from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Protocol, cast


class NotifyAdapter(Protocol):
    name: str

    def send(self, args: argparse.Namespace) -> int:
        raise NotImplementedError


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    factory: object


class _EntryPointLike(Protocol):
    name: str

    def load(self) -> Any:
        raise NotImplementedError


def _iter_entry_points() -> list[_EntryPointLike]:
    eps = metadata.entry_points()
    selected = eps.select(group="sdetkit.notify_adapters")
    return sorted(cast(list[_EntryPointLike], list(selected)), key=lambda item: item.name)


def load_adapter(name: str) -> NotifyAdapter | None:
    for ep in _iter_entry_points():
        if ep.name != name:
            continue
        factory = ep.load()
        adapter = factory() if callable(factory) else factory
        return cast(NotifyAdapter, adapter)
    return None


def available_adapters() -> list[str]:
    return [ep.name for ep in _iter_entry_points()]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit notify")
    p.add_argument("adapter", nargs="?", help="Adapter name (telegram, whatsapp, etc.)")
    p.add_argument("--message", default="", help="Message payload")
    p.add_argument("--dry-run", action="store_true", help="Print only; do not send")
    p.add_argument("--list", action="store_true", help="List discovered adapters")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)

    if ns.list:
        names = available_adapters()
        if not names:
            print(
                "No notify adapters installed. Install optional extras such as sdetkit[telegram]."
            )
            return 0
        print("\n".join(names))
        return 0

    if not ns.adapter:
        parser.print_help()
        return 2

    adapter = load_adapter(ns.adapter)
    if adapter is None:
        print(
            f"Adapter '{ns.adapter}' is not installed or not registered. "
            "Install optional extras (e.g., pip install sdetkit[telegram]) or add an "
            "entry point in group sdetkit.notify_adapters."
        )
        return 0

    if ns.dry_run:
        print(f"[dry-run] adapter={ns.adapter} message={ns.message}")
        return 0

    return int(adapter.send(ns))
