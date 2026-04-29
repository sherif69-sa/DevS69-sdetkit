from __future__ import annotations

import argparse
import json
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Check first-proof readiness threshold by profile.")
    p.add_argument("--dashboard", default="build/first-proof/dashboard.json")
    p.add_argument("--profiles", default="config/first_proof_readiness_profiles.json")
    p.add_argument("--profile", default="standard")
    p.add_argument("--out", default="build/first-proof/readiness-threshold.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    profiles = json.loads(Path(args.profiles).read_text(encoding="utf-8"))
    if args.profile not in profiles:
        raise SystemExit(f"unknown profile: {args.profile}")

    cfg = profiles[args.profile]
    errors: list[str] = []

    decision = str(dashboard.get("decision", "NO-DATA"))
    if decision != "SHIP":
        payload = {
            "ok": True,
            "profile": args.profile,
            "config": cfg,
            "errors": [],
            "enforced": False,
            "decision": decision,
            "note": "threshold gate skipped for non-SHIP decision",
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"readiness-threshold: profile={args.profile} skipped decision={decision}")
        return 0


    health_score = dashboard.get("health_score")
    if health_score is None or float(health_score) < float(cfg["min_health_score"]):
        errors.append(f"health_score<{cfg['min_health_score']}")

    if bool(cfg.get("require_followup_ready", False)) and not bool(dashboard.get("followup_ready", False)):
        errors.append("followup_ready_required")

    if bool(cfg.get("require_execution_contract_ok", False)) and not bool(
        dashboard.get("execution_contract_ok", False)
    ):
        errors.append("execution_contract_required")

    payload = {
        "ok": len(errors) == 0,
        "profile": args.profile,
        "config": cfg,
        "errors": errors,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"readiness-threshold: profile={args.profile} ok={payload['ok']} errors={len(errors)}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
