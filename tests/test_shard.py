from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli, dependency_map


def test_estimate_test_duration(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "def test_one():\n    pass\n\ndef test_two():\n    pass\n",
        encoding="utf-8",
    )
    duration = dependency_map._estimate_test_duration(test_file)
    assert duration > 0.0
    assert duration >= 0.5


def test_compute_ast_closure_hash(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    mod_a = src_dir / "mod_a.py"
    mod_a.write_text("def helper(): return 42\n", encoding="utf-8")

    test_file = tests_dir / "test_a.py"
    test_file.write_text(
        "import mod_a\ndef test_a(): assert mod_a.helper() == 42\n", encoding="utf-8"
    )

    file_graph: dict[str, set[str]] = {
        "tests/test_a.py": {"src/mod_a.py"},
        "src/mod_a.py": set(),
    }
    file_hashes: dict[str, str] = {
        "tests/test_a.py": dependency_map.sha256_file(test_file),
        "src/mod_a.py": dependency_map.sha256_file(mod_a),
    }

    hash1 = dependency_map.compute_ast_closure_hash(
        "tests/test_a.py",
        tmp_path,
        file_graph,
        file_hashes,
    )
    assert isinstance(hash1, str)
    assert len(hash1) == 64

    # Modifying mod_a changes the closure hash
    mod_a.write_text("def helper(): return 99\n", encoding="utf-8")
    file_hashes["src/mod_a.py"] = dependency_map.sha256_file(mod_a)

    hash2 = dependency_map.compute_ast_closure_hash(
        "tests/test_a.py",
        tmp_path,
        file_graph,
        file_hashes,
    )
    assert hash2 != hash1


def test_shard_test_suite_partitioning_balance(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    created_tests: list[str] = []
    for i in range(10):
        tpath = tests_dir / f"test_{i:02d}.py"
        content = "\n".join(f"def test_{j}(): pass" for j in range(i + 1)) + "\n"
        tpath.write_text(content, encoding="utf-8")
        created_tests.append(f"tests/test_{i:02d}.py")

    report = dependency_map.shard_test_suite(
        tmp_path,
        nodes=3,
        test_files=created_tests,
    )

    assert report["schema_version"] == "sdetkit.shard.v1"
    assert report["nodes"] == 3
    assert report["total_tests_discovered"] == 10
    assert report["balance_efficiency_pct"] >= 75.0

    shards = report["shards"]
    assert len(shards) == 3

    assigned: list[str] = []
    for s in shards:
        for f in s["files"]:
            assigned.append(f)
    assert sorted(assigned) == sorted(created_tests)


def test_shard_test_suite_selected_shard_index(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    t1 = tests_dir / "test_1.py"
    t1.write_text("def test_one(): pass\n", encoding="utf-8")
    t2 = tests_dir / "test_2.py"
    t2.write_text("def test_two(): pass\n", encoding="utf-8")

    report = dependency_map.shard_test_suite(
        tmp_path,
        nodes=2,
        index=1,
    )

    assert report["nodes"] == 2
    assert "selected_shard" in report
    selected = report["selected_shard"]
    assert selected["index"] == 1
    assert "pytest_args" in selected
    assert selected["file_count"] >= 1


def test_shard_test_suite_caching_hit_and_miss(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    t1 = tests_dir / "test_cache_target.py"
    t1.write_text("def test_cached(): pass\n", encoding="utf-8")

    manifest_path = tmp_path / ".sdetkit_cache.json"

    # 1. First run: miss
    rep1 = dependency_map.shard_test_suite(
        tmp_path,
        nodes=2,
        use_cache=True,
        cache_path=manifest_path,
    )
    assert rep1["cached_tests_skipped"] == 0
    assert rep1["active_tests_distributed"] == 1

    # Save manifest
    manifest_data = {
        "schema_version": "sdetkit.test_cache.v1",
        "hashes": rep1["current_closure_hashes"],
    }
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    # 2. Second run: hit
    rep2 = dependency_map.shard_test_suite(
        tmp_path,
        nodes=2,
        use_cache=True,
        cache_path=manifest_path,
    )
    assert rep2["cached_tests_skipped"] == 1
    assert rep2["active_tests_distributed"] == 0

    # 3. Third run: invalidate by modifying test
    t1.write_text("def test_modified(): pass\n", encoding="utf-8")
    rep3 = dependency_map.shard_test_suite(
        tmp_path,
        nodes=2,
        use_cache=True,
        cache_path=manifest_path,
    )
    assert rep3["cached_tests_skipped"] == 0
    assert rep3["active_tests_distributed"] == 1


def test_render_shard_markdown(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")

    report = dependency_map.shard_test_suite(tmp_path, nodes=2, index=0)
    md = dependency_map.render_shard_markdown(report)

    assert "SDETKit Duration-Weighted Test Sharding" in md
    assert "Balance Efficiency" in md
    assert "Shard Partition Matrix" in md
    assert "pytest" in md


def test_shard_cli_main_formats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_alpha.py").write_text("def test_alpha(): pass\n", encoding="utf-8")

    # Format JSON
    rc = dependency_map.shard_main(["--root", str(tmp_path), "--nodes", "2", "--format", "json"])
    assert rc == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["schema_version"] == "sdetkit.shard.v1"
    assert data["nodes"] == 2

    # Format MD
    rc = dependency_map.shard_main(["--root", str(tmp_path), "--nodes", "2", "--format", "md"])
    assert rc == 0
    out_md = capsys.readouterr().out
    assert "SDETKit Duration-Weighted Test Sharding" in out_md

    # Format args with index
    rc = dependency_map.shard_main(
        ["--root", str(tmp_path), "--nodes", "2", "--index", "0", "--format", "args"]
    )
    assert rc == 0
    out_args = capsys.readouterr().out
    assert "tests/test_alpha.py" in out_args

    # Out to file
    out_file = tmp_path / "shards.json"
    rc = dependency_map.shard_main(
        ["--root", str(tmp_path), "--nodes", "2", "--out", str(out_file), "--format", "json"]
    )
    assert rc == 0
    assert out_file.exists()


def test_cli_dispatch_shard(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        calls.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    rc = cli.main(["shard", "--nodes", "3", "--index", "1"])
    assert rc == 0
    assert calls == [("sdetkit.dependency_map", ["shard", "--nodes", "3", "--index", "1"])]

    calls.clear()
    rc_verify = cli.main(["verify", "shard", "--nodes", "4"])
    assert rc_verify == 0
    assert calls == [("sdetkit.dependency_map", ["--nodes", "4"])]
