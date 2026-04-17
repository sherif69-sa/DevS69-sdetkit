import json
from types import SimpleNamespace

from sdetkit import test_bootstrap_contract as contract


def test_extract_requirement_name_normalizes():
    assert contract.extract_requirement_name("PyYAML==6.0.3") == "pyyaml"
    assert contract.extract_requirement_name("pytest-xdist[psutil]==3.8.0") == "pytest-xdist"
    assert contract.extract_requirement_name(" # comment ") == ""


def test_build_report_flags_missing(tmp_path):
    (tmp_path / "requirements-test.txt").write_text("pytest==9.0.3\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\n[project.optional-dependencies]\ntest=['pytest']\n",
        encoding="utf-8",
    )

    report = contract.build_report(tmp_path)

    assert report["ok"] is False
    assert "pyyaml" in report["missing_from_requirements_test"]
    assert "httpx" in report["missing_from_pyproject_test_visible_deps"]


def test_main_json_success(monkeypatch, capsys):
    monkeypatch.setattr(
        contract,
        "parse_args",
        lambda: SimpleNamespace(format="json", strict=True, out=""),
    )
    monkeypatch.setattr(
        contract,
        "build_report",
        lambda repo_root: {
            "ok": True,
            "expected_packages": ["httpx", "hypothesis", "pyyaml"],
            "missing_from_requirements_test": [],
            "missing_from_pyproject_test_visible_deps": [],
            "paths": {"requirements_test": "requirements-test.txt", "pyproject": "pyproject.toml"},
        },
    )

    rc = contract.main()
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True


def test_main_writes_output_file(monkeypatch, tmp_path):
    out_file = tmp_path / "contract.json"
    monkeypatch.setattr(
        contract,
        "parse_args",
        lambda: SimpleNamespace(format="json", strict=True, out=str(out_file)),
    )
    monkeypatch.setattr(
        contract,
        "build_report",
        lambda repo_root: {
            "ok": True,
            "expected_packages": ["httpx", "hypothesis", "pyyaml"],
            "missing_from_requirements_test": [],
            "missing_from_pyproject_test_visible_deps": [],
            "paths": {"requirements_test": "requirements-test.txt", "pyproject": "pyproject.toml"},
        },
    )

    rc = contract.main()

    assert rc == 0
    assert out_file.exists()
    assert json.loads(out_file.read_text(encoding="utf-8"))["ok"] is True
