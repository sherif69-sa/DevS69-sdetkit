"""The external repository proof page is exactly what its recorded results say."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "external_repo_proof", ROOT / "scripts/external_repo_proof.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_page_is_rendered_from_the_recorded_results() -> None:
    assert _script().main(["render", "--check"]) == 0


def test_results_cover_exactly_the_pinned_repositories_and_their_notes() -> None:
    script = _script()
    data = json.loads(script.RESULTS.read_text(encoding="utf-8"))

    assert data["schema_version"] == script.SCHEMA_VERSION
    assert re.fullmatch(r"[0-9a-f]{40}", data["sdetkit_commit"])
    recorded = [(r["name"], r["commit"], r["notes"]) for r in data["repositories"]]
    pinned = [
        (spec["name"], spec["commit"], [{"kind": k, "text": t} for k, t in spec["notes"]])
        for spec in script.REPOS
    ]
    assert recorded == pinned
    for spec in script.REPOS:
        assert re.fullmatch(r"[0-9a-f]{40}", spec["commit"]), spec["name"]
        assert {kind for kind, _ in spec["notes"]} <= {script.GAP, script.TRUE, script.ENVIRONMENT}


def test_every_recorded_stage_has_a_verdict() -> None:
    data = json.loads(_script().RESULTS.read_text(encoding="utf-8"))

    for repo in data["repositories"]:
        for stage in ("fresh_clone", "after_setup"):
            result = repo[stage]
            assert result["decision"] in {"SHIP", "REVIEW", "NOT_RUN", "NO_SHIP"}
            assert (result["rc"] == 0) == (not result["failed_steps"]), (repo["name"], stage)
