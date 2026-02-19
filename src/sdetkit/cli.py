from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from importlib import metadata

from . import apiget, demo, docs_qa, evidence, kvcli, notify, onboarding, ops, patch, policy, proof, repo, report, weekly_review
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

    if argv and argv[0] == "demo":
        return demo.main(list(argv[1:]))

    if argv and argv[0] == "proof":
        return proof.main(list(argv[1:]))

    if argv and argv[0] == "docs-qa":
        return docs_qa.main(list(argv[1:]))

    if argv and argv[0] == "weekly-review":
        return weekly_review.main(list(argv[1:]))

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

    dmo = sub.add_parser("demo")
    dmo.add_argument("args", nargs=argparse.REMAINDER)

    prf = sub.add_parser("proof")
    prf.add_argument("args", nargs=argparse.REMAINDER)

    dqa = sub.add_parser("docs-qa")
    dqa.add_argument("args", nargs=argparse.REMAINDER)

    wrv = sub.add_parser("weekly-review")
    wrv.add_argument("args", nargs=argparse.REMAINDER)

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

    if ns.cmd == "demo":
        return demo.main(ns.args)

    if ns.cmd == "proof":
        return proof.main(ns.args)

    if ns.cmd == "docs-qa":
        return docs_qa.main(ns.args)

    if ns.cmd == "weekly-review":
        return weekly_review.main(ns.args)

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
