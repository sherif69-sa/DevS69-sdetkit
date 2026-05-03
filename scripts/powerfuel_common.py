from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def artifact_path(kind: str, date_tag: str, suffix: str = "json") -> Path:
    name = {
        "baseline": "powerfuel-baseline",
        "shadow": "powerfuel-shadow-log",
        "weekly": "powerfuel-weekly-report",
        "retirement": "powerfuel-retirement-plan",
        "contract": "powerfuel-contract-check",
    }[kind]
    return Path(f"docs/artifacts/{name}-{date_tag}.{suffix}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
