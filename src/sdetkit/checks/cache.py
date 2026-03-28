from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .results import CheckRecord

_IGNORED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}


class CheckCache:
    def init_(self, base_dir: Path, *, enabled: bool = True) -> None:
        self._base_dir = base_dir
        self.enabled = enabled
        self._fingerprint_cache: dict[tuple[str, ...], str] = {}

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def compute_repo_fingerprint(self, repo_root: Path, changed_paths: tuple[str, ...]) -> str:
        scope = tuple(changed_paths) if changed_paths else ("__repo__",)
        cached = self._fingerprint_cache.get(scope)
        if cached is not None:
            return cached

        digest = hashlib.sha256()
        paths = list(self._iter_paths(repo_root, changed_paths))
        for path in paths:
            rel = path.relative_to(repo_root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\\0")
            digest.update(path.read_bytes())
            digest.update(b"\\0")
        fingerprint = digest.hexdigest()
        self._fingerprint_cache[scope] = fingerprint
        return fingerprint

    def key_for(
        self,
        *,
        repo_root: Path,
        check_id: str,
        profile: str,
        target_mode: str,
        command: str,
        changed_paths: tuple[str, ...],
        selected_targets: tuple[str, ...],
    ) -> str:
        digest = hashlib.sha256()
        payload = {
            "check_id": check_id,
            "profile": profile,
            "target_mode": target_mode,
            "command": command,
            "changed_paths": list(changed_paths),
            "selected_targets": list(selected_targets),
            "repo_fingerprint": self.compute_repo_fingerprint(repo_root, changed_paths),
        }
        digest.update(json.dumps(payload, sort_keys=True).encode("utf-8"))
        return digest.hexdigest()

    def load(self, key: str) -> CheckRecord | None:
        if not self.enabled:
            return None
        path = self._entry_path(key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        metadata = dict(payload.get("metadata", {}))
        metadata["cache"] = {"status": "hit", "key": key}
        payload["metadata"] = metadata
        payload["advisory"] = tuple(payload.get("advisory", ()))
        payload["evidence_paths"] = tuple(payload.get("evidence_paths", ()))
        return CheckRecord(**payload)

    def save(self, key: str, record: CheckRecord) -> None:
        if not self.enabled:
            return
        path = self._entry_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(record)
        payload["advisory"] = list(record.advisory)
        payload["evidence_paths"] = list(record.evidence_paths)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _entry_path(self, key: str) -> Path:
        return self._base_dir / f"{key}.json"

    def _iter_paths(self, repo_root: Path, changed_paths: tuple[str, ...]):
        if changed_paths:
            for rel in changed_paths:
                path = repo_root / rel
                if path.is_file():
                    yield path
            return

        for path in sorted(repo_root.rglob("*")):
            if not path.is_file():
                continue
            parts = set(path.relative_to(repo_root).parts)
            if parts & _IGNORED_PARTS:
                continue
            if ".sdetkit" in parts and "out" in parts:
                continue
            yield path
