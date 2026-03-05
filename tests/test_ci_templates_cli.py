from __future__ import annotations

import json
from pathlib import Path

from sdetkit import ci


def _write_templates(root: Path) -> None:
    for template_id, spec in ci._TEMPLATE_SPECS.items():
        path = root / str(spec["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(str(marker) for marker in spec["markers"])
        path.write_text(f"# {template_id}\n{content}\n", encoding="utf-8")


def test_ci_validate_templates_json_strict_pass(tmp_path: Path, capsys) -> None:
    _write_templates(tmp_path)

    rc = ci.main(["validate-templates", "--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["missing"] == []
    assert [item["id"] for item in payload["checked"]] == sorted(ci._TEMPLATE_SPECS)


def test_ci_validate_templates_missing_markers_respects_strict_flag(tmp_path: Path, capsys) -> None:
    _write_templates(tmp_path)
    gitlab = tmp_path / ci._TEMPLATE_SPECS["gitlab"]["path"]
    gitlab.write_text("# gitlab template without required markers\n", encoding="utf-8")

    rc_non_strict = ci.main(["validate-templates", "--root", str(tmp_path)])
    io_non_strict = capsys.readouterr()
    assert rc_non_strict == 0
    assert "ci template validation: FAIL" in io_non_strict.out

    rc_strict = ci.main(
        ["validate-templates", "--root", str(tmp_path), "--strict", "--format", "json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc_strict == 2
    assert payload["ok"] is False
    bad = next(item for item in payload["checked"] if item["id"] == "gitlab")
    assert bad["ok"] is False
    assert bad["errors"]


def test_ci_validate_templates_writes_out_file(tmp_path: Path, capsys) -> None:
    _write_templates(tmp_path)
    out = tmp_path / "build" / "ci-validate.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    rc = ci.main(
        [
            "validate-templates",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )
    assert rc == 0

    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload


def test_ci_validate_templates_missing_file_recorded(tmp_path: Path, capsys) -> None:
    _write_templates(tmp_path)
    missing_template = tmp_path / str(ci._TEMPLATE_SPECS["tekton"]["path"])
    missing_template.unlink()

    rc = ci.main(["validate-templates", "--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["missing"] == [str(ci._TEMPLATE_SPECS["tekton"]["path"])]
    tekton = next(item for item in payload["checked"] if item["id"] == "tekton")
    assert tekton["ok"] is False
    assert tekton["errors"] == [f"missing file: {ci._TEMPLATE_SPECS['tekton']['path']}"]
