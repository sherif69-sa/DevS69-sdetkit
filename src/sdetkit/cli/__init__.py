"""CLI package compatibility wrappers."""

from __future__ import annotations

import hashlib
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
) -> tuple[bool, str, str | None, str | None, str | None, list[str]]:
    enabled = False
    output_format = "text"
    out_path: str | None = None
    artifact_dir: str | None = None
    failure_vector_bundle_path: str | None = None
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
        if token == "--report-artifact-dir":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            artifact_dir = argv[index + 1]
            index += 2
            continue
        if token.startswith("--report-artifact-dir="):
            artifact_dir = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--failure-vector-bundle":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            failure_vector_bundle_path = argv[index + 1]
            index += 2
            continue
        if token.startswith("--failure-vector-bundle="):
            failure_vector_bundle_path = token.split("=", 1)[1]
            index += 1
            continue
        inner.append(token)
        index += 1

    return enabled, output_format, out_path, artifact_dir, failure_vector_bundle_path, inner


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_dumps_pretty(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def _load_failure_vector_bundle(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("FailureVector bundle must be a JSON object")
    return payload


def _write_doctor_report_artifact_bundle(
    artifact_dir: str,
    contract: dict[str, Any],
    json_output: str,
    markdown_output: str,
    failure_vector_bundle: dict[str, Any] | None = None,
) -> None:
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)

    outputs = {
        "json": {
            "path": "doctor-report.json",
            "sha256": _sha256_text(json_output),
        },
        "markdown": {
            "path": "doctor-report.md",
            "sha256": _sha256_text(markdown_output),
        },
    }
    failure_vector_output = None
    if failure_vector_bundle is not None:
        failure_vector_output = _json_dumps_pretty(failure_vector_bundle)
        outputs["failure_vector"] = {
            "path": "failure-vector.json",
            "sha256": _sha256_text(failure_vector_output),
        }

    manifest = {
        "schema_version": "sdetkit.doctor_report_artifact_bundle.v1",
        "report_schema_version": str(contract.get("schema_version", "")),
        "status": str(contract.get("status", "")),
        "outputs": outputs,
    }
    manifest_output = _json_dumps_pretty(manifest)

    (target / "doctor-report.json").write_text(json_output, encoding="utf-8")
    (target / "doctor-report.md").write_text(markdown_output, encoding="utf-8")
    if failure_vector_output is not None:
        (target / "failure-vector.json").write_text(failure_vector_output, encoding="utf-8")
    (target / "doctor-report-manifest.json").write_text(manifest_output, encoding="utf-8")


def _run_doctor_report_contract(argv: list[str]) -> int | None:
    if not argv or argv[0] != "doctor":
        return None

    (
        enabled,
        output_format,
        out_path,
        artifact_dir,
        failure_vector_bundle_path,
        inner,
    ) = _split_doctor_report_contract_args(argv[1:])
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

    failure_vector_bundle = None
    if failure_vector_bundle_path:
        try:
            failure_vector_bundle = _load_failure_vector_bundle(failure_vector_bundle_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"doctor: error: could not load FailureVector bundle: {exc}", file=sys.stderr)
            return 2

    contract = build_doctor_report_contract(
        doctor_payload,
        failure_vector_bundle=failure_vector_bundle,
    )
    json_output = json.dumps(contract, sort_keys=True) + "\n"
    markdown_output = render_doctor_report_markdown(contract)
    output = json_output if output_format == "json" else markdown_output

    if artifact_dir:
        _write_doctor_report_artifact_bundle(
            artifact_dir,
            contract,
            json_output,
            markdown_output,
            failure_vector_bundle=failure_vector_bundle,
        )
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
