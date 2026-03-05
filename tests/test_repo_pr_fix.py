from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from sdetkit import cli, repo


class Result:
    def __init__(self, exit_code: int, stdout: str, stderr: str) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class CliRunner:
    def invoke(self, args: list[str]) -> Result:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(args)
        return Result(code, stdout.getvalue(), stderr.getvalue())


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    (root / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)


def test_pr_fix_apply_commit_creates_branch_and_commit(tmp_path: Path, monkeypatch) -> None:
    _init_git_repo(tmp_path)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "pr-fix",
            str(tmp_path),
            "--allow-absolute-path",
            "--apply",
            "--force-branch",
            "--branch",
            "sdetkit/fix-audit",
        ]
    )
    assert result.exit_code == 0
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == "sdetkit/fix-audit"
    commit_time = subprocess.run(
        ["git", "show", "--format=%ct", "--no-patch"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    assert commit_time == "1700000000"


def test_pr_fix_no_changes_exits_zero_without_commit(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    runner = CliRunner()
    prepared = runner.invoke(
        ["repo", "fix-audit", str(tmp_path), "--allow-absolute-path", "--apply", "--force"]
    )
    assert prepared.exit_code == 0
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "prepared"], cwd=tmp_path, check=True, capture_output=True
    )
    result = runner.invoke(
        ["repo", "pr-fix", str(tmp_path), "--allow-absolute-path", "--apply", "--force-branch"]
    )
    assert result.exit_code == 0
    assert "no changes" in result.stdout


def test_pr_fix_open_pr_requires_token(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "pr-fix",
            str(tmp_path),
            "--allow-absolute-path",
            "--apply",
            "--open-pr",
            "--force-branch",
        ]
    )
    assert result.exit_code == 2
    assert "missing GitHub token" in result.stderr


def test_pr_body_deterministic_ordering() -> None:
    body = repo._build_pr_body(
        profile="default",
        packs=["enterprise", "core"],
        rule_ids=["B", "A"],
        changed_files=["b.txt", "a.txt"],
        per_project=[],
    )
    assert "`A, B`" in body
    assert body.index("`a.txt`") < body.index("`b.txt`")


def test_pr_fix_no_network_calls_without_open_pr(tmp_path: Path, monkeypatch) -> None:
    _init_git_repo(tmp_path)
    called = {"count": 0}

    def _blocked(*_args, **_kwargs):
        called["count"] += 1
        raise AssertionError("network should not be called")

    monkeypatch.setattr(repo.urllib.request, "urlopen", _blocked)
    runner = CliRunner()
    result = runner.invoke(
        ["repo", "pr-fix", str(tmp_path), "--allow-absolute-path", "--apply", "--force-branch"]
    )
    assert result.exit_code == 0
    assert called["count"] == 0


def _policy() -> repo.RepoAuditPolicy:
    return repo.RepoAuditPolicy(
        profile="default",
        fail_on="none",
        baseline_path="",
        exclude_paths=(),
        disable_rules=frozenset(),
        severity_overrides={},
        org_packs=(),
        allowlist=(),
        org_pack_unknown=(),
        lint_expiry_max_days=0,
    )


def test_pr_fix_arg_validation_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    root = str(tmp_path)
    assert runner.invoke(["repo", "pr-fix", root, "--dry-run", "--apply"]).exit_code == 2
    assert runner.invoke(["repo", "pr-fix", root, "--open-pr"]).exit_code == 2
    assert (
        runner.invoke(["repo", "pr-fix", root, "--body", "x", "--body-file", "a.txt"]).exit_code
        == 2
    )


def test_pr_fix_project_discovery_error(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        repo,
        "discover_projects",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad manifest")),
    )
    res = runner.invoke(
        ["repo", "pr-fix", str(tmp_path), "--project", "p", "--allow-absolute-path"]
    )
    assert res.exit_code == 2
    assert "bad manifest" in res.stderr


def test_pr_fix_project_unknown_and_conflict_paths(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project = SimpleNamespace(name="p1")
    resolved = SimpleNamespace(
        name="p1",
        root=tmp_path,
        root_rel=".",
        profile="default",
        baseline_rel=None,
        exclude_paths=(),
        config_path=None,
        packs=(),
    )
    monkeypatch.setattr(repo, "discover_projects", lambda *_a, **_k: ("manifest", [project]))
    monkeypatch.setattr(repo, "resolve_project", lambda *_a, **_k: resolved)

    res_unknown = runner.invoke(
        ["repo", "pr-fix", str(tmp_path), "--project", "nope", "--allow-absolute-path"]
    )
    assert res_unknown.exit_code == 2

    monkeypatch.setattr(repo, "_resolve_repo_audit_policy", lambda *_a, **_k: _policy())
    monkeypatch.setattr(repo, "_plan_repo_fix_audit", lambda *_a, **_k: ([], ["x.patch"], []))
    res_conflict = runner.invoke(
        ["repo", "pr-fix", str(tmp_path), "--project", "p1", "--allow-absolute-path"]
    )
    assert res_conflict.exit_code == 2
    assert "refusing to overwrite" in res_conflict.stderr


def test_pr_fix_apply_git_failure_paths(tmp_path: Path, monkeypatch) -> None:
    _init_git_repo(tmp_path)
    runner = CliRunner()
    edit = SimpleNamespace(path="README.md", old_text="# test\n", new_text="# changed\n")
    fix = SimpleNamespace(rule_id="r1", changes=(edit,))
    monkeypatch.setattr(repo, "_plan_repo_fix_audit", lambda *_a, **_k: ([fix], [], []))
    monkeypatch.setattr(repo, "_resolve_repo_audit_policy", lambda *_a, **_k: _policy())

    monkeypatch.setattr(repo, "_git_branch_exists", lambda *_a, **_k: True)
    assert (
        runner.invoke(
            [
                "repo",
                "pr-fix",
                str(tmp_path),
                "--allow-absolute-path",
                "--apply",
                "--branch",
                "main",
            ]
        ).exit_code
        == 2
    )

    def fake_git_run(_root, args, env=None):
        if args[:2] == ["branch", "-f"]:
            return subprocess.CompletedProcess(args, 1, "", "reset failed")
        if args and args[0] == "checkout":
            return subprocess.CompletedProcess(args, 1, "", "checkout failed")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(repo, "_git_run", fake_git_run)
    assert (
        runner.invoke(
            [
                "repo",
                "pr-fix",
                str(tmp_path),
                "--allow-absolute-path",
                "--apply",
                "--branch",
                "main",
                "--force-branch",
            ]
        ).exit_code
        == 2
    )


def test_pr_fix_open_pr_push_and_slug_errors(tmp_path: Path, monkeypatch) -> None:
    _init_git_repo(tmp_path)
    runner = CliRunner()
    monkeypatch.setenv("GITHUB_TOKEN", "tok")

    edit = SimpleNamespace(path="README.md", old_text="# test\n", new_text="# changed\n")
    fix = SimpleNamespace(rule_id="r1", changes=(edit,))
    monkeypatch.setattr(repo, "_plan_repo_fix_audit", lambda *_a, **_k: ([fix], [], []))
    monkeypatch.setattr(repo, "_resolve_repo_audit_policy", lambda *_a, **_k: _policy())
    monkeypatch.setattr(repo, "_git_branch_exists", lambda *_a, **_k: False)

    def push_fail(_root, args, env=None):
        if args and args[0] == "push":
            return subprocess.CompletedProcess(args, 1, "", "push failed")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(repo, "_git_run", push_fail)
    assert (
        runner.invoke(
            ["repo", "pr-fix", str(tmp_path), "--allow-absolute-path", "--apply", "--open-pr"]
        ).exit_code
        == 2
    )

    monkeypatch.setattr(
        repo,
        "_git_run",
        lambda _root, args, env=None: subprocess.CompletedProcess(args, 0, "", ""),
    )
    monkeypatch.setattr(repo, "_detect_repo_slug", lambda *_a, **_k: "")
    assert (
        runner.invoke(
            ["repo", "pr-fix", str(tmp_path), "--allow-absolute-path", "--apply", "--open-pr"]
        ).exit_code
        == 2
    )


def test_repo_rules_and_projects_text_modes(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    rules = runner.invoke(["repo", "rules", "list"])
    assert rules.exit_code == 0
    assert "sev=" in rules.stdout

    project = SimpleNamespace(name="app")
    resolved = SimpleNamespace(
        name="app",
        root=tmp_path,
        root_rel=".",
        config_rel=None,
        config_path=None,
        profile="default",
        packs=(),
        baseline_rel=None,
        exclude_paths=(),
    )
    monkeypatch.setattr(repo, "discover_projects", lambda *_a, **_k: ("manifest.yml", [project]))
    monkeypatch.setattr(repo, "resolve_project", lambda *_a, **_k: resolved)
    projects = runner.invoke(["repo", "projects", "list", str(tmp_path), "--allow-absolute-path"])
    assert projects.exit_code == 0
    assert "Manifest: manifest.yml" in projects.stdout
    assert "- app:" in projects.stdout
