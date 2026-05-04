from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.mission_control.doctor_cortex_trend.v1"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _load_records(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _bundle_from_record(record: dict[str, Any]) -> dict[str, Any]:
    artifact_dir = record.get("artifact_dir")
    if not isinstance(artifact_dir, str) or not artifact_dir:
        return {}
    bundle_path = Path(artifact_dir) / "mission-control.json"
    if not bundle_path.exists():
        return {}
    try:
        return _load_json(bundle_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _doctor_cortex_from(record: dict[str, Any]) -> dict[str, Any]:
    embedded = record.get("doctor_cortex")
    if isinstance(embedded, dict):
        return embedded

    bundle = _bundle_from_record(record)
    doctor_cortex = bundle.get("doctor_cortex")
    if isinstance(doctor_cortex, dict):
        return doctor_cortex

    return {}


def _sample_from_record(index: int, record: dict[str, Any]) -> dict[str, Any] | None:
    doctor_cortex = _doctor_cortex_from(record)
    if not doctor_cortex.get("enabled"):
        return None

    diagnosis = _as_dict(doctor_cortex.get("diagnosis"))
    prescriptions = _as_dict(doctor_cortex.get("prescriptions"))

    return {
        "index": index,
        "run_id": str(record.get("run_id", "")),
        "timestamp": str(record.get("timestamp", record.get("generated_at_utc", ""))),
        "decision": str(record.get("decision", "unknown")),
        "risk_band": str(record.get("risk_band", "unknown")),
        "ok": bool(doctor_cortex.get("ok", False)),
        "diagnosis_status": str(diagnosis.get("status", "unknown")),
        "diagnosis_severity": str(diagnosis.get("severity", "unknown")),
        "diagnosis_count": _as_int(diagnosis.get("diagnosis_count")),
        "prescription_status": str(prescriptions.get("status", "unknown")),
        "prescription_severity": str(prescriptions.get("severity", "unknown")),
        "prescription_count": _as_int(prescriptions.get("prescription_count")),
    }


def _trend_direction(samples: Sequence[dict[str, Any]], key: str) -> str:
    if len(samples) < 2:
        return "insufficient_data"
    previous = _as_int(samples[-2].get(key))
    current = _as_int(samples[-1].get(key))
    if current < previous:
        return "improving"
    if current > previous:
        return "regressing"
    return "stable"


def build_trend_payload(ledger_path: Path) -> dict[str, Any]:
    records = _load_records(ledger_path)
    samples = [
        sample
        for index, record in enumerate(records, start=1)
        for sample in [_sample_from_record(index, record)]
        if sample is not None
    ]

    latest = samples[-1] if samples else {}
    diagnosis_counts = [_as_int(sample.get("diagnosis_count")) for sample in samples]
    prescription_counts = [_as_int(sample.get("prescription_count")) for sample in samples]
    not_ok = [sample for sample in samples if not bool(sample.get("ok", False))]

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "workflow": "mission_control",
            "ledger_path": "[REDACTED]",
        },
        "runs": len(records),
        "doctor_cortex_runs": len(samples),
        "doctor_cortex_ok": len(samples) - len(not_ok),
        "doctor_cortex_not_ok": len(not_ok),
        "latest_run_id": str(latest.get("run_id", "")),
        "latest_timestamp": str(latest.get("timestamp", "")),
        "latest_decision": str(latest.get("decision", "")),
        "latest_risk_band": str(latest.get("risk_band", "")),
        "latest_doctor_cortex_ok": bool(latest.get("ok", False)) if samples else False,
        "latest_diagnosis_status": str(latest.get("diagnosis_status", "")),
        "latest_diagnosis_count": _as_int(latest.get("diagnosis_count")),
        "latest_prescription_status": str(latest.get("prescription_status", "")),
        "latest_prescription_count": _as_int(latest.get("prescription_count")),
        "max_diagnosis_count": max(diagnosis_counts) if diagnosis_counts else 0,
        "max_prescription_count": max(prescription_counts) if prescription_counts else 0,
        "diagnosis_trend": _trend_direction(samples, "diagnosis_count"),
        "prescription_trend": _trend_direction(samples, "prescription_count"),
        "samples": samples,
    }


def render_text(payload: dict[str, Any]) -> str:
    keys = [
        "schema_version",
        "runs",
        "doctor_cortex_runs",
        "doctor_cortex_ok",
        "doctor_cortex_not_ok",
        "latest_run_id",
        "latest_timestamp",
        "latest_decision",
        "latest_risk_band",
        "latest_doctor_cortex_ok",
        "latest_diagnosis_status",
        "latest_diagnosis_count",
        "latest_prescription_status",
        "latest_prescription_count",
        "max_diagnosis_count",
        "max_prescription_count",
        "diagnosis_trend",
        "prescription_trend",
    ]
    return "\n".join(f"{key}={payload.get(key, '')}" for key in keys)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mission Control Doctor Cortex Trend",
        "",
        f"- Runs: {payload.get('runs', 0)}",
        f"- Doctor Cortex runs: {payload.get('doctor_cortex_runs', 0)}",
        f"- Doctor Cortex OK: {payload.get('doctor_cortex_ok', 0)}",
        f"- Doctor Cortex not OK: {payload.get('doctor_cortex_not_ok', 0)}",
        f"- Latest run id: {payload.get('latest_run_id', '')}",
        f"- Latest decision: {payload.get('latest_decision', '')}",
        f"- Latest risk band: {payload.get('latest_risk_band', '')}",
        f"- Latest diagnosis status: {payload.get('latest_diagnosis_status', '')}",
        f"- Latest diagnosis count: {payload.get('latest_diagnosis_count', 0)}",
        f"- Latest prescription status: {payload.get('latest_prescription_status', '')}",
        f"- Latest prescription count: {payload.get('latest_prescription_count', 0)}",
        f"- Max diagnosis count: {payload.get('max_diagnosis_count', 0)}",
        f"- Max prescription count: {payload.get('max_prescription_count', 0)}",
        f"- Diagnosis trend: {payload.get('diagnosis_trend', 'insufficient_data')}",
        f"- Prescription trend: {payload.get('prescription_trend', 'insufficient_data')}",
        "",
        "## Samples",
        "",
    ]

    samples = _as_list(payload.get("samples"))
    if not samples:
        lines.append("- none")
    else:
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            lines.append(
                "- {run_id}: ok={ok} diagnosis_count={diagnosis_count} "
                "prescription_count={prescription_count}".format(
                    run_id=sample.get("run_id", ""),
                    ok=str(sample.get("ok", False)).lower(),
                    diagnosis_count=sample.get("diagnosis_count", 0),
                    prescription_count=sample.get("prescription_count", 0),
                )
            )

    return "\n".join(lines) + "\n"


def _render(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_format == "md":
        return render_markdown(payload)
    return render_text(payload) + "\n"


def write_output(payload: dict[str, Any], out_path: Path | None, *, output_format: str) -> None:
    rendered = _render(payload, output_format)

    if out_path is None:
        # Public summary only: no raw doctor evidence, raw fix text, command
        # lists, source paths, or artifact paths are emitted.
        # codeql[py/clear-text-logging-sensitive-data]
        sys.stdout.write(rendered)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Public summary only: no raw doctor evidence, raw fix text, command lists,
    # source paths, or artifact paths are emitted.
    # codeql[py/clear-text-storage-sensitive-data]
    out_path.write_text(rendered, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.mission_control_cortex_trend",
        description="Summarize Doctor Cortex trends from a Mission Control run ledger.",
    )
    parser.add_argument("--ledger-path", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv if argv is not None else sys.argv[1:]))

    try:
        payload = build_trend_payload(Path(args.ledger_path))
        write_output(
            payload,
            Path(args.out) if args.out else None,
            output_format=str(args.format),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
