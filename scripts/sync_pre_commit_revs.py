"""Set pre-commit hook revs that follow a constraints-ci.txt pin to that pin.

Dependabot updates ruff and mypy in constraints-ci.txt but not their hook revs in
.pre-commit-config.yaml. Used by `make lock` and the Dependabot lock-refresh job.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Hook repository -> the constraints-ci.txt package its rev follows.
PINNED_HOOKS = {
    "https://github.com/astral-sh/ruff-pre-commit": "ruff",
    "https://github.com/pre-commit/mirrors-mypy": "mypy",
}


def constraint_pins(text: str) -> dict[str, str]:
    return dict(re.findall(r"(?m)^([A-Za-z0-9_.-]+)==([^\s;#]+)", text))


def sync(config: str, pins: dict[str, str]) -> str:
    for repo, package in PINNED_HOOKS.items():
        pattern = re.compile(rf"(-\s+repo:\s+{re.escape(repo)}\s*\n\s+rev:\s+)\S+")
        config, count = pattern.subn(rf"\g<1>v{pins[package]}", config)
        if count != 1:
            raise SystemExit(f"expected one rev for {repo} in .pre-commit-config.yaml")
    return config


def main() -> int:
    config_path = ROOT / ".pre-commit-config.yaml"
    pins = constraint_pins((ROOT / "constraints-ci.txt").read_text(encoding="utf-8"))
    config = config_path.read_text(encoding="utf-8")
    synced = sync(config, pins)
    if synced != config:
        config_path.write_text(synced, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
