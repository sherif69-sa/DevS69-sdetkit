from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from importlib import metadata

from . import (
    apiget,
    community_activation,
    contributor_funnel,
    day28_weekly_review,
    day29_phase1_hardening,
    day30_phase1_wrap,
    day31_phase2_kickoff,
    day32_release_cadence,
    day33_demo_asset,
    day34_demo_asset2,
    day35_kpi_instrumentation,
    day36_distribution_closeout,
    day37_experiment_lane,
    day38_distribution_batch,
    day39_playbook_post,
    day40_scale_lane,
    day41_expansion_automation,
    day42_optimization_closeout,
    day43_acceleration_closeout,
    day44_scale_closeout,
    day45_expansion_closeout,
    day46_optimization_closeout,
    day47_reliability_closeout,
    day48_objection_closeout,
    day49_weekly_review_closeout,
    day50_execution_prioritization_closeout,
    day51_case_snippet_closeout,
    day52_narrative_closeout,
    day53_docs_loop_closeout,
    day55_contributor_activation_closeout,
    day56_stabilization_closeout,
    day57_kpi_deep_audit_closeout,
    day58_phase2_hardening_closeout,
    day59_phase3_preplan_closeout,
    day60_phase2_wrap_handoff_closeout,
    day61_phase3_kickoff_closeout,
    day62_community_program_closeout,
    day63_onboarding_activation_closeout,
    day64_integration_expansion_closeout,
    day65_weekly_review_closeout,
    day66_integration_expansion2_closeout,
    day67_integration_expansion3_closeout,
    day68_integration_expansion4_closeout,
    day69_case_study_prep1_closeout,
    day70_case_study_prep2_closeout,
    day71_case_study_prep3_closeout,
    day72_case_study_prep4_closeout,
    day73_case_study_launch_closeout,
    day74_distribution_scaling_closeout,
    day75_trust_assets_refresh_closeout,
    day76_contributor_recognition_closeout,
    day77_community_touchpoint_closeout,
    day78_ecosystem_priorities_closeout,
    day79_scale_upgrade_closeout,
    day80_partner_outreach_closeout,
    day81_growth_campaign_closeout,
    day82_integration_feedback_closeout,
    day83_trust_faq_expansion_closeout,
    day84_evidence_narrative_closeout,
    day85_release_prioritization_closeout,
    day86_launch_readiness_closeout,
    day87_governance_handoff_closeout,
    day88_governance_priorities_closeout,
    day89_governance_scale_closeout,
    day90_phase3_wrap_publication_closeout,
    day91_continuous_upgrade_closeout,
    day92_continuous_upgrade_cycle2_closeout,
    day93_continuous_upgrade_cycle3_closeout,
    day94_continuous_upgrade_cycle4_closeout,
    day95_continuous_upgrade_cycle5_closeout,
    day96_continuous_upgrade_cycle6_closeout,
    day97_continuous_upgrade_cycle7_closeout,
    continuous_upgrade_cycle8_closeout,
    demo,
    docs_navigation,
    docs_qa,
    enterprise_use_case,
    evidence,
    external_contribution_push,
    faq_objections,
    first_contribution,
    forensics,
    github_actions_quickstart,
    gitlab_ci_quickstart,
    integration,
    intelligence,
    kits,
    kpi_audit,
    kvcli,
    notify,
    onboarding,
    onboarding_time_upgrade,
    ops,
    patch,
    phase_boost,
    policy,
    production_readiness,
    proof,
    quality_contribution_delta,
    release_narrative,
    release_readiness_board,
    reliability_evidence_pack,
    repo,
    report,
    roadmap,
    sdet_package,
    startup_use_case,
    triage_templates,
    trust_signal_upgrade,
    weekly_review,
)
from . import gate as gate_cmd
from .agent.cli import main as agent_main
from .maintenance import main as maintenance_main
from .public_surface_contract import render_root_help_groups
from .security_gate import main as security_main


def _tool_version() -> str:
    try:
        return metadata.version("sdetkit")
    except metadata.PackageNotFoundError:
        return "0+unknown"


def _add_apiget_args(p: argparse.ArgumentParser) -> None:
    apiget._add_apiget_args(p)

    p.add_argument("--cassette", default=None, help="Cassette file path (enables record/replay).")
    p.add_argument(
        "--cassette-mode",
        choices=["auto", "record", "replay"],
        default=None,
        help="Cassette mode: auto, record, or replay.",
    )


def _is_hidden_cmd(name: str) -> bool:
    if name == "playbooks":
        return False
    if name.startswith("impact") and len(name) > 3 and name[3].isdigit():
        return True
    if name.endswith("-closeout"):
        return True
    return False


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


def _print_playbooks(sub) -> None:
    mp = getattr(sub, "_name_parser_map", {})
    if not isinstance(mp, dict):
        return
    names = sorted([k for k in mp.keys() if isinstance(k, str) and _is_hidden_cmd(k)])
    print("Playbooks (hidden from main --help):")
    for n in names:
        print(f"  {n}")
    print("")
    print("Tip: these commands still run directly, e.g. sdetkit <name> --help")


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


def _build_root_parser() -> tuple[argparse.ArgumentParser, object]:
    help_description = """\
DevS69 SDETKit is an operator-grade SDET platform with four umbrella kits:
release confidence, test intelligence, integration assurance, and failure forensics.

Stability levels: Stable/Core, Stable/Compatibility, Stable/Supporting, Playbooks, Experimental.

Start here:
  1) [Stable/Core] Discover kits: sdetkit kits list
  2) [Stable/Core] Release lane: sdetkit release gate fast
  3) [Stable/Core] Test lane: sdetkit intelligence flake classify --history <history.json>
  4) [Stable/Compatibility] Existing direct commands (gate/doctor/security/...) still work
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
    sub = p.add_subparsers(
        dest="cmd",
        required=True,
        metavar="command",
        title="commands",
        description="Run `sdetkit <command> --help` for command-specific guidance.",
    )
    _add_passthrough_subcommand(sub, "baseline")
    sub.add_parser(
        "playbooks",
        help="Discover and run adoption/rollout playbooks",
    )
    _add_passthrough_subcommand(
        sub, "kits", help_text="[Stable/Core] Umbrella kit catalog and kit details"
    )

    _add_passthrough_subcommand(
        sub, "release", help_text="[Stable/Core] Release Confidence Kit (primary surface)"
    )
    _add_passthrough_subcommand(
        sub, "intelligence", help_text="[Stable/Core] Test Intelligence Kit (primary surface)"
    )
    _add_passthrough_subcommand(
        sub, "integration", help_text="[Stable/Core] Integration Assurance Kit (primary surface)"
    )
    _add_passthrough_subcommand(
        sub,
        "forensics",
        help_text="[Stable/Core] Failure Forensics Kit (experimental sublanes possible)",
    )
    _add_passthrough_subcommand(
        sub, "kv", help_text="Utility: parse key=value input into JSON (supporting surface)"
    )

    ag = sub.add_parser("apiget", help="Deterministic HTTP JSON fetch and replay helper")
    _add_apiget_args(ag)

    _add_passthrough_subcommand(
        sub,
        "doctor",
        help_text="[Stable/Compatibility] Deterministic repo and release-readiness checks",
    )

    _add_passthrough_subcommand(
        sub,
        "gate",
        help_text="[Stable/Compatibility] Quick confidence and strict release gate checks",
    )

    _add_passthrough_subcommand(sub, "ci", help_text="CI template and pipeline validation")

    _add_passthrough_subcommand(sub, "patch", help_text="Apply controlled file/text patches")

    _add_passthrough_subcommand(
        sub,
        "cassette-get",
        help_text="Utility: record/replay HTTP captures for deterministic checks",
    )

    _add_passthrough_subcommand(
        sub, "repo", help_text="[Stable/Compatibility] Repository automation tasks"
    )

    _add_passthrough_subcommand(sub, "dev", help_text="Shortcut to `repo dev` workflows")

    rpt = sub.add_parser("report", help="Reporting workflows and output packs")
    rpt.add_argument("args", nargs=argparse.REMAINDER)

    mnt = sub.add_parser("maintenance", help="Maintenance automation and cleanup")
    mnt.add_argument("args", nargs=argparse.REMAINDER)

    agt = sub.add_parser("agent", help="Agent-centric automation workflows")
    agt.add_argument("args", nargs=argparse.REMAINDER)

    sec = sub.add_parser(
        "security", help="[Stable/Compatibility] Security policy checks and enforcement"
    )
    sec.add_argument("args", nargs=argparse.REMAINDER)

    osp = sub.add_parser("ops", help="Operational control-plane workflows")
    osp.add_argument("args", nargs=argparse.REMAINDER)

    ntf = sub.add_parser("notify", help="Notification adapters and delivery workflows")
    ntf.add_argument("args", nargs=argparse.REMAINDER)

    plc = sub.add_parser("policy", help="Policy evaluation and helper commands")
    plc.add_argument("args", nargs=argparse.REMAINDER)

    evd = sub.add_parser(
        "evidence", help="[Stable/Compatibility] Generate audit-friendly release evidence"
    )
    evd.add_argument("args", nargs=argparse.REMAINDER)

    onb = sub.add_parser("onboarding", help="Role-based onboarding playbook")
    onb.add_argument("args", nargs=argparse.REMAINDER)

    otu = sub.add_parser("onboarding-time-upgrade", help="Onboarding-time improvement playbook")
    otu.add_argument("args", nargs=argparse.REMAINDER)

    cau = sub.add_parser("community-activation", help="Community activation rollout playbook")
    cau.add_argument("args", nargs=argparse.REMAINDER)

    ecp = sub.add_parser(
        "external-contribution-push", help="External contribution rollout playbook"
    )
    ecp.add_argument("args", nargs=argparse.REMAINDER)

    kpa = sub.add_parser("kpi-audit", help="KPI audit and tracking playbook")
    kpa.add_argument("args", nargs=argparse.REMAINDER)

    dwr = sub.add_parser("weekly-review-lane", aliases=["day28-weekly-review"])
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

    pa41 = sub.add_parser("expansion-automation")
    pa41.add_argument("args", nargs=argparse.REMAINDER)
    d41 = sub.add_parser("day41-expansion-automation")
    d41.add_argument("args", nargs=argparse.REMAINDER)

    pa42 = sub.add_parser("optimization-closeout-foundation")
    pa42.add_argument("args", nargs=argparse.REMAINDER)
    d42 = sub.add_parser("day42-optimization-closeout")
    d42.add_argument("args", nargs=argparse.REMAINDER)

    pa43 = sub.add_parser("acceleration-closeout")
    pa43.add_argument("args", nargs=argparse.REMAINDER)
    d43 = sub.add_parser("day43-acceleration-closeout")
    d43.add_argument("args", nargs=argparse.REMAINDER)

    pa44 = sub.add_parser("scale-closeout")
    pa44.add_argument("args", nargs=argparse.REMAINDER)
    d44 = sub.add_parser("day44-scale-closeout")
    d44.add_argument("args", nargs=argparse.REMAINDER)

    pa45 = sub.add_parser("expansion-closeout")
    pa45.add_argument("args", nargs=argparse.REMAINDER)
    d45 = sub.add_parser("day45-expansion-closeout")
    d45.add_argument("args", nargs=argparse.REMAINDER)

    pa46 = sub.add_parser("optimization-closeout")
    pa46.add_argument("args", nargs=argparse.REMAINDER)
    d46 = sub.add_parser("day46-optimization-closeout")
    d46.add_argument("args", nargs=argparse.REMAINDER)

    pa47 = sub.add_parser("reliability-closeout")
    pa47.add_argument("args", nargs=argparse.REMAINDER)
    d47 = sub.add_parser("day47-reliability-closeout")
    d47.add_argument("args", nargs=argparse.REMAINDER)
    pa48 = sub.add_parser("objection-closeout")
    pa48.add_argument("args", nargs=argparse.REMAINDER)
    d48 = sub.add_parser("day48-objection-closeout")
    d48.add_argument("args", nargs=argparse.REMAINDER)
    pa49 = sub.add_parser("weekly-review-closeout")
    pa49.add_argument("args", nargs=argparse.REMAINDER)
    d49 = sub.add_parser("day49-weekly-review-closeout")
    d49.add_argument("args", nargs=argparse.REMAINDER)
    d49_adv = sub.add_parser("day49-advanced-weekly-review-control-tower")
    d49_adv.add_argument("args", nargs=argparse.REMAINDER)
    pa50 = sub.add_parser("execution-prioritization-closeout")
    pa50.add_argument("args", nargs=argparse.REMAINDER)
    d50 = sub.add_parser("day50-execution-prioritization-closeout")
    d50.add_argument("args", nargs=argparse.REMAINDER)
    p51 = sub.add_parser("case-snippet-closeout")
    p51.add_argument("args", nargs=argparse.REMAINDER)
    d51 = sub.add_parser("day51-case-snippet-closeout")
    d51.add_argument("args", nargs=argparse.REMAINDER)
    p52 = sub.add_parser("narrative-closeout")
    p52.add_argument("args", nargs=argparse.REMAINDER)
    d52 = sub.add_parser("day52-narrative-closeout")
    d52.add_argument("args", nargs=argparse.REMAINDER)

    p53 = sub.add_parser("docs-loop-closeout")
    p53.add_argument("args", nargs=argparse.REMAINDER)
    d53 = sub.add_parser("day53-docs-loop-closeout")
    d53.add_argument("args", nargs=argparse.REMAINDER)

    p55 = sub.add_parser("contributor-activation-closeout")
    p55.add_argument("args", nargs=argparse.REMAINDER)
    d55 = sub.add_parser("day55-contributor-activation-closeout")
    d55.add_argument("args", nargs=argparse.REMAINDER)

    p56 = sub.add_parser("stabilization-closeout")
    p56.add_argument("args", nargs=argparse.REMAINDER)
    d56 = sub.add_parser("day56-stabilization-closeout")
    d56.add_argument("args", nargs=argparse.REMAINDER)

    p57 = sub.add_parser("kpi-deep-audit-closeout")
    p57.add_argument("args", nargs=argparse.REMAINDER)
    d57 = sub.add_parser("day57-kpi-deep-audit-closeout")
    d57.add_argument("args", nargs=argparse.REMAINDER)

    p58 = sub.add_parser("phase2-hardening-closeout")
    p58.add_argument("args", nargs=argparse.REMAINDER)
    d58 = sub.add_parser("day58-phase2-hardening-closeout")
    d58.add_argument("args", nargs=argparse.REMAINDER)

    p59 = sub.add_parser("phase3-preplan-closeout")
    p59.add_argument("args", nargs=argparse.REMAINDER)
    d59 = sub.add_parser("day59-phase3-preplan-closeout")
    d59.add_argument("args", nargs=argparse.REMAINDER)

    p60 = sub.add_parser("phase2-wrap-handoff-closeout")
    p60.add_argument("args", nargs=argparse.REMAINDER)
    d60 = sub.add_parser("day60-phase2-wrap-handoff-closeout")
    d60.add_argument("args", nargs=argparse.REMAINDER)

    d61 = sub.add_parser("phase3-kickoff-closeout", aliases=["day61-phase3-kickoff-closeout"])
    d61.set_defaults(cmd="phase3-kickoff-closeout")
    d61.add_argument("args", nargs=argparse.REMAINDER)

    d62 = sub.add_parser("community-program-closeout", aliases=["day62-community-program-closeout"])
    d62.set_defaults(cmd="community-program-closeout")
    d62.add_argument("args", nargs=argparse.REMAINDER)

    d63 = sub.add_parser(
        "onboarding-activation-closeout", aliases=["day63-onboarding-activation-closeout"]
    )
    d63.set_defaults(cmd="onboarding-activation-closeout")
    d63.add_argument("args", nargs=argparse.REMAINDER)

    d64 = sub.add_parser(
        "integration-expansion-closeout", aliases=["day64-integration-expansion-closeout"]
    )
    d64.set_defaults(cmd="integration-expansion-closeout")
    d64.add_argument("args", nargs=argparse.REMAINDER)

    d65 = sub.add_parser("weekly-review-closeout-cycle2", aliases=["day65-weekly-review-closeout"])
    d65.set_defaults(cmd="weekly-review-closeout-cycle2")
    d65.add_argument("args", nargs=argparse.REMAINDER)

    d66 = sub.add_parser(
        "integration-expansion2-closeout", aliases=["day66-integration-expansion2-closeout"]
    )
    d66.set_defaults(cmd="integration-expansion2-closeout")
    d66.add_argument("args", nargs=argparse.REMAINDER)

    d67 = sub.add_parser(
        "integration-expansion3-closeout", aliases=["day67-integration-expansion3-closeout"]
    )
    d67.set_defaults(cmd="integration-expansion3-closeout")
    d67.add_argument("args", nargs=argparse.REMAINDER)

    d68 = sub.add_parser(
        "integration-expansion4-closeout", aliases=["day68-integration-expansion4-closeout"]
    )
    d68.set_defaults(cmd="integration-expansion4-closeout")
    d68.add_argument("args", nargs=argparse.REMAINDER)

    d69 = sub.add_parser("case-study-prep1-closeout", aliases=["day69-case-study-prep1-closeout"])
    d69.set_defaults(cmd="case-study-prep1-closeout")
    d69.add_argument("args", nargs=argparse.REMAINDER)

    d70 = sub.add_parser("case-study-prep2-closeout", aliases=["day70-case-study-prep2-closeout"])
    d70.set_defaults(cmd="case-study-prep2-closeout")
    d70.add_argument("args", nargs=argparse.REMAINDER)
    d71 = sub.add_parser("case-study-prep3-closeout", aliases=["day71-case-study-prep3-closeout"])
    d71.set_defaults(cmd="case-study-prep3-closeout")
    d71.add_argument("args", nargs=argparse.REMAINDER)
    d72 = sub.add_parser("case-study-prep4-closeout", aliases=["day72-case-study-prep4-closeout"])
    d72.set_defaults(cmd="case-study-prep4-closeout")
    d72.add_argument("args", nargs=argparse.REMAINDER)
    d73 = sub.add_parser("case-study-launch-closeout", aliases=["day73-case-study-launch-closeout"])
    d73.set_defaults(cmd="case-study-launch-closeout")
    d73.add_argument("args", nargs=argparse.REMAINDER)
    d74 = sub.add_parser(
        "distribution-scaling-closeout", aliases=["day74-distribution-scaling-closeout"]
    )
    d74.set_defaults(cmd="distribution-scaling-closeout")
    d74.add_argument("args", nargs=argparse.REMAINDER)
    d75 = sub.add_parser(
        "trust-assets-refresh-closeout", aliases=["day75-trust-assets-refresh-closeout"]
    )
    d75.set_defaults(cmd="trust-assets-refresh-closeout")
    d75.add_argument("args", nargs=argparse.REMAINDER)
    d76 = sub.add_parser(
        "contributor-recognition-closeout", aliases=["day76-contributor-recognition-closeout"]
    )
    d76.set_defaults(cmd="contributor-recognition-closeout")
    d76.add_argument("args", nargs=argparse.REMAINDER)
    d77 = sub.add_parser(
        "community-touchpoint-closeout", aliases=["day77-community-touchpoint-closeout"]
    )
    d77.add_argument("args", nargs=argparse.REMAINDER)
    d78 = sub.add_parser(
        "ecosystem-priorities-closeout", aliases=["day78-ecosystem-priorities-closeout"]
    )
    d78.add_argument("args", nargs=argparse.REMAINDER)
    d79 = sub.add_parser("scale-upgrade-closeout", aliases=["day79-scale-upgrade-closeout"])
    d79.add_argument("args", nargs=argparse.REMAINDER)
    d80 = sub.add_parser("partner-outreach-closeout", aliases=["day80-partner-outreach-closeout"])
    d80.add_argument("args", nargs=argparse.REMAINDER)
    d81 = sub.add_parser("growth-campaign-closeout", aliases=["day81-growth-campaign-closeout"])
    d81.set_defaults(cmd="growth-campaign-closeout")
    d81.add_argument("args", nargs=argparse.REMAINDER)
    d82 = sub.add_parser(
        "integration-feedback-closeout", aliases=["day82-integration-feedback-closeout"]
    )
    d82.set_defaults(cmd="integration-feedback-closeout")
    d82.add_argument("args", nargs=argparse.REMAINDER)
    d83 = sub.add_parser(
        "trust-faq-expansion-closeout", aliases=["day83-trust-faq-expansion-closeout"]
    )
    d83.set_defaults(cmd="trust-faq-expansion-closeout")
    d83.add_argument("args", nargs=argparse.REMAINDER)
    d84 = sub.add_parser(
        "evidence-narrative-closeout", aliases=["day84-evidence-narrative-closeout"]
    )
    d84.set_defaults(cmd="evidence-narrative-closeout")
    d84.add_argument("args", nargs=argparse.REMAINDER)
    d85 = sub.add_parser(
        "release-prioritization-closeout", aliases=["day85-release-prioritization-closeout"]
    )
    d85.set_defaults(cmd="release-prioritization-closeout")
    d85.add_argument("args", nargs=argparse.REMAINDER)
    d86 = sub.add_parser("launch-readiness-closeout", aliases=["day86-launch-readiness-closeout"])
    d86.set_defaults(cmd="launch-readiness-closeout")
    d86.add_argument("args", nargs=argparse.REMAINDER)
    d87 = sub.add_parser(
        "governance-handoff-closeout", aliases=["day87-governance-handoff-closeout"]
    )
    d87.set_defaults(cmd="governance-handoff-closeout")
    d87.add_argument("args", nargs=argparse.REMAINDER)
    d88 = sub.add_parser(
        "governance-priorities-closeout", aliases=["day88-governance-priorities-closeout"]
    )
    d88.set_defaults(cmd="governance-priorities-closeout")
    d88.add_argument("args", nargs=argparse.REMAINDER)
    d89 = sub.add_parser("governance-scale-closeout", aliases=["day89-governance-scale-closeout"])
    d89.set_defaults(cmd="governance-scale-closeout")
    d89.add_argument("args", nargs=argparse.REMAINDER)
    d90 = sub.add_parser(
        "phase3-wrap-publication-closeout", aliases=["day90-phase3-wrap-publication-closeout"]
    )
    d90.set_defaults(cmd="phase3-wrap-publication-closeout")
    d90.add_argument("args", nargs=argparse.REMAINDER)
    d91 = sub.add_parser(
        "continuous-upgrade-closeout", aliases=["day91-continuous-upgrade-closeout"]
    )
    d91.set_defaults(cmd="continuous-upgrade-closeout")
    d91.add_argument("args", nargs=argparse.REMAINDER)
    d92 = sub.add_parser(
        "continuous-upgrade-cycle2-closeout", aliases=["day92-continuous-upgrade-cycle2-closeout"]
    )
    d92.set_defaults(cmd="continuous-upgrade-cycle2-closeout")
    d92.add_argument("args", nargs=argparse.REMAINDER)
    d93 = sub.add_parser(
        "continuous-upgrade-cycle3-closeout", aliases=["day93-continuous-upgrade-cycle3-closeout"]
    )
    d93.set_defaults(cmd="continuous-upgrade-cycle3-closeout")
    d93.add_argument("args", nargs=argparse.REMAINDER)
    d94 = sub.add_parser(
        "continuous-upgrade-cycle4-closeout", aliases=["day94-continuous-upgrade-cycle4-closeout"]
    )
    d94.set_defaults(cmd="continuous-upgrade-cycle4-closeout")
    d94.add_argument("args", nargs=argparse.REMAINDER)
    d95 = sub.add_parser(
        "continuous-upgrade-cycle5-closeout", aliases=["day95-continuous-upgrade-cycle5-closeout"]
    )
    d95.set_defaults(cmd="continuous-upgrade-cycle5-closeout")
    d95.add_argument("args", nargs=argparse.REMAINDER)
    d96 = sub.add_parser(
        "continuous-upgrade-cycle6-closeout", aliases=["day96-continuous-upgrade-cycle6-closeout"]
    )
    d96.set_defaults(cmd="continuous-upgrade-cycle6-closeout")
    d96.add_argument("args", nargs=argparse.REMAINDER)
    d97 = sub.add_parser(
        "continuous-upgrade-cycle7-closeout", aliases=["day97-continuous-upgrade-cycle7-closeout"]
    )
    d97.set_defaults(cmd="continuous-upgrade-cycle7-closeout")
    d97.add_argument("args", nargs=argparse.REMAINDER)
    d98 = sub.add_parser(
        "continuous-upgrade-cycle8-closeout"
    )
    d98.set_defaults(cmd="continuous-upgrade-cycle8-closeout")
    d98.add_argument("args", nargs=argparse.REMAINDER)

    fqo = sub.add_parser("faq-objections", help="FAQ objections playbook")
    fqo.add_argument("args", nargs=argparse.REMAINDER)

    dmo = sub.add_parser("demo")
    dmo.add_argument("args", nargs=argparse.REMAINDER)

    fct = sub.add_parser("first-contribution", help="First contribution playbook")
    fct.add_argument("args", nargs=argparse.REMAINDER)

    ctf = sub.add_parser("contributor-funnel", help="Contributor funnel playbook")
    ctf.add_argument("args", nargs=argparse.REMAINDER)

    prf = sub.add_parser("proof", help="Proof and evidence workflows")
    prf.add_argument("args", nargs=argparse.REMAINDER)

    ttp = sub.add_parser("triage-templates", help="Issue and triage template workflows")
    ttp.add_argument("args", nargs=argparse.REMAINDER)

    dqa = sub.add_parser("docs-qa", help="Docs quality and link checks")
    dqa.add_argument("args", nargs=argparse.REMAINDER)

    wrv = sub.add_parser("weekly-review", help="Weekly review playbook")
    wrv.add_argument("args", nargs=argparse.REMAINDER)

    dnv = sub.add_parser("docs-nav", help="Docs navigation validation")
    dnv.add_argument("args", nargs=argparse.REMAINDER)
    rdm = sub.add_parser("roadmap")
    rdm.add_argument("args", nargs=argparse.REMAINDER)

    suc = sub.add_parser("startup-use-case", help="Startup use-case playbook")
    suc.add_argument("args", nargs=argparse.REMAINDER)

    spk = sub.add_parser("sdet-package")
    spk.add_argument("args", nargs=argparse.REMAINDER)

    euc = sub.add_parser("enterprise-use-case", help="Enterprise use-case playbook")
    euc.add_argument("args", nargs=argparse.REMAINDER)

    gha = sub.add_parser("github-actions-quickstart", help="GitHub Actions quickstart playbook")
    gha.add_argument("args", nargs=argparse.REMAINDER)

    glc = sub.add_parser("gitlab-ci-quickstart", help="GitLab CI quickstart playbook")
    glc.add_argument("args", nargs=argparse.REMAINDER)

    qcd = sub.add_parser("quality-contribution-delta", help="Quality contribution delta report")
    qcd.add_argument("args", nargs=argparse.REMAINDER)

    rep = sub.add_parser("reliability-evidence-pack", help="Reliability evidence pack")
    rep.add_argument("args", nargs=argparse.REMAINDER)

    rrb = sub.add_parser("release-readiness-board", help="Release readiness board")
    rrb.add_argument("args", nargs=argparse.REMAINDER)

    rn = sub.add_parser("release-narrative", help="Release narrative playbook")
    rn.add_argument("args", nargs=argparse.REMAINDER)

    tsu = sub.add_parser("trust-signal-upgrade", help="Trust signal upgrade playbook")
    tsu.add_argument("args", nargs=argparse.REMAINDER)
    return p, sub


def main(argv: Sequence[str] | None = None) -> int:

    if argv is None:
        argv = sys.argv[1:]

    if argv:
        argv = list(argv)
        argv[0] = _resolve_non_day_playbook_alias(str(argv[0]))

    if argv and argv[0] == "playbooks":
        from .playbooks_cli import main as _playbooks_main

        return _playbooks_main(list(argv[1:]))

    if argv and argv[0] == "cassette-get":
        from .__main__ import _cassette_get

        try:
            return _cassette_get(argv[1:])
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 2

    if argv and argv[0] == "doctor":
        from .doctor import main as _doctor_main

        return _doctor_main(argv[1:])

    if argv and argv[0] == "gate":
        from .gate import main as _gate_main

        return _gate_main(list(argv[1:]))

    if argv and argv[0] == "ci":
        from .ci import main as _ci_main

        return _ci_main(list(argv[1:]))

    if argv and argv[0] == "patch":
        return patch.main(list(argv[1:]))

    if argv and argv[0] == "repo":
        return repo.main(list(argv[1:]))

    if argv and argv[0] == "dev":
        return repo.main(["dev", *list(argv[1:])])

    if argv and argv[0] == "report":
        return report.main(list(argv[1:]))

    if argv and argv[0] == "maintenance":
        return maintenance_main(list(argv[1:]))

    if argv and argv[0] == "agent":
        return agent_main(list(argv[1:]))

    if argv and argv[0] == "security":
        return security_main(list(argv[1:]))

    if argv and argv[0] == "ops":
        return ops.main(list(argv[1:]))

    if argv and argv[0] == "notify":
        return notify.main(list(argv[1:]))

    if argv and argv[0] == "policy":
        return policy.main(list(argv[1:]))

    if argv and argv[0] == "evidence":
        return evidence.main(list(argv[1:]))

    if argv and argv[0] == "onboarding":
        return onboarding.main(list(argv[1:]))

    if argv and argv[0] == "onboarding-time-upgrade":
        return onboarding_time_upgrade.main(list(argv[1:]))

    if argv and argv[0] == "phase-boost":
        return phase_boost.main(list(argv[1:]))

    if argv and argv[0] == "production-readiness":
        return production_readiness.main(list(argv[1:]))

    if argv and argv[0] == "community-activation":
        return community_activation.main(list(argv[1:]))

    if argv and argv[0] == "external-contribution-push":
        return external_contribution_push.main(list(argv[1:]))

    if argv and argv[0] == "kpi-audit":
        return kpi_audit.main(list(argv[1:]))

    if argv and argv[0] in {"weekly-review-lane", "day28-weekly-review"}:
        return day28_weekly_review.main(list(argv[1:]))

    if argv and argv[0] == "phase1-hardening":
        return day29_phase1_hardening.main(list(argv[1:]))

    if argv and argv[0] == "phase1-wrap":
        return day30_phase1_wrap.main(list(argv[1:]))

    if argv and argv[0] == "phase2-kickoff":
        return day31_phase2_kickoff.main(list(argv[1:]))

    if argv and argv[0] == "release-cadence":
        return day32_release_cadence.main(list(argv[1:]))

    if argv and argv[0] == "demo-asset":
        return day33_demo_asset.main(list(argv[1:]))

    if argv and argv[0] == "demo-asset2":
        return day34_demo_asset2.main(list(argv[1:]))

    if argv and argv[0] == "kpi-instrumentation":
        return day35_kpi_instrumentation.main(list(argv[1:]))

    if argv and argv[0] == "distribution-closeout":
        return day36_distribution_closeout.main(list(argv[1:]))

    if argv and argv[0] == "experiment-lane":
        return day37_experiment_lane.main(list(argv[1:]))

    if argv and argv[0] == "distribution-batch":
        return day38_distribution_batch.main(list(argv[1:]))

    if argv and argv[0] == "playbook-post":
        return day39_playbook_post.main(list(argv[1:]))

    if argv and argv[0] == "scale-lane":
        return day40_scale_lane.main(list(argv[1:]))

    if argv and argv[0] == "expansion-automation":
        return day41_expansion_automation.main(list(argv[1:]))
    if argv and argv[0] == "day41-expansion-automation":
        return day41_expansion_automation.main(list(argv[1:]))

    if argv and argv[0] in {"optimization-closeout-foundation", "day42-optimization-closeout"}:
        return day42_optimization_closeout.main(list(argv[1:]))

    if argv and argv[0] == "acceleration-closeout":
        return day43_acceleration_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day43-acceleration-closeout":
        return day43_acceleration_closeout.main(list(argv[1:]))

    if argv and argv[0] == "scale-closeout":
        return day44_scale_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day44-scale-closeout":
        return day44_scale_closeout.main(list(argv[1:]))

    if argv and argv[0] == "expansion-closeout":
        return day45_expansion_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day45-expansion-closeout":
        return day45_expansion_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"optimization-closeout", "day46-optimization-closeout"}:
        return day46_optimization_closeout.main(list(argv[1:]))

    if argv and argv[0] == "reliability-closeout":
        return day47_reliability_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day47-reliability-closeout":
        return day47_reliability_closeout.main(list(argv[1:]))
    if argv and argv[0] == "objection-closeout":
        return day48_objection_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day48-objection-closeout":
        return day48_objection_closeout.main(list(argv[1:]))
    if argv and argv[0] in {
        "weekly-review-closeout",
        "day49-weekly-review-closeout",
        "day49-advanced-weekly-review-control-tower",
    }:
        return day49_weekly_review_closeout.main(list(argv[1:]))
    if argv and argv[0] in {
        "execution-prioritization-closeout",
        "day50-execution-prioritization-closeout",
    }:
        return day50_execution_prioritization_closeout.main(list(argv[1:]))
    if argv and argv[0] in {"case-snippet-closeout", "day51-case-snippet-closeout"}:
        return day51_case_snippet_closeout.main(list(argv[1:]))
    if argv and argv[0] in {"narrative-closeout", "day52-narrative-closeout"}:
        return day52_narrative_closeout.main(list(argv[1:]))
    if argv and argv[0] in {"docs-loop-closeout", "day53-docs-loop-closeout"}:
        return day53_docs_loop_closeout.main(list(argv[1:]))
    if argv and argv[0] in {
        "contributor-activation-closeout",
        "day55-contributor-activation-closeout",
    }:
        return day55_contributor_activation_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"stabilization-closeout", "day56-stabilization-closeout"}:
        return day56_stabilization_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"kpi-deep-audit-closeout", "day57-kpi-deep-audit-closeout"}:
        return day57_kpi_deep_audit_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"phase2-hardening-closeout", "day58-phase2-hardening-closeout"}:
        return day58_phase2_hardening_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"phase3-preplan-closeout", "day59-phase3-preplan-closeout"}:
        return day59_phase3_preplan_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"phase2-wrap-handoff-closeout", "day60-phase2-wrap-handoff-closeout"}:
        return day60_phase2_wrap_handoff_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"phase3-kickoff-closeout", "day61-phase3-kickoff-closeout"}:
        return day61_phase3_kickoff_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"community-program-closeout", "day62-community-program-closeout"}:
        return day62_community_program_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "onboarding-activation-closeout",
        "day63-onboarding-activation-closeout",
    }:
        return day63_onboarding_activation_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion-closeout",
        "day64-integration-expansion-closeout",
    }:
        return day64_integration_expansion_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"weekly-review-closeout-cycle2", "day65-weekly-review-closeout"}:
        return day65_weekly_review_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion2-closeout",
        "day66-integration-expansion2-closeout",
    }:
        return day66_integration_expansion2_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion3-closeout",
        "day67-integration-expansion3-closeout",
    }:
        return day67_integration_expansion3_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "integration-expansion4-closeout",
        "day68-integration-expansion4-closeout",
    }:
        return day68_integration_expansion4_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"case-study-prep1-closeout", "day69-case-study-prep1-closeout"}:
        return day69_case_study_prep1_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"case-study-prep2-closeout", "day70-case-study-prep2-closeout"}:
        return day70_case_study_prep2_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"case-study-prep3-closeout", "day71-case-study-prep3-closeout"}:
        return day71_case_study_prep3_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"case-study-prep4-closeout", "day72-case-study-prep4-closeout"}:
        return day72_case_study_prep4_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"case-study-launch-closeout", "day73-case-study-launch-closeout"}:
        return day73_case_study_launch_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"distribution-scaling-closeout", "day74-distribution-scaling-closeout"}:
        return day74_distribution_scaling_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"trust-assets-refresh-closeout", "day75-trust-assets-refresh-closeout"}:
        return day75_trust_assets_refresh_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "contributor-recognition-closeout",
        "day76-contributor-recognition-closeout",
    }:
        return day76_contributor_recognition_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"community-touchpoint-closeout", "day77-community-touchpoint-closeout"}:
        return day77_community_touchpoint_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"ecosystem-priorities-closeout", "day78-ecosystem-priorities-closeout"}:
        return day78_ecosystem_priorities_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"scale-upgrade-closeout", "day79-scale-upgrade-closeout"}:
        return day79_scale_upgrade_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"partner-outreach-closeout", "day80-partner-outreach-closeout"}:
        return day80_partner_outreach_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"growth-campaign-closeout", "day81-growth-campaign-closeout"}:
        return day81_growth_campaign_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"integration-feedback-closeout", "day82-integration-feedback-closeout"}:
        return day82_integration_feedback_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"trust-faq-expansion-closeout", "day83-trust-faq-expansion-closeout"}:
        return day83_trust_faq_expansion_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"evidence-narrative-closeout", "day84-evidence-narrative-closeout"}:
        return day84_evidence_narrative_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "release-prioritization-closeout",
        "day85-release-prioritization-closeout",
    }:
        return day85_release_prioritization_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"launch-readiness-closeout", "day86-launch-readiness-closeout"}:
        return day86_launch_readiness_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"governance-handoff-closeout", "day87-governance-handoff-closeout"}:
        return day87_governance_handoff_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "governance-priorities-closeout",
        "day88-governance-priorities-closeout",
    }:
        return day88_governance_priorities_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"governance-scale-closeout", "day89-governance-scale-closeout"}:
        return day89_governance_scale_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "phase3-wrap-publication-closeout",
        "day90-phase3-wrap-publication-closeout",
    }:
        return day90_phase3_wrap_publication_closeout.main(list(argv[1:]))

    if argv and argv[0] in {"continuous-upgrade-closeout", "day91-continuous-upgrade-closeout"}:
        return day91_continuous_upgrade_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "continuous-upgrade-cycle2-closeout",
        "day92-continuous-upgrade-cycle2-closeout",
    }:
        return day92_continuous_upgrade_cycle2_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "continuous-upgrade-cycle3-closeout",
        "day93-continuous-upgrade-cycle3-closeout",
    }:
        return day93_continuous_upgrade_cycle3_closeout.main(list(argv[1:]))

    if argv and argv[0] in {
        "continuous-upgrade-cycle4-closeout",
        "day94-continuous-upgrade-cycle4-closeout",
    }:
        return day94_continuous_upgrade_cycle4_closeout.main(list(argv[1:]))
    if argv and argv[0] in {
        "continuous-upgrade-cycle5-closeout",
        "day95-continuous-upgrade-cycle5-closeout",
    }:
        return day95_continuous_upgrade_cycle5_closeout.main(list(argv[1:]))
    if argv and argv[0] in {
        "continuous-upgrade-cycle6-closeout",
        "day96-continuous-upgrade-cycle6-closeout",
    }:
        return day96_continuous_upgrade_cycle6_closeout.main(list(argv[1:]))
    if argv and argv[0] in {
        "continuous-upgrade-cycle7-closeout",
        "day97-continuous-upgrade-cycle7-closeout",
    }:
        return day97_continuous_upgrade_cycle7_closeout.main(list(argv[1:]))
    if argv and argv[0] == "continuous-upgrade-cycle8-closeout":
        return continuous_upgrade_cycle8_closeout.main(list(argv[1:]))

    if argv and argv[0] == "faq-objections":
        return faq_objections.main(list(argv[1:]))

    if argv and argv[0] == "first-contribution":
        return first_contribution.main(list(argv[1:]))

    if argv and argv[0] == "demo":
        return demo.main(list(argv[1:]))

    if argv and argv[0] == "contributor-funnel":
        return contributor_funnel.main(list(argv[1:]))

    if argv and argv[0] == "proof":
        return proof.main(list(argv[1:]))

    if argv and argv[0] == "triage-templates":
        return triage_templates.main(list(argv[1:]))

    if argv and argv[0] == "docs-qa":
        return docs_qa.main(list(argv[1:]))

    if argv and argv[0] == "weekly-review":
        return weekly_review.main(list(argv[1:]))

    if argv and argv[0] == "docs-nav":
        return docs_navigation.main(list(argv[1:]))
    if argv and argv[0] == "roadmap":
        return roadmap.main(list(argv[1:]))

    if argv and argv[0] == "startup-use-case":
        return startup_use_case.main(list(argv[1:]))

    if argv and argv[0] == "sdet-package":
        return sdet_package.main(list(argv[1:]))

    if argv and argv[0] == "enterprise-use-case":
        return enterprise_use_case.main(list(argv[1:]))

    if argv and argv[0] == "github-actions-quickstart":
        return github_actions_quickstart.main(list(argv[1:]))

    if argv and argv[0] == "gitlab-ci-quickstart":
        return gitlab_ci_quickstart.main(list(argv[1:]))

    if argv and argv[0] == "quality-contribution-delta":
        return quality_contribution_delta.main(list(argv[1:]))

    if argv and argv[0] == "reliability-evidence-pack":
        return reliability_evidence_pack.main(list(argv[1:]))

    if argv and argv[0] == "release-readiness-board":
        return release_readiness_board.main(list(argv[1:]))

    if argv and argv[0] == "release-narrative":
        return release_narrative.main(list(argv[1:]))

    if argv and argv[0] == "trust-signal-upgrade":
        return trust_signal_upgrade.main(list(argv[1:]))

    p, sub = _build_root_parser()

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
        _print_playbooks(sub)

        return 0

    if ns.cmd == "kits":
        return kits.main(ns.args)

    if ns.cmd == "release":
        if not ns.args:
            sys.stderr.write(
                "release error: expected subcommand (gate|doctor|security|evidence|repo)\n"
            )
            return 2
        subcmd = ns.args[0]
        rest = ns.args[1:]
        if subcmd == "gate":
            return gate_cmd.main(rest)
        if subcmd == "doctor":
            return doctor.main(rest)
        if subcmd == "security":
            return security_main(rest)
        if subcmd == "evidence":
            return evidence.main(rest)
        if subcmd == "repo":
            return repo.main(rest)
        sys.stderr.write(
            "release error: supported subcommands are gate|doctor|security|evidence|repo\n"
        )
        return 2

    if ns.cmd == "intelligence":
        return intelligence.main(ns.args)

    if ns.cmd == "integration":
        return integration.main(ns.args)

    if ns.cmd == "forensics":
        return forensics.main(ns.args)

    if ns.cmd == "kv":
        return kvcli.main(ns.args)

    if ns.cmd == "patch":
        return patch.main(ns.args)

    if ns.cmd == "repo":
        return repo.main(ns.args)

    if ns.cmd == "dev":
        return repo.main(["dev", *ns.args])

    if ns.cmd == "report":
        return report.main(ns.args)

    if ns.cmd == "maintenance":
        return maintenance_main(ns.args)

    if ns.cmd == "agent":
        return agent_main(ns.args)

    if ns.cmd == "security":
        return security_main(ns.args)

    if ns.cmd == "ops":
        return ops.main(ns.args)

    if ns.cmd == "notify":
        return notify.main(ns.args)

    if ns.cmd == "policy":
        return policy.main(ns.args)

    if ns.cmd == "evidence":
        return evidence.main(ns.args)

    if ns.cmd == "onboarding":
        return onboarding.main(ns.args)

    if ns.cmd == "onboarding-time-upgrade":
        return onboarding_time_upgrade.main(ns.args)

    if ns.cmd == "community-activation":
        return community_activation.main(ns.args)

    if ns.cmd == "external-contribution-push":
        return external_contribution_push.main(ns.args)

    if ns.cmd == "kpi-audit":
        return kpi_audit.main(ns.args)

    if ns.cmd == "day28-weekly-review":
        return day28_weekly_review.main(ns.args)

    if ns.cmd in {"expansion-automation", "day41-expansion-automation"}:
        return day41_expansion_automation.main(ns.args)

    if ns.cmd in {"optimization-closeout-foundation", "day42-optimization-closeout"}:
        return day42_optimization_closeout.main(ns.args)

    if ns.cmd in {"acceleration-closeout", "day43-acceleration-closeout"}:
        return day43_acceleration_closeout.main(ns.args)

    if ns.cmd in {"scale-closeout", "day44-scale-closeout"}:
        return day44_scale_closeout.main(ns.args)

    if ns.cmd in {"expansion-closeout", "day45-expansion-closeout"}:
        return day45_expansion_closeout.main(ns.args)

    if ns.cmd in {"optimization-closeout", "day46-optimization-closeout"}:
        return day46_optimization_closeout.main(ns.args)

    if ns.cmd in {"reliability-closeout", "day47-reliability-closeout"}:
        return day47_reliability_closeout.main(ns.args)
    if ns.cmd in {"objection-closeout", "day48-objection-closeout"}:
        return day48_objection_closeout.main(ns.args)
    if ns.cmd in {
        "weekly-review-closeout",
        "day49-weekly-review-closeout",
        "day49-advanced-weekly-review-control-tower",
    }:
        return day49_weekly_review_closeout.main(ns.args)
    if ns.cmd in {"execution-prioritization-closeout", "day50-execution-prioritization-closeout"}:
        return day50_execution_prioritization_closeout.main(ns.args)
    if ns.cmd in {"case-snippet-closeout", "day51-case-snippet-closeout"}:
        return day51_case_snippet_closeout.main(ns.args)
    if ns.cmd in {"narrative-closeout", "day52-narrative-closeout"}:
        return day52_narrative_closeout.main(ns.args)
    if ns.cmd in {"docs-loop-closeout", "day53-docs-loop-closeout"}:
        return day53_docs_loop_closeout.main(ns.args)
    if ns.cmd in {"contributor-activation-closeout", "day55-contributor-activation-closeout"}:
        return day55_contributor_activation_closeout.main(ns.args)

    if ns.cmd in {"stabilization-closeout", "day56-stabilization-closeout"}:
        return day56_stabilization_closeout.main(ns.args)

    if ns.cmd in {"kpi-deep-audit-closeout", "day57-kpi-deep-audit-closeout"}:
        return day57_kpi_deep_audit_closeout.main(ns.args)

    if ns.cmd in {"phase2-hardening-closeout", "day58-phase2-hardening-closeout"}:
        return day58_phase2_hardening_closeout.main(ns.args)

    if ns.cmd in {"phase3-preplan-closeout", "day59-phase3-preplan-closeout"}:
        return day59_phase3_preplan_closeout.main(ns.args)

    if ns.cmd in {"phase2-wrap-handoff-closeout", "day60-phase2-wrap-handoff-closeout"}:
        return day60_phase2_wrap_handoff_closeout.main(ns.args)

    if ns.cmd in {"phase3-kickoff-closeout", "day61-phase3-kickoff-closeout"}:
        return day61_phase3_kickoff_closeout.main(ns.args)

    if ns.cmd in {"community-program-closeout", "day62-community-program-closeout"}:
        return day62_community_program_closeout.main(ns.args)

    if ns.cmd in {"onboarding-activation-closeout", "day63-onboarding-activation-closeout"}:
        return day63_onboarding_activation_closeout.main(ns.args)

    if ns.cmd in {"integration-expansion-closeout", "day64-integration-expansion-closeout"}:
        return day64_integration_expansion_closeout.main(ns.args)

    if ns.cmd in {"weekly-review-closeout-cycle2", "day65-weekly-review-closeout"}:
        return day65_weekly_review_closeout.main(ns.args)

    if ns.cmd in {"integration-expansion2-closeout", "day66-integration-expansion2-closeout"}:
        return day66_integration_expansion2_closeout.main(ns.args)

    if ns.cmd in {"integration-expansion3-closeout", "day67-integration-expansion3-closeout"}:
        return day67_integration_expansion3_closeout.main(ns.args)

    if ns.cmd in {"integration-expansion4-closeout", "day68-integration-expansion4-closeout"}:
        return day68_integration_expansion4_closeout.main(ns.args)

    if ns.cmd in {"case-study-prep1-closeout", "day69-case-study-prep1-closeout"}:
        return day69_case_study_prep1_closeout.main(ns.args)

    if ns.cmd in {"case-study-prep2-closeout", "day70-case-study-prep2-closeout"}:
        return day70_case_study_prep2_closeout.main(ns.args)

    if ns.cmd == "case-study-prep3-closeout":
        return day71_case_study_prep3_closeout.main(ns.args)

    if ns.cmd == "case-study-prep4-closeout":
        return day72_case_study_prep4_closeout.main(ns.args)

    if ns.cmd == "case-study-launch-closeout":
        return day73_case_study_launch_closeout.main(ns.args)

    if ns.cmd == "distribution-scaling-closeout":
        return day74_distribution_scaling_closeout.main(ns.args)

    if ns.cmd == "trust-assets-refresh-closeout":
        return day75_trust_assets_refresh_closeout.main(ns.args)

    if ns.cmd == "contributor-recognition-closeout":
        return day76_contributor_recognition_closeout.main(ns.args)

    if ns.cmd == "community-touchpoint-closeout":
        return day77_community_touchpoint_closeout.main(ns.args)

    if ns.cmd == "ecosystem-priorities-closeout":
        return day78_ecosystem_priorities_closeout.main(ns.args)

    if ns.cmd == "scale-upgrade-closeout":
        return day79_scale_upgrade_closeout.main(ns.args)

    if ns.cmd == "partner-outreach-closeout":
        return day80_partner_outreach_closeout.main(ns.args)

    if ns.cmd == "day81-growth-campaign-closeout":
        return day81_growth_campaign_closeout.main(ns.args)

    if ns.cmd == "day82-integration-feedback-closeout":
        return day82_integration_feedback_closeout.main(ns.args)

    if ns.cmd == "day83-trust-faq-expansion-closeout":
        return day83_trust_faq_expansion_closeout.main(ns.args)

    if ns.cmd == "day84-evidence-narrative-closeout":
        return day84_evidence_narrative_closeout.main(ns.args)

    if ns.cmd == "day85-release-prioritization-closeout":
        return day85_release_prioritization_closeout.main(ns.args)

    if ns.cmd == "day86-launch-readiness-closeout":
        return day86_launch_readiness_closeout.main(ns.args)

    if ns.cmd == "day87-governance-handoff-closeout":
        return day87_governance_handoff_closeout.main(ns.args)

    if ns.cmd == "day88-governance-priorities-closeout":
        return day88_governance_priorities_closeout.main(ns.args)

    if ns.cmd == "day89-governance-scale-closeout":
        return day89_governance_scale_closeout.main(ns.args)

    if ns.cmd == "day90-phase3-wrap-publication-closeout":
        return day90_phase3_wrap_publication_closeout.main(ns.args)

    if ns.cmd == "day91-continuous-upgrade-closeout":
        return day91_continuous_upgrade_closeout.main(ns.args)

    if ns.cmd == "day92-continuous-upgrade-cycle2-closeout":
        return day92_continuous_upgrade_cycle2_closeout.main(ns.args)

    if ns.cmd == "day93-continuous-upgrade-cycle3-closeout":
        return day93_continuous_upgrade_cycle3_closeout.main(ns.args)

    if ns.cmd in {"continuous-upgrade-cycle4-closeout", "day94-continuous-upgrade-cycle4-closeout"}:
        return day94_continuous_upgrade_cycle4_closeout.main(ns.args)
    if ns.cmd in {"continuous-upgrade-cycle5-closeout", "day95-continuous-upgrade-cycle5-closeout"}:
        return day95_continuous_upgrade_cycle5_closeout.main(ns.args)
    if ns.cmd in {"continuous-upgrade-cycle6-closeout", "day96-continuous-upgrade-cycle6-closeout"}:
        return day96_continuous_upgrade_cycle6_closeout.main(ns.args)
    if ns.cmd in {"continuous-upgrade-cycle7-closeout", "day97-continuous-upgrade-cycle7-closeout"}:
        return day97_continuous_upgrade_cycle7_closeout.main(ns.args)

    if ns.cmd == "continuous-upgrade-cycle8-closeout":
        return continuous_upgrade_cycle8_closeout.main(ns.args)

    if ns.cmd == "faq-objections":
        return faq_objections.main(ns.args)

    if ns.cmd == "demo":
        return demo.main(ns.args)

    if ns.cmd == "first-contribution":
        return first_contribution.main(ns.args)

    if ns.cmd == "contributor-funnel":
        return contributor_funnel.main(ns.args)

    if ns.cmd == "proof":
        return proof.main(ns.args)

    if ns.cmd == "triage-templates":
        return triage_templates.main(ns.args)

    if ns.cmd == "docs-qa":
        return docs_qa.main(ns.args)

    if ns.cmd == "weekly-review":
        return weekly_review.main(ns.args)

    if ns.cmd == "docs-nav":
        return docs_navigation.main(ns.args)
    if ns.cmd == "roadmap":
        return roadmap.main(ns.args)

    if ns.cmd == "startup-use-case":
        return startup_use_case.main(ns.args)

    if ns.cmd == "sdet-package":
        return sdet_package.main(ns.args)

    if ns.cmd == "enterprise-use-case":
        return enterprise_use_case.main(ns.args)

    if ns.cmd == "github-actions-quickstart":
        return github_actions_quickstart.main(ns.args)

    if ns.cmd == "gitlab-ci-quickstart":
        return gitlab_ci_quickstart.main(ns.args)

    if ns.cmd == "quality-contribution-delta":
        return quality_contribution_delta.main(ns.args)

    if ns.cmd == "reliability-evidence-pack":
        return reliability_evidence_pack.main(ns.args)

    if ns.cmd == "release-readiness-board":
        return release_readiness_board.main(ns.args)

    if ns.cmd == "release-narrative":
        return release_narrative.main(ns.args)

    if ns.cmd == "trust-signal-upgrade":
        return trust_signal_upgrade.main(ns.args)

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
            return apiget.main(rest)
        old_cassette = os.environ.get("SDETKIT_CASSETTE")
        old_mode = os.environ.get("SDETKIT_CASSETTE_MODE")
        try:
            os.environ["SDETKIT_CASSETTE"] = str(cassette)
            os.environ["SDETKIT_CASSETTE_MODE"] = str(cassette_mode)
            return apiget.main(rest)
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
