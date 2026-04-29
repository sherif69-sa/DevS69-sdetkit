from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cleanup stale first-proof artifacts using TTL policy.")
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--ttl-hours", type=int, default=168)
    p.add_argument("--dry-run", action="store_true", help="Report deletions without removing files.")
    p.add_argument("--out", default="build/first-proof/retention-cleanup.json")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    now = time.time()
    ttl_seconds = args.ttl_hours * 3600

    deleted: list[str] = []
    kept: list[str] = []
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            age = now - path.stat().st_mtime
            if age > ttl_seconds:
                deleted.append(str(path))
                if not args.dry_run:
                    path.unlink(missing_ok=True)
            else:
                kept.append(str(path))

    payload = {
        "ok": True,
        "artifact_dir": str(root),
        "ttl_hours": args.ttl_hours,
        "dry_run": bool(args.dry_run),
        "deleted_count": len(deleted),
        "kept_count": len(kept),
        "deleted": deleted,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"retention-cleanup: deleted={len(deleted)} kept={len(kept)} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
