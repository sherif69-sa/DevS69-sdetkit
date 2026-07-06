"""CLI package compatibility wrappers."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

from ..versioning import tool_version

# Exposed for compatibility: tests and downstream callers monkeypatch these names.
__all__ = ["import_module", "tool_version", "_run_module_main", "main"]


def _normalize_professional_command_aliases(argv: list[str]) -> list[str]:
    normalized = list(argv)
    if normalized and normalized[0] == "example":
        normalized[0] = "demo"
    return normalized


def _split_doctor_report_contract_args(
    argv: list[str],
) -> tuple[bool, str, str | None, list[str]]:
    enabled = False
    output_format = "text"
    out_path: str | None = None
    inner: list[str] = []

    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--report-contract":
            enabled = True
            index += 1
            continue
        if token == "--json":
            output_format = "json"
            index += 1
            continue
        if token == "--format":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            output_format = argv[index + 1]
            index += 2
            continue
        if token.startswith("--format="):
            output_format = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--out":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            out_path = argv[index + 1]
            index += 2
            continue
        if token.startswith("--out="):
            out_path = token.split("=", 1)[1]
            index += 1
            continue
        inner.append(token)
        index += 1

    return enabled, output_format, out_path, inner


def _run_doctor_report_contract(argv: list[str]) -> int | None:
    if not argv or argv[0] != "doctor":
        return None

    enabled, output_format, out_path, inner = _split_doctor_report_contract_args(argv[1:])
    if not enabled:
        return None

    if output_format == "markdown":
        output_format = "md"
    if output_format not in {"text", "json", "md"}:
        print(
            "doctor: error: --report-contract supports --format text, json, md, or markdown",
            file=sys.stderr,
        )
        raise SystemExit(2)

    from .. import doctor as doctor_module
    from ..doctor_report import build_doctor_report_contract, render_doctor_report_markdown

    doctor_args = [*inner, "--format", "json"]
    if "--no-workspace" not in inner:
        doctor_args.append("--no-workspace")

    captured = io.StringIO()
    with redirect_stdout(captured):
        rc = int(doctor_module.main(doctor_args))

    raw = captured.getvalue()
    try:
        doctor_payload = json.loads(raw)
    except json.JSONDecodeError:
        print("doctor: error: could not build report contract from doctor JSON", file=sys.stderr)
        return rc if rc else 2

    contract = build_doctor_report_contract(doctor_payload)
    if output_format == "json":
        output = json.dumps(contract, sort_keys=True) + "\n"
    else:
        output = render_doctor_report_markdown(contract)

    if out_path:
        Path(out_path).write_text(output, encoding="utf-8")
    sys.stdout.write(output)
    return rc


def _load_legacy_cli_module() -> ModuleType:
    cached = getattr(_load_legacy_cli_module, "_cached_module", None)
    if isinstance(cached, ModuleType):
        return cached
    module_path = Path(__file__).resolve().parent.parent / "_legacy_cli.py"
    spec = importlib.util.spec_from_file_location("sdetkit._legacy_cli_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CLI module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "_sdetkit_orig_run_module_main"):
        module._sdetkit_orig_run_module_main = module._run_module_main
    _load_legacy_cli_module._cached_module = module
    return module


def _sync_compat_bindings(module: Any) -> None:
    """Keep compatibility-layer monkeypatch targets wired into legacy module."""
    module.import_module = import_module
    module.tool_version = tool_version


def _run_module_main(module_name: str, args: Sequence[str]) -> int:
    module = _load_legacy_cli_module()
    _sync_compat_bindings(module)
    return int(module._sdetkit_orig_run_module_main(module_name, list(args)))


def __getattr__(name: str):
    module = _load_legacy_cli_module()
    _sync_compat_bindings(module)
    return getattr(module, name)


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = list(sys.argv[1:])
    else:
        argv = list(argv)
    report_contract_rc = _run_doctor_report_contract(argv)
    if report_contract_rc is not None:
        return report_contract_rc
    argv = _normalize_professional_command_aliases(argv)
    module = _load_legacy_cli_module()
    _sync_compat_bindings(module)
    module._run_module_main = globals().get("_run_module_main", _run_module_main)
    return int(module.main(argv))
