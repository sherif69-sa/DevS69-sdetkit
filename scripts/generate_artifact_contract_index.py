#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from sdetkit.artifact_contract_index import write_index


def main() -> int:
    out = Path("docs/artifact-contract-index.json")
    write_index(out)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
