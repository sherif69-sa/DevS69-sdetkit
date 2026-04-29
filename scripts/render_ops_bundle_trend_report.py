from __future__ import annotations

import argparse
import json
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render markdown report for ops-bundle contract trend.")
    p.add_argument("--trend", default="build/first-proof/ops-bundle-contract-trend.json")
    p.add_argument("--history", default="build/first-proof/ops-bundle-contract-history.jsonl")
    p.add_argument("--out-md", default="build/first-proof/ops-bundle-contract-trend.md")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    trend = json.loads(Path(args.trend).read_text(encoding="utf-8"))
    history_rows = (
        [
            json.loads(line)
            for line in Path(args.history).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if Path(args.history).exists()
        else []
    )

    md = [
        "# Ops Bundle Contract Trend",
        "",
        f"- recent runs: **{trend.get('recent_runs', 0)}**",
        f"- recent passes: **{trend.get('recent_passes', 0)}**",
        f"- recent pass rate: **{trend.get('recent_pass_rate', 0)}**",
        f"- policy ok: **{trend.get('ok', False)}**",
        "",
        "## Recent history",
    ]
    for row in history_rows[-10:]:
        md.append(
            f"- {row.get('ts')} :: ok={row.get('ok')} missing_count={row.get('missing_count')}"
        )

    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps({"ok": True, "out_md": str(out)}, indent=2, sort_keys=True))
    else:
        print(f"ops-bundle-trend-report: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
