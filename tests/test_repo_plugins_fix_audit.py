from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

from sdetkit import cli


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str


class CliRunner:
    def invoke(self, args: list[str]) -> Result:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli.main(args)
        return Result(exit_code=exit_code, stdout=stdout.getvalue(), stderr=stderr.getvalue())


def test_rules_list_json_is_deterministic() -> None:
    runner = CliRunner()
    first = runner.invoke(["repo", "rules", "list", "--json"])
    second = runner.invoke(["repo", "rules", "list", "--json"])
    assert first.exit_code == 0
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert payload["packs"] == ["core"]
    assert payload["rules"] == sorted(payload["rules"], key=lambda x: x["rule_id"])


def test_profile_pack_mapping_enterprise_includes_enterprise_rules(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--profile",
            "enterprise",
            "--format",
            "json",
            "--fail-on",
            "none",
        ]
    )
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["summary"]["packs"] == ["core", "enterprise"]
    assert any(item["rule_id"] == "ENT_REPO_AUDIT_WORKFLOW_MISSING" for item in payload["findings"])


def test_fix_audit_dry_run_apply_and_idempotent(tmp_path: Path) -> None:
    runner = CliRunner()
    dry = runner.invoke(
        [
            "repo",
            "fix-audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--dry-run",
            "--diff",
            "--patch",
            "changes.patch",
            "--force",
        ]
    )
    assert dry.exit_code == 0
    assert "PLAN" in dry.stdout
    assert not (tmp_path / "SECURITY.md").exists()
    assert (tmp_path / "changes.patch").exists()

    apply = runner.invoke(
        [
            "repo",
            "fix-audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--apply",
            "--force",
        ]
    )
    assert apply.exit_code == 0
    assert (tmp_path / "SECURITY.md").exists()

    second = runner.invoke(
        [
            "repo",
            "fix-audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--apply",
            "--force",
        ]
    )
    assert second.exit_code == 0
    assert "no changes" in second.stdout


def test_fix_audit_refuses_patch_overwrite_without_force(tmp_path: Path) -> None:
    (tmp_path / "out.patch").write_text("existing\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        [
            "repo",
            "fix-audit",
            str(tmp_path),
            "--allow-absolute-path",
            "--dry-run",
            "--patch",
            "out.patch",
        ]
    )
    assert result.exit_code == 2
    assert "refusing to overwrite existing patch output" in result.stderr


def test_fix_audit_respects_disable_rules_and_baseline(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.sdetkit.repo_audit]
disable_rules = ["CORE_MISSING_SECURITY_MD"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        ["repo", "fix-audit", str(tmp_path), "--allow-absolute-path", "--apply", "--force"]
    )
    assert result.exit_code == 0
    assert not (tmp_path / "SECURITY.md").exists()


def test_plugin_loader_accepts_entry_points(monkeypatch) -> None:
    from sdetkit import plugins

    class FakeRule:
        meta = plugins.RuleMeta(
            id="ZZZ_FAKE_RULE",
            title="fake",
            description="fake",
            default_severity="warn",
            tags=("pack:core",),
        )

        def run(self, repo_root: Path, context: dict[str, object]) -> list[plugins.Finding]:
            return []

    class FakeEP:
        name = "fake"

        def load(self):
            return FakeRule

    class EPs:
        def select(self, *, group: str):
            if group == "sdetkit.repo_audit_rules":
                return [FakeEP()]
            return []

    monkeypatch.setattr(plugins.importlib_metadata, "entry_points", lambda: EPs())
    catalog = plugins.load_rule_catalog()
    ids = [item.meta.id for item in catalog.rules]
    assert "ZZZ_FAKE_RULE" in ids
    assert ids == sorted(ids)
