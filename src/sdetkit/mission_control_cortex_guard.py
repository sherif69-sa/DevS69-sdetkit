from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit import mission_control_cortex_trend

SCHEMA_VERSION = "sdetkit.mission_control.doctor_cortex_guard.v1"


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


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a non-negative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer")
    return parsed


def _safe_samples(payload: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for sample in _as_list(payload.get("samples")):
        if isinstance(sample, dict):
            samples.append(sample)
    return samples


def _safe_status(value: Any) -> str:
    candidate = str(value or "insufficient_data")
    allowed = {"pass", "warn", "fail", "insufficient_data"}
    return candidate if candidate in allowed else "insufficient_data"


def _recommendation(status: str) -> str:
    recommendations = {
        "pass": "Doctor Cortex counts did not regress versus the previous run.",
        "warn": "Doctor Cortex counts regressed within the configured threshold; review before release.",
        "fail": "Doctor Cortex counts regressed beyond the configured threshold; investigate before release.",
        "insufficient_data": "Collect at least two Doctor Cortex Mission Control runs before evaluating regression.",
    }
    return recommendations[_safe_status(status)]


def _guard_status(
    diagnosis_delta: int,
    prescription_delta: int,
    *,
    max_diagnosis_regression: int,
    max_prescription_regression: int,
) -> str:
    if diagnosis_delta <= 0 and prescription_delta <= 0:
        return "pass"
    if diagnosis_delta > max_diagnosis_regression:
        return "fail"
    if prescription_delta > max_prescription_regression:
        return "fail"
    return "warn"


def _public_output_payload(payload: dict[str, Any]) -> dict[str, Any]:
    status = _safe_status(payload.get("status"))
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(payload.get("ok", False)),
        "status": status,
        "runs": _as_int(payload.get("runs")),
        "doctor_cortex_runs": _as_int(payload.get("doctor_cortex_runs")),
        "latest_diagnosis_count": _as_int(payload.get("latest_diagnosis_count")),
        "previous_diagnosis_count": _as_int(payload.get("previous_diagnosis_count")),
        "diagnosis_delta": _as_int(payload.get("diagnosis_delta")),
        "latest_prescription_count": _as_int(payload.get("latest_prescription_count")),
        "previous_prescription_count": _as_int(payload.get("previous_prescription_count")),
        "prescription_delta": _as_int(payload.get("prescription_delta")),
        "max_diagnosis_regression": _as_int(payload.get("max_diagnosis_regression")),
        "max_prescription_regression": _as_int(payload.get("max_prescription_regression")),
        "recommendation": _recommendation(status),
    }


def build_guard_payload(
    ledger_path: Path,
    *,
    max_diagnosis_regression: int = 0,
    max_prescription_regression: int = 0,
) -> dict[str, Any]:
    trend_payload = mission_control_cortex_trend.build_trend_payload(ledger_path)
    samples = _safe_samples(trend_payload)
    max_diagnosis_regression = max(0, max_diagnosis_regression)
    max_prescription_regression = max(0, max_prescription_regression)
    base_payload = {
        "runs": _as_int(trend_payload.get("runs")),
        "doctor_cortex_runs": _as_int(trend_payload.get("doctor_cortex_runs")),
        "max_diagnosis_regression": max_diagnosis_regression,
        "max_prescription_regression": max_prescription_regression,
    }

    if len(samples) < 2:
        latest = samples[-1] if samples else {}
        return _public_output_payload(
            {
                **base_payload,
                "ok": True,
                "status": "insufficient_data",
                "latest_diagnosis_count": _as_int(latest.get("diagnosis_count")),
                "previous_diagnosis_count": 0,
                "diagnosis_delta": 0,
                "latest_prescription_count": _as_int(latest.get("prescription_count")),
                "previous_prescription_count": 0,
                "prescription_delta": 0,
            }
        )

    previous = samples[-2]
    latest = samples[-1]
    previous_diagnosis_count = _as_int(previous.get("diagnosis_count"))
    latest_diagnosis_count = _as_int(latest.get("diagnosis_count"))
    previous_prescription_count = _as_int(previous.get("prescription_count"))
    latest_prescription_count = _as_int(latest.get("prescription_count"))
    diagnosis_delta = latest_diagnosis_count - previous_diagnosis_count
    prescription_delta = latest_prescription_count - previous_prescription_count
    status = _guard_status(
        diagnosis_delta,
        prescription_delta,
        max_diagnosis_regression=max_diagnosis_regression,
        max_prescription_regression=max_prescription_regression,
    )

    return _public_output_payload(
        {
            **base_payload,
            "ok": status != "fail",
            "status": status,
            "latest_diagnosis_count": latest_diagnosis_count,
            "previous_diagnosis_count": previous_diagnosis_count,
            "diagnosis_delta": diagnosis_delta,
            "latest_prescription_count": latest_prescription_count,
            "previous_prescription_count": previous_prescription_count,
            "prescription_delta": prescription_delta,
        }
    )


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def render_text(payload: dict[str, Any]) -> str:
    public_payload = _public_output_payload(payload)
    keys = [
        "schema_version",
        "ok",
        "status",
        "runs",
        "doctor_cortex_runs",
        "latest_diagnosis_count",
        "previous_diagnosis_count",
        "diagnosis_delta",
        "latest_prescription_count",
        "previous_prescription_count",
        "prescription_delta",
        "max_diagnosis_regression",
        "max_prescription_regression",
        "recommendation",
    ]
    return "\n".join(f"{key}={_format_value(public_payload.get(key, ''))}" for key in keys)


def render_markdown(payload: dict[str, Any]) -> str:
    public_payload = _public_output_payload(payload)
    lines = [
        "# Mission Control Doctor Cortex Guard",
        "",
        f"- Status: {public_payload['status']}",
        f"- OK: {_format_value(public_payload['ok'])}",
        f"- Runs: {public_payload['runs']}",
        f"- Doctor Cortex runs: {public_payload['doctor_cortex_runs']}",
        f"- Latest diagnosis count: {public_payload['latest_diagnosis_count']}",
        f"- Previous diagnosis count: {public_payload['previous_diagnosis_count']}",
        f"- Diagnosis delta: {public_payload['diagnosis_delta']}",
        f"- Latest prescription count: {public_payload['latest_prescription_count']}",
        f"- Previous prescription count: {public_payload['previous_prescription_count']}",
        f"- Prescription delta: {public_payload['prescription_delta']}",
        f"- Max diagnosis regression: {public_payload['max_diagnosis_regression']}",
        f"- Max prescription regression: {public_payload['max_prescription_regression']}",
        f"- Recommendation: {public_payload['recommendation']}",
        "",
    ]
    return "\n".join(lines)


def _render(payload: dict[str, Any], output_format: str) -> str:
    public_payload = _public_output_payload(payload)
    if output_format == "json":
        return json.dumps(public_payload, indent=2, sort_keys=True) + "\n"
    if output_format == "md":
        return render_markdown(public_payload) + "\n"
    return render_text(public_payload) + "\n"


def write_output(payload: dict[str, Any], out_path: Path | None, *, output_format: str) -> None:
    rendered = _render(payload, output_format)

    if out_path is None:
        sys.stdout.write(rendered)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.mission_control_cortex_guard",
        description="Guard Doctor Cortex counts against the previous Mission Control run.",
    )
    parser.add_argument("--ledger-path", required=True)
    parser.add_argument("--max-diagnosis-regression", type=_non_negative_int, default=0)
    parser.add_argument("--max-prescription-regression", type=_non_negative_int, default=0)
    parser.add_argument("--out", default="")
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv if argv is not None else sys.argv[1:]))

    try:
        payload = build_guard_payload(
            Path(args.ledger_path),
            max_diagnosis_regression=args.max_diagnosis_regression,
            max_prescription_regression=args.max_prescription_regression,
        )
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
