from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast


class Provider(Protocol):
    def complete(self, *, role: str, task: str, context: dict[str, object]) -> str: ...


@dataclass(frozen=True)
class NoneProvider:
    def complete(self, *, role: str, task: str, context: dict[str, object]) -> str:
        return f"{role}: deterministic mode active for task={task}"


@dataclass(frozen=True)
class LocalHTTPProvider:
    endpoint: str
    model: str
    timeout_s: float = 20.0

    def complete(self, *, role: str, task: str, context: dict[str, object]) -> str:
        payload = {"model": self.model, "prompt": f"[{role}] {task}", "context": context}
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as response:  # noqa: S310
            raw = cast(str, response.read().decode("utf-8"))
        try:
            data = json.loads(raw)
        except ValueError:
            return raw
        if isinstance(data, dict):
            text = data.get("response") or data.get("text") or data.get("output")
            if isinstance(text, str):
                return text
        return str(raw)


@dataclass(frozen=True)
class FakeProvider:
    suffix: str = "fake"

    def complete(self, *, role: str, task: str, context: dict[str, object]) -> str:
        return f"{role}:{task}:{self.suffix}"


@dataclass(frozen=True)
class CachedProvider:
    wrapped: Provider
    cache_dir: Path
    enabled: bool = True

    def _cache_key(self, *, role: str, task: str, context: dict[str, object]) -> str:
        payload = {"role": role, "task": task, "context": context}
        canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def complete(self, *, role: str, task: str, context: dict[str, object]) -> str:
        if not self.enabled:
            return self.wrapped.complete(role=role, task=task, context=context)
        key = self._cache_key(role=role, task=task, context=context)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                payload = {}
            cached = payload.get("response") if isinstance(payload, dict) else None
            if isinstance(cached, str):
                return cached
        value = self.wrapped.complete(role=role, task=task, context=context)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"response": value}, ensure_ascii=True, sort_keys=True), encoding="utf-8"
        )
        return value
