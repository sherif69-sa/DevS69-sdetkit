from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path
from typing import Protocol

from .notify_plugins import StdoutAdapter, TelegramAdapter, WhatsAppAdapter
from .plugin_system import discover


def _entrypoint_adapters() -> dict[str, NotifyAdapter]:
    out: dict[str, NotifyAdapter] = {}
    for ep in sorted(
        metadata.entry_points().select(group="sdetkit.notify_adapters"), key=lambda i: i.name
    ):
        try:
            loaded = ep.load()
            adapter = loaded() if callable(loaded) else loaded
            if hasattr(adapter, "name") and hasattr(adapter, "send"):
                out[str(adapter.name)] = adapter
        except Exception:
            continue
    return out


class NotifyAdapter(Protocol):
    name: str

    def send(self, args: argparse.Namespace) -> int:
        raise NotImplementedError


def _adapter_map() -> dict[str, NotifyAdapter]:
    adapters: dict[str, NotifyAdapter] = {
        "stdout": StdoutAdapter(),
        "telegram": TelegramAdapter(),
        "whatsapp": WhatsAppAdapter(),
    }
    adapters.update(_entrypoint_adapters())
    for record in discover("sdetkit.notify_adapters", "notify", Path.cwd()):
        try:
            plugin = record.factory()
            if hasattr(plugin, "send") and hasattr(plugin, "name"):
                adapters[str(plugin.name)] = plugin
        except Exception:
            continue
    return dict(sorted(adapters.items()))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit notify")
    p.add_argument("adapter", nargs="?", help="Adapter name (stdout, telegram, whatsapp, etc.)")
    p.add_argument("--message", default="", help="Message payload")
    p.add_argument("--dry-run", action="store_true", help="Print only; do not send")
    p.add_argument(
        "--real-send", action="store_true", help="Send through the live adapter when configured"
    )
    p.add_argument(
        "--timeout", type=float, default=10.0, help="Network timeout for live adapter sends"
    )
    p.add_argument("--list", action="store_true", help="List discovered adapters")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    adapters = _adapter_map()

    if ns.list:
        sys.stdout.write("\n".join(sorted(adapters)) + "\n")
        return 0

    if not ns.adapter:
        parser.print_help()
        return 2

    adapter = adapters.get(ns.adapter)
    if adapter is None:
        sys.stdout.write(f"Adapter '{ns.adapter}' is not installed or not registered.\n")
        return 2

    if ns.dry_run:
        sys.stdout.write(f"[dry-run] adapter={ns.adapter} message={ns.message}\n")
        return 0

    return int(adapter.send(ns))
