from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _count_checks(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("- [")
    )


def run_lane(argv: list[str] | None, cfg: dict[str, Any]) -> int:
    p = argparse.ArgumentParser(prog=f"sdetkit {cfg['name']}")
    p.add_argument("--root", default=".")
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--emit-pack-dir", default=None)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--write-defaults", action="store_true")
    ns = p.parse_args(argv)

    root = Path(ns.root)
    page = root / cfg["page_path"]
    strict_ok = True
    checks: list[dict[str, Any]] = []

    for rel in cfg.get("required_inputs", []):
        exists = (root / rel).exists()
        checks.append({"check_id": rel, "passed": exists})
        strict_ok = strict_ok and exists
    for rel in cfg.get("required_boards", []):
        cnt = _count_checks(root / rel)
        passed = cnt >= cfg.get("min_board_checks", 5)
        checks.append({"check_id": rel, "passed": passed, "count": cnt})
        strict_ok = strict_ok and passed

    if cfg.get("required_page_marker"):
        marker_ok = cfg["required_page_marker"] in (
            page.read_text(encoding="utf-8") if page.exists() else ""
        )
        checks.append({"check_id": "page_marker", "passed": marker_ok})
        strict_ok = strict_ok and marker_ok

    score = 100 if strict_ok else 60
    payload = {
        "name": cfg["name"],
        "summary": {"activation_score": score, "strict_pass": strict_ok},
        "checks": checks,
    }

    if ns.strict and not strict_ok:
        if ns.format == "json":
            sys.stdout.write(json.dumps(payload) + "\n")
        return 1

    if ns.emit_pack_dir:
        pack = root / ns.emit_pack_dir
        pack.mkdir(parents=True, exist_ok=True)
        (pack / cfg["summary_json"]).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        (pack / cfg["summary_md"]).write_text(f"# {cfg['name']} summary\n", encoding="utf-8")
        for rel in cfg.get("pack_files", []):
            (pack / rel).write_text("generated\n", encoding="utf-8")
        if ns.execute and ns.evidence_dir:
            evidence = root / ns.evidence_dir
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / cfg["evidence_json"]).write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload) + "\n")
    elif ns.format == "markdown":
        sys.stdout.write(f"# {cfg['name']}\n\n")
    else:
        sys.stdout.write(str(cfg["text_output"]) + "\n")
    return 0
