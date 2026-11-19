from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.lockfiles import (
    PROVENANCE_SCHEMA_VERSION,
    _from_go_sum,
    _from_package_lock_json,
    _scan_unpinned_dependencies,
    audit_provenance,
    classify_license,
    provenance_main,
    render_provenance_markdown,
)


def test_classify_license() -> None:
    assert classify_license("requests", "") == "PERMISSIVE"
    assert classify_license("pytest", "") == "PERMISSIVE"
    assert classify_license("unknown-pkg", "MIT") == "PERMISSIVE"
    assert classify_license("unknown-pkg", "Apache-2.0") == "PERMISSIVE"
    assert classify_license("unknown-pkg", "GPL-3.0") == "COPYLEFT_RESTRICTED"
    assert classify_license("unknown-pkg", "AGPL-3.0-only") == "COPYLEFT_RESTRICTED"
    assert classify_license("unknown-pkg", "LGPL-2.1") == "COPYLEFT_RESTRICTED"
    assert classify_license("unknown-pkg", "Proprietary-Custom") == "UNKNOWN"


def test_scan_unpinned_dependencies(tmp_path: Path) -> None:
    assert _scan_unpinned_dependencies(tmp_path) == []

    req = tmp_path / "requirements.txt"
    req.write_text(
        "# Comment\npytest==8.0.0\nrequests>=2.0.0\nclick\n-r other.txt\n",
        encoding="utf-8",
    )
    unpinned = _scan_unpinned_dependencies(tmp_path)
    packages = [u["package"] for u in unpinned]
    assert "requests" in packages
    assert "click" in packages
    assert "pytest" not in packages


def test_from_package_lock_json(tmp_path: Path) -> None:
    non_existent = tmp_path / "non_existent.json"
    assert _from_package_lock_json(non_existent) == []

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    assert _from_package_lock_json(bad_json) == []

    pkg_lock = tmp_path / "package-lock.json"
    content = {
        "packages": {
            "node_modules/lodash": {"name": "lodash", "version": "4.17.21"},
            "node_modules/bad-lib": {"version": "1.0.0", "license": "GPL-3.0"},
            "": {"name": "root-app", "version": "1.0.0"},
        }
    }
    pkg_lock.write_text(json.dumps(content), encoding="utf-8")
    pkgs = _from_package_lock_json(pkg_lock)
    names = [p["name"] for p in pkgs]
    assert "lodash" in names
    assert "bad-lib" in names


def test_from_go_sum(tmp_path: Path) -> None:
    non_existent = tmp_path / "go.sum"
    assert _from_go_sum(non_existent) == []

    go_sum = tmp_path / "go.sum"
    go_sum.write_text(
        "github.com/gin-gonic/gin v1.9.1 h1:xyz=\n"
        "github.com/gin-gonic/gin v1.9.1/go.mod h1:abc=\n"
        "golang.org/x/sync v0.6.0 h1:def=\n",
        encoding="utf-8",
    )
    pkgs = _from_go_sum(go_sum)
    names = [p["name"] for p in pkgs]
    assert "github.com/gin-gonic/gin" in names
    assert "golang.org/x/sync" in names
    assert len(pkgs) == 2


def test_audit_provenance_clean(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "pytest==8.0.0\nrequests==2.31.0\n",
        encoding="utf-8",
    )
    report = audit_provenance(tmp_path)
    assert report["schema_version"] == PROVENANCE_SCHEMA_VERSION
    assert report["verdict"] == "PASS"
    assert report["total_packages"] == 2
    assert report["unpinned_count"] == 0
    assert report["license_summary"]["copyleft_restricted"] == 0
    assert len(report["violations"]) == 0
    assert len(report["dependency_tree_digest"]) == 64


def test_audit_provenance_copyleft_violation(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "pytest==8.0.0\n",
        encoding="utf-8",
    )
    pkg_lock = tmp_path / "package-lock.json"
    content = {
        "packages": {
            "node_modules/copyleft-pkg": {"version": "1.0.0", "license": "GPL-3.0"},
        }
    }
    pkg_lock.write_text(json.dumps(content), encoding="utf-8")

    strict_report = audit_provenance(tmp_path, policy="permissive")
    assert strict_report["verdict"] == "FAIL"
    lic_violations = [v for v in strict_report["violations"] if v.get("category") == "LICENSE_RISK"]
    assert len(lic_violations) == 1

    permissive_policy_report = audit_provenance(tmp_path, policy="allow-copyleft")
    assert permissive_policy_report["verdict"] == "PASS"


def test_audit_provenance_unpinned_and_typosquatting(tmp_path: Path) -> None:
    # Typosquatting triggers HIGH severity -> FAIL
    (tmp_path / "requirements.txt").write_text(
        "reqeusts==2.31.0\nclick>=8.0\n",
        encoding="utf-8",
    )
    report = audit_provenance(tmp_path, allow_unpinned=False)
    assert report["verdict"] == "FAIL"
    cats = {v["category"] for v in report["violations"]}
    assert "SUSPICIOUS_NAME" in cats
    assert "UNPINNED" in cats

    # Only unpinned triggers MEDIUM severity -> WARNING
    clean_dir = tmp_path / "clean_sub"
    clean_dir.mkdir()
    (clean_dir / "requirements.txt").write_text("pytest==8.0.0\nclick>=8.0\n", encoding="utf-8")
    warn_report = audit_provenance(clean_dir, allow_unpinned=False)
    assert warn_report["verdict"] == "WARNING"

    allowed_report = audit_provenance(clean_dir, allow_unpinned=True)
    assert allowed_report["verdict"] == "PASS"
    allowed_cats = {v["category"] for v in allowed_report["violations"]}
    assert "UNPINNED" not in allowed_cats


def test_render_provenance_markdown(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("pytest==8.0.0\n", encoding="utf-8")
    report = audit_provenance(tmp_path)
    md = render_provenance_markdown(report)
    assert "# SDETKit Supply-Chain & License Provenance Radar" in md
    assert "Total Dependency Pins" in md


def test_provenance_main_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "requirements.txt").write_text("pytest==8.0.0\n", encoding="utf-8")
    json_out = tmp_path / "out.json"
    summary_out = tmp_path / "summary.md"

    rc = provenance_main(
        [
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(summary_out),
        ]
    )
    assert rc == 0
    assert json_out.is_file()
    assert summary_out.is_file()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["verdict"] == "PASS"


def test_provenance_main_cli_fail(tmp_path: Path) -> None:
    pkg_lock = tmp_path / "package-lock.json"
    content = {
        "packages": {
            "node_modules/gpl-pkg": {"version": "1.0.0", "license": "GPL-3.0"},
        }
    }
    pkg_lock.write_text(json.dumps(content), encoding="utf-8")

    rc = provenance_main([str(tmp_path), "--policy", "permissive", "--format", "md"])
    assert rc == 1
