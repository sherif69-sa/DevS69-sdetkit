from __future__ import annotations

import json
from pathlib import Path

from sdetkit.ci_failure_triage import (
    CLUSTER_SCHEMA_VERSION,
    _collect_cluster_inputs,
    cluster_failures,
    cluster_main,
    compute_signature_similarity,
    normalize_failure,
    render_cluster_markdown,
)
from sdetkit.cli import main as cli_main


def test_normalize_failure_strips_noise() -> None:
    raw = (
        "FAILED tests/test_db.py::test_pool_connect - "
        "TimeoutError: Connection failed at 0x7ffd9a1b2c to 127.0.0.1:5432 "
        "trace id 12345678-1234-5678-1234-567812345678 at 2026-11-20T12:00:00Z line 142"
    )
    sig = normalize_failure(raw)
    assert sig.test_node == "tests/test_db.py::test_pool_connect"
    assert sig.exception_type == "TimeoutError"
    assert "<HEX>" in sig.normalized_message or "<HOST:PORT>" in sig.normalized_message
    assert "0x7ffd9a1b2c" not in sig.normalized_message
    assert "12345678-1234-5678-1234-567812345678" not in sig.normalized_message
    assert "line 142" not in sig.normalized_message


def test_compute_signature_similarity_same_and_different() -> None:
    sig1 = normalize_failure(
        {
            "node": "tests/test_a.py::test_1",
            "error": "ConnectionRefusedError: dial tcp 127.0.0.1:8080 timeout connecting to upstream",
        }
    )
    sig2 = normalize_failure(
        {
            "node": "tests/test_b.py::test_2",
            "error": "ConnectionRefusedError: dial tcp 127.0.0.1:8080 timeout connecting to worker",
        }
    )
    sig3 = normalize_failure(
        {
            "node": "tests/test_c.py::test_3",
            "error": "AssertionError: expected True but got False",
        }
    )

    sim_high = compute_signature_similarity(sig1, sig2)
    sim_low = compute_signature_similarity(sig1, sig3)

    assert sim_high >= 0.65
    assert sim_low < 0.45


def test_cluster_failures_groups_correlated_and_isolates_unrelated() -> None:
    failures = [
        {
            "node": "tests/test_api.py::test_login",
            "error": "ConnectionRefusedError: failed to reach auth service at 0x1a2b",
        },
        {
            "node": "tests/test_api.py::test_token_refresh",
            "error": "ConnectionRefusedError: failed to reach auth service at 0x3c4d",
        },
        {
            "node": "tests/test_calc.py::test_add",
            "error": "AssertionError: assert 4 + 4 == 9",
        },
    ]

    report = cluster_failures(failures, min_similarity=0.6)
    assert report["schema_version"] == CLUSTER_SCHEMA_VERSION
    assert report["total_failures"] == 3
    assert report["cluster_count"] == 2

    # Verify cluster 1 has 2 tests and cluster 2 has 1 test
    clusters_by_size = sorted(report["clusters"], key=lambda c: c["size"], reverse=True)
    c_large = clusters_by_size[0]
    c_small = clusters_by_size[1]

    assert c_large["size"] == 2
    assert c_large["primary_exception"] == "ConnectionRefusedError"
    assert c_small["size"] == 1
    assert c_small["primary_exception"] == "AssertionError"


def test_render_cluster_markdown() -> None:
    failures = [
        {
            "node": "tests/test_worker.py::test_deadlock",
            "error": "TimeoutError: asyncio future timed out waiting for lock in thread pool",
        },
        {
            "node": "tests/test_worker.py::test_queue_sync",
            "error": "TimeoutError: asyncio future timed out waiting for lock in worker sync",
        },
    ]
    report = cluster_failures(failures, min_similarity=0.6)
    md = render_cluster_markdown(report)

    assert "# Failure Signature & Root-Cause Clustering Report" in md
    assert "Root-Cause Clusters Overview" in md
    assert "Root-Cause Dependency Graph" in md
    assert "```mermaid" in md
    assert "CONCURRENCY_RACE" in md
    assert "Prioritized Remediation Guidance" in md


def test_collect_cluster_inputs_from_file_and_dir(tmp_path: Path) -> None:
    # JSON input
    json_file = tmp_path / "failures.json"
    json_file.write_text(
        json.dumps([{"node": "tests/test_1.py::test_a", "error": "ValueError: bad input"}]),
        encoding="utf-8",
    )
    items = _collect_cluster_inputs(tmp_path, json_file)
    assert len(items) == 1

    # Text log input
    log_file = tmp_path / "ci.log"
    log_file.write_text(
        "FAILED tests/test_2.py::test_b - KeyError: 'user_id'\n"
        "FAILED tests/test_3.py::test_c - KeyError: 'user_id'\n",
        encoding="utf-8",
    )
    log_items = _collect_cluster_inputs(tmp_path, log_file)
    assert len(log_items) == 2


def test_cluster_main_json_and_file_outputs(tmp_path: Path, capsys) -> None:
    fail_file = tmp_path / "test_failures.json"
    fail_file.write_text(
        json.dumps(
            [
                {"node": "tests/test_x.py::test_1", "error": "TypeError: 'NoneType' object"},
                {"node": "tests/test_y.py::test_2", "error": "TypeError: 'NoneType' object"},
            ]
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "cluster_report.json"
    sum_md = tmp_path / "summary.md"

    rc = cluster_main(
        [
            "--input",
            str(fail_file),
            "--format",
            "json",
            "--out",
            str(out_json),
            "--summary-out",
            str(sum_md),
            "--fail-on",
            "none",
        ]
    )
    assert rc == 0
    assert out_json.is_file()
    assert sum_md.is_file()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == CLUSTER_SCHEMA_VERSION
    assert payload["cluster_count"] == 1


def test_cluster_main_exit_codes(tmp_path: Path) -> None:
    fail_file = tmp_path / "failures.json"
    fail_file.write_text(
        json.dumps([{"node": "tests/test_fail.py::test_bad", "error": "AssertionError: boom"}]),
        encoding="utf-8",
    )

    # With --fail-on clusters -> exits 1
    rc_fail = cluster_main(["--input", str(fail_file), "--fail-on", "clusters"])
    assert rc_fail == 1

    # With --fail-on none -> exits 0
    rc_pass = cluster_main(["--input", str(fail_file), "--fail-on", "none"])
    assert rc_pass == 0


def test_cli_dispatch_sdetkit_cluster(tmp_path: Path, capsys) -> None:
    rc = cli_main(
        ["cluster", "--repo-root", str(tmp_path), "--format", "json", "--fail-on", "none"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == CLUSTER_SCHEMA_VERSION


def test_cli_dispatch_sdetkit_verify_cluster(tmp_path: Path, capsys) -> None:
    rc = cli_main(
        ["verify", "cluster", "--repo-root", str(tmp_path), "--format", "text", "--fail-on", "none"]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "Failure Clusters:" in captured.out
