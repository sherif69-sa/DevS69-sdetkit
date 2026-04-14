from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from importlib import import_module
from typing import cast

from .apiget_dispatch import run_apiget_with_cassette
from .argv_flags import extract_global_flag
from .cli_shortcuts import dispatch_preparse_shortcut
from .cli_timing import emit_cli_timing
from .help_surface import filter_hidden_subcommands, hide_help_subcommands
from .inspect_compare_forwarding import build_inspect_compare_forwarded_args
from .inspect_project_forwarding import build_inspect_project_forwarded_args
from .legacy_cli import run_legacy_migrate_hint
from .legacy_commands import (
    LEGACY_NAMESPACE_COMMANDS,
)
from .legacy_namespace import handle_legacy_namespace
from .parsed_shortcuts import dispatch_parsed_shortcut
from .parser_helpers import add_passthrough_subcommand as _add_passthrough_subcommand
from .playbook_aliases import resolve_non_day_playbook_alias
from .public_surface_contract import render_root_help_groups
from .repo_init_forwarding import build_repo_init_forwarded_args
from .review_forwarding import build_review_forwarded_args
from .serve_forwarding import build_serve_args
from .versioning import tool_version


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
    started = time.perf_counter()
    arg_list = list(args)
    module = import_module(module_name)
    rc = cast(int, module.main(arg_list))
    emit_cli_timing(
        f"event=dispatch module={module_name} argc={len(arg_list)} elapsed_ms={(time.perf_counter() - started) * 1000.0:.3f}"
    )
    return rc


def _build_root_parser(
    *, show_hidden_commands: bool = False
) -> tuple[argparse.ArgumentParser, object]:
    started = time.perf_counter()
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
    p.add_argument("--version", action="version", version=tool_version())
    p.add_argument(
        "--show-hidden",
        action="store_true",
        help="Include hidden/legacy playbook commands in `sdetkit --help` output.",
    )
    p.add_argument(
        "--no-legacy-hint",
        action="store_true",
        help="Suppress legacy migration hints for this invocation.",
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
        allow_abbrev=False,
    )
    inspect_parser.add_argument(
        "--rules-template",
        action="store_true",
        help="Print a canonical inspect rules JSON template and exit.",
    )
    inspect_parser.add_argument(
        "--rules-lint",
        default=None,
        help="Validate an inspect rules JSON file and exit.",
    )
    inspect_parser.add_argument("args", nargs=argparse.REMAINDER)
    inspect_compare_parser = sub.add_parser(
        "inspect-compare",
        help="[Advanced but supported] Compare inspect baseline/previous runs and drift evidence",
    )
    inspect_compare_parser.add_argument("--left", default=None)
    inspect_compare_parser.add_argument("--right", default=None)
    inspect_compare_parser.add_argument("--left-run", default=None)
    inspect_compare_parser.add_argument("--right-run", default=None)
    inspect_compare_parser.add_argument("--scope", default=None)
    inspect_compare_parser.add_argument("--latest-vs-previous", action="store_true")
    inspect_compare_parser.add_argument("--workspace-root", default=None)
    inspect_compare_parser.add_argument("--workflow", default=None)
    inspect_compare_parser.add_argument("--format", choices=["text", "json"], default=None)
    inspect_compare_parser.add_argument("--out-dir", default=None)
    inspect_compare_parser.add_argument("--no-workspace", action="store_true")
    inspect_compare_parser.add_argument("args", nargs=argparse.REMAINDER)
    inspect_project_parser = sub.add_parser(
        "inspect-project",
        help="[Advanced but supported] Run reusable inspection policy packs over project datasets",
    )
    inspect_project_parser.add_argument("project_dir")
    inspect_project_parser.add_argument("--policy", default=None)
    inspect_project_parser.add_argument("--workspace-root", default=None)
    inspect_project_parser.add_argument("--out-dir", default=None)
    inspect_project_parser.add_argument("--format", choices=["text", "json"], default=None)
    inspect_project_parser.add_argument("--no-workspace", action="store_true")
    review_parser = sub.add_parser(
        "review",
        help="[Public / stable] Front-door workflow that orchestrates doctor/inspect/judgment/history",
    )
    review_parser.add_argument("path")
    review_parser.add_argument("--workspace-root", default=None)
    review_parser.add_argument("--out-dir", default=None)
    review_parser.add_argument(
        "--profile", choices=["release", "triage", "forensics", "monitor"], default=None
    )
    review_parser.add_argument(
        "--format",
        choices=["text", "json", "operator-json"],
        default=None,
        help=(
            "Output format: json for full payload/debug automation; "
            "operator-json for the stable operator-facing integration contract."
        ),
    )
    review_parser.add_argument("--interactive", action="store_true")
    review_parser.add_argument("--no-workspace", action="store_true")
    review_parser.add_argument("--work-id", default=None)
    review_parser.add_argument("--work-context", action="append", default=None)
    review_parser.add_argument("--code-scan-json", default=None)

    serve_parser = sub.add_parser(
        "serve",
        help="[Public / stable] Run local API server for deterministic review automation",
    )
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)

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
    _add_passthrough_subcommand(
        sub,
        "contract",
        help_text="[Public / stable] Runtime/install integration contract surfaces for adopters",
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
        filter_hidden_subcommands(p)
    emit_cli_timing(
        f"event=parser-build show_hidden={str(show_hidden_commands).lower()} elapsed_ms={(time.perf_counter() - started) * 1000.0:.3f}"
    )
    return p, sub


def main(argv: Sequence[str] | None = None) -> int:

    if argv is None:
        argv = sys.argv[1:]

    argv, no_legacy_hint = extract_global_flag(argv, "--no-legacy-hint")

    if argv:
        argv = list(argv)
        argv[0] = resolve_non_day_playbook_alias(str(argv[0]))

    if argv and argv[0] == "legacy":
        legacy_result = handle_legacy_namespace(argv)
        if legacy_result is not None:
            return legacy_result
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

    preparse_result = dispatch_preparse_shortcut(
        argv,
        no_legacy_hint=no_legacy_hint,
        run_module_main=_run_module_main,
    )
    if preparse_result is not None:
        return preparse_result

    show_hidden_commands = "--show-hidden" in argv
    p, sub = _build_root_parser(show_hidden_commands=show_hidden_commands)

    if not show_hidden_commands:
        hide_help_subcommands(sub)

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
        if ns.args[0] == "migrate-hint":
            return run_legacy_migrate_hint(list(ns.args[1:]))
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
        if ns.rules_lint:
            inspect_args = ["--rules-lint", ns.rules_lint, *inspect_args]
        return _run_module_main("sdetkit.inspect_data", inspect_args)
    if ns.cmd == "inspect-compare":
        return _run_module_main(
            "sdetkit.inspect_compare",
            build_inspect_compare_forwarded_args(ns, ns.args),
        )
    if ns.cmd == "inspect-project":
        return _run_module_main("sdetkit.inspect_project", build_inspect_project_forwarded_args(ns))
    if ns.cmd == "review":
        return _run_module_main("sdetkit.review", build_review_forwarded_args(ns))

    if ns.cmd == "serve":
        return _run_module_main("sdetkit.serve", build_serve_args(ns))

    if ns.cmd == "init":
        return _run_module_main("sdetkit.repo", build_repo_init_forwarded_args(ns))

    parsed_shortcut_result = dispatch_parsed_shortcut(
        str(ns.cmd),
        list(getattr(ns, "args", [])),
        run_module_main=_run_module_main,
    )
    if parsed_shortcut_result is not None:
        return parsed_shortcut_result

    if ns.cmd == "apiget":
        return run_apiget_with_cassette(
            list(argv),
            cassette=getattr(ns, "cassette", None),
            cassette_mode=getattr(ns, "cassette_mode", None),
            run_module_main=_run_module_main,
        )
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
