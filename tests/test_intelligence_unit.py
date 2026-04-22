from __future__ import annotations

import json
from pathlib import Path

from sdetkit import intelligence


def test_intelligence_command_helpers(tmp_path: Path, monkeypatch) -> None:
    module = intelligence._load_legacy_intelligence_module()
    history = tmp_path / "history.json"
    history.write_text(
        json.dumps(
            {
                "tests": [
                    {"id": "t.flaky", "outcomes": ["failed", "passed", "failed"]},
                    {"id": "t.fail", "outcomes": ["failed", "failed"]},
                    {"id": "t.pass", "outcomes": ["passed", "passed"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    flake = module._cmd_flake_classify(history, rerun_threshold=2)
    assert flake["summary"]["flaky"] == 1
    assert flake["summary"]["stable_failing"] == 1
    assert flake["summary"]["stable_passing"] == 1

    monkeypatch.setenv("SDETKIT_SEED", "99")
    env_payload = module._cmd_capture_env(seed=None)
    assert env_payload["seed"] == 99
    assert "derived_seed" in env_payload

    changed = tmp_path / "changed.txt"
    changed.write_text("a.py\n# ignore\nb.py\n", encoding="utf-8")
    test_map = tmp_path / "map.json"
    test_map.write_text(json.dumps({"a.py": ["ta"], "b.py": ["tb", "tc"]}), encoding="utf-8")
    impact = module._cmd_impact(changed, test_map)
    assert impact["impacted_tests"] == ["ta", "tb", "tc"]

    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {"minimum_score": 60, "observed_score": 62, "owners": ["qa"], "justification": "ok"}
        ),
        encoding="utf-8",
    )
    mut = module._cmd_mutation_policy(policy)
    assert mut["passed"] is True

    failures = tmp_path / "failures.json"
    failures.write_text(
        json.dumps(
            {
                "failures": [
                    {
                        "test_id": "t.network",
                        "message": "Connection reset after timeout",
                        "fixture_scope": "session",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    fp = module._cmd_failure_fingerprint(failures)
    assert fp["summary"]["with_nondeterminism_hints"] == 1


def test_intelligence_main_routes_and_errors(tmp_path: Path, monkeypatch, capsys) -> None:
    module = intelligence._load_legacy_intelligence_module()
    history = tmp_path / "history.json"
    history.write_text(
        json.dumps({"tests": [{"id": "t", "outcomes": ["passed"]}]}), encoding="utf-8"
    )
    rc = module.main(["flake", "classify", "--history", str(history)])
    assert rc == 0
    assert "schema_version" in capsys.readouterr().out

    rc = module.main(["capture-env", "--seed", "7"])
    assert rc == 0
    capsys.readouterr()

    changed = tmp_path / "changed.txt"
    changed.write_text("a.py\n", encoding="utf-8")
    test_map = tmp_path / "map.json"
    test_map.write_text(json.dumps({"a.py": ["ta"]}), encoding="utf-8")
    rc = module.main(["impact", "summarize", "--changed", str(changed), "--map", str(test_map)])
    assert rc == 0
    capsys.readouterr()

    failures = tmp_path / "failures.json"
    failures.write_text(json.dumps({"failures": []}), encoding="utf-8")
    rc = module.main(["failure-fingerprint", "--failures", str(failures)])
    assert rc == 0
    capsys.readouterr()

    mut_policy = tmp_path / "mut.json"
    mut_policy.write_text(json.dumps({"minimum_score": 99, "observed_score": 1}), encoding="utf-8")
    rc = module.main(["mutation-policy", "--policy", str(mut_policy)])
    assert rc == 1
    capsys.readouterr()

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    monkeypatch.setattr(
        module.upgrade_audit,
        "_discover_requirement_files",
        lambda _root, include_lockfiles=False: [],
    )
    monkeypatch.setattr(module.upgrade_audit, "run", lambda *_a, **_k: 0)
    rc = module.main(["upgrade-audit", "--pyproject", str(pyproject)])
    assert rc == 0

    bad_history = tmp_path / "bad-history.json"
    bad_history.write_text(json.dumps({"tests": "not-list"}), encoding="utf-8")
    rc = module.main(["flake", "classify", "--history", str(bad_history)])
    assert rc == 2
    assert "intelligence error:" in capsys.readouterr().err
