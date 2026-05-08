from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.integration_adapter_contract.v1"
PROVIDERS = {"github-actions", "gitlab", "jenkins", "local"}
REQUIRED_INPUTS = ("adaptive_diagnosis_json", "operator_brief_md")
OPTIONAL_INPUTS = ("fix_audit_jsonl", "portfolio_rollup_json", "enterprise_governance_json")
UPLOAD_TARGETS = {
    "github-actions": "actions-artifact",
    "gitlab": "job-artifacts",
    "jenkins": "archiveArtifacts",
    "local": "filesystem",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _artifact_map(payload: dict[str, Any]) -> dict[str, str]:
    raw = _as_dict(payload.get("artifacts", payload))
    return {str(key): str(value) for key, value in raw.items() if str(value).strip()}


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_adapter_contract(
    *, provider: str, artifacts: dict[str, str], root: Path | None = None
) -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {', '.join(sorted(PROVIDERS))}")
    base = root or Path.cwd()
    normalized: dict[str, str] = {}
    missing: list[str] = []
    present: list[str] = []
    for name in (*REQUIRED_INPUTS, *OPTIONAL_INPUTS):
        value = artifacts.get(name, "")
        if not value:
            if name in REQUIRED_INPUTS:
                missing.append(name)
            continue
        path = _resolve(base, value)
        normalized[name] = path.as_posix()
        if path.exists():
            present.append(name)
        elif name in REQUIRED_INPUTS:
            missing.append(name)
    outputs = {
        "upload_target": UPLOAD_TARGETS[provider],
        "artifact_names": [
            name for name in (*REQUIRED_INPUTS, *OPTIONAL_INPUTS) if name in normalized
        ],
        "local_retention_dir": (base / "build" / "sdetkit").as_posix(),
    }
    ok = not missing
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "provider": provider,
        "required_inputs": list(REQUIRED_INPUTS),
        "optional_inputs": list(OPTIONAL_INPUTS),
        "present_inputs": present,
        "missing_inputs": missing,
        "normalized_artifacts": normalized,
        "outputs": outputs,
        "recommendation": "READY" if ok else "BLOCKED",
        "next_owner_action": "Adapter contract is ready for CI artifact upload."
        if ok
        else "Generate the missing adaptive artifacts before running this adapter.",
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"provider={payload['provider']}",
        f"recommendation={payload['recommendation']}",
        f"missing_inputs={','.join(payload.get('missing_inputs', []))}",
        f"upload_target={_as_dict(payload.get('outputs')).get('upload_target')}",
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_integration_adapters")
    sub = parser.add_subparsers(dest="cmd", required=True)
    validate = sub.add_parser("validate", help="Validate adaptive integration adapter artifacts")
    validate.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    validate.add_argument(
        "--artifacts", required=True, help="JSON file containing artifact path map"
    )
    validate.add_argument("--root", default=".")
    validate.add_argument("--format", choices=["text", "json"], default="text")
    validate.add_argument("--out", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        artifact_map = _artifact_map(_load_json(Path(args.artifacts)))
        payload = validate_adapter_contract(
            provider=str(args.provider), artifacts=artifact_map, root=Path(args.root)
        )
        rendered = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_text(payload)
        )
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
