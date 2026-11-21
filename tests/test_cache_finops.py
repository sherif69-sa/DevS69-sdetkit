"""Tests for Frontier 19: Cryptographic AST Result Cache and FinOps CI Savings Ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cockpit, dependency_map, safety_gate


def test_find_associated_fixtures_and_hashing(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    test_file = tests_dir / "test_billing.py"
    test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")

    # Add direct adjacent fixtures
    sql_fixture = tests_dir / "test_billing_schema.sql"
    sql_fixture.write_text("CREATE TABLE billing (id INT);\n", encoding="utf-8")

    json_fixture = tests_dir / "test_billing_data.json"
    json_fixture.write_text('{"account": 123}\n', encoding="utf-8")

    # Add fixture directory
    fix_sub = tests_dir / "fixtures"
    fix_sub.mkdir()
    yaml_fixture = fix_sub / "rates.yaml"
    yaml_fixture.write_text("usd_rate: 1.0\n", encoding="utf-8")

    discovered = dependency_map.find_associated_fixtures("tests/test_billing.py", tmp_path)
    assert "tests/test_billing_schema.sql" in discovered
    assert "tests/test_billing_data.json" in discovered
    assert "tests/fixtures/rates.yaml" in discovered

    file_hashes: dict[str, str] = {}
    h1 = dependency_map.compute_fixtures_hash("tests/test_billing.py", tmp_path, file_hashes)
    assert len(h1) == 64

    # Modifying fixture changes hash
    sql_fixture.write_text("CREATE TABLE billing (id INT, amount NUMERIC);\n", encoding="utf-8")
    file_hashes.clear()
    h2 = dependency_map.compute_fixtures_hash("tests/test_billing.py", tmp_path, file_hashes)
    assert h1 != h2


def test_inspect_test_cache_smells_detection(tmp_path: Path) -> None:
    # 1. Clean test
    clean_path = tmp_path / "test_clean.py"
    clean_path.write_text(
        "def test_pure():\n    x = 1 + 2\n    assert x == 3\n",
        encoding="utf-8",
    )
    has_smell, smells = dependency_map.inspect_test_cache_smells(clean_path)
    assert not has_smell
    assert len(smells) == 0

    # 2. os.environ pollution smell
    env_path = tmp_path / "test_env.py"
    env_path.write_text(
        "import os\n"
        "def test_pollute():\n"
        "    os.environ['API_KEY'] = 'secret'\n"
        "    assert os.getenv('API_KEY') == 'secret'\n",
        encoding="utf-8",
    )
    has_smell, smells = dependency_map.inspect_test_cache_smells(env_path)
    assert has_smell
    assert any("ENV_POLLUTION" in s for s in smells)

    # 3. Arbitrary sleep smell
    sleep_path = tmp_path / "test_sleep.py"
    sleep_path.write_text(
        "import time\ndef test_sleepy():\n    time.sleep(2)\n    assert True\n",
        encoding="utf-8",
    )
    has_smell, smells = dependency_map.inspect_test_cache_smells(sleep_path)
    assert has_smell
    assert any("CLOCK_SMELL" in s for s in smells)

    # 4. Direct socket network smell
    net_path = tmp_path / "test_net.py"
    net_path.write_text(
        "import socket\n"
        "def test_socket_call():\n"
        "    s = socket.socket()\n"
        "    assert s is not None\n",
        encoding="utf-8",
    )
    has_smell, smells = dependency_map.inspect_test_cache_smells(net_path)
    assert has_smell
    assert any("NETWORK_SMELL" in s for s in smells)

    # 5. Direct filesystem write smell
    fs_path = tmp_path / "test_fs.py"
    fs_path.write_text(
        "from pathlib import Path\ndef test_write():\n    Path('out.txt').write_text('data')\n",
        encoding="utf-8",
    )
    has_smell, smells = dependency_map.inspect_test_cache_smells(fs_path)
    assert has_smell
    assert any("FS_WRITE" in s for s in smells)


def test_compute_test_cache_receipt_schema(tmp_path: Path) -> None:
    test_file = tmp_path / "test_example.py"
    test_file.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")

    receipt = dependency_map.compute_test_cache_receipt(
        "test_example.py",
        tmp_path,
        file_dep_graph={},
        file_hashes={},
    )
    assert receipt["schema_version"] == "1.0"
    assert receipt["node_id"] == "test_example.py"
    assert receipt["cacheable"] is True
    assert len(receipt["cache_key"]) == 64
    assert receipt["bypass_reasons"] == []
    assert len(receipt["ast_subtree_sha256"]) == 64


def test_shard_test_suite_with_cache_and_smell_bypass(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    clean_test = tests_dir / "test_pure.py"
    clean_test.write_text("def test_one(): assert 1 == 1\n", encoding="utf-8")

    smell_test = tests_dir / "test_polluting.py"
    smell_test.write_text(
        "import os\ndef test_two():\n    os.environ['TEST_VAR'] = 'val'\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / ".sdetkit" / "test_cache.json"

    # Run 1: initial run without prior cache
    rep1 = dependency_map.shard_test_suite(
        tmp_path,
        nodes=2,
        use_cache=True,
        cache_path=manifest_path,
    )
    assert rep1["total_tests_discovered"] == 2
    assert rep1["cached_tests_skipped"] == 0
    assert rep1["smell_bypassed_tests_count"] == 1
    assert "tests/test_polluting.py" in rep1["smell_bypassed_tests"]

    # Save cache
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": dependency_map.CACHE_SCHEMA_VERSION,
                "hashes": rep1["current_closure_hashes"],
                "receipts": rep1["cache_receipts"],
            }
        ),
        encoding="utf-8",
    )

    # Run 2: clean test should hit cache; smell test is bypassed and distributed
    rep2 = dependency_map.shard_test_suite(
        tmp_path,
        nodes=2,
        use_cache=True,
        cache_path=manifest_path,
    )
    assert rep2["cached_tests_skipped"] == 1
    assert "tests/test_pure.py" in rep2["cached_test_files"]
    assert rep2["smell_bypassed_tests_count"] == 1
    assert rep2["avoided_duration_sec"] > 0.0


def test_finops_report_calculations_and_markdown(tmp_path: Path) -> None:
    ledger_path = tmp_path / ".sdetkit" / "finops_ledger.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    entries = [
        {"timestamp": 1000.0, "avoided_compute_seconds": 120.0, "cached_tests_count": 5},
        {"timestamp": 2000.0, "avoided_compute_seconds": 180.0, "cached_tests_count": 8},
    ]
    with ledger_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    report = cockpit.compute_finops_report(
        tmp_path,
        days=0,
        ci_runner_cost_per_minute=0.008,
        engineer_hourly_rate=75.0,
        ledger_path=ledger_path,
    )
    assert report["schema_version"] == "sdetkit.finops.v1"
    assert report["avoided_compute_seconds"] == 300.0
    assert report["avoided_compute_minutes"] == 5.0
    # 5.0 min * $0.008 = $0.04
    assert report["ci_spend_saved_usd"] == 0.04
    # 300 / 3600 = 0.0833 hrs * $75 = $6.25
    assert report["developer_hours_saved"] == 0.083
    assert report["developer_productivity_saved_usd"] == 6.23
    assert report["total_finops_roi_usd"] == 6.27

    md = cockpit.render_finops_markdown(report)
    assert "SDETKit CI Compute & FinOps Savings Ledger" in md
    assert "$6.27" in md
    assert all(ord(c) < 128 for c in md)

    txt = cockpit.render_finops_text(report)
    assert "SDETKit FinOps Ledger" in txt
    assert "$6.27" in txt
    assert all(ord(c) < 128 for c in txt)


def test_finops_policy_rates_parsing(tmp_path: Path) -> None:
    policy_file = tmp_path / ".sdetkit-policy.toml"
    policy_file.write_text(
        "[finops]\nci_runner_cost_per_minute_usd = 0.016\nengineer_hourly_rate_usd = 120.0\n",
        encoding="utf-8",
    )

    ci_rate, dev_rate = cockpit.load_finops_rates_from_policy(tmp_path)
    assert ci_rate == 0.016
    assert dev_rate == 120.0


def test_trend_cli_with_finops(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cockpit.trend_main(["--repo-root", str(tmp_path), "--finops", "--format", "json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "sdetkit.finops.v1"
    assert "total_finops_roi_usd" in payload


def test_ship_cli_with_cache(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = safety_gate.ship_main(["--repo-root", str(tmp_path), "--cache", "--format", "json"])
    captured = capsys.readouterr()
    assert rc in (0, 1)
    payload = json.loads(captured.out)
    assert "ast_cache" in payload
    assert payload["ast_cache"]["enabled"] is True
