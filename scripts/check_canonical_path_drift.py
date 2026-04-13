from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CANONICAL_TOKENS = (
    "gate fast",
    "gate release",
    "doctor",
)

CHECKS = (
    ("README", Path("README.md")),
    ("docs_index", Path("docs/index.md")),
    ("docs_cli", Path("docs/cli.md")),
    ("docs_taxonomy", Path("docs/command-taxonomy.md")),
    ("cli_help_source", Path("src/sdetkit/cli.py")),
)


def _contains_all(text: str, tokens: tuple[str, ...]) -> tuple[bool, list[str]]:
    lowered = text.lower()
    missing = [token for token in tokens if token not in lowered]
    return (len(missing) == 0, missing)


def _build_report(root: Path) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    for name, rel in CHECKS:
        path = root / rel
        if not path.exists():
            checks[name] = {"path": str(rel), "ok": False, "missing_tokens": list(CANONICAL_TOKENS)}
            continue
        ok, missing = _contains_all(path.read_text(encoding="utf-8"), CANONICAL_TOKENS)
        checks[name] = {"path": str(rel), "ok": ok, "missing_tokens": missing}
    overall_ok = all(item["ok"] for item in checks.values())
    return {
        "schema_version": "1",
        "canonical_tokens": list(CANONICAL_TOKENS),
        "overall_ok": overall_ok,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/check_canonical_path_drift.py")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    ns = parser.parse_args(argv)
    report = _build_report(Path(ns.root).resolve())
    if ns.format == "json":
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"canonical-path-drift: {'OK' if report['overall_ok'] else 'FAIL'}")
        for name, item in report["checks"].items():
            status = "OK" if item["ok"] else "FAIL"
            missing = ", ".join(item["missing_tokens"]) if item["missing_tokens"] else "-"
            print(f"[{status}] {name} ({item['path']}) missing: {missing}")
    return 0 if report["overall_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
