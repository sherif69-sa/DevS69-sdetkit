import json

from sdetkit import cli, sdet_package


def test_sdet_package_default_text(capsys):
    rc = sdet_package.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "SDET super package report" in out
    assert "Kits:" in out


def test_sdet_package_json_strict_success(capsys):
    rc = sdet_package.main(["--write-defaults", "--format", "json", "--strict"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "sdet-super-package"
    assert data["passed_checks"] == data["total_checks"]
    assert len(data["kits"]) == 3


def test_sdet_package_strict_fails_when_missing(tmp_path, capsys):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/sdet-super-package.md").write_text("# Placeholder\n", encoding="utf-8")
    rc = sdet_package.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Coverage gaps:" in out


def test_sdet_package_emit_pack(tmp_path, capsys):
    rc = sdet_package.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--emit-pack-dir",
            "docs/artifacts/sdet-super-package",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["pack_files"]) == 4
    assert "docs/artifacts/sdet-super-package/reliability-gate-kit.json" in data["pack_files"]


def test_main_cli_dispatches_sdet_package(capsys):
    rc = cli.main(["sdet-package", "--write-defaults", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "SDET super package report" in out
