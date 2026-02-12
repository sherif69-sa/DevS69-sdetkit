from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MaintenanceContext:
    repo_root: Path
    python_exe: str
    mode: str
    fix: bool
    env: dict[str, str]
    logger: Any


@dataclass
class CheckAction:
    id: str
    title: str
    applied: bool = False
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "applied": self.applied,
            "notes": self.notes,
        }


@dataclass
class CheckResult:
    ok: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    actions: list[CheckAction] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "details": self.details,
            "actions": [action.as_dict() for action in self.actions],
        }
