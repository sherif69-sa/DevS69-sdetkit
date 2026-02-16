from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import doctor_agent, history_agent, init_agent, run_agent


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit agent")
    sub = parser.add_subparsers(dest="agent_cmd", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--config", default=".sdetkit/agent/config.yaml")

    run_p = sub.add_parser("run")
    run_p.add_argument("task")
    run_p.add_argument("--config", default=".sdetkit/agent/config.yaml")
    run_p.add_argument("--approve", action="store_true", help="Auto-approve dangerous actions.")
    run_p.add_argument("--cache-dir", default=".sdetkit/agent/cache")
    run_p.add_argument("--no-cache", action="store_true")

    doctor_p = sub.add_parser("doctor")
    doctor_p.add_argument("--config", default=".sdetkit/agent/config.yaml")

    hist_p = sub.add_parser("history")
    hist_p.add_argument("--limit", type=int, default=10)

    ns = parser.parse_args(argv)
    root = Path.cwd()

    if ns.agent_cmd == "init":
        created = init_agent(root, root / ns.config)
        sys.stdout.write(json.dumps({"created": created}, ensure_ascii=True, sort_keys=True) + "\n")
        return 0

    if ns.agent_cmd == "run":
        record = run_agent(
            root,
            config_path=root / ns.config,
            task=ns.task,
            auto_approve=bool(ns.approve),
            cache_dir=root / ns.cache_dir,
            no_cache=bool(ns.no_cache),
        )
        sys.stdout.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        return 0 if record.get("status") == "ok" else 1

    if ns.agent_cmd == "doctor":
        doctor_payload = doctor_agent(root, config_path=root / ns.config)
        sys.stdout.write(json.dumps(doctor_payload, ensure_ascii=True, sort_keys=True) + "\n")
        return 0 if doctor_payload.get("ok") else 1

    if ns.agent_cmd == "history":
        history_payload = history_agent(root, limit=ns.limit)
        sys.stdout.write(json.dumps(history_payload, ensure_ascii=True, sort_keys=True) + "\n")
        return 0

    return 2
