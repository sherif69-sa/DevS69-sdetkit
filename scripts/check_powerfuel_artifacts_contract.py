#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from pathlib import Path

from powerfuel_common import artifact_path, dump_json, load_json

REQUIRED_TOP_LEVEL={"baseline":["date","status","generated_at","kpis","trigger_counts","workflow_trigger_map"],"shadow":["date","status","generated_at","summary","retirement_candidates"],"weekly":["date","status","generated_at","scoreboard","next_retirement_batch"],"retirement":["date","status","generated_at","batch"]}

def parse_args()->argparse.Namespace:
    p=argparse.ArgumentParser(description="Validate Powerfuel artifact contract")
    p.add_argument("--date-tag", default="2026-05-03")
    p.add_argument("--baseline", default=None)
    p.add_argument("--shadow", default=None)
    p.add_argument("--weekly", default=None)
    p.add_argument("--retirement", default=None)
    p.add_argument("--out", default=None)
    return p.parse_args()

def main()->int:
    args=parse_args()
    artifacts={"baseline":Path(args.baseline) if args.baseline else artifact_path("baseline", args.date_tag),"shadow":Path(args.shadow) if args.shadow else artifact_path("shadow", args.date_tag),"weekly":Path(args.weekly) if args.weekly else artifact_path("weekly", args.date_tag),"retirement":Path(args.retirement) if args.retirement else artifact_path("retirement", args.date_tag)}
    result={"status":"pass","checks":{}}
    for key,path in artifacts.items():
        payload=load_json(path)
        missing=[k for k in REQUIRED_TOP_LEVEL[key] if k not in payload]
        result["checks"][key]={"path":str(path),"missing_fields":missing,"pass":len(missing)==0}
        if missing: result["status"]="fail"
    out=Path(args.out) if args.out else artifact_path("contract", args.date_tag)
    dump_json(out, result)
    print(f"wrote {out}")
    print("contract check passed" if result["status"]=="pass" else "contract check failed")
    return 0 if result["status"]=="pass" else 1

if __name__=="__main__":
    raise SystemExit(main())
