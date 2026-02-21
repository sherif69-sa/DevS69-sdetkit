from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from importlib import metadata

from . import (
    apiget,
    contributor_funnel,
    demo,
    docs_navigation,
    docs_qa,
    enterprise_use_case,
    evidence,
    faq_objections,
    first_contribution,
    github_actions_quickstart,
    gitlab_ci_quickstart,
    kvcli,
    notify,
    onboarding,
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
