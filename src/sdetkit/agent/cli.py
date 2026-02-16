from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import doctor_agent, history_agent, init_agent, run_agent
from .dashboard import build_dashboard as build_agent_dashboard
from .dashboard import export_history_summary
from .demo import run_demo
from .omnichannel import AgentServeApp
from .templates import (
    TemplateValidationError,
    discover_templates,
    pack_templates,
    parse_set_values,
    run_template,
    template_by_id,
)


def _json_out(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _fail(message: str) -> int:
    print(message.replace("\n", " "), file=sys.stderr)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=(
            "AgentOS workflows for deterministic orchestration: init, run, templates, "
            "serve, history, and dashboard."
        ),
        epilog=(
            "Workflows: `sdetkit agent init` to bootstrap, `run` for orchestration, "
            "`templates` for reusable automation, `serve` for omnichannel ingestion, "
            "`history` for run records, and `dashboard build` for exports."
        ),
    )
    sub = parser.add_subparsers(
        dest="agent_cmd", required=True, parser_class=argparse.ArgumentParser
    )

    init_p = sub.add_parser(
        "init",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Create AgentOS config and working directories.",
    )
    init_p.add_argument(
        "--config", default=".sdetkit/agent/config.yaml", help="Path to agent config file."
    )

    run_p = sub.add_parser(
        "run",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Execute one deterministic orchestration run.",
    )
    run_p.add_argument("task", help="Task description or explicit action payload.")
    run_p.add_argument(
        "--config", default=".sdetkit/agent/config.yaml", help="Path to agent config file."
    )
    run_p.add_argument("--approve", action="store_true", help="Auto-approve dangerous actions.")
    run_p.add_argument(
        "--cache-dir", default=".sdetkit/agent/cache", help="Provider cache directory."
    )
    run_p.add_argument(
        "--no-cache", action="store_true", help="Disable provider cache reads and writes."
    )

    doctor_p = sub.add_parser(
        "doctor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Validate AgentOS config and safety posture.",
    )
    doctor_p.add_argument(
        "--config", default=".sdetkit/agent/config.yaml", help="Path to agent config file."
    )

    hist_p = sub.add_parser(
        "history",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="List or export run history artifacts.",
    )
    hist_p.add_argument(
        "--limit", type=int, default=10, help="Maximum number of records returned for list mode."
    )
    hist_sub = hist_p.add_subparsers(dest="history_cmd", parser_class=argparse.ArgumentParser)
    hist_sub.required = False

    hist_list = hist_sub.add_parser(
        "list",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="List run history records.",
    )
    hist_list.add_argument(
        "--limit", type=int, default=10, help="Maximum number of records returned."
    )

    hist_export = hist_sub.add_parser(
        "export",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Export run history summary.",
    )
    hist_export.add_argument(
        "--history-dir",
        default=".sdetkit/agent/history",
        help="Directory containing run history JSON files.",
    )
    hist_export.add_argument("--format", choices=["csv"], default="csv", help="Export format.")
    hist_export.add_argument(
        "--output",
        default=".sdetkit/agent/workdir/history-summary.csv",
        help="Path for exported history summary.",
    )

    dash_p = sub.add_parser(
        "dashboard",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Build dashboard artifacts from run history.",
    )
    dash_sub = dash_p.add_subparsers(
        dest="dashboard_cmd", required=True, parser_class=argparse.ArgumentParser
    )
    dash_build = dash_sub.add_parser(
        "build",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Build dashboard outputs (html/md/json/csv).",
    )
    dash_build.add_argument(
        "--history-dir",
        default=".sdetkit/agent/history",
        help="Directory containing run history JSON files.",
    )
    dash_build.add_argument(
        "--output",
        default=".sdetkit/agent/workdir/agent-dashboard.html",
        help="Main output file path.",
    )
    dash_build.add_argument(
        "--summary-output",
        default=".sdetkit/agent/workdir/agent-summary.md",
        help="Markdown summary output path used in html mode.",
    )
    dash_build.add_argument(
        "--format",
        choices=["json", "md", "html", "csv"],
        default="html",
        help="Dashboard output format.",
    )

    demo_p = sub.add_parser(
        "demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Run deterministic end-to-end demo workflow.",
    )
    demo_p.add_argument(
        "--scenario",
        choices=["repo-enterprise-audit"],
        required=True,
        help="Demo scenario identifier.",
    )

    serve_p = sub.add_parser(
        "serve",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Start omnichannel webhook server.",
    )
    serve_p.add_argument(
        "--config", default=".sdetkit/agent/config.yaml", help="Path to agent config file."
    )
    serve_p.add_argument("--host", default="127.0.0.1", help="Bind host for the HTTP server.")
    serve_p.add_argument("--port", type=int, default=8787, help="Bind port for the HTTP server.")
    serve_p.add_argument(
        "--telegram-simulation-mode",
        action="store_true",
        help="Annotate telegram events as simulation mode.",
    )
    serve_p.add_argument(
        "--telegram-enable-outgoing", action="store_true", help="Enable outgoing telegram replies."
    )
    serve_p.add_argument(
        "--rate-limit-max-tokens",
        type=int,
        default=5,
        help="Token bucket capacity per channel/user key.",
    )
    serve_p.add_argument(
        "--rate-limit-refill-per-second",
        type=float,
        default=1.0,
        help="Token refill rate per second.",
    )
    serve_p.add_argument(
        "--tool-bridge-enabled", action="store_true", help="Enable MCP/tool bridge invocation."
    )
    serve_p.add_argument(
        "--tool-bridge-allow",
        action="append",
        default=[],
        help="Allowlisted tool name (repeatable).",
    )
    serve_p.add_argument(
        "--tool-bridge-command",
        action="append",
        default=[],
        help="Bridge command token (repeatable, build full command in order).",
    )

    tpl = sub.add_parser(
        "templates",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Discover, inspect, run, and package templates.",
    )
    tpl_sub = tpl.add_subparsers(
        dest="templates_cmd", required=True, parser_class=argparse.ArgumentParser
    )

    tpl_sub.add_parser(
        "list",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="List available template metadata.",
    )

    tpl_show = tpl_sub.add_parser(
        "show",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Show template details.",
    )
    tpl_show.add_argument("id", help="Template identifier.")

    tpl_run = tpl_sub.add_parser(
        "run",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Run template with optional input overrides.",
    )
    tpl_run.add_argument("id", help="Template identifier.")
    tpl_run.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help="Set template input as key=value (repeatable).",
    )
    tpl_run.add_argument(
        "--output-dir",
        default=".sdetkit/agent/template-runs",
        help="Directory for template run artifacts.",
    )

    tpl_pack = tpl_sub.add_parser(
        "pack",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        help="Create deterministic template tar package.",
    )
    tpl_pack.add_argument(
        "--output",
        default=".sdetkit/agent/templates/automation-templates.tar",
        help="Output tar path.",
    )

    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    root = Path.cwd()

    try:
        if ns.agent_cmd == "init":
            created = init_agent(root, root / ns.config)
            _json_out({"created": created})
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
            _json_out(record)
            return 0 if record.get("status") == "ok" else 1

        if ns.agent_cmd == "doctor":
            doctor_payload = doctor_agent(root, config_path=root / ns.config)
            _json_out(doctor_payload)
            return 0 if doctor_payload.get("ok") else 1

        if ns.agent_cmd == "history":
            history_cmd = ns.history_cmd or "list"
            if history_cmd == "export":
                export_payload = export_history_summary(
                    history_dir=root / ns.history_dir,
                    output=root / ns.output,
                    fmt=ns.format,
                )
                _json_out(export_payload)
                return 0
            history_payload = history_agent(root, limit=ns.limit)
            _json_out(history_payload)
            return 0

        if ns.agent_cmd == "dashboard":
            dashboard_payload = build_agent_dashboard(
                history_dir=root / ns.history_dir,
                output=root / ns.output,
                fmt=ns.format,
                summary_output=root / ns.summary_output,
            )
            _json_out(dashboard_payload)
            return 0

        if ns.agent_cmd == "demo":
            demo_payload = run_demo(root=root, scenario=ns.scenario)
            _json_out(demo_payload)
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
            _json_out(
                {
                    "status": "serving",
                    "host": ns.host,
                    "port": ns.port,
                    "tool_bridge_enabled": bool(ns.tool_bridge_enabled),
                }
            )
            app.serve_forever()
            return 0

        if ns.agent_cmd == "templates":
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
                _json_out({"templates": list_payload})
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
                _json_out(show_payload)
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
                _json_out(record)
                return 0 if record.get("status") == "ok" else 1

            if ns.templates_cmd == "pack":
                pack_payload = pack_templates(root, output=root / ns.output)
                _json_out(pack_payload)
                return 0
    except (TemplateValidationError, ValueError, OSError) as exc:
        return _fail(f"agent error: {exc}")

    return 2
