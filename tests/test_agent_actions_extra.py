from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sdetkit.agent.actions import ActionRegistry, maybe_parse_action_task


def test_maybe_parse_action_task_variants() -> None:
    assert maybe_parse_action_task("noop") is None
    assert maybe_parse_action_task("action fs.read") == ("fs.read", {})
    assert maybe_parse_action_task("action x 1") == ("x", {"value": 1})
    assert maybe_parse_action_task("action x [1,2]") == ("x", {"value": [1, 2]})


def test_action_registry_error_paths(tmp_path: Path, monkeypatch) -> None:
    reg = ActionRegistry(
        root=tmp_path, write_allowlist=("allowed",), shell_allowlist=("python -c",)
    )

    assert reg.run("missing", {}).ok is False
    assert reg.run("fs.read", {"path": "/abs"}).ok is False
    assert reg.run("fs.write", {"path": "denied/out.txt", "content": "x"}).ok is False
    assert reg.run("shell.run", {"cmd": ""}).ok is False
    assert reg.run("shell.run", {"cmd": 'python -c "x'}).ok is False

    class _P:
        returncode = 1
        stdout = ""
        stderr = "bad"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
    res = reg.run("shell.run", {"cmd": 'python -c "print(1)"'})
    assert res.ok is False

    import pytest

    with pytest.raises(ValueError):
        reg.run("report.build", {"output": "/abs/path.html", "format": "html"})


def test_action_registry_success_paths(tmp_path: Path, monkeypatch) -> None:
    reg = ActionRegistry(
        root=tmp_path,
        write_allowlist=("allowed", "nested/dir"),
        shell_allowlist=("python -c", "bad ["),
    )
    (tmp_path / "allowed").mkdir()
    (tmp_path / "allowed" / "in.txt").write_text("hello", encoding="utf-8")

    read_res = reg.run("fs.read", {"path": "allowed/in.txt"})
    assert read_res.ok is True
    assert read_res.payload["content"] == "hello"

    write_res = reg.run("fs.write", {"path": "nested/dir/out.txt", "content": "abc"})
    assert write_res.ok is True
    assert write_res.payload["bytes"] == 3
    assert (tmp_path / "nested" / "dir" / "out.txt").read_text(encoding="utf-8") == "abc"

    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    shell_res = reg.run("shell.run", {"cmd": 'python -c "print(1)"'})
    assert shell_res.ok is True
    assert shell_res.payload["stdout"] == "ok"


def test_action_registry_write_allowlist_rejects_traversal(tmp_path: Path) -> None:
    reg = ActionRegistry(
        root=tmp_path,
        write_allowlist=("allowed",),
        shell_allowlist=(),
    )
    (tmp_path / "allowed").mkdir(parents=True, exist_ok=True)
    (tmp_path / "elsewhere").mkdir(parents=True, exist_ok=True)

    result = reg.run(
        "fs.write",
        {"path": "allowed/../elsewhere/out.txt", "content": "blocked"},
    )

    assert result.ok is False
    assert "write denied by allowlist" in str(result.payload.get("error", ""))
    assert not (tmp_path / "elsewhere" / "out.txt").exists()


def test_action_registry_repo_audit_and_report_build(tmp_path: Path, monkeypatch) -> None:
    reg = ActionRegistry(root=tmp_path, write_allowlist=(".sdetkit",), shell_allowlist=("python",))

    monkeypatch.setattr(
        "sdetkit.repo.run_repo_audit",
        lambda root, profile="default": {"findings": [1, 2], "checks": ["a"]},
    )
    seen: dict[str, object] = {}

    def _fake_build_dashboard(*, history_dir, output, fmt, since):
        seen["history_dir"] = history_dir
        seen["output"] = output
        seen["fmt"] = fmt
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("dashboard", encoding="utf-8")

    monkeypatch.setattr("sdetkit.agent.actions.build_dashboard", _fake_build_dashboard)

    audit_res = reg.run("repo.audit", {"profile": "strict"})
    assert audit_res.ok is True
    assert audit_res.payload == {"profile": "strict", "findings": 2, "checks": 1}

    report_res = reg.run("report.build", {"output": ".sdetkit/out.html", "format": "html"})
    assert report_res.ok is True
    assert seen["fmt"] == "html"
    assert str(seen["history_dir"]).endswith(".sdetkit/agent/history")
    assert (tmp_path / ".sdetkit" / "out.html").read_text(encoding="utf-8") == "dashboard"


def test_action_registry_can_write_optimize_artifact(tmp_path: Path) -> None:
    reg = ActionRegistry(
        root=tmp_path, write_allowlist=(".sdetkit/agent/workdir",), shell_allowlist=()
    )
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

    result = reg.run(
        "kits.optimize",
        {
            "goal": "upgrade umbrella architecture with agentos optimization",
            "output": ".sdetkit/agent/workdir/umbrella-optimize.json",
        },
    )

    assert result.ok is True
    assert result.payload["alignment_score"] > 0
    artifact = tmp_path / ".sdetkit" / "agent" / "workdir" / "umbrella-optimize.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["alignment_score"]["status"] in {"strong", "maximized"}
    assert payload["operating_sequence"][0]["stage"] == "doctor-first"


def test_action_registry_can_write_expand_artifact(tmp_path: Path) -> None:
    reg = ActionRegistry(
        root=tmp_path, write_allowlist=(".sdetkit/agent/workdir",), shell_allowlist=()
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "premium-gate.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "ci.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "constraints-ci.txt").write_text("ruff==0.15.7\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text("site_name: demo\n", encoding="utf-8")
    (tmp_path / "RELEASE.md").write_text("# release\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github" / "workflows" / "pages.yml").write_text("name: pages\n", encoding="utf-8")
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
        "metadata:\n  id: repo-health-audit\n  title: x\n  version: 1\n  description: x\nworkflow:\n  - action: fs.write\n    with:\n      path: out.txt\n",
        encoding="utf-8",
    )

    result = reg.run(
        "kits.expand",
        {
            "goal": "add more bots workers search and repo expansion",
            "output": ".sdetkit/agent/workdir/umbrella-expand.json",
        },
    )

    assert result.ok is True
    assert result.payload["recommended_workers"] > 0
    artifact = tmp_path / ".sdetkit" / "agent" / "workdir" / "umbrella-expand.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["recommended_workers"]
    assert payload["worker_launch_pack"][0]["launch_command"].startswith(
        "python -m sdetkit agent templates run "
    )
