from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
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
