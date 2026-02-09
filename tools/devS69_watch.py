from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def run(cmd: list[str]) -> int:
    p = subprocess.run(cmd)
    return int(p.returncode)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python tools/devS69_watch.py SPEC.json", file=sys.stderr)
        return 2

    spec = Path(sys.argv[1])
    if not spec.exists():
        print(f"missing spec: {spec}", file=sys.stderr)
        return 2

    last = spec.stat().st_mtime_ns
    print(f"watching: {spec}")

    while True:
        time.sleep(0.35)
        cur = spec.stat().st_mtime_ns
        if cur == last:
            continue
        last = cur

        print("\n== change detected ==")
        rc = run(["python", "tools/patch_harness.py", str(spec)])
        if rc != 0:
            print("patch_harness failed")
            continue

        rc = run(["pre-commit", "run", "-a"])
        if rc != 0:
            print("pre-commit failed")
            continue

        rc = run(["python", "-m", "pytest", "-q"])
        if rc != 0:
            print("pytest failed")
            continue

        print("OK [OK]")
