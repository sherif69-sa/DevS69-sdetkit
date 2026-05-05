import importlib.util
import json


def _load_autopilot():
    spec = importlib.util.spec_from_file_location(
        "maintenance_autopilot", "tools/maintenance_autopilot.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _same_repo_event(path):
    payload = {
        "pull_request": {
            "head": {"repo": {"full_name": "sherif69-sa/DevS69-sdetkit"}},
            "base": {"repo": {"full_name": "sherif69-sa/DevS69-sdetkit"}},
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _safe_plan(fix_type="format_only", source_code="PRE_COMMIT_FORMAT_DRIFT"):
    return {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "safe_to_auto_fix": True,
        "fix_type": fix_type,
        "requires_human_review": False,
        "source_code": source_code,
        "affected_files": ["src/sdetkit/example.py"],
    }


def _success_result():
    return {
        "schema_version": "sdetkit.adaptive_safe_remediation.v1",
        "ok": True,
        "status": "success",
    }


def test_commit_safe_fix_changes_pushes_same_repo_branch(tmp_path, monkeypatch):
    autopilot = _load_autopilot()
    event_path = tmp_path / "event.json"
    _same_repo_event(event_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/example")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GH_TOKEN", "token")
    autopilot._ACTIVE_FAILURE_CONTEXT.update(
        {
            "commit_safe_fixes": True,
            "token_env": "GH_TOKEN",
            "owner": "sherif69-sa",
            "repo": "DevS69-sdetkit",
        }
    )

    calls = []

    def runner(cmd):
        calls.append(cmd)
        if cmd == ["git", "diff", "--name-only"]:
            return {"ok": True, "returncode": 0, "stdout": "src/sdetkit/example.py\n", "stderr": ""}
        return {"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""}

    result = autopilot._commit_safe_fix_changes(
        tmp_path, _safe_plan(), _success_result(), git_runner=runner
    )

    assert result["ok"] is True
    assert result["pushed"] is True
    assert calls[-1] == ["git", "push", "origin", "HEAD:feature/example"]
    assert (tmp_path / "adaptive-safe-commit-result.json").exists()


def test_commit_safe_fix_changes_accepts_ruff_fixable_lint_plan(tmp_path, monkeypatch):
    autopilot = _load_autopilot()
    event_path = tmp_path / "event.json"
    _same_repo_event(event_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/example")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GH_TOKEN", "token")
    autopilot._ACTIVE_FAILURE_CONTEXT.update(
        {
            "commit_safe_fixes": True,
            "token_env": "GH_TOKEN",
            "owner": "sherif69-sa",
            "repo": "DevS69-sdetkit",
        }
    )

    calls = []

    def runner(cmd):
        calls.append(cmd)
        if cmd == ["git", "diff", "--name-only"]:
            return {"ok": True, "returncode": 0, "stdout": "src/sdetkit/example.py\n", "stderr": ""}
        return {"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""}

    result = autopilot._commit_safe_fix_changes(
        tmp_path,
        _safe_plan(fix_type="ruff_fixable_lint", source_code="RUFF_FIXABLE_LINT"),
        _success_result(),
        git_runner=runner,
    )

    assert result["ok"] is True
    assert result["pushed"] is True
    assert calls[-1] == ["git", "push", "origin", "HEAD:feature/example"]


def test_commit_safe_fix_changes_rejects_fork_pull_request(tmp_path, monkeypatch):
    autopilot = _load_autopilot()
    event_path = tmp_path / "event.json"
    payload = {
        "pull_request": {
            "head": {"repo": {"full_name": "someone/fork"}},
            "base": {"repo": {"full_name": "sherif69-sa/DevS69-sdetkit"}},
        }
    }
    event_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/example")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GH_TOKEN", "token")
    autopilot._ACTIVE_FAILURE_CONTEXT.update(
        {
            "commit_safe_fixes": True,
            "token_env": "GH_TOKEN",
            "owner": "sherif69-sa",
            "repo": "DevS69-sdetkit",
        }
    )

    result = autopilot._commit_safe_fix_changes(
        tmp_path,
        _safe_plan(),
        _success_result(),
        git_runner=lambda cmd: (_ for _ in ()).throw(AssertionError()),
    )

    assert result["ok"] is False
    assert result["attempted"] is False
    assert "same-repository" in result["reason"]


def test_commit_safe_fix_changes_rejects_files_outside_plan(tmp_path, monkeypatch):
    autopilot = _load_autopilot()
    event_path = tmp_path / "event.json"
    _same_repo_event(event_path)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/example")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GH_TOKEN", "token")
    autopilot._ACTIVE_FAILURE_CONTEXT.update(
        {
            "commit_safe_fixes": True,
            "token_env": "GH_TOKEN",
            "owner": "sherif69-sa",
            "repo": "DevS69-sdetkit",
        }
    )

    def runner(cmd):
        if cmd == ["git", "diff", "--name-only"]:
            return {"ok": True, "returncode": 0, "stdout": "src/sdetkit/other.py\n", "stderr": ""}
        raise AssertionError("must stop before git add/commit/push")

    result = autopilot._commit_safe_fix_changes(
        tmp_path, _safe_plan(), _success_result(), git_runner=runner
    )

    assert result["ok"] is False
    assert result["attempted"] is False
    assert result["outside_plan"] == ["src/sdetkit/other.py"]


def test_commit_safe_fix_changes_disabled_by_default(tmp_path):
    autopilot = _load_autopilot()
    autopilot._ACTIVE_FAILURE_CONTEXT["commit_safe_fixes"] = False

    result = autopilot._commit_safe_fix_changes(
        tmp_path,
        _safe_plan(),
        _success_result(),
        git_runner=lambda cmd: (_ for _ in ()).throw(AssertionError()),
    )

    assert result["ok"] is False
    assert result["attempted"] is False
    assert "disabled" in result["reason"]
