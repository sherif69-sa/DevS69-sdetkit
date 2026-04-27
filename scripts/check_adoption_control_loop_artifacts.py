from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = (
    "sdetkit-fit-recommendation.json",
    "gate-decision-summary.json",
    "gate-decision-summary.md",
    "adoption-followup.json",
    "adoption-followup.md",
    "adoption-followup-history-rollup.json",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate adoption control-loop artifacts exist.")
    parser.add_argument("--artifact-dir", type=Path, default=Path("build"))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    missing = [name for name in REQUIRED if not (args.artifact_dir / name).exists()]
    result = {"ok": not missing, "missing": missing, "artifact_dir": str(args.artifact_dir)}
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print("adoption-control-loop artifacts: ok")
    else:
        print("adoption-control-loop artifacts: fail")
        for name in missing:
            print(f"- missing: {name}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
