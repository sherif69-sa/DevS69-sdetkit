from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from importlib import import_module, metadata
from typing import cast

from .public_surface_contract import render_root_help_groups

expansion_automation_41 = import_module("sdetkit.expansion_automation_41")
optimization_closeout_42 = import_module("sdetkit.optimization_closeout_42")
acceleration_closeout_43 = import_module("sdetkit.acceleration_closeout_43")
scale_closeout_44 = import_module("sdetkit.scale_closeout_44")
expansion_closeout_45 = import_module("sdetkit.expansion_closeout_45")
optimization_closeout_46 = import_module("sdetkit.optimization_closeout_46")
reliability_closeout_47 = import_module("sdetkit.reliability_closeout_47")
objection_closeout_48 = import_module("sdetkit.objection_closeout_48")
weekly_review_closeout_49 = import_module("sdetkit.weekly_review_closeout_49")
execution_prioritization_closeout_50 = import_module("sdetkit.execution_prioritization_closeout_50")

LEGACY_NAMESPACE_COMMANDS: tuple[str, ...] = (
    "weekly-review-lane",
    "phase1-hardening",
    "phase1-wrap",
    "phase2-kickoff",
    "release-cadence",
    "demo-asset",
    "demo-asset2",
    "kpi-instrumentation",
    "experiment-lane",
    "distribution-batch",
    "playbook-post",
    "scale-lane",
    "expansion-automation",
    "optimization-closeout-foundation",
)


def _tool_version() -> str:
    try:
        return metadata.version("sdetkit")
    except metadata.PackageNotFoundError:
        return "0+unknown"


def _add_apiget_args(p: argparse.ArgumentParser) -> None:
    apiget_module = import_module("sdetkit.apiget")
    apiget_module._add_apiget_args(p)

    p.add_argument("--cassette", default=None, help="Cassette file path (enables record/replay).")
    p.add_argument(
        "--cassette-mode",
        choices=["auto", "record", "replay"],
        default=None,
        help="Cassette mode: auto, record, or replay.",
    )


def _run_module_main(module_name: str, args: Sequence[str]) -> int:
    module = import_module(module_name)
    return cast(int, module.main(list(args)))


def _is_hidden_cmd(name: str) -> bool:
    if name == "playbooks":
        return False
    if name == "legacy":
        return False
    if name in {
        "docs-qa",
        "docs-nav",
        "github-actions-quickstart",
        "gitlab-ci-quickstart",
        "quality-contribution-delta",
        "proof",
    }:
        return True
    if name in LEGACY_NAMESPACE_COMMANDS:
        return True
    if name.startswith("impact") and len(name) > 3 and name[3].isdigit():
        return True
    if name.endswith("-closeout"):
        return True
    return False


def _filter_hidden_subcommands(parser: argparse.ArgumentParser) -> None:
    for action in parser._actions:
        if not hasattr(action, "_choices_actions"):
            continue
        filtered = []
        for choice_action in list(getattr(action, "_choices_actions", [])):
            name = getattr(choice_action, "dest", "")
            help_text = getattr(choice_action, "help", None)
            if help_text == argparse.SUPPRESS:
                continue
            if _is_hidden_cmd(name):
                continue
            filtered.append(choice_action)
        action._choices_actions = filtered


def _hide_help_subcommands(sub) -> None:
    actions = getattr(sub, "_choices_actions", None)
    if not isinstance(actions, list):
        return
    filtered = []
    for a in actions:
        n = getattr(a, "name", "")
        if isinstance(n, str) and _is_hidden_cmd(n):
            continue
        filtered.append(a)
    sub._choices_actions = filtered


def _resolve_non_day_playbook_alias(cmd: str) -> str:
    """Resolve product/legacy playbook names to a parser-backed command."""
    try:
        from . import playbooks_cli

        cmd_to_mod, alias_to_canonical = playbooks_cli._build_registry(playbooks_cli._pkg_dir())
    except Exception:
        return cmd

    if cmd in alias_to_canonical and cmd in cmd_to_mod and not cmd.startswith("impact"):
        return alias_to_canonical[cmd]

    return cmd


def _add_passthrough_subcommand(
    sub,
    name: str,
    *,
    help_text: str | None = None,
    aliases: list[str] | None = None,
    default_cmd: str | None = None,
):
    kwargs: dict[str, object] = {}
    if help_text is not None:
        kwargs["help"] = help_text
    if aliases:
        kwargs["aliases"] = aliases
    parser = sub.add_parser(name, **kwargs)
    if default_cmd is not None:
        parser.set_defaults(cmd=default_cmd)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def _build_root_parser(
    *, show_hidden_commands: bool = False
) -> tuple[argparse.ArgumentParser, object]:
    help_description = """\
DevS69 SDETKit is an operator-grade SDET platform for deterministic release confidence
and shipping readiness.

Policy tiers: Public / stable, Advanced but supported, Experimental / incubator.

Start here (canonical release-confidence path):
  1) [Public / stable] python -m sdetkit gate fast
  2) [Public / stable] python -m sdetkit gate release
  3) [Public / stable] python -m sdetkit doctor

Then use stability-aware command discovery:
  4) [Advanced but supported] python -m sdetkit kits list
"""

    help_epilog = render_root_help_groups()

    p = argparse.ArgumentParser(
        prog="sdetkit",
        add_help=True,
        description=help_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=help_epilog,
    )
    p.add_argument("--version", action="version", version=_tool_version())
    p.add_argument(
        "--show-hidden",
        action="store_true",
        help="Include hidden/legacy playbook commands in `sdetkit --help` output.",
    )
    sub = p.add_subparsers(
        dest="cmd",
        required=True,
        metavar="command",
        title="commands",
        description="Run `sdetkit <command> --help` for command-specific guidance.",
    )
    _add_passthrough_subcommand(sub, "baseline")
    _add_passthrough_subcommand(
        sub,
        "playbooks",
        help_text="Discover and run adoption/rollout playbooks",
    )
    _add_passthrough_subcommand(
        sub,
        "legacy",
        help_text="[Advanced but supported] Access historical/closeout compatibility lanes",
    )
    _add_passthrough_subcommand(
        sub, "kits", help_text="[Advanced but supported] Umbrella kit catalog and kit details"
    )

    _add_passthrough_subcommand(
        sub, "release", help_text="[Public / stable] Release Confidence Kit (primary surface)"
    )
    _add_passthrough_subcommand(
        sub,
        "intelligence",
        help_text="[Advanced but supported] Test Intelligence Kit (primary surface)",
    )
    _add_passthrough_subcommand(
        sub,
        "integration",
        help_text="[Advanced but supported] Integration Assurance Kit (primary surface)",
    )
    _add_passthrough_subcommand(
        sub,
        "author",
        help_text="[Advanced but supported] Platform-style Python problem authoring workflow",
    )
    _add_passthrough_subcommand(
        sub,
        "forensics",
        help_text="[Advanced but supported] Failure Forensics Kit (experimental sublanes possible)",
    )
    _add_passthrough_subcommand(
        sub, "kv", help_text="Utility: parse key=value input into JSON (supporting surface)"
    )
    inspect_parser = sub.add_parser(
        "inspect",
        help="[Advanced but supported] Inspect CSV/JSON evidence inputs for operational diagnostics",
    )
    inspect_parser.add_argument(
        "--rules-template",
        action="store_true",
        help="Print a canonical inspect rules JSON template and exit.",
    )
    inspect_parser.add_argument("args", nargs=argparse.REMAINDER)

    ag = sub.add_parser("apiget", help="Deterministic HTTP JSON fetch and replay helper")
    _add_apiget_args(ag)

    _add_passthrough_subcommand(
        sub,
        "doctor",
        help_text="[Public / stable] Deterministic repo and release-readiness checks",
    )

    _add_passthrough_subcommand(
        sub,
        "gate",
        help_text="[Public / stable] Quick confidence and strict release gate checks",
    )

    _add_passthrough_subcommand(sub, "ci", help_text="CI template and pipeline validation")

    _add_passthrough_subcommand(sub, "patch", help_text="Apply controlled file/text patches")

    _add_passthrough_subcommand(
        sub,
        "cassette-get",
        help_text="Utility: record/replay HTTP captures for deterministic checks",
    )

    initp = sub.add_parser(
        "init",
        help="[Advanced but supported] Bootstrap repo adoption with preset templates and optional config",
    )
    initp.add_argument("--preset", choices=["enterprise_python"], default="enterprise_python")
    initp.add_argument("--root", default=".")
    initp.add_argument("--dry-run", action="store_true")
    initp.add_argument("--force", action="store_true")
    initp.add_argument("--diff", action="store_true")
    initp.add_argument("--format", choices=["text", "json"], default="text")
    initp.add_argument("--write-config", action="store_true")

    _add_passthrough_subcommand(
        sub, "repo", help_text="[Public / stable] Repository automation tasks"
    )

    _add_passthrough_subcommand(sub, "dev", help_text="Shortcut to `repo dev` workflows")

    _add_passthrough_subcommand(
        sub, "feature-registry", help_text="Inspect feature-registry entries and filters"
    )

    rpt = sub.add_parser("report", help="Reporting workflows and output packs")
    rpt.add_argument("args", nargs=argparse.REMAINDER)

    mnt = sub.add_parser("maintenance", help="Maintenance automation and cleanup")
    mnt.add_argument("args", nargs=argparse.REMAINDER)

    agt = sub.add_parser("agent", help="Agent-centric automation workflows")
    agt.add_argument("args", nargs=argparse.REMAINDER)

    sec = sub.add_parser(
        "security", help="[Public / stable] Security policy checks and enforcement"
    )
    sec.add_argument("args", nargs=argparse.REMAINDER)

    osp = sub.add_parser("ops", help="Operational control-plane workflows")
    osp.add_argument("args", nargs=argparse.REMAINDER)

    ntf = sub.add_parser("notify", help="Notification adapters and delivery workflows")
    ntf.add_argument("args", nargs=argparse.REMAINDER)

    plc = sub.add_parser("policy", help="Policy evaluation and helper commands")
    plc.add_argument("args", nargs=argparse.REMAINDER)

    evd = sub.add_parser(
        "evidence", help="[Public / stable] Generate audit-friendly release evidence"
    )
    evd.add_argument("args", nargs=argparse.REMAINDER)

    onb = sub.add_parser("onboarding", help="Role-based onboarding playbook")
    onb.add_argument("args", nargs=argparse.REMAINDER)

    ono = sub.add_parser("onboarding-optimization", help="Onboarding optimization playbook")
    ono.add_argument("args", nargs=argparse.REMAINDER)

    cau = sub.add_parser("community-activation", help="Community activation rollout playbook")
    cau.add_argument("args", nargs=argparse.REMAINDER)

    exc = sub.add_parser("external-contribution", help="External contribution rollout playbook")
    exc.add_argument("args", nargs=argparse.REMAINDER)

    kpa = sub.add_parser("kpi-audit", help="KPI audit and tracking playbook")
    kpa.add_argument("args", nargs=argparse.REMAINDER)

    kpr = sub.add_parser("kpi-report", help="Release confidence KPI weekly pack")
    kpr.add_argument("args", nargs=argparse.REMAINDER)

    dwr = sub.add_parser("weekly-review-lane")
    dwr.set_defaults(cmd="weekly-review-lane")
    dwr.add_argument("args", nargs=argparse.REMAINDER)

    d29 = sub.add_parser("phase1-hardening")
    d29.set_defaults(cmd="phase1-hardening")
    d29.add_argument("args", nargs=argparse.REMAINDER)

    d30 = sub.add_parser("phase1-wrap")
    d30.set_defaults(cmd="phase1-wrap")
    d30.add_argument("args", nargs=argparse.REMAINDER)

    d31 = sub.add_parser("phase2-kickoff")
    d31.set_defaults(cmd="phase2-kickoff")
    d31.add_argument("args", nargs=argparse.REMAINDER)

    d32 = sub.add_parser("release-cadence")
    d32.set_defaults(cmd="release-cadence")
    d32.add_argument("args", nargs=argparse.REMAINDER)

    d33 = sub.add_parser("demo-asset")
    d33.set_defaults(cmd="demo-asset")
    d33.add_argument("args", nargs=argparse.REMAINDER)

    d34 = sub.add_parser("demo-asset2")
    d34.set_defaults(cmd="demo-asset2")
    d34.add_argument("args", nargs=argparse.REMAINDER)

    d35 = sub.add_parser("kpi-instrumentation")
    d35.set_defaults(cmd="kpi-instrumentation")
    d35.add_argument("args", nargs=argparse.REMAINDER)

    d36 = sub.add_parser("distribution-closeout")
    d36.set_defaults(cmd="distribution-closeout")
    d36.add_argument("args", nargs=argparse.REMAINDER)

    d37 = sub.add_parser("experiment-lane")
    d37.set_defaults(cmd="experiment-lane")
    d37.add_argument("args", nargs=argparse.REMAINDER)

    d38 = sub.add_parser("distribution-batch")
    d38.set_defaults(cmd="distribution-batch")
    d38.add_argument("args", nargs=argparse.REMAINDER)

    d39 = sub.add_parser("playbook-post")
    d39.set_defaults(cmd="playbook-post")
    d39.add_argument("args", nargs=argparse.REMAINDER)

    d40 = sub.add_parser("scale-lane")
    d40.set_defaults(cmd="scale-lane")
    d40.add_argument("args", nargs=argparse.REMAINDER)

    d41 = sub.add_parser("expansion-automation")
    d41.set_defaults(cmd="expansion-automation")
    d41.add_argument("args", nargs=argparse.REMAINDER)

    d42 = sub.add_parser("optimization-closeout-foundation")
    d42.set_defaults(cmd="optimization-closeout-foundation")
    d42.add_argument("args", nargs=argparse.REMAINDER)

    d43 = sub.add_parser("acceleration-closeout")
    d43.set_defaults(cmd="acceleration-closeout")
    d43.add_argument("args", nargs=argparse.REMAINDER)

    d44 = sub.add_parser("scale-closeout")
    d44.set_defaults(cmd="scale-closeout")
    d44.add_argument("args", nargs=argparse.REMAINDER)

    d45 = sub.add_parser("expansion-closeout")
    d45.set_defaults(cmd="expansion-closeout")
    d45.add_argument("args", nargs=argparse.REMAINDER)

    d46 = sub.add_parser("optimization-closeout")
    d46.set_defaults(cmd="optimization-closeout")
    d46.add_argument("args", nargs=argparse.REMAINDER)

    d47 = sub.add_parser("reliability-closeout")
    d47.set_defaults(cmd="reliability-closeout")
    d47.add_argument("args", nargs=argparse.REMAINDER)
    d48 = sub.add_parser("objection-closeout")
    d48.set_defaults(cmd="objection-closeout")
    d48.add_argument("args", nargs=argparse.REMAINDER)
    d49 = sub.add_parser("weekly-review-closeout")
    d49.set_defaults(cmd="weekly-review-closeout")
    d49.add_argument("args", nargs=argparse.REMAINDER)
    d50 = sub.add_parser("execution-prioritization-closeout")
    d50.set_defaults(cmd="execution-prioritization-closeout")
    d50.add_argument("args", nargs=argparse.REMAINDER)
    d51 = sub.add_parser("case-snippet-closeout")
    d51.set_defaults(cmd="case-snippet-closeout")
    d51.add_argument("args", nargs=argparse.REMAINDER)
    d52 = sub.add_parser("narrative-closeout")
    d52.set_defaults(cmd="narrative-closeout")
    d52.add_argument("args", nargs=argparse.REMAINDER)

    d53 = sub.add_parser("docs-loop-closeout")
    d53.set_defaults(cmd="docs-loop-closeout")
    d53.add_argument("args", nargs=argparse.REMAINDER)

    d55 = sub.add_parser("contributor-activation-closeout")
    d55.set_defaults(cmd="contributor-activation-closeout")
    d55.add_argument("args", nargs=argparse.REMAINDER)

    d56 = sub.add_parser("stabilization-closeout")
    d56.set_defaults(cmd="stabilization-closeout")
    d56.add_argument("args", nargs=argparse.REMAINDER)

    d57 = sub.add_parser("kpi-deep-audit-closeout")
    d57.set_defaults(cmd="kpi-deep-audit-closeout")
    d57.add_argument("args", nargs=argparse.REMAINDER)

    d58 = sub.add_parser("phase2-hardening-closeout")
    d58.set_defaults(cmd="phase2-hardening-closeout")
    d58.add_argument("args", nargs=argparse.REMAINDER)

    d59 = sub.add_parser("phase3-preplan-closeout")
    d59.set_defaults(cmd="phase3-preplan-closeout")
    d59.add_argument("args", nargs=argparse.REMAINDER)

    d60 = sub.add_parser("phase2-wrap-handoff-closeout")
    d60.set_defaults(cmd="phase2-wrap-handoff-closeout")
    d60.add_argument("args", nargs=argparse.REMAINDER)

    d61 = sub.add_parser("phase3-kickoff-closeout")
    d61.set_defaults(cmd="phase3-kickoff-closeout")
    d61.add_argument("args", nargs=argparse.REMAINDER)

    d62 = sub.add_parser("community-program-closeout")
    d62.set_defaults(cmd="community-program-closeout")
    d62.add_argument("args", nargs=argparse.REMAINDER)

    d63 = sub.add_parser("onboarding-activation-closeout")
    d63.set_defaults(cmd="onboarding-activation-closeout")
    d63.add_argument("args", nargs=argparse.REMAINDER)

    d64 = sub.add_parser("integration-expansion-closeout")
    d64.set_defaults(cmd="integration-expansion-closeout")
    d64.add_argument("args", nargs=argparse.REMAINDER)

    d65 = sub.add_parser("weekly-review-closeout-2")
    d65.set_defaults(cmd="weekly-review-closeout-2")
    d65.add_argument("args", nargs=argparse.REMAINDER)

    d66 = sub.add_parser("integration-expansion2-closeout")
    d66.set_defaults(cmd="integration-expansion2-closeout")
    d66.add_argument("args", nargs=argparse.REMAINDER)

    d67 = sub.add_parser("integration-expansion3-closeout")
    d67.set_defaults(cmd="integration-expansion3-closeout")
    d67.add_argument("args", nargs=argparse.REMAINDER)

    d68 = sub.add_parser("integration-expansion4-closeout")
    d68.set_defaults(cmd="integration-expansion4-closeout")
    d68.add_argument("args", nargs=argparse.REMAINDER)

    d69 = sub.add_parser("case-study-prep1-closeout")
    d69.set_defaults(cmd="case-study-prep1-closeout")
    d69.add_argument("args", nargs=argparse.REMAINDER)

    d70 = sub.add_parser("case-study-prep2-closeout")
    d70.set_defaults(cmd="case-study-prep2-closeout")
    d70.add_argument("args", nargs=argparse.REMAINDER)
    d71 = sub.add_parser("case-study-prep3-closeout")
    d71.set_defaults(cmd="case-study-prep3-closeout")
    d71.add_argument("args", nargs=argparse.REMAINDER)
    d72 = sub.add_parser("case-study-prep4-closeout")
    d72.set_defaults(cmd="case-study-prep4-closeout")
    d72.add_argument("args", nargs=argparse.REMAINDER)
    d73 = sub.add_parser("case-study-launch-closeout")
    d73.set_defaults(cmd="case-study-launch-closeout")
    d73.add_argument("args", nargs=argparse.REMAINDER)
    d74 = sub.add_parser("distribution-scaling-closeout")
    d74.set_defaults(cmd="distribution-scaling-closeout")
    d74.add_argument("args", nargs=argparse.REMAINDER)
    d75 = sub.add_parser("trust-assets-refresh-closeout")
    d75.set_defaults(cmd="trust-assets-refresh-closeout")
    d75.add_argument("args", nargs=argparse.REMAINDER)
    d76 = sub.add_parser("contributor-recognition-closeout")
    d76.set_defaults(cmd="contributor-recognition-closeout")
    d76.add_argument("args", nargs=argparse.REMAINDER)
    d77 = sub.add_parser("community-touchpoint-closeout")
    d77.add_argument("args", nargs=argparse.REMAINDER)
    d78 = sub.add_parser("ecosystem-priorities-closeout")
    d78.add_argument("args", nargs=argparse.REMAINDER)
    d79 = sub.add_parser("scale-upgrade-closeout")
    d79.add_argument("args", nargs=argparse.REMAINDER)
    d80 = sub.add_parser("partner-outreach-closeout")
    d80.add_argument("args", nargs=argparse.REMAINDER)
    d81 = sub.add_parser("growth-campaign-closeout")
    d81.set_defaults(cmd="growth-campaign-closeout")
    d81.add_argument("args", nargs=argparse.REMAINDER)
    d82 = sub.add_parser("integration-feedback-closeout")
    d82.set_defaults(cmd="integration-feedback-closeout")
    d82.add_argument("args", nargs=argparse.REMAINDER)
    d83 = sub.add_parser("trust-faq-expansion-closeout")
    d83.set_defaults(cmd="trust-faq-expansion-closeout")
    d83.add_argument("args", nargs=argparse.REMAINDER)
    d84 = sub.add_parser("evidence-narrative-closeout")
    d84.set_defaults(cmd="evidence-narrative-closeout")
    d84.add_argument("args", nargs=argparse.REMAINDER)
    d85 = sub.add_parser("release-prioritization-closeout")
    d85.set_defaults(cmd="release-prioritization-closeout")
    d85.add_argument("args", nargs=argparse.REMAINDER)
    d86 = sub.add_parser("launch-readiness-closeout")
    d86.set_defaults(cmd="launch-readiness-closeout")
    d86.add_argument("args", nargs=argparse.REMAINDER)
    d87 = sub.add_parser("governance-handoff-closeout")
    d87.set_defaults(cmd="governance-handoff-closeout")
    d87.add_argument("args", nargs=argparse.REMAINDER)
    d88 = sub.add_parser("governance-priorities-closeout")
    d88.set_defaults(cmd="governance-priorities-closeout")
    d88.add_argument("args", nargs=argparse.REMAINDER)
    d89 = sub.add_parser("governance-scale-closeout")
    d89.set_defaults(cmd="governance-scale-closeout")
    d89.add_argument("args", nargs=argparse.REMAINDER)
    d90 = sub.add_parser("phase3-wrap-publication-closeout")
    d90.set_defaults(cmd="phase3-wrap-publication-closeout")
    d90.add_argument("args", nargs=argparse.REMAINDER)
    parser = sub.add_parser(
        "continuous-upgrade-closeout-1", aliases=["continuous-upgrade-closeout-1"]
    )
    parser.set_defaults(cmd="continuous-upgrade-closeout-1")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parser = sub.add_parser("continuous-upgrade-closeout-2")
    parser.set_defaults(cmd="continuous-upgrade-closeout-2")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    c3 = sub.add_parser("continuous-upgrade-closeout-3")
    c3.set_defaults(cmd="continuous-upgrade-closeout-3")
    c3.add_argument("args", nargs=argparse.REMAINDER)
    d94 = sub.add_parser("continuous-upgrade-closeout-4")
    d94.set_defaults(cmd="continuous-upgrade-closeout-4")
    d94.add_argument("args", nargs=argparse.REMAINDER)
    d95 = sub.add_parser("continuous-upgrade-closeout-5")
    d95.set_defaults(cmd="continuous-upgrade-closeout-5")
    d95.add_argument("args", nargs=argparse.REMAINDER)
    parser = sub.add_parser("continuous-upgrade-closeout-6")
    parser.set_defaults(cmd="continuous-upgrade-closeout-6")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    d97 = sub.add_parser("continuous-upgrade-closeout-7")
    d97.set_defaults(cmd="continuous-upgrade-closeout-7")
    d97.add_argument("args", nargs=argparse.REMAINDER)
    parser = sub.add_parser("continuous-upgrade-closeout-8")
    parser.set_defaults(cmd="continuous-upgrade-closeout-8")
    parser.add_argument("args", nargs=argparse.REMAINDER)

    d99 = sub.add_parser("continuous-upgrade-closeout-9")
    d99.set_defaults(cmd="continuous-upgrade-closeout-9")
    d99.add_argument("args", nargs=argparse.REMAINDER)

    d100 = sub.add_parser("continuous-upgrade-closeout-10")
    d100.set_defaults(cmd="continuous-upgrade-closeout-10")
    d100.add_argument("args", nargs=argparse.REMAINDER)
    d101 = sub.add_parser("continuous-upgrade-closeout-11")
    d101.set_defaults(cmd="continuous-upgrade-closeout-11")
    d101.add_argument("args", nargs=argparse.REMAINDER)

    obj = sub.add_parser("objection-handling", help="Objection handling playbook")
    obj.add_argument("args", nargs=argparse.REMAINDER)

    dmo = sub.add_parser("demo")
    dmo.add_argument("args", nargs=argparse.REMAINDER)

    fct = sub.add_parser("first-contribution", help="First contribution playbook")
    fct.add_argument("args", nargs=argparse.REMAINDER)

    ctf = sub.add_parser("contributor-funnel", help="Contributor funnel playbook")
    ctf.add_argument("args", nargs=argparse.REMAINDER)

    eva = sub.add_parser("evidence-assets", help="Evidence assets and trust collateral")
    eva.add_argument("args", nargs=argparse.REMAINDER)
    _add_passthrough_subcommand(
        sub,
        "proof",
        help_text=argparse.SUPPRESS,
        default_cmd="evidence-assets",
    )

    ttp = sub.add_parser("triage-templates", help="Issue and triage template workflows")
    ttp.add_argument("args", nargs=argparse.REMAINDER)

    dql = sub.add_parser("docs-quality", help="Docs quality and link checks")
    dql.add_argument("args", nargs=argparse.REMAINDER)
    _add_passthrough_subcommand(
        sub,
        "docs-qa",
        help_text=argparse.SUPPRESS,
        default_cmd="docs-quality",
    )

    wrv = sub.add_parser("weekly-review", help="Weekly review playbook")
    wrv.add_argument("args", nargs=argparse.REMAINDER)

    dgo = sub.add_parser("docs-governance", help="Docs navigation validation")
    dgo.add_argument("args", nargs=argparse.REMAINDER)
    _add_passthrough_subcommand(
        sub,
        "docs-nav",
        help_text=argparse.SUPPRESS,
        default_cmd="docs-governance",
    )
    rdm = sub.add_parser("roadmap")
    rdm.add_argument("args", nargs=argparse.REMAINDER)

    suc = sub.add_parser("startup-readiness", help="Startup readiness playbook")
    suc.add_argument("args", nargs=argparse.REMAINDER)

    ugh = sub.add_parser("upgrade-hub", help="Deep-dig hidden upgrade lanes and contracts")
    ugh.add_argument("args", nargs=argparse.REMAINDER)

    spk = sub.add_parser("sdet-package")
    spk.add_argument("args", nargs=argparse.REMAINDER)

    eur = sub.add_parser("enterprise-readiness", help="Enterprise readiness playbook")
    eur.add_argument("args", nargs=argparse.REMAINDER)

    gha = sub.add_parser("github-actions-onboarding", help="GitHub Actions onboarding playbook")
    gha.add_argument("args", nargs=argparse.REMAINDER)
    _add_passthrough_subcommand(
        sub,
        "github-actions-quickstart",
        help_text=argparse.SUPPRESS,
        default_cmd="github-actions-onboarding",
    )

    glc = sub.add_parser("gitlab-ci-onboarding", help="GitLab CI onboarding playbook")
    glc.add_argument("args", nargs=argparse.REMAINDER)
    _add_passthrough_subcommand(
        sub,
        "gitlab-ci-quickstart",
        help_text=argparse.SUPPRESS,
        default_cmd="gitlab-ci-onboarding",
    )

    qcr = sub.add_parser("contribution-quality-report", help="Contribution quality report")
    qcr.add_argument("args", nargs=argparse.REMAINDER)
    _add_passthrough_subcommand(
        sub,
        "quality-contribution-delta",
        help_text=argparse.SUPPRESS,
        default_cmd="contribution-quality-report",
    )

    rep = sub.add_parser("reliability-evidence-pack", help="Reliability evidence pack")
    rep.add_argument("args", nargs=argparse.REMAINDER)

    rrd = sub.add_parser("release-readiness", help="Release readiness board")
    rrd.add_argument("args", nargs=argparse.REMAINDER)

    rnc = sub.add_parser("release-communications", help="Release communications playbook")
    rnc.add_argument("args", nargs=argparse.REMAINDER)

    tsa = sub.add_parser("trust-assets", help="Trust assets playbook")
    tsa.add_argument("args", nargs=argparse.REMAINDER)
    if not show_hidden_commands:
        _filter_hidden_subcommands(p)
    return p, sub


def main(argv: Sequence[str] | None = None) -> int:

    if argv is None:
        argv = sys.argv[1:]

    if argv:
        argv = list(argv)
        argv[0] = _resolve_non_day_playbook_alias(str(argv[0]))

    if argv and argv[0] == "legacy":
        if len(argv) == 1:
            sys.stderr.write("legacy error: expected a legacy command name\n")
            return 2
        if argv[1] == "list":
            sys.stdout.write("\n".join(LEGACY_NAMESPACE_COMMANDS) + "\n")
            return 0
        return main(list(argv[1:]))

    if argv and argv[0] == "cassette-get":
        from .__main__ import _cassette_get

        try:
            return _cassette_get(list(argv[1:]))
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 2

    if argv and argv[0] == "doctor":
        from .doctor import main as _doctor_main

        return _doctor_main(list(argv[1:]))

    if argv and argv[0] == "gate":
        from .gate import main as _gate_main

        return _gate_main(list(argv[1:]))

    if argv and argv[0] == "ci":
        from .ci import main as _ci_main

        return _ci_main(list(argv[1:]))

    if argv and argv[0] == "patch":
        return _run_module_main("sdetkit.patch", list(argv[1:]))

    if argv and argv[0] == "repo":
        return _run_module_main("sdetkit.repo", list(argv[1:]))

    if argv and argv[0] == "dev":
        return _run_module_main("sdetkit.repo", ["dev", *list(argv[1:])])

    if argv and argv[0] == "report":
        return _run_module_main("sdetkit.report", list(argv[1:]))

    if argv and argv[0] == "maintenance":
        return _run_module_main("sdetkit.maintenance", list(argv[1:]))

    if argv and argv[0] == "agent":
        return _run_module_main("sdetkit.agent.cli", list(argv[1:]))

    if argv and argv[0] == "security":
        return _run_module_main("sdetkit.security_gate", list(argv[1:]))

    if argv and argv[0] == "ops":
        return _run_module_main("sdetkit.ops", list(argv[1:]))

    if argv and argv[0] == "notify":
        return _run_module_main("sdetkit.notify", list(argv[1:]))

    if argv and argv[0] == "policy":
        return _run_module_main("sdetkit.policy", list(argv[1:]))

    if argv and argv[0] == "evidence":
        return _run_module_main("sdetkit.evidence", list(argv[1:]))

    if argv and argv[0] == "onboarding":
        return _run_module_main("sdetkit.onboarding", list(argv[1:]))

    if argv and argv[0] == "onboarding-optimization":
        return _run_module_main("sdetkit.onboarding_optimization", list(argv[1:]))

    if argv and argv[0] == "phase-boost":
        return _run_module_main("sdetkit.phase_boost", list(argv[1:]))

    if argv and argv[0] == "production-readiness":
        return _run_module_main("sdetkit.production_readiness", list(argv[1:]))

    if argv and argv[0] == "community-activation":
        return _run_module_main("sdetkit.community_activation", list(argv[1:]))

    if argv and argv[0] == "external-contribution":
        return _run_module_main("sdetkit.external_contribution", list(argv[1:]))

    if argv and argv[0] == "kpi-audit":
        return _run_module_main("sdetkit.kpi_audit", list(argv[1:]))
    if argv and argv[0] == "kpi-report":
        return _run_module_main("sdetkit.kpi_report", list(argv[1:]))

    if argv and argv[0] in {"weekly-review-lane"}:
        return _run_module_main("sdetkit.weekly_review_28", list(argv[1:]))

    if argv and argv[0] == "phase1-hardening":
        return _run_module_main("sdetkit.phase1_hardening_29", list(argv[1:]))

    if argv and argv[0] == "phase1-wrap":
        return _run_module_main("sdetkit.phase1_wrap_30", list(argv[1:]))

    if argv and argv[0] == "phase2-kickoff":
        return _run_module_main("sdetkit.phase2_kickoff_31", list(argv[1:]))

    if argv and argv[0] == "release-cadence":
        return _run_module_main("sdetkit.release_cadence_32", list(argv[1:]))

    if argv and argv[0] == "demo-asset":
        return _run_module_main("sdetkit.demo_asset_33", list(argv[1:]))

    if argv and argv[0] == "demo-asset2":
        return _run_module_main("sdetkit.demo_asset2_34", list(argv[1:]))

    if argv and argv[0] == "kpi-instrumentation":
        return _run_module_main("sdetkit.kpi_instrumentation_35", list(argv[1:]))

    if argv and argv[0] in {"distribution-closeout"}:
        return _run_module_main("sdetkit.distribution_closeout_36", list(argv[1:]))

    if argv and argv[0] in {"experiment-lane"}:
        return _run_module_main("sdetkit.experiment_lane_37", list(argv[1:]))

    if argv and argv[0] in {"distribution-batch"}:
        return _run_module_main("sdetkit.distribution_batch_38", list(argv[1:]))

    if argv and argv[0] == "playbook-post":
        return _run_module_main("sdetkit.playbook_post_39", list(argv[1:]))

    if argv and argv[0] in {"scale-lane"}:
        return _run_module_main("sdetkit.scale_lane_40", list(argv[1:]))

    if argv and argv[0] == "expansion-automation":
        return _run_module_main("sdetkit.expansion_automation_41", list(argv[1:]))

    if argv and argv[0] in {"optimization-closeout-foundation"}:
        return _run_module_main("sdetkit.optimization_closeout_42", list(argv[1:]))

    if argv and argv[0] == "acceleration-closeout":
        return _run_module_main("sdetkit.acceleration_closeout_43", list(argv[1:]))

    if argv and argv[0] == "scale-closeout":
        return _run_module_main("sdetkit.scale_closeout_44", list(argv[1:]))

    if argv and argv[0] == "expansion-closeout":
        return _run_module_main("sdetkit.expansion_closeout_45", list(argv[1:]))

    if argv and argv[0] in {"optimization-closeout"}:
        return _run_module_main("sdetkit.optimization_closeout_46", list(argv[1:]))

    if argv and argv[0] == "reliability-closeout":
        return _run_module_main("sdetkit.reliability_closeout_47", list(argv[1:]))
    if argv and argv[0] == "objection-closeout":
        return _run_module_main("sdetkit.objection_closeout_48", list(argv[1:]))
    if argv and argv[0] in {
        "weekly-review-closeout",
    }:
        return _run_module_main("sdetkit.weekly_review_closeout_49", list(argv[1:]))
    if argv and argv[0] in {
        "execution-prioritization-closeout",
    }:
        return _run_module_main("sdetkit.execution_prioritization_closeout_50", list(argv[1:]))
    if argv and argv[0] in {"case-snippet-closeout"}:
        return _run_module_main("sdetkit.case_snippet_closeout_51", list(argv[1:]))
    if argv and argv[0] in {"narrative-closeout"}:
        return _run_module_main("sdetkit.narrative_closeout_52", list(argv[1:]))
    if argv and argv[0] in {"docs-loop-closeout"}:
        return _run_module_main("sdetkit.docs_loop_closeout_53", list(argv[1:]))
    if argv and argv[0] in {
        "contributor-activation-closeout",
    }:
        return _run_module_main("sdetkit.contributor_activation_closeout_55", list(argv[1:]))

    if argv and argv[0] in {"stabilization-closeout"}:
        return _run_module_main("sdetkit.stabilization_closeout_56", list(argv[1:]))

    if argv and argv[0] in {"kpi-deep-audit-closeout"}:
        return _run_module_main("sdetkit.kpi_deep_audit_closeout_57", list(argv[1:]))

    if argv and argv[0] in {"phase2-hardening-closeout"}:
        return _run_module_main("sdetkit.phase2_hardening_closeout_58", list(argv[1:]))

    if argv and argv[0] in {"phase3-preplan-closeout"}:
        return _run_module_main("sdetkit.phase3_preplan_closeout_59", list(argv[1:]))

    if argv and argv[0] in {"phase2-wrap-handoff-closeout"}:
        return _run_module_main("sdetkit.phase2_wrap_handoff_closeout_60", list(argv[1:]))

    if argv and argv[0] in {"phase3-kickoff-closeout"}:
        return _run_module_main("sdetkit.phase3_kickoff_closeout_61", list(argv[1:]))

    if argv and argv[0] in {"community-program-closeout"}:
        return _run_module_main("sdetkit.community_program_closeout_62", list(argv[1:]))

    if argv and argv[0] in {
        "onboarding-activation-closeout",
    }:
        return _run_module_main("sdetkit.onboarding_activation_closeout_63", list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion-closeout",
    }:
        return _run_module_main("sdetkit.integration_expansion_closeout_64", list(argv[1:]))

    if argv and argv[0] in {"weekly-review-closeout-2"}:
        return _run_module_main("sdetkit.weekly_review_closeout_65", list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion2-closeout",
    }:
        return _run_module_main("sdetkit.integration_expansion2_closeout_66", list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion3-closeout",
    }:
        return _run_module_main("sdetkit.integration_expansion3_closeout_67", list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion4-closeout",
    }:
        return _run_module_main("sdetkit.integration_expansion4_closeout_68", list(argv[1:]))

    if argv and argv[0] in {"case-study-prep1-closeout"}:
        return _run_module_main("sdetkit.case_study_prep1_closeout_69", list(argv[1:]))

    if argv and argv[0] in {"case-study-prep2-closeout"}:
        return _run_module_main("sdetkit.case_study_prep2_closeout_70", list(argv[1:]))

    if argv and argv[0] in {"case-study-prep3-closeout"}:
        return _run_module_main("sdetkit.case_study_prep3_closeout_71", list(argv[1:]))

    if argv and argv[0] in {"case-study-prep4-closeout"}:
        return _run_module_main("sdetkit.case_study_prep4_closeout_72", list(argv[1:]))

    if argv and argv[0] in {"case-study-launch-closeout"}:
        return _run_module_main("sdetkit.case_study_launch_closeout_73", list(argv[1:]))

    if argv and argv[0] in {"distribution-scaling-closeout"}:
        return _run_module_main("sdetkit.distribution_scaling_closeout_74", list(argv[1:]))

    if argv and argv[0] in {"trust-assets-refresh-closeout"}:
        return _run_module_main("sdetkit.trust_assets_refresh_closeout_75", list(argv[1:]))

    if argv and argv[0] in {
        "contributor-recognition-closeout",
    }:
        return _run_module_main("sdetkit.contributor_recognition_closeout_76", list(argv[1:]))

    if argv and argv[0] in {"community-touchpoint-closeout"}:
        return _run_module_main("sdetkit.community_touchpoint_closeout_77", list(argv[1:]))

    if argv and argv[0] in {"ecosystem-priorities-closeout"}:
        return _run_module_main("sdetkit.ecosystem_priorities_closeout_78", list(argv[1:]))

    if argv and argv[0] in {"scale-upgrade-closeout"}:
        return _run_module_main("sdetkit.scale_upgrade_closeout_79", list(argv[1:]))

    if argv and argv[0] in {"partner-outreach-closeout"}:
        return _run_module_main("sdetkit.partner_outreach_closeout_80", list(argv[1:]))

    if argv and argv[0] in {"growth-campaign-closeout"}:
        return _run_module_main("sdetkit.growth_campaign_closeout_81", list(argv[1:]))

    if argv and argv[0] in {"integration-feedback-closeout"}:
        return _run_module_main("sdetkit.integration_feedback_closeout_82", list(argv[1:]))

    if argv and argv[0] in {"trust-faq-expansion-closeout"}:
        return _run_module_main("sdetkit.trust_faq_expansion_closeout_83", list(argv[1:]))

    if argv and argv[0] in {"evidence-narrative-closeout"}:
        return _run_module_main("sdetkit.evidence_narrative_closeout_84", list(argv[1:]))

    if argv and argv[0] in {
        "release-prioritization-closeout",
    }:
        return _run_module_main("sdetkit.release_prioritization_closeout_85", list(argv[1:]))

    if argv and argv[0] in {"launch-readiness-closeout"}:
        return _run_module_main("sdetkit.launch_readiness_closeout_86", list(argv[1:]))

    if argv and argv[0] in {"governance-handoff-closeout"}:
        return _run_module_main("sdetkit.governance_handoff_closeout_87", list(argv[1:]))

    if argv and argv[0] in {
        "governance-priorities-closeout",
    }:
        return _run_module_main("sdetkit.governance_priorities_closeout_88", list(argv[1:]))

    if argv and argv[0] in {"governance-scale-closeout"}:
        return _run_module_main("sdetkit.governance_scale_closeout_89", list(argv[1:]))

    if argv and argv[0] in {
        "phase3-wrap-publication-closeout",
    }:
        return _run_module_main("sdetkit.phase3_wrap_publication_closeout_90", list(argv[1:]))

    if argv and argv[0] == "continuous-upgrade-closeout-1":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_1", list(argv[1:]))

    if argv and argv[0] in {
        "continuous-upgrade-closeout-2",
    }:
        return _run_module_main("sdetkit.continuous_upgrade_closeout_2", list(argv[1:]))

    if argv and argv[0] in {
        "continuous-upgrade-closeout-3",
    }:
        return _run_module_main("sdetkit.continuous_upgrade_closeout_3", list(argv[1:]))

    if argv and argv[0] in {
        "continuous-upgrade-closeout-4",
    }:
        return _run_module_main("sdetkit.continuous_upgrade_closeout_4", list(argv[1:]))
    if argv and argv[0] in {
        "continuous-upgrade-closeout-5",
    }:
        return _run_module_main("sdetkit.continuous_upgrade_closeout_5", list(argv[1:]))
    if argv and argv[0] in {
        "continuous-upgrade-closeout-6",
    }:
        return _run_module_main("sdetkit.continuous_upgrade_closeout_6", list(argv[1:]))
    if argv and argv[0] in {
        "continuous-upgrade-closeout-7",
    }:
        return _run_module_main("sdetkit.continuous_upgrade_closeout_7", list(argv[1:]))
    if argv and argv[0] == "continuous-upgrade-closeout-8":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_8", list(argv[1:]))

    if argv and argv[0] == "continuous-upgrade-closeout-9":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_9", list(argv[1:]))

    if argv and argv[0] == "continuous-upgrade-closeout-10":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_10", list(argv[1:]))

    if argv and argv[0] == "continuous-upgrade-closeout-11":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_11", list(argv[1:]))

    if argv and argv[0] == "objection-handling":
        return _run_module_main("sdetkit.objection_handling", list(argv[1:]))

    if argv and argv[0] == "first-contribution":
        return _run_module_main("sdetkit.first_contribution", list(argv[1:]))

    if argv and argv[0] == "demo":
        return _run_module_main("sdetkit.demo", list(argv[1:]))

    if argv and argv[0] == "contributor-funnel":
        return _run_module_main("sdetkit.contributor_funnel", list(argv[1:]))

    if argv and argv[0] in {"evidence-assets", "proof"}:
        return _run_module_main("sdetkit.proof", list(argv[1:]))

    if argv and argv[0] == "triage-templates":
        return _run_module_main("sdetkit.triage_templates", list(argv[1:]))

    if argv and argv[0] in {"docs-quality", "docs-qa"}:
        return _run_module_main("sdetkit.docs_qa", list(argv[1:]))

    if argv and argv[0] == "weekly-review":
        return _run_module_main("sdetkit.weekly_review", list(argv[1:]))

    if argv and argv[0] in {"docs-governance", "docs-nav"}:
        return _run_module_main("sdetkit.docs_navigation", list(argv[1:]))
    if argv and argv[0] == "roadmap":
        return _run_module_main("sdetkit.roadmap", list(argv[1:]))

    if argv and argv[0] == "startup-readiness":
        return _run_module_main("sdetkit.startup_readiness", list(argv[1:]))

    if argv and argv[0] == "upgrade-hub":
        return _run_module_main("sdetkit.upgrade_hub", list(argv[1:]))

    if argv and argv[0] == "sdet-package":
        return _run_module_main("sdetkit.sdet_package", list(argv[1:]))

    if argv and argv[0] == "enterprise-readiness":
        return _run_module_main("sdetkit.enterprise_readiness", list(argv[1:]))

    if argv and argv[0] in {"github-actions-onboarding", "github-actions-quickstart"}:
        return _run_module_main("sdetkit.github_actions_quickstart", list(argv[1:]))

    if argv and argv[0] in {"gitlab-ci-onboarding", "gitlab-ci-quickstart"}:
        return _run_module_main("sdetkit.gitlab_ci_quickstart", list(argv[1:]))

    if argv and argv[0] in {"contribution-quality-report", "quality-contribution-delta"}:
        return _run_module_main("sdetkit.quality_contribution_delta", list(argv[1:]))

    if argv and argv[0] == "reliability-evidence-pack":
        return _run_module_main("sdetkit.reliability_evidence_pack", list(argv[1:]))

    if argv and argv[0] == "release-readiness":
        return _run_module_main("sdetkit.release_readiness", list(argv[1:]))

    if argv and argv[0] == "release-communications":
        return _run_module_main("sdetkit.release_communications", list(argv[1:]))

    if argv and argv[0] == "trust-assets":
        return _run_module_main("sdetkit.trust_assets", list(argv[1:]))

    if argv and argv[0] == "feature-registry":
        return _run_module_main("sdetkit.feature_registry_cli", list(argv[1:]))

    show_hidden_commands = "--show-hidden" in argv
    p, sub = _build_root_parser(show_hidden_commands=show_hidden_commands)

    if not show_hidden_commands:
        _hide_help_subcommands(sub)

    ns = p.parse_args(argv)

    if ns.cmd == "baseline":
        import io
        import json
        from contextlib import redirect_stderr, redirect_stdout

        bp = argparse.ArgumentParser(prog="sdetkit baseline")
        bp.add_argument("action", choices=["write", "check"])
        bp.add_argument("--format", choices=["text", "json"], default="text")
        bp.add_argument("--diff", action="store_true")
        bp.add_argument("--diff-context", type=int, default=3)
        bns, extra = bp.parse_known_args(list(getattr(ns, "args", [])))
        if extra and extra[0] == "--":
            extra = extra[1:]

        from sdetkit import doctor, gate

        steps: list[dict[str, object]] = []
        failed: list[str] = []

        diff_args: list[str] = []
        if getattr(bns, "diff", False):
            diff_args.append("--diff")
            diff_args.extend(["--diff-context", str(getattr(bns, "diff_context", 3))])
        for sid, fn in [
            ("doctor_baseline", doctor.main),
            ("gate_baseline", gate.main),
        ]:
            buf_out = io.StringIO()
            buf_err = io.StringIO()
            with redirect_stdout(buf_out), redirect_stderr(buf_err):
                rc = fn(["baseline", bns.action] + diff_args + (["--"] + extra if extra else []))
            step = {
                "id": sid,
                "rc": rc,
                "ok": rc == 0,
                "stdout": buf_out.getvalue(),
                "stderr": buf_err.getvalue(),
            }
            steps.append(step)
            if rc != 0:
                failed.append(sid)

        ok = not failed
        payload: dict[str, object] = {"ok": ok, "steps": steps, "failed_steps": failed}
        if bns.format == "json":
            sys.stdout.write(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
            )
        else:
            lines: list[str] = []
            lines.append(f"baseline: {'OK' if ok else 'FAIL'}")
            for s in steps:
                marker = "OK" if s.get("ok") else "FAIL"
                lines.append(f"[{marker}] {s.get('id')} rc={s.get('rc')}")
            if failed:
                lines.append("failed_steps:")
                for f in failed:
                    lines.append(f"- {f}")
            sys.stdout.write("\n".join(lines) + "\n")
        return 0 if ok else 2

    if ns.cmd == "playbooks":
        from .playbooks_cli import main as _playbooks_main

        return _playbooks_main(list(ns.args))

    if ns.cmd == "legacy":
        if not ns.args:
            sys.stderr.write("legacy error: expected a legacy command name\n")
            return 2
        if ns.args[0] == "list":
            sys.stdout.write("\n".join(LEGACY_NAMESPACE_COMMANDS) + "\n")
            return 0
        return main(list(ns.args))

    if ns.cmd == "kits":
        return _run_module_main("sdetkit.kits", ns.args)

    if ns.cmd == "release":
        if not ns.args:
            sys.stderr.write(
                "release error: expected subcommand (gate|doctor|security|evidence|repo)\n"
            )
            return 2
        subcmd = ns.args[0]
        rest = ns.args[1:]
        if subcmd == "gate":
            return _run_module_main("sdetkit.gate", rest)
        if subcmd == "doctor":
            return _run_module_main("sdetkit.doctor", rest)
        if subcmd == "security":
            return _run_module_main("sdetkit.security_gate", rest)
        if subcmd == "evidence":
            return _run_module_main("sdetkit.evidence", rest)
        if subcmd == "repo":
            return _run_module_main("sdetkit.repo", rest)
        sys.stderr.write(
            "release error: supported subcommands are gate|doctor|security|evidence|repo\n"
        )
        return 2

    if ns.cmd == "intelligence":
        return _run_module_main("sdetkit.intelligence", ns.args)

    if ns.cmd == "integration":
        return _run_module_main("sdetkit.integration", ns.args)

    if ns.cmd == "author":
        return _run_module_main("sdetkit.author_problem", ns.args)

    if ns.cmd == "forensics":
        return _run_module_main("sdetkit.forensics", ns.args)

    if ns.cmd == "kv":
        return _run_module_main("sdetkit.kvcli", ns.args)

    if ns.cmd == "inspect":
        inspect_args = list(ns.args)
        if ns.rules_template:
            inspect_args = ["--rules-template", *inspect_args]
        return _run_module_main("sdetkit.inspect_data", inspect_args)

    if ns.cmd == "patch":
        return _run_module_main("sdetkit.patch", ns.args)

    if ns.cmd == "init":
        forwarded = [
            "init",
            "--preset",
            ns.preset,
            "--root",
            ns.root,
            "--format",
            ns.format,
        ]
        if ns.dry_run:
            forwarded.append("--dry-run")
        if ns.force:
            forwarded.append("--force")
        if ns.diff:
            forwarded.append("--diff")
        if ns.write_config:
            forwarded.append("--write-config")
        return _run_module_main("sdetkit.repo", forwarded)

    if ns.cmd == "repo":
        return _run_module_main("sdetkit.repo", ns.args)

    if ns.cmd == "dev":
        return _run_module_main("sdetkit.repo", ["dev", *ns.args])

    if ns.cmd == "feature-registry":
        return _run_module_main("sdetkit.feature_registry_cli", ns.args)

    if ns.cmd == "report":
        return _run_module_main("sdetkit.report", ns.args)

    if ns.cmd == "maintenance":
        return _run_module_main("sdetkit.maintenance", ns.args)

    if ns.cmd == "agent":
        return _run_module_main("sdetkit.agent.cli", ns.args)

    if ns.cmd == "security":
        return _run_module_main("sdetkit.security_gate", ns.args)

    if ns.cmd == "ops":
        return _run_module_main("sdetkit.ops", ns.args)

    if ns.cmd == "notify":
        return _run_module_main("sdetkit.notify", ns.args)

    if ns.cmd == "policy":
        return _run_module_main("sdetkit.policy", ns.args)

    if ns.cmd == "evidence":
        return _run_module_main("sdetkit.evidence", ns.args)

    if ns.cmd == "onboarding":
        return _run_module_main("sdetkit.onboarding", ns.args)

    if ns.cmd == "onboarding-optimization":
        return _run_module_main("sdetkit.onboarding_optimization", ns.args)

    if ns.cmd == "community-activation":
        return _run_module_main("sdetkit.community_activation", ns.args)

    if ns.cmd == "external-contribution":
        return _run_module_main("sdetkit.external_contribution", ns.args)

    if ns.cmd == "kpi-audit":
        return _run_module_main("sdetkit.kpi_audit", ns.args)
    if ns.cmd == "kpi-report":
        return _run_module_main("sdetkit.kpi_report", ns.args)

    if ns.cmd in {"distribution-closeout"}:
        return _run_module_main("sdetkit.distribution_closeout_36", ns.args)

    if ns.cmd in {"experiment-lane"}:
        return _run_module_main("sdetkit.experiment_lane_37", ns.args)

    if ns.cmd in {"distribution-batch"}:
        return _run_module_main("sdetkit.distribution_batch_38", ns.args)

    if ns.cmd == "playbook-post":
        return _run_module_main("sdetkit.playbook_post_39", ns.args)

    if ns.cmd in {"scale-lane"}:
        return _run_module_main("sdetkit.scale_lane_40", ns.args)

    if ns.cmd in {"expansion-automation"}:
        return _run_module_main("sdetkit.expansion_automation_41", ns.args)

    if ns.cmd in {"optimization-closeout-foundation"}:
        return _run_module_main("sdetkit.optimization_closeout_42", ns.args)

    if ns.cmd in {"acceleration-closeout"}:
        return _run_module_main("sdetkit.acceleration_closeout_43", ns.args)

    if ns.cmd in {"scale-closeout"}:
        return _run_module_main("sdetkit.scale_closeout_44", ns.args)

    if ns.cmd in {"expansion-closeout"}:
        return _run_module_main("sdetkit.expansion_closeout_45", ns.args)

    if ns.cmd in {"optimization-closeout"}:
        return _run_module_main("sdetkit.optimization_closeout_46", ns.args)

    if ns.cmd in {"reliability-closeout"}:
        return _run_module_main("sdetkit.reliability_closeout_47", ns.args)
    if ns.cmd in {"objection-closeout"}:
        return _run_module_main("sdetkit.objection_closeout_48", ns.args)
    if ns.cmd in {
        "weekly-review-closeout",
    }:
        return _run_module_main("sdetkit.weekly_review_closeout_49", ns.args)
    if ns.cmd in {"execution-prioritization-closeout"}:
        return _run_module_main("sdetkit.execution_prioritization_closeout_50", ns.args)
    if ns.cmd in {"case-snippet-closeout"}:
        return _run_module_main("sdetkit.case_snippet_closeout_51", ns.args)
    if ns.cmd in {"narrative-closeout"}:
        return _run_module_main("sdetkit.narrative_closeout_52", ns.args)
    if ns.cmd in {"docs-loop-closeout"}:
        return _run_module_main("sdetkit.docs_loop_closeout_53", ns.args)
    if ns.cmd in {"contributor-activation-closeout"}:
        return _run_module_main("sdetkit.contributor_activation_closeout_55", ns.args)

    if ns.cmd in {"stabilization-closeout"}:
        return _run_module_main("sdetkit.stabilization_closeout_56", ns.args)

    if ns.cmd in {"kpi-deep-audit-closeout"}:
        return _run_module_main("sdetkit.kpi_deep_audit_closeout_57", ns.args)

    if ns.cmd in {"phase2-hardening-closeout"}:
        return _run_module_main("sdetkit.phase2_hardening_closeout_58", ns.args)

    if ns.cmd in {"phase3-preplan-closeout"}:
        return _run_module_main("sdetkit.phase3_preplan_closeout_59", ns.args)

    if ns.cmd in {"phase2-wrap-handoff-closeout"}:
        return _run_module_main("sdetkit.phase2_wrap_handoff_closeout_60", ns.args)

    if ns.cmd in {"phase3-kickoff-closeout"}:
        return _run_module_main("sdetkit.phase3_kickoff_closeout_61", ns.args)

    if ns.cmd in {"community-program-closeout"}:
        return _run_module_main("sdetkit.community_program_closeout_62", ns.args)

    if ns.cmd in {"onboarding-activation-closeout"}:
        return _run_module_main("sdetkit.onboarding_activation_closeout_63", ns.args)

    if ns.cmd in {"integration-expansion-closeout"}:
        return _run_module_main("sdetkit.integration_expansion_closeout_64", ns.args)

    if ns.cmd in {"weekly-review-closeout-2"}:
        return _run_module_main("sdetkit.weekly_review_closeout_65", ns.args)

    if ns.cmd in {"integration-expansion2-closeout"}:
        return _run_module_main("sdetkit.integration_expansion2_closeout_66", ns.args)

    if ns.cmd in {"integration-expansion3-closeout"}:
        return _run_module_main("sdetkit.integration_expansion3_closeout_67", ns.args)

    if ns.cmd in {"integration-expansion4-closeout"}:
        return _run_module_main("sdetkit.integration_expansion4_closeout_68", ns.args)

    if ns.cmd in {"case-study-prep1-closeout"}:
        return _run_module_main("sdetkit.case_study_prep1_closeout_69", ns.args)

    if ns.cmd in {"case-study-prep2-closeout"}:
        return _run_module_main("sdetkit.case_study_prep2_closeout_70", ns.args)

    if ns.cmd == "case-study-prep3-closeout":
        return _run_module_main("sdetkit.case_study_prep3_closeout_71", ns.args)

    if ns.cmd == "case-study-prep4-closeout":
        return _run_module_main("sdetkit.case_study_prep4_closeout_72", ns.args)

    if ns.cmd == "case-study-launch-closeout":
        return _run_module_main("sdetkit.case_study_launch_closeout_73", ns.args)

    if ns.cmd == "distribution-scaling-closeout":
        return _run_module_main("sdetkit.distribution_scaling_closeout_74", ns.args)

    if ns.cmd == "trust-assets-refresh-closeout":
        return _run_module_main("sdetkit.trust_assets_refresh_closeout_75", ns.args)

    if ns.cmd == "contributor-recognition-closeout":
        return _run_module_main("sdetkit.contributor_recognition_closeout_76", ns.args)

    if ns.cmd == "community-touchpoint-closeout":
        return _run_module_main("sdetkit.community_touchpoint_closeout_77", ns.args)

    if ns.cmd == "ecosystem-priorities-closeout":
        return _run_module_main("sdetkit.ecosystem_priorities_closeout_78", ns.args)

    if ns.cmd == "scale-upgrade-closeout":
        return _run_module_main("sdetkit.scale_upgrade_closeout_79", ns.args)

    if ns.cmd == "partner-outreach-closeout":
        return _run_module_main("sdetkit.partner_outreach_closeout_80", ns.args)

    if ns.cmd in {"growth-campaign-closeout"}:
        return _run_module_main("sdetkit.growth_campaign_closeout_81", ns.args)

    if ns.cmd in {"integration-feedback-closeout"}:
        return _run_module_main("sdetkit.integration_feedback_closeout_82", ns.args)

    if ns.cmd in {"trust-faq-expansion-closeout"}:
        return _run_module_main("sdetkit.trust_faq_expansion_closeout_83", ns.args)

    if ns.cmd in {"evidence-narrative-closeout"}:
        return _run_module_main("sdetkit.evidence_narrative_closeout_84", ns.args)

    if ns.cmd in {"release-prioritization-closeout"}:
        return _run_module_main("sdetkit.release_prioritization_closeout_85", ns.args)

    if ns.cmd in {"launch-readiness-closeout"}:
        return _run_module_main("sdetkit.launch_readiness_closeout_86", ns.args)

    if ns.cmd in {"governance-handoff-closeout"}:
        return _run_module_main("sdetkit.governance_handoff_closeout_87", ns.args)

    if ns.cmd in {"governance-priorities-closeout"}:
        return _run_module_main("sdetkit.governance_priorities_closeout_88", ns.args)

    if ns.cmd in {"governance-scale-closeout"}:
        return _run_module_main("sdetkit.governance_scale_closeout_89", ns.args)

    if ns.cmd in {"phase3-wrap-publication-closeout"}:
        return _run_module_main("sdetkit.phase3_wrap_publication_closeout_90", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-1":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_1", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-2":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_2", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-3":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_3", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-4":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_4", ns.args)
    if ns.cmd == "continuous-upgrade-closeout-5":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_5", ns.args)
    if ns.cmd == "continuous-upgrade-closeout-6":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_6", ns.args)
    if ns.cmd == "continuous-upgrade-closeout-7":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_7", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-8":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_8", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-9":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_9", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-10":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_10", ns.args)

    if ns.cmd == "continuous-upgrade-closeout-11":
        return _run_module_main("sdetkit.continuous_upgrade_closeout_11", ns.args)

    if ns.cmd == "objection-handling":
        return _run_module_main("sdetkit.objection_handling", ns.args)

    if ns.cmd == "demo":
        return _run_module_main("sdetkit.demo", ns.args)

    if ns.cmd == "first-contribution":
        return _run_module_main("sdetkit.first_contribution", ns.args)

    if ns.cmd == "contributor-funnel":
        return _run_module_main("sdetkit.contributor_funnel", ns.args)

    if ns.cmd == "evidence-assets":
        return _run_module_main("sdetkit.proof", ns.args)

    if ns.cmd == "triage-templates":
        return _run_module_main("sdetkit.triage_templates", ns.args)

    if ns.cmd == "docs-quality":
        return _run_module_main("sdetkit.docs_qa", ns.args)

    if ns.cmd == "weekly-review":
        return _run_module_main("sdetkit.weekly_review", ns.args)

    if ns.cmd == "docs-governance":
        return _run_module_main("sdetkit.docs_navigation", ns.args)
    if ns.cmd == "roadmap":
        return _run_module_main("sdetkit.roadmap", ns.args)

    if ns.cmd == "startup-readiness":
        return _run_module_main("sdetkit.startup_readiness", ns.args)

    if ns.cmd == "upgrade-hub":
        return _run_module_main("sdetkit.upgrade_hub", ns.args)

    if ns.cmd == "sdet-package":
        return _run_module_main("sdetkit.sdet_package", ns.args)

    if ns.cmd == "enterprise-readiness":
        return _run_module_main("sdetkit.enterprise_readiness", ns.args)

    if ns.cmd == "github-actions-onboarding":
        return _run_module_main("sdetkit.github_actions_quickstart", ns.args)

    if ns.cmd == "gitlab-ci-onboarding":
        return _run_module_main("sdetkit.gitlab_ci_quickstart", ns.args)

    if ns.cmd == "contribution-quality-report":
        return _run_module_main("sdetkit.quality_contribution_delta", ns.args)

    if ns.cmd == "reliability-evidence-pack":
        return _run_module_main("sdetkit.reliability_evidence_pack", ns.args)

    if ns.cmd == "release-readiness":
        return _run_module_main("sdetkit.release_readiness", ns.args)

    if ns.cmd == "release-communications":
        return _run_module_main("sdetkit.release_communications", ns.args)

    if ns.cmd == "trust-assets":
        return _run_module_main("sdetkit.trust_assets", ns.args)

    if ns.cmd == "apiget":
        raw_args = list(argv)
        rest = raw_args[1:]
        cassette = getattr(ns, "cassette", None)
        cassette_mode = getattr(ns, "cassette_mode", None) or "auto"
        clean: list[str] = []
        it = iter(rest)
        for a in it:
            if a.startswith("--cassette="):
                continue
            if a == "--cassette":
                next(it, None)
                continue
            if a.startswith("--cassette-mode="):
                continue
            if a == "--cassette-mode":
                next(it, None)
                continue
            clean.append(a)
        rest = clean
        if not cassette:
            return _run_module_main("sdetkit.apiget", rest)
        old_cassette = os.environ.get("SDETKIT_CASSETTE")
        old_mode = os.environ.get("SDETKIT_CASSETTE_MODE")
        try:
            os.environ["SDETKIT_CASSETTE"] = str(cassette)
            os.environ["SDETKIT_CASSETTE_MODE"] = str(cassette_mode)
            return _run_module_main("sdetkit.apiget", rest)
        finally:
            if old_cassette is None:
                os.environ.pop("SDETKIT_CASSETTE", None)
            else:
                os.environ["SDETKIT_CASSETTE"] = old_cassette
            if old_mode is None:
                os.environ.pop("SDETKIT_CASSETTE_MODE", None)
            else:
                os.environ["SDETKIT_CASSETTE_MODE"] = old_mode
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
