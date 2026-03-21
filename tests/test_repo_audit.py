from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli
from sdetkit import repo as repo_mod
from sdetkit.atomicio import atomic_write_bytes
from sdetkit.security import (
    SecurityError,
    redact_keys,
    redact_secrets_headers,
    redact_secrets_text,
    safe_path,
)


def test_safe_path_allows_dot_and_blocks_traversal(tmp_path: Path) -> None:
    assert safe_path(tmp_path, ".") == tmp_path.resolve()
    try:
        safe_path(tmp_path, "../x")
    except SecurityError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected SecurityError for traversal path")


def test_atomic_write_bytes_writes_exact(tmp_path: Path) -> None:
    target = tmp_path / "bin.dat"
    atomic_write_bytes(target, b"a\x00b")
    assert target.read_bytes() == b"a\x00b"


def test_redact_secrets_helpers_are_deterministic() -> None:
    keys = redact_keys(["x-auth-token"])
    text = "authorization: abc token=xyz"
    assert (
        redact_secrets_text(text, enabled=True, keys=keys)
        == "authorization: <redacted> token=<redacted>"
    )

    headers = {"X-Api-Key": "abc", "Accept": "application/json"}
    assert redact_secrets_headers(headers, enabled=True, keys=keys) == {
        "Accept": "application/json",
        "X-Api-Key": "<redacted>",
    }


def _create_bad_repo(root: Path) -> None:
    (root / "a.txt").write_bytes(b"hello \nline2")
    (root / "b.txt").write_bytes(b"x\r\ny\n")
    (root / "bad.bin").write_bytes(b"\xff\xfe")
    (root / "secret.env").write_text("API_KEY=shhh\n", encoding="utf-8")
    (root / "hidden.txt").write_text("ok\u202eoops\n", encoding="utf-8")


def test_repo_check_json_is_deterministic_and_stable(tmp_path: Path, capsys) -> None:
    _create_bad_repo(tmp_path)
    rc = cli.main(["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "json"])
    assert rc == 1
    out = capsys.readouterr().out
    first = json.loads(out)

    rc2 = cli.main(["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "json"])
    assert rc2 == 1
    out2 = capsys.readouterr().out
    second = json.loads(out2)
    assert first == second

    finding_paths = [f["path"] for f in first["findings"]]
    assert finding_paths == sorted(finding_paths)
    assert set(first["summary"]["counts"].keys()) == {"error", "info", "warn"}


def test_repo_fix_then_recheck_clean(tmp_path: Path) -> None:
    _create_bad_repo(tmp_path)
    rc = cli.main(["repo", "fix", str(tmp_path), "--allow-absolute-path", "--eol", "lf"])
    assert rc == 0

    rc2 = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--fail-on",
            "warn",
        ]
    )
    assert rc2 == 1  # utf8 decode + secret + hidden unicode still present

    # remove unsafe/unfixable files then re-check clean
    (tmp_path / "bad.bin").unlink()
    (tmp_path / "secret.env").write_text("SAFE=value\n", encoding="utf-8")
    (tmp_path / "hidden.txt").write_text("ok\n", encoding="utf-8")
    rc3 = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--fail-on",
            "warn",
        ]
    )
    assert rc3 == 0


def test_repo_fix_check_mode_exit_one_when_changes_needed(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("a  ", encoding="utf-8")
    rc = cli.main(["repo", "fix", str(tmp_path), "--allow-absolute-path", "--check"])
    assert rc == 1
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "a  "


def test_repo_check_out_requires_force(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("ok\n", encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text("old", encoding="utf-8")
    rc = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--out",
            "report.json",
        ]
    )
    assert rc == 2
    rc2 = cli.main(
        [
            "repo",
            "check",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--out",
            "report.json",
            "--force",
        ]
    )
    assert rc2 == 1
    assert json.loads(report.read_text(encoding="utf-8"))["summary"]["ok"] is False


def test_repo_check_ignores_egg_info_metadata(tmp_path: Path) -> None:
    egg_info = tmp_path / "src" / "sdetkit.egg-info"
    egg_info.mkdir(parents=True)
    (egg_info / "SOURCES.txt").write_text("no trailing newline", encoding="utf-8")
    (tmp_path / "clean.txt").write_text("clean\n", encoding="utf-8")

    rc = cli.main(["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "json"])
    assert rc == 0


def test_repo_check_skips_venv_prefix_and_dist_build_dirs(tmp_path: Path) -> None:
    venv = tmp_path / ".venv-smoke" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_bytes(b"\xff\xfe")

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "artifact.whl").write_bytes(b"\x80\x03")

    build = tmp_path / "build"
    build.mkdir()
    (build / "tmp.bin").write_bytes(b"\x00\xff")

    (tmp_path / "clean.txt").write_text("clean\n", encoding="utf-8")

    rc = cli.main(["repo", "check", str(tmp_path), "--allow-absolute-path", "--format", "json"])
    assert rc == 0


def test_repo_scanner_helpers_cover_workflow_dependency_and_baseline(tmp_path: Path) -> None:
    py_text = """
eval('1')
exec('2')
import pickle, yaml, subprocess
pickle.loads(data)
yaml.load(doc)
subprocess.run('echo x', shell=True)
subprocess.Popen('echo y', shell=True)
""".strip()
    py_findings = repo_mod._scan_python_ast("src/a.py", py_text)
    codes = {f.code for f in py_findings}
    assert {"eval", "exec", "pickle_loads", "yaml_load", "subprocess_shell_true"}.issubset(codes)

    assert repo_mod._scan_python_ast("src/bad.py", "def x(:\n") == []

    wf = """
- uses: actions/checkout@v4
on: pull_request_target
permissions: write-all
run: curl https://x | bash
""".strip()
    wf_codes = {f.code for f in repo_mod._scan_workflow(".github/workflows/ci.yml", wf)}
    assert {
        "unpinned_action",
        "pull_request_target",
        "write_all_permissions",
        "curl_bash",
    } == wf_codes

    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pkg\n#x\npinned==1.2.3\n", encoding="utf-8")
    dep = repo_mod._scan_dependency_hygiene(tmp_path, None)
    dep_codes = {f.code for f in dep}
    assert "missing_python_lockfile" in dep_codes
    assert "missing_node_lockfile" in dep_codes
    assert "unpinned_dependency" in dep_codes

    findings = [repo_mod.Finding("c", "warn", "a.py", 1, 1, "x", "m")]
    assert repo_mod._apply_baseline(findings, [{"path": "a.py", "check": "c", "code": "x"}]) == []
    # expired suppression should not apply
    kept = repo_mod._apply_baseline(
        findings,
        [{"path": "a.py", "check": "c", "code": "x", "expires": "2001-01-01"}],
    )
    assert kept == findings

    assert repo_mod._load_baseline(tmp_path / "missing.json") == []
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert repo_mod._load_baseline(bad) == []
    ok = tmp_path / "ok.json"
    ok.write_text('[{"path":"a.py"}, 1]', encoding="utf-8")
    assert repo_mod._load_baseline(ok) == [{"path": "a.py"}]

    assert repo_mod._severity_rank("info") < repo_mod._severity_rank("warn")
    assert repo_mod._score([]) == 100


def test_repo_init_template_planning_helpers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:

    templates = repo_mod._load_repo_preset_templates("enterprise_python")
    assert "SECURITY.md" in templates
    with pytest.raises(ValueError):
        repo_mod._load_repo_preset_templates("nope")

    root = tmp_path / "repo"
    root.mkdir()
    (root / "SECURITY.md").write_text("custom\n", encoding="utf-8")

    changes, conflicts = repo_mod._plan_repo_init(root, preset="enterprise_python", force=False)
    assert "SECURITY.md" in conflicts
    assert any(c.action == "create" for c in changes)

    changes_force, conflicts_force = repo_mod._plan_repo_init(
        root, preset="enterprise_python", force=True
    )
    assert conflicts_force == []
    assert any(c.path == "SECURITY.md" and c.action == "update" for c in changes_force)

    # print helpers + apply dry-run and write path
    repo_mod._print_repo_init_plan([], command="init", dry_run=True)
    assert "no changes" in capsys.readouterr().out

    rc = repo_mod._run_repo_init(
        root,
        preset="enterprise_python",
        command="apply",
        dry_run=True,
        force=False,
        diff=True,
    )
    assert rc == 0

    rc2 = repo_mod._run_repo_init(
        root,
        preset="enterprise_python",
        command="init",
        dry_run=False,
        force=False,
        diff=False,
    )
    assert rc2 == 2

    rc3 = repo_mod._run_repo_init(
        root,
        preset="enterprise_python",
        command="init",
        dry_run=False,
        force=True,
        diff=False,
    )
    assert rc3 == 0
    assert (root / "SECURITY.md").exists()


def test_repo_report_sorting_sarif_and_sbom_helpers(tmp_path: Path) -> None:
    finding = repo_mod.Finding("check", "warn", "b.py", 3, 2, "code", "msg")
    payload = repo_mod._report_payload(tmp_path, [finding], profile="enterprise", policy_text="p")
    assert payload["summary"]["findings"] == 1
    assert payload["summary"]["ok"] is False
    assert payload["metadata"]["policy_hash"]

    assert repo_mod._sorted_dict_items("no", repo_mod._audit_finding_sort_key) == []
    sorted_payload = repo_mod._audit_sorted_payload(
        {
            "findings": [
                {"rule_id": "B", "path": "z.py", "line": 2, "column": 1, "severity": "warn"},
                {"rule_id": "A", "path": "a.py", "line": 1, "column": 1, "severity": "error"},
            ],
            "checks": [{"pack": "x", "key": "z", "status": "fail"}, {"pack": "x", "key": "a"}],
            "projects": [{"name": "b", "root": "2"}, {"name": "a", "root": "1"}],
        }
    )
    assert sorted_payload["findings"][0]["rule_id"] == "A"
    assert sorted_payload["checks"][0]["key"] == "a"
    assert sorted_payload["projects"][0]["name"] == "a"

    sarif = repo_mod._to_sarif(
        {
            "findings": [
                {
                    "check": "c",
                    "code": "x",
                    "severity": "warn",
                    "message": "m",
                    "path": "C:/repo/x.py",
                    "line": 7,
                    "column": 3,
                    "rule_id": "RID",
                    "rule_tags": "bad",
                }
            ]
        }
    )
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["rules"][0]["id"] == "RID"
    assert (
        run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        == "repo/x.py"
    )

    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
dependencies = ["alpha>=1", "beta==2"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text('{"dependencies":{"react":"1.0.0"}}\n', encoding="utf-8")
    sbom = repo_mod._generate_sbom(tmp_path)
    names = {c["name"] for c in sbom["components"]}
    assert {"alpha", "beta", "react"}.issubset(names)
