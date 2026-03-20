from __future__ import annotations

import json
import sys
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


def test_manager_plan_routes_umbrella_tasks_to_blueprint_action(tmp_path: Path) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    cfg = load_config(tmp_path / ".sdetkit/agent/config.yaml")

    _message, plan = _manager_plan(
        task="umbrella architecture optimization blueprint",
        config=cfg,
        provider=CountingProvider(),
        worker_ids=["worker-1", "worker-2"],
    )

    assert plan[0].action == "kits.blueprint"
    assert plan[0].params["goal"] == "umbrella architecture optimization blueprint"


def test_manager_plan_routes_optimize_tasks_to_optimize_action(tmp_path: Path) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    cfg = load_config(tmp_path / ".sdetkit/agent/config.yaml")

    _message, plan = _manager_plan(
        task="optimize umbrella architecture and align doctor quality gate integration agentos",
        config=cfg,
        provider=CountingProvider(),
        worker_ids=["worker-1", "worker-2"],
    )

    assert plan[0].action == "kits.optimize"
    assert plan[0].params["goal"].startswith("optimize umbrella architecture")


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


def test_worker_can_write_umbrella_blueprint_artifact(tmp_path: Path) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    registry = ActionRegistry(
        root=tmp_path,
        write_allowlist=(".sdetkit/agent/workdir",),
        shell_allowlist=(),
    )

    result = registry.run(
        "kits.blueprint",
        {
            "goal": "upgrade umbrella architecture with agentos",
            "output": ".sdetkit/agent/workdir/umbrella-blueprint.json",
            "kits": ["release", "integration"],
        },
    )

    assert result.ok is True
    artifact = tmp_path / ".sdetkit/agent/workdir/umbrella-blueprint.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["upgrade_backlog"]
    assert payload["selected_kits"][0]["id"] == "release-confidence"


def test_worker_can_write_umbrella_optimize_artifact(tmp_path: Path) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "premium-gate.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "ci.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "constraints-ci.txt").write_text("ruff==0.15.7\n", encoding="utf-8")
    (tmp_path / "examples" / "kits" / "integration").mkdir(parents=True, exist_ok=True)
    (tmp_path / "examples" / "kits" / "integration" / "profile.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (tmp_path / "examples" / "kits" / "integration" / "heterogeneous-topology.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (tmp_path / "templates" / "automations").mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "automations" / "repo-health-audit.yaml").write_text(
        "metadata:\n  id: repo-health-audit\nworkflow: []\n",
        encoding="utf-8",
    )
    registry = ActionRegistry(
        root=tmp_path,
        write_allowlist=(".sdetkit/agent/workdir",),
        shell_allowlist=(),
    )

    result = registry.run(
        "kits.optimize",
        {
            "goal": "upgrade umbrella architecture with agentos optimization",
            "output": ".sdetkit/agent/workdir/umbrella-optimize.json",
        },
    )

    assert result.ok is True
    artifact = tmp_path / ".sdetkit/agent/workdir/umbrella-optimize.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["alignment_score"]["score"] > 0
    assert payload["doctor_quality_contract"]["entrypoint"].startswith("sdetkit doctor ")


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


def test_shell_action_uses_shlex_parsing_for_quoted_arguments(tmp_path: Path) -> None:
    registry = ActionRegistry(
        root=tmp_path,
        write_allowlist=(".sdetkit/agent/workdir",),
        shell_allowlist=(sys.executable,),
    )

    result = registry.run(
        "shell.run",
        {"cmd": f'{sys.executable} -c "import sys; print(sys.argv[1])" "hello world"'},
    )

    assert result.ok is True
    assert result.payload["stdout"].strip() == "hello world"


def test_shell_action_rejects_invalid_shell_syntax(tmp_path: Path) -> None:
    registry = ActionRegistry(
        root=tmp_path,
        write_allowlist=(".sdetkit/agent/workdir",),
        shell_allowlist=("python",),
    )

    result = registry.run("shell.run", {"cmd": 'python -c "print(1)'})

    assert result.ok is False
    assert "invalid shell command" in str(result.payload.get("error", ""))


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


def test_agent_dashboard_summary_tracks_workers_approvals_and_task_families(tmp_path: Path) -> None:
    init_agent(tmp_path, tmp_path / ".sdetkit/agent/config.yaml")
    history_dir = tmp_path / ".sdetkit" / "agent" / "history"

    (history_dir / "a.json").write_text(
        json.dumps(
            {
                "hash": "a",
                "captured_at": "2026-03-20T00:00:00Z",
                "status": "ok",
                "task": "template:repo-health-audit",
                "actions": [
                    {
                        "action": "repo.audit",
                        "worker_id": "worker-1",
                        "ok": True,
                        "approved": True,
                        "denied": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (history_dir / "b.json").write_text(
        json.dumps(
            {
                "hash": "b",
                "captured_at": "2026-03-20T00:01:00Z",
                "status": "error",
                "task": "umbrella architecture optimization blueprint",
                "actions": [
                    {
                        "action": "shell.run",
                        "worker_id": "worker-2",
                        "ok": False,
                        "approved": False,
                        "denied": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    from sdetkit.agent.dashboard import summarize_history

    summary = summarize_history(history_dir)
    assert summary["workers"][0]["name"] in {"worker-1", "worker-2"}
    assert summary["approvals"]["approved"] == 1
    assert summary["approvals"]["denied"] == 1
    families = {item["name"] for item in summary["task_families"]}
    assert {"template", "blueprint"} <= families
