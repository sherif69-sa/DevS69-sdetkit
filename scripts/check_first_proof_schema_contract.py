from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
REQUIRED = [
    "health-score.json",
    "ops-bundle-contract-trend.json",
    "execution-report.json",
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate schema version consistency for first-proof artifacts.")
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--out", default="build/first-proof/schema-contract.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    errors: list[str] = []

    for name in REQUIRED:
        path = root / name
        if not path.exists():
            errors.append(f"missing: {name}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{name}: schema_version={payload.get('schema_version')} expected={SCHEMA_VERSION}")

    out_payload = {"ok": len(errors) == 0, "schema_version": SCHEMA_VERSION, "errors": errors}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(out_payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(out_payload, indent=2, sort_keys=True))
    else:
        print(f"schema-contract: ok={out_payload['ok']} errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
