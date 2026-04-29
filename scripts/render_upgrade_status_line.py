from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Render a single status line for upgrade follow-up workflows."
    )
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--onboarding", default="build/onboarding-next.json")
    p.add_argument("--out", default="build/first-proof/upgrade-status-line.txt")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    summary = _load(root / "first-proof-summary.json")
    health = _load(root / "health-score.json")
    contract = _load(root / "execution-contract.json")
    onboarding = _load(Path(args.onboarding))

    status = (
        f"UPGRADE_STATUS decision={summary.get('decision', 'NO-DATA')} "
        f"health={health.get('score', 'NA')} "
        f"contract_ok={contract.get('ok', 'NA')} "
        f"onboarding={onboarding.get('decision', 'NA')}"
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(status + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps({"status_line": status}, indent=2, sort_keys=True))
    else:
        print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
