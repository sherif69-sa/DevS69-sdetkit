from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PRIMARY_MAP = {
    "start_page": "start-here-5-minutes.md",
    "ci_page": "recommended-ci-flow.md",
    "troubleshooting_page": "first-failure-triage.md",
}


def _build_report(root: Path) -> dict[str, Any]:
    index_path = root / "docs" / "index.md"
    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    checks: dict[str, dict[str, Any]] = {}
    for key, rel_name in PRIMARY_MAP.items():
        path = root / "docs" / rel_name
        checks[key] = {
            "path": str(path.relative_to(root)),
            "exists": path.exists(),
            "linked_in_index": rel_name in index_text,
        }
        checks[key]["ok"] = checks[key]["exists"] and checks[key]["linked_in_index"]
    overall_ok = all(item["ok"] for item in checks.values())
    return {"schema_version": "1", "overall_ok": overall_ok, "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/check_primary_docs_map.py")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    ns = parser.parse_args(argv)
    report = _build_report(Path(ns.root).resolve())
    if ns.format == "json":
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"primary-docs-map: {'OK' if report['overall_ok'] else 'FAIL'}")
        for key, item in report["checks"].items():
            status = "OK" if item["ok"] else "FAIL"
            print(
                f"[{status}] {key}: exists={item['exists']} linked_in_index={item['linked_in_index']} ({item['path']})"
            )
    return 0 if report["overall_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
