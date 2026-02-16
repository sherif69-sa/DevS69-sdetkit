from __future__ import annotations

import json
from pathlib import Path

from sdetkit.agent.actions import ActionRegistry
from sdetkit.agent.core import (
    _manager_plan,
    canonical_json_dumps,
    init_agent,
    load_config,
    run_agent,
)
from sdetkit.agent.providers import CachedProvider


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, role: str, task: str, context: dict[str, object]) -> str:
        self.calls += 1
        return f"{role}-{task}-ok"


def test_agent_init_creates_expected_files(tmp_path: Path) -> None:
    created = init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")

    assert ".sdetkit/agent" in created
    assert ".sdetkit/agent/history" in created
    assert ".sdetkit/agent/workdir" in created
    assert ".sdetkit/agent/cache" in created
    assert (tmp_path / ".sdetkit/agent/config.yaml").exists()


def test_manager_plan_generation_is_deterministic_in_no_llm_mode(tmp_path: Path) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    cfg = load_config(tmp_path / ".sdetkit/agent/config.yaml")

    msg1, plan1 = _manager_plan(
        task='action repo.audit {"profile":"default"}',
        config=cfg,
        provider=CountingProvider(),
        worker_ids=["worker-1", "worker-2"],
    )
    msg2, plan2 = _manager_plan(
        task='action repo.audit {"profile":"default"}',
        config=cfg,
        provider=CountingProvider(),
        worker_ids=["worker-1", "worker-2"],
    )

    assert msg1 == msg2
    assert plan1 == plan2
    assert plan1[0].worker_id == "worker-1"


def test_worker_action_execution_success(tmp_path: Path) -> None:
    registry = ActionRegistry(
        root=tmp_path,
        write_allowlist=(".sdetkit/agent/workdir",),
        shell_allowlist=(),
    )
    result = registry.run(
        "fs.write", {"path": ".sdetkit/agent/workdir/out.txt", "content": "hello"}
    )

    assert result.ok is True
    assert (tmp_path / ".sdetkit/agent/workdir/out.txt").read_text(encoding="utf-8") == "hello"


def test_reviewer_rejects_failed_action(tmp_path: Path, monkeypatch) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    record = run_agent(
        tmp_path,
        config_path=tmp_path / ".sdetkit/agent/config.yaml",
        task='action fs.read {"path":"missing.txt"}',
        auto_approve=True,
    )

    assert record["status"] == "error"
    assert any(
        step["role"] == "reviewer" and step["status"] == "rejected" for step in record["steps"]
    )


def test_approval_gating_denies_dangerous_actions_by_default(tmp_path: Path, monkeypatch) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    record = run_agent(
        tmp_path,
        config_path=tmp_path / ".sdetkit/agent/config.yaml",
        task='action shell.run {"cmd":"python -V"}',
    )

    assert record["status"] == "error"
    assert record["actions"][0]["denied"] is True
    assert "approval" in record["actions"][0]["payload"]["reason"]


def test_cached_provider_hits_after_first_call(tmp_path: Path) -> None:
    wrapped = CountingProvider()
    provider = CachedProvider(wrapped=wrapped, cache_dir=tmp_path / "cache", enabled=True)

    first = provider.complete(role="manager", task="x", context={"a": 1})
    second = provider.complete(role="manager", task="x", context={"a": 1})

    assert first == second
    assert wrapped.calls == 1


def test_cached_provider_miss_when_disabled(tmp_path: Path) -> None:
    wrapped = CountingProvider()
    provider = CachedProvider(wrapped=wrapped, cache_dir=tmp_path / "cache", enabled=False)

    provider.complete(role="manager", task="x", context={"a": 1})
    provider.complete(role="manager", task="x", context={"a": 1})

    assert wrapped.calls == 2


def test_agent_run_records_are_canonical_and_stable(tmp_path: Path, monkeypatch) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    first = run_agent(
        tmp_path, config_path=tmp_path / ".sdetkit/agent/config.yaml", task="health-check"
    )
    second = run_agent(
        tmp_path,
        config_path=tmp_path / ".sdetkit/agent/config.yaml",
        task="health-check",
    )

    assert first["hash"] == second["hash"]
    assert first["steps"] == second["steps"]

    history_file = tmp_path / ".sdetkit/agent/history" / f"{first['hash']}.json"
    on_disk = history_file.read_text(encoding="utf-8")
    loaded = json.loads(on_disk)
    assert on_disk == canonical_json_dumps(loaded)
