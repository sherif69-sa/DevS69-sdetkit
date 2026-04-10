from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _build_summary(artifact_dir: Path) -> dict[str, Any]:
    gate = _read_json(artifact_dir / "gate-fast.json")
    doctor = _read_json(artifact_dir / "doctor.json")
    security = _read_json(artifact_dir / "security-enforce.json")
    package_validate = _read_json(artifact_dir / "package-validate.json")

    gate_ok = gate.get("ok") if gate else None
    doctor_ok = doctor.get("ok") if doctor else None
    security_ok = security.get("ok") if security else None
    package_ok = package_validate.get("ok") if package_validate else None

    checks = {
        "gate_fast": {
            "present": gate is not None,
            "ok": gate_ok,
            "failed_steps": gate.get("failed_steps", []) if gate else [],
        },
        "doctor": {
            "present": doctor is not None,
            "ok": doctor_ok,
            "score": doctor.get("score") if doctor else None,
        },
        "security": {
            "present": security is not None,
            "ok": security_ok,
            "max_error": security.get("max_error") if security else None,
            "max_warn": security.get("max_warn") if security else None,
        },
        "package_validate": {
            "present": package_validate is not None,
            "ok": package_ok,
            "note": "Produced by package-validate job when available.",
        },
    }

    hard_fail = gate_ok is False or security_ok is False
    status = "fail" if hard_fail else "pass"

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "checks": checks,
    }


def _render_markdown(summary: dict[str, Any]) -> str:
    checks = summary["checks"]
    lines = [
        "# CI Operator Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Overall status: **{summary['status'].upper()}**",
        "",
        "| Check | Present | OK | Notes |",
        "| --- | --- | --- | --- |",
    ]
    lines.append(
        f"| gate_fast | {checks['gate_fast']['present']} | {checks['gate_fast']['ok']} | failed_steps={checks['gate_fast']['failed_steps']} |"
    )
    lines.append(
        f"| doctor | {checks['doctor']['present']} | {checks['doctor']['ok']} | score={checks['doctor']['score']} |"
    )
    lines.append(
        f"| security | {checks['security']['present']} | {checks['security']['ok']} | max_error={checks['security']['max_error']}, max_warn={checks['security']['max_warn']} |"
    )
    lines.append(
        f"| package_validate | {checks['package_validate']['present']} | {checks['package_validate']['ok']} | {checks['package_validate']['note']} |"
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build unified CI summary artifacts.")
    parser.add_argument("--artifact-dir", default="build")
    parser.add_argument("--out-json", default="build/ci-summary.json")
    parser.add_argument("--out-md", default="build/ci-summary.md")
    ns = parser.parse_args(argv)

    artifact_dir = Path(ns.artifact_dir)
    summary = _build_summary(artifact_dir)

    out_json = Path(ns.out_json)
    out_md = Path(ns.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(summary, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_render_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
