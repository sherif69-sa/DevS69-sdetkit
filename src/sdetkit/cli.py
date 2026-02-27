from __future__ import annotations

import argparse
import os
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
    demo,
    docs_navigation,
    docs_qa,
    enterprise_use_case,
    evidence,
    external_contribution_push,
    faq_objections,
    first_contribution,
    github_actions_quickstart,
    gitlab_ci_quickstart,
    kpi_audit,
    kvcli,
    notify,
    onboarding,
    onboarding_time_upgrade,
    ops,
    patch,
    policy,
    proof,
    quality_contribution_delta,
    release_narrative,
    release_readiness_board,
    reliability_evidence_pack,
    repo,
    report,
    startup_use_case,
    triage_templates,
    trust_signal_upgrade,
    weekly_review,
)
from .agent.cli import main as agent_main
from .maintenance import main as maintenance_main
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


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    if argv is None:
        argv = sys.argv[1:]

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

    if argv and argv[0] == "community-activation":
        return community_activation.main(list(argv[1:]))

    if argv and argv[0] == "external-contribution-push":
        return external_contribution_push.main(list(argv[1:]))

    if argv and argv[0] == "kpi-audit":
        return kpi_audit.main(list(argv[1:]))

    if argv and argv[0] == "day28-weekly-review":
        return day28_weekly_review.main(list(argv[1:]))

    if argv and argv[0] == "day29-phase1-hardening":
        return day29_phase1_hardening.main(list(argv[1:]))

    if argv and argv[0] == "day30-phase1-wrap":
        return day30_phase1_wrap.main(list(argv[1:]))

    if argv and argv[0] == "day31-phase2-kickoff":
        return day31_phase2_kickoff.main(list(argv[1:]))

    if argv and argv[0] == "day32-release-cadence":
        return day32_release_cadence.main(list(argv[1:]))

    if argv and argv[0] == "day33-demo-asset":
        return day33_demo_asset.main(list(argv[1:]))

    if argv and argv[0] == "day34-demo-asset2":
        return day34_demo_asset2.main(list(argv[1:]))

    if argv and argv[0] == "day35-kpi-instrumentation":
        return day35_kpi_instrumentation.main(list(argv[1:]))

    if argv and argv[0] == "day36-distribution-closeout":
        return day36_distribution_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day37-experiment-lane":
        return day37_experiment_lane.main(list(argv[1:]))

    if argv and argv[0] == "day38-distribution-batch":
        return day38_distribution_batch.main(list(argv[1:]))

    if argv and argv[0] == "day39-playbook-post":
        return day39_playbook_post.main(list(argv[1:]))

    if argv and argv[0] == "day40-scale-lane":
        return day40_scale_lane.main(list(argv[1:]))

    if argv and argv[0] == "day41-expansion-automation":
        return day41_expansion_automation.main(list(argv[1:]))

    if argv and argv[0] == "day42-optimization-closeout":
        return day42_optimization_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day43-acceleration-closeout":
        return day43_acceleration_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day44-scale-closeout":
        return day44_scale_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day45-expansion-closeout":
        return day45_expansion_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day46-optimization-closeout":
        return day46_optimization_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day47-reliability-closeout":
        return day47_reliability_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day48-objection-closeout":
        return day48_objection_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day49-weekly-review-closeout":
        return day49_weekly_review_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day50-execution-prioritization-closeout":
        return day50_execution_prioritization_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day51-case-snippet-closeout":
        return day51_case_snippet_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day52-narrative-closeout":
        return day52_narrative_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day53-docs-loop-closeout":
        return day53_docs_loop_closeout.main(list(argv[1:]))
    if argv and argv[0] == "day55-contributor-activation-closeout":
        return day55_contributor_activation_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day56-stabilization-closeout":
        return day56_stabilization_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day57-kpi-deep-audit-closeout":
        return day57_kpi_deep_audit_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day58-phase2-hardening-closeout":
        return day58_phase2_hardening_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day59-phase3-preplan-closeout":
        return day59_phase3_preplan_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day60-phase2-wrap-handoff-closeout":
        return day60_phase2_wrap_handoff_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day61-phase3-kickoff-closeout":
        return day61_phase3_kickoff_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day62-community-program-closeout":
        return day62_community_program_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day63-onboarding-activation-closeout":
        return day63_onboarding_activation_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day64-integration-expansion-closeout":
        return day64_integration_expansion_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day65-weekly-review-closeout":
        return day65_weekly_review_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day66-integration-expansion2-closeout":
        return day66_integration_expansion2_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day67-integration-expansion3-closeout":
        return day67_integration_expansion3_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day68-integration-expansion4-closeout":
        return day68_integration_expansion4_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day69-case-study-prep1-closeout":
        return day69_case_study_prep1_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day70-case-study-prep2-closeout":
        return day70_case_study_prep2_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day71-case-study-prep3-closeout":
        return day71_case_study_prep3_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day72-case-study-prep4-closeout":
        return day72_case_study_prep4_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day73-case-study-launch-closeout":
        return day73_case_study_launch_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day74-distribution-scaling-closeout":
        return day74_distribution_scaling_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day75-trust-assets-refresh-closeout":
        return day75_trust_assets_refresh_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day76-contributor-recognition-closeout":
        return day76_contributor_recognition_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day77-community-touchpoint-closeout":
        return day77_community_touchpoint_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day78-ecosystem-priorities-closeout":
        return day78_ecosystem_priorities_closeout.main(list(argv[1:]))

    if argv and argv[0] == "day79-scale-upgrade-closeout":
        return day79_scale_upgrade_closeout.main(list(argv[1:]))

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

    if argv and argv[0] == "startup-use-case":
        return startup_use_case.main(list(argv[1:]))

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

    p = argparse.ArgumentParser(prog="sdetkit", add_help=True)
    p.add_argument("--version", action="version", version=_tool_version())
    sub = p.add_subparsers(dest="cmd", required=True)

    kv = sub.add_parser("kv")
    kv.add_argument("args", nargs=argparse.REMAINDER)

    ag = sub.add_parser("apiget")
    _add_apiget_args(ag)

    doc = sub.add_parser("doctor")
    doc.add_argument("args", nargs=argparse.REMAINDER)

    pg = sub.add_parser("patch")
    pg.add_argument("args", nargs=argparse.REMAINDER)

    cg = sub.add_parser("cassette-get")
    cg.add_argument("args", nargs=argparse.REMAINDER)

    rp = sub.add_parser("repo")
    rp.add_argument("args", nargs=argparse.REMAINDER)

    dv = sub.add_parser("dev")
    dv.add_argument("args", nargs=argparse.REMAINDER)

    rpt = sub.add_parser("report")
    rpt.add_argument("args", nargs=argparse.REMAINDER)

    mnt = sub.add_parser("maintenance")
    mnt.add_argument("args", nargs=argparse.REMAINDER)

    agt = sub.add_parser("agent")
    agt.add_argument("args", nargs=argparse.REMAINDER)

    sec = sub.add_parser("security")
    sec.add_argument("args", nargs=argparse.REMAINDER)

    osp = sub.add_parser("ops")
    osp.add_argument("args", nargs=argparse.REMAINDER)

    ntf = sub.add_parser("notify")
    ntf.add_argument("args", nargs=argparse.REMAINDER)

    plc = sub.add_parser("policy")
    plc.add_argument("args", nargs=argparse.REMAINDER)

    evd = sub.add_parser("evidence")
    evd.add_argument("args", nargs=argparse.REMAINDER)

    onb = sub.add_parser("onboarding")
    onb.add_argument("args", nargs=argparse.REMAINDER)

    otu = sub.add_parser("onboarding-time-upgrade")
    otu.add_argument("args", nargs=argparse.REMAINDER)

    cau = sub.add_parser("community-activation")
    cau.add_argument("args", nargs=argparse.REMAINDER)

    ecp = sub.add_parser("external-contribution-push")
    ecp.add_argument("args", nargs=argparse.REMAINDER)

    kpa = sub.add_parser("kpi-audit")
    kpa.add_argument("args", nargs=argparse.REMAINDER)

    dwr = sub.add_parser("day28-weekly-review")
    dwr.add_argument("args", nargs=argparse.REMAINDER)

    d29 = sub.add_parser("day29-phase1-hardening")
    d29.add_argument("args", nargs=argparse.REMAINDER)

    d30 = sub.add_parser("day30-phase1-wrap")
    d30.add_argument("args", nargs=argparse.REMAINDER)

    d31 = sub.add_parser("day31-phase2-kickoff")
    d31.add_argument("args", nargs=argparse.REMAINDER)

    d32 = sub.add_parser("day32-release-cadence")
    d32.add_argument("args", nargs=argparse.REMAINDER)

    d33 = sub.add_parser("day33-demo-asset")
    d33.add_argument("args", nargs=argparse.REMAINDER)

    d34 = sub.add_parser("day34-demo-asset2")
    d34.add_argument("args", nargs=argparse.REMAINDER)

    d35 = sub.add_parser("day35-kpi-instrumentation")
    d35.add_argument("args", nargs=argparse.REMAINDER)

    d36 = sub.add_parser("day36-distribution-closeout")
    d36.add_argument("args", nargs=argparse.REMAINDER)

    d37 = sub.add_parser("day37-experiment-lane")
    d37.add_argument("args", nargs=argparse.REMAINDER)

    d38 = sub.add_parser("day38-distribution-batch")
    d38.add_argument("args", nargs=argparse.REMAINDER)

    d39 = sub.add_parser("day39-playbook-post")
    d39.add_argument("args", nargs=argparse.REMAINDER)

    d40 = sub.add_parser("day40-scale-lane")
    d40.add_argument("args", nargs=argparse.REMAINDER)

    d41 = sub.add_parser("day41-expansion-automation")
    d41.add_argument("args", nargs=argparse.REMAINDER)

    d42 = sub.add_parser("day42-optimization-closeout")
    d42.add_argument("args", nargs=argparse.REMAINDER)

    d43 = sub.add_parser("day43-acceleration-closeout")
    d43.add_argument("args", nargs=argparse.REMAINDER)

    d44 = sub.add_parser("day44-scale-closeout")
    d44.add_argument("args", nargs=argparse.REMAINDER)

    d45 = sub.add_parser("day45-expansion-closeout")
    d45.add_argument("args", nargs=argparse.REMAINDER)

    d46 = sub.add_parser("day46-optimization-closeout")
    d46.add_argument("args", nargs=argparse.REMAINDER)

    d47 = sub.add_parser("day47-reliability-closeout")
    d47.add_argument("args", nargs=argparse.REMAINDER)
    d48 = sub.add_parser("day48-objection-closeout")
    d48.add_argument("args", nargs=argparse.REMAINDER)
    d49 = sub.add_parser("day49-weekly-review-closeout")
    d49.add_argument("args", nargs=argparse.REMAINDER)
    d50 = sub.add_parser("day50-execution-prioritization-closeout")
    d50.add_argument("args", nargs=argparse.REMAINDER)
    d51 = sub.add_parser("day51-case-snippet-closeout")
    d51.add_argument("args", nargs=argparse.REMAINDER)
    d52 = sub.add_parser("day52-narrative-closeout")
    d52.add_argument("args", nargs=argparse.REMAINDER)

    d53 = sub.add_parser("day53-docs-loop-closeout")
    d53.add_argument("args", nargs=argparse.REMAINDER)

    d55 = sub.add_parser("day55-contributor-activation-closeout")
    d55.add_argument("args", nargs=argparse.REMAINDER)

    d56 = sub.add_parser("day56-stabilization-closeout")
    d56.add_argument("args", nargs=argparse.REMAINDER)

    d57 = sub.add_parser("day57-kpi-deep-audit-closeout")
    d57.add_argument("args", nargs=argparse.REMAINDER)

    d59 = sub.add_parser("day59-phase3-preplan-closeout")
    d59.add_argument("args", nargs=argparse.REMAINDER)

    d60 = sub.add_parser("day60-phase2-wrap-handoff-closeout")
    d60.add_argument("args", nargs=argparse.REMAINDER)

    d61 = sub.add_parser("day61-phase3-kickoff-closeout")
    d61.add_argument("args", nargs=argparse.REMAINDER)

    d62 = sub.add_parser("day62-community-program-closeout")
    d62.add_argument("args", nargs=argparse.REMAINDER)

    d63 = sub.add_parser("day63-onboarding-activation-closeout")
    d63.add_argument("args", nargs=argparse.REMAINDER)

    d64 = sub.add_parser("day64-integration-expansion-closeout")
    d64.add_argument("args", nargs=argparse.REMAINDER)

    d65 = sub.add_parser("day65-weekly-review-closeout")
    d65.add_argument("args", nargs=argparse.REMAINDER)

    d66 = sub.add_parser("day66-integration-expansion2-closeout")
    d66.add_argument("args", nargs=argparse.REMAINDER)

    d67 = sub.add_parser("day67-integration-expansion3-closeout")
    d67.add_argument("args", nargs=argparse.REMAINDER)

    d68 = sub.add_parser("day68-integration-expansion4-closeout")
    d68.add_argument("args", nargs=argparse.REMAINDER)

    d69 = sub.add_parser("day69-case-study-prep1-closeout")
    d69.add_argument("args", nargs=argparse.REMAINDER)

    d70 = sub.add_parser("day70-case-study-prep2-closeout")
    d70.add_argument("args", nargs=argparse.REMAINDER)
    d71 = sub.add_parser("day71-case-study-prep3-closeout")
    d71.add_argument("args", nargs=argparse.REMAINDER)
    d72 = sub.add_parser("day72-case-study-prep4-closeout")
    d72.add_argument("args", nargs=argparse.REMAINDER)
    d73 = sub.add_parser("day73-case-study-launch-closeout")
    d73.add_argument("args", nargs=argparse.REMAINDER)
    d74 = sub.add_parser("day74-distribution-scaling-closeout")
    d74.add_argument("args", nargs=argparse.REMAINDER)
    d75 = sub.add_parser("day75-trust-assets-refresh-closeout")
    d75.add_argument("args", nargs=argparse.REMAINDER)
    d76 = sub.add_parser("day76-contributor-recognition-closeout")
    d76.add_argument("args", nargs=argparse.REMAINDER)
    d77 = sub.add_parser("day77-community-touchpoint-closeout")
    d77.add_argument("args", nargs=argparse.REMAINDER)
    d78 = sub.add_parser("day78-ecosystem-priorities-closeout")
    d78.add_argument("args", nargs=argparse.REMAINDER)
    d79 = sub.add_parser("day79-scale-upgrade-closeout")
    d79.add_argument("args", nargs=argparse.REMAINDER)

    fqo = sub.add_parser("faq-objections")
    fqo.add_argument("args", nargs=argparse.REMAINDER)

    dmo = sub.add_parser("demo")
    dmo.add_argument("args", nargs=argparse.REMAINDER)

    fct = sub.add_parser("first-contribution")
    fct.add_argument("args", nargs=argparse.REMAINDER)

    ctf = sub.add_parser("contributor-funnel")
    ctf.add_argument("args", nargs=argparse.REMAINDER)

    prf = sub.add_parser("proof")
    prf.add_argument("args", nargs=argparse.REMAINDER)

    ttp = sub.add_parser("triage-templates")
    ttp.add_argument("args", nargs=argparse.REMAINDER)

    dqa = sub.add_parser("docs-qa")
    dqa.add_argument("args", nargs=argparse.REMAINDER)

    wrv = sub.add_parser("weekly-review")
    wrv.add_argument("args", nargs=argparse.REMAINDER)

    dnv = sub.add_parser("docs-nav")
    dnv.add_argument("args", nargs=argparse.REMAINDER)

    suc = sub.add_parser("startup-use-case")
    suc.add_argument("args", nargs=argparse.REMAINDER)

    euc = sub.add_parser("enterprise-use-case")
    euc.add_argument("args", nargs=argparse.REMAINDER)

    gha = sub.add_parser("github-actions-quickstart")
    gha.add_argument("args", nargs=argparse.REMAINDER)

    glc = sub.add_parser("gitlab-ci-quickstart")
    glc.add_argument("args", nargs=argparse.REMAINDER)

    qcd = sub.add_parser("quality-contribution-delta")
    qcd.add_argument("args", nargs=argparse.REMAINDER)

    rep = sub.add_parser("reliability-evidence-pack")
    rep.add_argument("args", nargs=argparse.REMAINDER)

    rrb = sub.add_parser("release-readiness-board")
    rrb.add_argument("args", nargs=argparse.REMAINDER)

    rn = sub.add_parser("release-narrative")
    rn.add_argument("args", nargs=argparse.REMAINDER)

    tsu = sub.add_parser("trust-signal-upgrade")
    tsu.add_argument("args", nargs=argparse.REMAINDER)

    ns = p.parse_args(argv)

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

    if ns.cmd == "day29-phase1-hardening":
        return day29_phase1_hardening.main(ns.args)

    if ns.cmd == "day30-phase1-wrap":
        return day30_phase1_wrap.main(ns.args)

    if ns.cmd == "day31-phase2-kickoff":
        return day31_phase2_kickoff.main(ns.args)

    if ns.cmd == "day32-release-cadence":
        return day32_release_cadence.main(ns.args)

    if ns.cmd == "day33-demo-asset":
        return day33_demo_asset.main(ns.args)

    if ns.cmd == "day34-demo-asset2":
        return day34_demo_asset2.main(ns.args)

    if ns.cmd == "day35-kpi-instrumentation":
        return day35_kpi_instrumentation.main(ns.args)

    if ns.cmd == "day36-distribution-closeout":
        return day36_distribution_closeout.main(ns.args)

    if ns.cmd == "day37-experiment-lane":
        return day37_experiment_lane.main(ns.args)

    if ns.cmd == "day38-distribution-batch":
        return day38_distribution_batch.main(ns.args)

    if ns.cmd == "day39-playbook-post":
        return day39_playbook_post.main(ns.args)

    if ns.cmd == "day40-scale-lane":
        return day40_scale_lane.main(ns.args)

    if ns.cmd == "day41-expansion-automation":
        return day41_expansion_automation.main(ns.args)

    if ns.cmd == "day42-optimization-closeout":
        return day42_optimization_closeout.main(ns.args)

    if ns.cmd == "day43-acceleration-closeout":
        return day43_acceleration_closeout.main(ns.args)

    if ns.cmd == "day44-scale-closeout":
        return day44_scale_closeout.main(ns.args)

    if ns.cmd == "day45-expansion-closeout":
        return day45_expansion_closeout.main(ns.args)

    if ns.cmd == "day46-optimization-closeout":
        return day46_optimization_closeout.main(ns.args)

    if ns.cmd == "day47-reliability-closeout":
        return day47_reliability_closeout.main(ns.args)
    if ns.cmd == "day48-objection-closeout":
        return day48_objection_closeout.main(ns.args)
    if ns.cmd == "day49-weekly-review-closeout":
        return day49_weekly_review_closeout.main(ns.args)
    if ns.cmd == "day50-execution-prioritization-closeout":
        return day50_execution_prioritization_closeout.main(ns.args)
    if ns.cmd == "day51-case-snippet-closeout":
        return day51_case_snippet_closeout.main(ns.args)
    if ns.cmd == "day52-narrative-closeout":
        return day52_narrative_closeout.main(ns.args)
    if ns.cmd == "day53-docs-loop-closeout":
        return day53_docs_loop_closeout.main(ns.args)
    if ns.cmd == "day55-contributor-activation-closeout":
        return day55_contributor_activation_closeout.main(ns.args)

    if ns.cmd == "day56-stabilization-closeout":
        return day56_stabilization_closeout.main(ns.args)

    if ns.cmd == "day57-kpi-deep-audit-closeout":
        return day57_kpi_deep_audit_closeout.main(ns.args)

    if ns.cmd == "day59-phase3-preplan-closeout":
        return day59_phase3_preplan_closeout.main(ns.args)

    if ns.cmd == "day60-phase2-wrap-handoff-closeout":
        return day60_phase2_wrap_handoff_closeout.main(ns.args)

    if ns.cmd == "day61-phase3-kickoff-closeout":
        return day61_phase3_kickoff_closeout.main(ns.args)

    if ns.cmd == "day62-community-program-closeout":
        return day62_community_program_closeout.main(ns.args)

    if ns.cmd == "day63-onboarding-activation-closeout":
        return day63_onboarding_activation_closeout.main(ns.args)

    if ns.cmd == "day64-integration-expansion-closeout":
        return day64_integration_expansion_closeout.main(ns.args)

    if ns.cmd == "day65-weekly-review-closeout":
        return day65_weekly_review_closeout.main(ns.args)

    if ns.cmd == "day66-integration-expansion2-closeout":
        return day66_integration_expansion2_closeout.main(ns.args)

    if ns.cmd == "day67-integration-expansion3-closeout":
        return day67_integration_expansion3_closeout.main(ns.args)

    if ns.cmd == "day68-integration-expansion4-closeout":
        return day68_integration_expansion4_closeout.main(ns.args)

    if ns.cmd == "day69-case-study-prep1-closeout":
        return day69_case_study_prep1_closeout.main(ns.args)

    if ns.cmd == "day70-case-study-prep2-closeout":
        return day70_case_study_prep2_closeout.main(ns.args)

    if ns.cmd == "day71-case-study-prep3-closeout":
        return day71_case_study_prep3_closeout.main(ns.args)

    if ns.cmd == "day72-case-study-prep4-closeout":
        return day72_case_study_prep4_closeout.main(ns.args)

    if ns.cmd == "day73-case-study-launch-closeout":
        return day73_case_study_launch_closeout.main(ns.args)

    if ns.cmd == "day74-distribution-scaling-closeout":
        return day74_distribution_scaling_closeout.main(ns.args)

    if ns.cmd == "day75-trust-assets-refresh-closeout":
        return day75_trust_assets_refresh_closeout.main(ns.args)

    if ns.cmd == "day76-contributor-recognition-closeout":
        return day76_contributor_recognition_closeout.main(ns.args)

    if ns.cmd == "day77-community-touchpoint-closeout":
        return day77_community_touchpoint_closeout.main(ns.args)

    if ns.cmd == "day78-ecosystem-priorities-closeout":
        return day78_ecosystem_priorities_closeout.main(ns.args)

    if ns.cmd == "day79-scale-upgrade-closeout":
        return day79_scale_upgrade_closeout.main(ns.args)

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

    if ns.cmd == "startup-use-case":
        return startup_use_case.main(ns.args)

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
