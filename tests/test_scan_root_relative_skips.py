from __future__ import annotations

from pathlib import Path

from sdetkit import boost, index
from sdetkit.gates import security_gate

# Each scanner skips directories such as build/ and site/ inside the repo. A repo that is itself
# checked out under a directory with one of those names must still be scanned.


def _repo_under(tmp_path: Path, parent: str) -> Path:
    root = tmp_path / parent / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        "import os\n\n\ndef run(cmd):\n    os.system(cmd)  # FIXME\n", encoding="utf-8"
    )
    (root / "build").mkdir()
    (root / "build" / "generated.py").write_text("import os\nos.system('x')\n", encoding="utf-8")
    return root


def test_security_scan_covers_a_repo_under_a_build_directory(tmp_path: Path) -> None:
    root = _repo_under(tmp_path, "build")
    paths = {finding.path for finding in security_gate.scan_repo(root)}
    assert "src/app.py" in paths
    assert "build/generated.py" not in paths


def test_security_fingerprints_do_not_depend_on_the_current_directory(
    tmp_path: Path, monkeypatch
) -> None:
    root = _repo_under(tmp_path, "work")
    monkeypatch.chdir(root)
    from_root = [f.fingerprint for f in security_gate.scan_repo(root)]
    monkeypatch.chdir(tmp_path)
    elsewhere = [f.fingerprint for f in security_gate.scan_repo(root)]
    assert from_root
    assert from_root == elsewhere


def test_boost_scan_files_cover_a_repo_under_a_site_directory(tmp_path: Path) -> None:
    root = _repo_under(tmp_path, "site")
    files = {p.relative_to(root).as_posix() for p in boost._limited_text_files(root, 100)}
    assert "src/app.py" in files


def test_index_files_cover_a_repo_under_a_venv_directory(tmp_path: Path) -> None:
    root = _repo_under(tmp_path, "venv")
    files = {p.relative_to(root).as_posix() for p in index._iter_files(root)}
    assert "src/app.py" in files
