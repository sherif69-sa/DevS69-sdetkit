from __future__ import annotations

import argparse
import json
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate follow-up readiness for first-proof operator handoff.")
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--onboarding", default="build/onboarding-next.json")
    p.add_argument("--out", default="build/first-proof/followup-ready.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    required = [
        root / "execution-contract.json",
        root / "execution-report.json",
        root / "upgrade-status-line.txt",
        Path(args.onboarding),
    ]
    missing = [str(p) for p in required if not p.exists()]

    execution_contract = {}
    if (root / "execution-contract.json").exists():
        execution_contract = json.loads((root / "execution-contract.json").read_text(encoding="utf-8"))

    ok = len(missing) == 0 and bool(execution_contract.get("ok", False))
    payload = {
        "ok": ok,
        "missing": missing,
        "execution_contract_ok": execution_contract.get("ok", False),
        "artifact_dir": str(root),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"followup-ready: ok={ok} missing={len(missing)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
