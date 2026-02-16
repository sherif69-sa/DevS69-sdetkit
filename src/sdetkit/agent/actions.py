from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdetkit import repo
from sdetkit.atomicio import atomic_write_text
from sdetkit.report import build_dashboard


@dataclass(frozen=True)
class ActionResult:
    name: str
    ok: bool
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.name, "ok": self.ok, "payload": self.payload}


ActionHandler = Callable[[dict[str, Any]], ActionResult]


class ActionRegistry:
    def __init__(
        self,
        *,
        root: Path,
        write_allowlist: tuple[str, ...],
        shell_allowlist: tuple[str, ...],
    ) -> None:
        self.root = root
        self.write_allowlist = write_allowlist
        self.shell_allowlist = shell_allowlist
        self._handlers: dict[str, ActionHandler] = {
            "fs.read": self._fs_read,
            "fs.write": self._fs_write,
            "shell.run": self._shell_run,
            "repo.audit": self._repo_audit,
            "report.build": self._report_build,
        }

    def run(self, name: str, params: dict[str, Any]) -> ActionResult:
        handler = self._handlers.get(name)
        if handler is None:
            return ActionResult(name=name, ok=False, payload={"error": "unknown action"})
        return handler(params)

    def _safe_rel(self, rel: str) -> Path:
        candidate = Path(rel)
        if candidate.is_absolute():
            raise ValueError("absolute paths are not allowed")
        resolved = (self.root / candidate).resolve()
        if self.root.resolve() not in resolved.parents and resolved != self.root.resolve():
            raise ValueError("path escapes repository root")
        return resolved

    def _is_write_allowed(self, rel: str) -> bool:
        normalized = rel.replace("\\", "/").lstrip("/")
        return any(
            normalized == item or normalized.startswith(item.rstrip("/") + "/")
            for item in self.write_allowlist
        )

    def _fs_read(self, params: dict[str, Any]) -> ActionResult:
        rel = str(params.get("path", ""))
        try:
            path = self._safe_rel(rel)
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            return ActionResult("fs.read", False, {"error": str(exc), "path": rel})
        return ActionResult("fs.read", True, {"path": rel, "content": text})

    def _fs_write(self, params: dict[str, Any]) -> ActionResult:
        rel = str(params.get("path", ""))
        content = str(params.get("content", ""))
        if not self._is_write_allowed(rel):
            return ActionResult(
                "fs.write",
                False,
                {
                    "error": "write denied by allowlist",
                    "path": rel,
                    "allowlist": list(self.write_allowlist),
                },
            )
        try:
            path = self._safe_rel(rel)
            atomic_write_text(path, content)
        except (OSError, ValueError) as exc:
            return ActionResult("fs.write", False, {"error": str(exc), "path": rel})
        return ActionResult("fs.write", True, {"path": rel, "bytes": len(content.encode("utf-8"))})

    def _shell_run(self, params: dict[str, Any]) -> ActionResult:
        cmd = str(params.get("cmd", "")).strip()
        if not cmd:
            return ActionResult("shell.run", False, {"error": "cmd is required"})
        if not any(cmd == allow or cmd.startswith(allow + " ") for allow in self.shell_allowlist):
            return ActionResult(
                "shell.run", False, {"error": "command denied by allowlist", "cmd": cmd}
            )
        proc = subprocess.run(cmd.split(), text=True, capture_output=True, check=False)
        return ActionResult(
            "shell.run",
            proc.returncode == 0,
            {
                "cmd": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )

    def _repo_audit(self, params: dict[str, Any]) -> ActionResult:
        profile = str(params.get("profile", "default"))
        payload = repo.run_repo_audit(self.root, profile=profile)
        return ActionResult(
            "repo.audit",
            True,
            {
                "profile": profile,
                "findings": len(payload.get("findings", [])),
                "checks": len(payload.get("checks", [])),
            },
        )

    def _report_build(self, params: dict[str, Any]) -> ActionResult:
        output = str(params.get("output", ".sdetkit/agent/dashboard.html"))
        fmt = str(params.get("format", "html"))
        history_dir = self.root / ".sdetkit" / "agent" / "history"
        target = self._safe_rel(output)
        build_dashboard(history_dir=history_dir, output=target, fmt=fmt, since=None)
        return ActionResult("report.build", True, {"output": output, "format": fmt})


def maybe_parse_action_task(task: str) -> tuple[str, dict[str, Any]] | None:
    stripped = task.strip()
    if not stripped.startswith("action "):
        return None
    rest = stripped[len("action ") :].strip()
    if " " not in rest:
        return rest, {}
    name, raw = rest.split(" ", 1)
    raw = raw.strip()
    if not raw:
        return name, {}
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {"arg": raw}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return name, payload
