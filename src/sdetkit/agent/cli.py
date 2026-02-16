from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import doctor_agent, history_agent, init_agent, run_agent
from .omnichannel import AgentServeApp
from .templates import (
    TemplateValidationError,
    discover_templates,
    pack_templates,
    parse_set_values,
    run_template,
    template_by_id,
)


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

    serve_p = sub.add_parser("serve")
    serve_p.add_argument("--config", default=".sdetkit/agent/config.yaml")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8787)
    serve_p.add_argument("--telegram-simulation-mode", action="store_true")
    serve_p.add_argument("--telegram-enable-outgoing", action="store_true")
    serve_p.add_argument("--rate-limit-max-tokens", type=int, default=5)
    serve_p.add_argument("--rate-limit-refill-per-second", type=float, default=1.0)
    serve_p.add_argument("--tool-bridge-enabled", action="store_true")
    serve_p.add_argument("--tool-bridge-allow", action="append", default=[])
    serve_p.add_argument("--tool-bridge-command", action="append", default=[])

    tpl = sub.add_parser("templates")
    tpl_sub = tpl.add_subparsers(dest="templates_cmd", required=True)

    tpl_sub.add_parser("list")

    tpl_show = tpl_sub.add_parser("show")
    tpl_show.add_argument("id")

    tpl_run = tpl_sub.add_parser("run")
    tpl_run.add_argument("id")
    tpl_run.add_argument("--set", dest="set_values", action="append", default=[])
    tpl_run.add_argument("--output-dir", default=".sdetkit/agent/template-runs")

    tpl_pack = tpl_sub.add_parser("pack")
    tpl_pack.add_argument("--output", default=".sdetkit/agent/templates/automation-templates.tar")

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

    if ns.agent_cmd == "serve":
        app = AgentServeApp(
            root=root,
            config_path=root / ns.config,
            host=ns.host,
            port=ns.port,
            telegram_simulation_mode=bool(ns.telegram_simulation_mode),
            telegram_enable_outgoing=bool(ns.telegram_enable_outgoing),
            capacity=int(ns.rate_limit_max_tokens),
            refill_per_second=float(ns.rate_limit_refill_per_second),
            tool_bridge_enabled=bool(ns.tool_bridge_enabled),
            tool_bridge_allowlist=tuple(str(x) for x in ns.tool_bridge_allow),
            tool_bridge_command=[str(x) for x in ns.tool_bridge_command],
        )
        sys.stdout.write(
            json.dumps(
                {
                    "status": "serving",
                    "host": ns.host,
                    "port": ns.port,
                    "tool_bridge_enabled": bool(ns.tool_bridge_enabled),
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            + "\n"
        )
        app.serve_forever()
        return 0

    if ns.agent_cmd == "templates":
        try:
            if ns.templates_cmd == "list":
                list_payload = [
                    {
                        "id": item.metadata["id"],
                        "title": item.metadata["title"],
                        "version": item.metadata["version"],
                        "description": item.metadata["description"],
                    }
                    for item in discover_templates(root)
                ]
                sys.stdout.write(
                    json.dumps({"templates": list_payload}, ensure_ascii=True, sort_keys=True)
                    + "\n"
                )
                return 0

            if ns.templates_cmd == "show":
                item = template_by_id(root, ns.id)
                show_payload = {
                    "metadata": item.metadata,
                    "inputs": {
                        name: {"default": spec.default, "description": spec.description}
                        for name, spec in item.inputs.items()
                    },
                    "workflow": [
                        {"id": step.step_id, "action": step.action, "with": step.params}
                        for step in item.workflow
                    ],
                    "source": item.source.relative_to(root).as_posix(),
                }
                sys.stdout.write(json.dumps(show_payload, ensure_ascii=True, sort_keys=True) + "\n")
                return 0

            if ns.templates_cmd == "run":
                item = template_by_id(root, ns.id)
                parsed_set_values = parse_set_values(list(ns.set_values))
                output_dir = Path(ns.output_dir)
                if output_dir == Path(".sdetkit/agent/template-runs"):
                    output_dir = output_dir / item.metadata["id"]
                record = run_template(
                    root,
                    template=item,
                    set_values=parsed_set_values,
                    output_dir=root / output_dir,
                )
                sys.stdout.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
                return 0 if record.get("status") == "ok" else 1

            if ns.templates_cmd == "pack":
                pack_payload = pack_templates(root, output=root / ns.output)
                sys.stdout.write(json.dumps(pack_payload, ensure_ascii=True, sort_keys=True) + "\n")
                return 0
        except TemplateValidationError as exc:
            sys.stdout.write(
                json.dumps({"error": str(exc)}, ensure_ascii=True, sort_keys=True) + "\n"
            )
            return 1

    return 2
