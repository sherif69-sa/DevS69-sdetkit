from __future__ import annotations

import hashlib
import json
import os
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
    def __init__(self, base_dir: Path, *, enabled: bool = True) -> None:
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

    def _is_ignored_path(self, repo_root: Path, path: Path) -> bool:
        try:
            parts = set(path.relative_to(repo_root).parts)
        except ValueError:
            return True
        if parts & _IGNORED_PARTS:
            return True
        if ".sdetkit" in parts and "out" in parts:
            return True
        return False

    def _iter_tree_files(self, root: Path):
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            rel_parts = current.relative_to(root).parts
            if set(rel_parts) & _IGNORED_PARTS:
                dirnames[:] = []
                continue
            if ".sdetkit" in rel_parts and "out" in rel_parts:
                dirnames[:] = []
                continue
            if current.name == ".sdetkit":
                dirnames[:] = [name for name in dirnames if name != "out"]
            dirnames[:] = [name for name in dirnames if name not in _IGNORED_PARTS]
            for filename in filenames:
                yield current / filename

    def _iter_paths(self, repo_root: Path, changed_paths: tuple[str, ...]):
        repo_root_resolved = repo_root.resolve()
        if changed_paths:
            seen: set[Path] = set()
            for rel in changed_paths:
                hinted = Path(rel)
                path = hinted if hinted.is_absolute() else (repo_root / hinted)
                try:
                    path.resolve().relative_to(repo_root_resolved)
                except ValueError:
                    continue
                if path.is_file():
                    seen.add(path)
                    continue
                if path.is_dir():
                    if self._is_ignored_path(repo_root, path):
                        continue
                    for child in self._iter_tree_files(path):
                        seen.add(child)
            for path in sorted(seen):
                if self._is_ignored_path(repo_root, path):
                    continue
                yield path
            return

        for path in sorted(self._iter_tree_files(repo_root)):
            if self._is_ignored_path(repo_root, path):
                continue
            yield path
