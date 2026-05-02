from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .adaptive_memory import _history_payload, explain_path, init_db
from .boost import build_scan
from .index import inspect_index
from .intelligence.review import run_review
from .repo import run_checks
from .risk_hygiene import classify_risks
from .security import safe_path

SCHEMA_VERSION = "sdetkit.release_room.plan.v1"


def _call(name: str, fn):
    try:
        return {"ok": True, "payload": fn(), "error": ""}
    except Exception as exc:  # pragma: no cover - defensive degradation
        return {"ok": False, "payload": {}, "error": f"{type(exc).__name__}: {exc}"}


def _head(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def build_plan(
    root: Path, *, deep: bool, learn: bool, db: str, max_lines: int, evidence_dir: str
) -> dict[str, object]:
    resolved = root.resolve()
    idx = _call("index", lambda: inspect_index(resolved))
    boost = _call(
        "boost",
        lambda: build_scan(
            resolved,
            minutes=5,
            max_lines=max_lines,
            deep=deep,
            learn=learn,
            db=db,
            index_out="build/sdetkit-index",
            evidence_dir="",
        ),
    )

    def _review_payload():
        rc, payload, _, _ = run_review(
            target=resolved,
            out_dir=Path(".sdetkit/review/release-room"),
            workspace_root=Path(".sdetkit/workspace"),
            profile="release",
            no_workspace=True,
            work_id="",
            work_context={},
            adaptive_mode=True,
            adaptive_deep=deep,
            adaptive_learn=learn,
            adaptive_db=Path(db),
            adaptive_evidence_dir=None,
        )
        return {"rc": rc, "operator": payload.get("operator_summary", {})}

    review = _call("review", _review_payload)
    mem_hist = _call("memory_history", lambda: _history_payload(Path(db)))
    mem_exp = _call("memory_explain", lambda: explain_path(Path(db), "."))
    repo = _call("repo_check", lambda: run_checks(resolved))

    patch_candidates = []
    if boost["ok"]:
        for item in boost["payload"].get("patch_candidates", [])[:5]:
            patch_candidates.append(
                {
                    "title": item.get("title", "boost candidate"),
                    "priority": item.get("priority", 5),
                    "reason": item.get("reason", "boost signal"),
                    "files": item.get("files", []),
                    "expected_validation": item.get("expected_validation", "python -m pytest -q"),
                    "source_signals": ["boost"],
                }
            )
    if review["ok"]:
        for item in review["payload"].get("operator", {}).get("patch_candidates", [])[:5]:
            patch_candidates.append(
                {
                    "title": item.get("title", "review candidate"),
                    "priority": item.get("priority", 5),
                    "reason": item.get("reason", "adaptive review signal"),
                    "files": item.get("files", []),
                    "expected_validation": item.get("expected_validation", "python -m pytest -q"),
                    "source_signals": ["adaptive-review"],
                }
            )

    patch_candidates = sorted(
        patch_candidates, key=lambda x: (-int(x.get("priority", 0)), str(x.get("title", "")))
    )[:6]
    severe = any(
        r.get("severity") in {"major", "severe", "critical"}
        for r in boost.get("payload", {}).get("top_risks", [])
    )
    repo_findings = len(repo.get("payload", {}).get("findings", [])) if repo["ok"] else 1
    boost_score = int(boost.get("payload", {}).get("score", 0)) if boost["ok"] else 0

    if not idx["ok"] or not boost["ok"] or not review["ok"]:
        decision = "NO-SHIP"
    elif repo_findings == 0 and not severe and boost_score >= 85:
        decision = "SHIP"
    elif patch_candidates:
        decision = "REVIEW"
    else:
        decision = "NO-SHIP"

    present = sum(1 for x in (idx, boost, review, mem_hist, mem_exp, repo) if x["ok"])
    confidence = "high" if present == 6 else ("normal" if present >= 5 else "degraded")

    validation = [
        "python -m pytest -q tests/test_release_room_plan.py",
        "python -m ruff check src tests",
        "python -m ruff format --check src tests",
        "python -m sdetkit repo check --format json --force",
        "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict",
    ]
    if patch_candidates:
        validation.append(
            str(patch_candidates[0].get("expected_validation", "python -m pytest -q"))
        )

    raw_top_risks = boost.get("payload", {}).get("top_risks", [])
    hygiene = classify_risks(resolved, raw_top_risks if isinstance(raw_top_risks, list) else [])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit release-room plan",
        "root": resolved.as_posix(),
        "decision": decision,
        "confidence": confidence,
        "summary": "Deterministic local release-room execution planner.",
        "budget": {"max_lines": max_lines, "deep": bool(deep), "learn": bool(learn)},
        "signals": {
            "index": idx,
            "boost": boost,
            "adaptive_review": review,
            "memory_history": mem_hist,
            "memory_explain": mem_exp,
            "repo_check": repo,
        },
        "release_decision": {
            "head": _head(resolved),
            "repo_findings": repo_findings,
            "boost_score": boost_score,
        },
        "top_risks": hygiene["source_risks"][:3],
        "recurring_risks": mem_exp.get("payload", {}).get("recurring_hotspots", [])[:5]
        if mem_exp["ok"]
        else [],
        "patch_candidates": patch_candidates,
        "recommended_fixes": boost.get("payload", {}).get("recommended_fixes", [])[:5]
        if boost["ok"]
        else [],
        "validation_plan": validation,
        "evidence_files": [],
        "next_pr": {"title": "release-room-next-patch", "focus": patch_candidates[:3]},
        "operator_brief": "",
        "risk_hygiene_summary": hygiene["risk_hygiene_summary"],
        "source_risks": hygiene["source_risks"],
        "generated_artifact_risks": hygiene["generated_artifact_risks"],
        "suppressed_risks": hygiene["suppressed_risks"],
        "suppression_reasons": hygiene["suppression_reasons"],
        "workspace_noise_detected": hygiene["workspace_noise_detected"],
        "diagnostics": [
            x
            for x in [
                idx["error"],
                boost["error"],
                review["error"],
                mem_hist["error"],
                mem_exp["error"],
                repo["error"],
            ]
            if x
        ],
    }
    payload["repo_path"] = str(root)
    payload["source_status"] = {
        name: {
            "available": isinstance(signal.get("payload"), dict) and bool(signal.get("payload")),
            "rc": signal.get("rc"),
        }
        for name, signal in payload.get("signals", {}).items()
        if isinstance(signal, dict)
    }
    payload["validation_commands"] = list(payload.get("validation_plan", []))
    payload["evidence_paths"] = list(payload.get("evidence_files", []))
    payload["next_pr_recommendation"] = payload.get("next_pr", {})
    payload["operator_brief"] = render_text(payload, max_lines=max_lines)
    return payload


def render_text(payload: dict[str, object], *, max_lines: int) -> str:
    rd = payload.get("release_decision", {})
    lines = [
        f"Decision: {payload.get('decision')}",
        f"Confidence: {payload.get('confidence')}",
        f"HEAD: {rd.get('head', '') or 'unavailable'}",
        "Top risks:",
    ]
    for risk in payload.get("top_risks", [])[:3]:
        lines.append(
            f"- {risk.get('severity', '?')}: {risk.get('title', 'risk')} ({risk.get('file', 'repo')})"
        )
    lines.append("Top patch candidates:")
    for cand in payload.get("patch_candidates", [])[:3]:
        lines.append(
            f"- P{cand.get('priority', 5)} {cand.get('title')} files={','.join(cand.get('files', [])[:3])}"
        )
    lines.append("Next PR: release-room-next-patch")
    lines.append("Validation commands:")
    for cmd in payload.get("validation_plan", []):
        lines.append(f"- {cmd}")
    lines.append(
        "Evidence files: release-room-plan.json, release-room-plan.txt, index.json, boost-v2.json, adaptive-review.json, memory-history.json, memory-explain.json, repo-check.json"
    )
    return "\n".join(lines[: max(1, max_lines)])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit release-room")
    sub = p.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan", help="Build deterministic release-room operator plan")
    plan.add_argument("path")
    plan.add_argument("--deep", action="store_true")
    plan.add_argument("--learn", action="store_true")
    plan.add_argument("--db", default=".sdetkit/adaptive.db")
    plan.add_argument("--max-lines", type=int, default=100)
    plan.add_argument("--format", choices=["text", "operator-json"], default="text")
    plan.add_argument("--evidence-dir", default="")
    ns = p.parse_args(argv)
    init_db(Path(ns.db))
    payload = build_plan(
        Path(ns.path),
        deep=bool(ns.deep),
        learn=bool(ns.learn),
        db=str(ns.db),
        max_lines=int(ns.max_lines),
        evidence_dir=str(ns.evidence_dir),
    )
    if ns.evidence_dir:
        ed = safe_path(Path.cwd(), ns.evidence_dir, allow_absolute=True)
        ed.mkdir(parents=True, exist_ok=True)
        files = {
            "release-room-plan.json": json.dumps(payload, indent=2, sort_keys=True) + "\n",
            "release-room-plan.txt": render_text(payload, max_lines=int(ns.max_lines)) + "\n",
            "index.json": json.dumps(
                payload["signals"]["index"]["payload"], indent=2, sort_keys=True
            )
            + "\n",
            "boost-v2.json": json.dumps(
                payload["signals"]["boost"]["payload"], indent=2, sort_keys=True
            )
            + "\n",
            "adaptive-review.json": json.dumps(
                payload["signals"]["adaptive_review"]["payload"], indent=2, sort_keys=True
            )
            + "\n",
            "memory-history.json": json.dumps(
                payload["signals"]["memory_history"]["payload"], indent=2, sort_keys=True
            )
            + "\n",
            "memory-explain.json": json.dumps(
                payload["signals"]["memory_explain"]["payload"], indent=2, sort_keys=True
            )
            + "\n",
        }
        if payload["signals"]["repo_check"]["ok"]:
            files["repo-check.json"] = (
                json.dumps(payload["signals"]["repo_check"]["payload"], indent=2, sort_keys=True)
                + "\n"
            )
        payload["evidence_files"] = []
        for name, body in files.items():
            out = safe_path(ed, name, allow_absolute=False)
            out.write_text(body, encoding="utf-8")
            payload["evidence_files"].append(out.as_posix())
    payload["evidence_paths"] = list(payload.get("evidence_files", []))
    if ns.format == "operator-json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload, max_lines=int(ns.max_lines)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
