from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {
    "first-proof-summary.json": ["decision", "ok"],
    "health-score.json": ["score", "decision"],
    "ops-bundle-contract.json": ["ok", "artifacts"],
    "ops-bundle-contract-trend.json": ["recent_pass_rate", "recent_runs"],
    "execution-report.json": ["decision", "health_score", "next_tasks"],
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate final first-proof execution artifact contract."
    )
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--out", default="build/first-proof/execution-contract.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    errors: list[str] = []

    for file_name, required_keys in REQUIRED.items():
        p = root / file_name
        if not p.exists():
            errors.append(f"missing file: {file_name}")
            continue
        payload = json.loads(p.read_text(encoding="utf-8"))
        for key in required_keys:
            if key not in payload:
                errors.append(f"{file_name}: missing key `{key}`")

    out_payload = {"ok": not errors, "errors": errors, "artifact_dir": str(root)}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(out_payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(out_payload, indent=2, sort_keys=True))
    else:
        print(f"execution-contract: ok={out_payload['ok']} errors={len(errors)}")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
