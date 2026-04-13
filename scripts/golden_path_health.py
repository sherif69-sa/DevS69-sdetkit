from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_ok(path: Path) -> tuple[str, bool | None]:
    if not path.exists():
        return "missing", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "invalid-json", None
    ok = payload.get("ok")
    if isinstance(ok, bool):
        return "present", ok
    return "missing-ok", None


def _build_payload(gate_fast: Path, gate_release: Path, doctor: Path) -> dict[str, Any]:
    checks = {
        "gate_fast": {"path": str(gate_fast)},
        "gate_release": {"path": str(gate_release)},
        "doctor": {"path": str(doctor)},
    }
    for key, path in (
        ("gate_fast", gate_fast),
        ("gate_release", gate_release),
        ("doctor", doctor),
    ):
        state, ok = _load_ok(path)
        checks[key]["state"] = state
        checks[key]["ok"] = ok

    all_states_present = all(item["state"] == "present" for item in checks.values())
    all_ok = all(item["ok"] is True for item in checks.values())
    return {
        "schema_version": "1",
        "canonical_path": ["gate fast", "gate release", "doctor"],
        "overall_ok": bool(all_states_present and all_ok),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/golden_path_health.py")
    parser.add_argument("--gate-fast", default="build/gate-fast.json")
    parser.add_argument("--gate-release", default="build/release-preflight.json")
    parser.add_argument("--doctor", default="build/doctor.json")
    parser.add_argument("--out", default=".sdetkit/out/golden-path-health.json")
    ns = parser.parse_args(argv)

    payload = _build_payload(
        gate_fast=Path(ns.gate_fast),
        gate_release=Path(ns.gate_release),
        doctor=Path(ns.doctor),
    )
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["overall_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
