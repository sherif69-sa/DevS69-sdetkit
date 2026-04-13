from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module, metadata
from pathlib import Path
from typing import Any, cast

from . import _toml


@dataclass(frozen=True)
class PluginRecord:
    name: str
    source: str
    factory: Callable[[], Any]


def _load_ref(ref: str) -> Callable[[], Any]:
    module_name, _, attr = ref.partition(":")
    if not module_name or not attr:
        raise ValueError(f"invalid plugin reference: {ref}")
    module = import_module(module_name)
    factory = getattr(module, attr)
    if callable(factory):
        return cast(Callable[[], Any], factory)

    def _const() -> Any:
        return factory

    return _const


def _debug_enabled(debug: bool | None) -> bool:
    if debug is not None:
        return debug
    raw = str(os.environ.get("SDETKIT_PLUGIN_DEBUG", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _emit_discovery_error(
    *,
    source: str,
    group: str | None,
    section: str | None,
    name: str,
    ref: str | None,
    exc: Exception,
) -> None:
    payload = {
        "event": "plugin_discovery_load_failure",
        "source": source,
        "group": group,
        "section": section,
        "name": name,
        "ref": ref,
        "reason": f"{type(exc).__name__}: {exc}",
    }
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)


def _registry_entries(root: Path, section: str, *, debug: bool = False) -> list[PluginRecord]:
    path = root / ".sdetkit" / "plugins.toml"
    if not path.is_file():
        return []
    doc = _toml.loads(path.read_text(encoding="utf-8"))
    block = doc.get(section, {})
    if not isinstance(block, dict):
        return []
    out: list[PluginRecord] = []
    for name in sorted(block):
        ref = block[name]
        if not isinstance(ref, str):
            continue
        try:
            out.append(PluginRecord(name=name, source="registry", factory=_load_ref(ref)))
        except Exception as exc:
            if debug:
                _emit_discovery_error(
                    source="registry",
                    group=None,
                    section=section,
                    name=name,
                    ref=ref,
                    exc=exc,
                )
            continue
    return out


def discover(
    group: str,
    section: str,
    root: Path | None = None,
    *,
    debug: bool | None = None,
) -> list[PluginRecord]:
    plugin_debug = _debug_enabled(debug)
    records: list[PluginRecord] = []
    for ep in sorted(metadata.entry_points().select(group=group), key=lambda i: i.name):
        try:
            loaded = ep.load()
            if callable(loaded):
                factory = cast(Callable[[], Any], loaded)
            else:

                def _const(value: Any = loaded) -> Any:
                    return value

                factory = _const
            records.append(PluginRecord(name=ep.name, source="entrypoint", factory=factory))
        except Exception as exc:
            if plugin_debug:
                _emit_discovery_error(
                    source="entrypoint",
                    group=group,
                    section=section,
                    name=ep.name,
                    ref=None,
                    exc=exc,
                )
            continue
    if root is not None:
        records.extend(_registry_entries(root, section, debug=plugin_debug))
    dedup: dict[str, PluginRecord] = {}
    for record in records:
        dedup[record.name] = record
    return [dedup[name] for name in sorted(dedup)]
