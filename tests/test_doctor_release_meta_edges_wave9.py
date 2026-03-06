from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import sdetkit.doctor as d


def test_run_returns_tuple_and_passes_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_run(
        cmd: list[str], *, cwd: str | None, text: bool, capture_output: bool
    ) -> SimpleNamespace:
        seen["cmd"] = cmd
        seen["cwd"] = cwd
        seen["text"] = text
        seen["capture_output"] = capture_output
        return SimpleNamespace(returncode=3, stdout="out", stderr="err")

    monkeypatch.setattr(d.subprocess, "run", fake_run)

    rc, out, err = d._run(["x"], cwd=tmp_path)
    assert (rc, out, err) == (3, "out", "err")
    assert seen["cmd"] == ["x"]
    assert seen["cwd"] == str(tmp_path)
    assert seen["text"] is True
    assert seen["capture_output"] is True


def test_package_info_falls_back_to_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        d.metadata, "version", lambda _n: (_ for _ in ()).throw(RuntimeError("nope"))
    )
    info = d._package_info()
    assert info["name"] == "sdetkit"
    assert info["version"] == "unknown"


def test_in_virtualenv_falls_back_to_prefix_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setattr(d.sys, "prefix", "/a", raising=False)
    monkeypatch.setattr(d.sys, "base_prefix", "/b", raising=False)
    assert d._in_virtualenv() is True


def test_check_pyproject_toml_missing_parse_failed_and_valid(tmp_path: Path) -> None:
    ok, msg = d._check_pyproject_toml(tmp_path)
    assert ok is False
    assert msg == "pyproject.toml is missing"

    (tmp_path / "pyproject.toml").write_text("not toml\n", encoding="utf-8")
    ok2, msg2 = d._check_pyproject_toml(tmp_path)
    assert ok2 is False
    assert msg2.startswith("pyproject.toml parse failed:")

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.0.0"\n', encoding="utf-8"
    )
    ok3, msg3 = d._check_pyproject_toml(tmp_path)
    assert ok3 is True
    assert msg3 == "pyproject.toml is valid TOML"


def test_project_version_from_pyproject_errors_and_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    v0, e0 = d._project_version_from_pyproject(tmp_path)
    assert v0 is None
    assert e0 == "pyproject.toml is missing"

    (tmp_path / "pyproject.toml").write_text("not toml\n", encoding="utf-8")
    v1, e1 = d._project_version_from_pyproject(tmp_path)
    assert v1 is None
    assert e1.startswith("pyproject.toml parse failed:")

    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n', encoding="utf-8")
    v2, e2 = d._project_version_from_pyproject(tmp_path)
    assert v2 is None
    assert e2 == "[project].version is missing"

    (tmp_path / "pyproject.toml").write_text('{"not": "toml"}\n', encoding="utf-8")
    monkeypatch.setattr(d, "_toml", SimpleNamespace(loads=lambda _s: ["not-a-table"]))
    v3, e3 = d._project_version_from_pyproject(tmp_path)
    assert v3 is None
    assert e3 == "pyproject.toml did not parse to a table"

    monkeypatch.setattr(d, "_toml", SimpleNamespace(loads=lambda _s: {}))
    v4, e4 = d._project_version_from_pyproject(tmp_path)
    assert v4 is None
    assert e4 == "[project] table is missing"

    monkeypatch.setattr(
        d, "_toml", SimpleNamespace(loads=lambda _s: {"project": {"version": "  2.0.0  "}})
    )
    v5, e5 = d._project_version_from_pyproject(tmp_path)
    assert v5 == "2.0.0"
    assert e5 is None


def test_check_release_meta_ok_summary_for_version(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## 1.2.3\n", encoding="utf-8")
    wf = tmp_path / ".github" / "workflows" / "release.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text("scripts/check_release_tag_version.py\n", encoding="utf-8")
    script = tmp_path / "scripts" / "check_release_tag_version.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("print('ok')\n", encoding="utf-8")

    ok, summary, evidence, fix, meta = d._check_release_meta(tmp_path)
    assert ok is True
    assert summary == "release metadata present for v1.2.3"
    assert evidence == []
    assert fix == []
    assert meta["version"] == "1.2.3"


def test_check_release_meta_collects_missing_components(tmp_path: Path) -> None:
    ok, summary, evidence, fix, meta = d._check_release_meta(tmp_path)
    assert ok is False
    assert summary == "release metadata missing or inconsistent"
    assert meta == {}

    types = {e["type"] for e in evidence}
    assert "pyproject_version" in types
    assert "missing_file" in types

    joined = "\n".join(fix)
    assert "Set [project].version" in joined
    assert "Add CHANGELOG.md" in joined
    assert "Add .github/workflows/release.yml" in joined
    assert "Add scripts/check_release_tag_version.py" in joined


def test_check_release_meta_workflow_missing_script_is_reported(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="9.9.9"\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## 9.9.9\n", encoding="utf-8")
    wf = tmp_path / ".github" / "workflows" / "release.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text("name: release\n", encoding="utf-8")
    script = tmp_path / "scripts" / "check_release_tag_version.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("print('ok')\n", encoding="utf-8")

    ok, summary, evidence, fix, meta = d._check_release_meta(tmp_path)
    assert ok is False
    assert summary == "release metadata missing or inconsistent"
    assert any(e["type"] == "workflow" for e in evidence)
    assert any("Update the release workflow" in x for x in fix)
    assert meta["version"] == "9.9.9"


def test_scan_non_ascii_collects_and_ignores_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    (src / "bad.py").write_bytes(b"print('x')\n\x80\n")
    (src / "err.py").write_text("x\n", encoding="utf-8")

    real_read_bytes = Path.read_bytes

    def read_bytes_maybe_fail(self: Path) -> bytes:
        if self.name == "err.py":
            raise OSError("boom")
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes_maybe_fail)

    bad_rel, bad_stderr = d._scan_non_ascii(tmp_path)
    assert bad_rel == ["src/bad.py"]
    assert bad_stderr == ["non-ascii: src/bad.py"]
