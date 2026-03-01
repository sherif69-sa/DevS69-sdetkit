from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sdetkit import cli


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo-repo"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    src = root / "src" / "demo_repo"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("", encoding="utf-8")


def _run_audit(root: Path, fmt: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}.json", delete=False) as f:
        out = Path(f.name)
    try:
        rc = cli.main(
            [
                "repo",
                "audit",
                str(root),
                "--allow-absolute-path",
                "--format",
                fmt,
                "--output",
                str(out),
                "--force",
            ]
        )
        text = out.read_text(encoding="utf-8")
    finally:
        try:
            out.unlink()
        except FileNotFoundError:
            pass
    return rc, text


def test_repo_audit_json_output_is_deterministic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_repo(repo)

    rc1, t1 = _run_audit(repo, "json")
    rc2, t2 = _run_audit(repo, "json")

    assert rc1 in {0, 1}
    assert rc2 in {0, 1}
    json.loads(t1)
    json.loads(t2)
    assert t1 == t2


def test_repo_audit_sarif_output_is_deterministic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_repo(repo)

    rc1, t1 = _run_audit(repo, "sarif")
    rc2, t2 = _run_audit(repo, "sarif")

    assert rc1 in {0, 1}
    assert rc2 in {0, 1}

    d1 = json.loads(t1)
    d2 = json.loads(t2)

    assert isinstance(d1, dict) and isinstance(d2, dict)
    assert d1.get("version") == "2.1.0"
    assert d2.get("version") == "2.1.0"
    assert t1 == t2
