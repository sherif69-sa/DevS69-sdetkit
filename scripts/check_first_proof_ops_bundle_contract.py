from __future__ import annotations

import argparse
import json
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate first-proof ops bundle manifest and artifacts."
    )
    p.add_argument("--manifest", default="build/first-proof/ops-bundle-manifest.json")
    p.add_argument("--out", default="build/first-proof/ops-bundle-contract.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    manifest_path = Path(args.manifest)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    artifacts = payload.get("artifacts") or []
    missing = [a for a in artifacts if not Path(a).exists()]
    ok = payload.get("bundle") == "first-proof-ops" and len(missing) == 0

    out_payload = {
        "ok": ok,
        "manifest": str(manifest_path),
        "missing": missing,
        "artifacts": artifacts,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(out_payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(out_payload, indent=2, sort_keys=True))
    else:
        print(f"ops-bundle-contract: ok={ok} missing={len(missing)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
