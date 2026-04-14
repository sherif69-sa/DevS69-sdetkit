from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_generated_artifacts_freshness.py"
)
_SPEC = importlib.util.spec_from_file_location("check_generated_artifacts_freshness", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
freshness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(freshness)


def test_main_runs_generators_then_diff(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd: Path, check: bool):
        assert check is False
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(freshness.subprocess, "run", _fake_run)
    rc = freshness.main([])

    assert rc == 0
    assert calls[0][1:] == ["scripts/sync_feature_registry_docs.py", "--check"]
    assert calls[1][1:] == ["scripts/regenerate_real_repo_adoption_goldens.py", "--check"]
    assert calls[2] == [
        "git",
        "diff",
        "--exit-code",
        "--",
        "docs/feature-registry.md",
        "artifacts/adoption/real-repo-golden",
    ]


def test_main_stops_on_first_failure(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd: Path, check: bool):
        assert check is False
        calls.append(list(cmd))
        if len(calls) == 1:
            return SimpleNamespace(returncode=9)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(freshness.subprocess, "run", _fake_run)
    rc = freshness.main([])

    assert rc == 9
    assert len(calls) == 1
