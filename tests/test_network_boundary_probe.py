from __future__ import annotations

import sys

import pytest

from sdetkit import network_boundary as nb


def _backend(name: str, executable: str) -> nb.NetworkIsolationBackend:
    return nb.NetworkIsolationBackend(
        backend_id=name, executable_name=executable, variant="test", argv_prefix=()
    )


def test_probe_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError):
        nb.probe_registered_backends(timeout_seconds=0)


def test_probe_baseline_reaches_controlled_loopback_without_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nb, "REGISTERED_BACKENDS", {})

    report = nb.probe_registered_backends(timeout_seconds=10)

    assert report["baseline_control_passed"] is True
    assert report["baseline"]["loopback_connect_succeeded"] is True
    assert report["candidates"] == []
    assert report["verified_candidate_count"] == 0
    assert report["selected_candidate"]["backend_id"] == ""
    assert report["decision_boundary"]["automation_allowed"] is False


def test_probe_does_not_verify_backends_that_do_not_isolate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nb,
        "REGISTERED_BACKENDS",
        {
            "missing": _backend("missing", "definitely-not-a-real-sdetkit-binary"),
            "passthrough": _backend("passthrough", "env"),
        },
    )

    report = nb.probe_registered_backends(timeout_seconds=10)

    by_id = {item["backend_id"]: item for item in report["candidates"]}
    assert by_id["missing"]["available"] is False
    assert by_id["missing"]["network_namespace_isolation_verified"] is False
    passthrough = by_id["passthrough"]
    assert passthrough["available"] is True
    assert passthrough["executable_sha256"]
    assert passthrough["child_executed"] is True
    # `env` runs the child in the same network namespace, so loopback still works.
    assert passthrough["loopback_connect_succeeded"] is True
    assert passthrough["network_namespace_isolation_verified"] is False
    assert report["verified_candidate_count"] == 0


def test_run_probe_process_reports_missing_executable() -> None:
    result = nb._run_probe_process(
        ["definitely-not-a-real-sdetkit-binary"], timeout_seconds=5, parent_namespace="ns"
    )

    assert result["process_started"] is False
    assert "FileNotFoundError" in result["stderr"]
    assert result["network_namespace_isolation_verified"] is False


def test_run_probe_process_reports_timeout() -> None:
    result = nb._run_probe_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_seconds=1,
        parent_namespace="ns",
    )

    assert result["process_started"] is True
    assert result["timed_out"] is True
    assert result["child_executed"] is False


def test_run_probe_process_ignores_output_without_probe_payload() -> None:
    result = nb._run_probe_process(
        [sys.executable, "-c", "print('not json'); print('{\"other\": 1}')"],
        timeout_seconds=5,
        parent_namespace="ns",
    )

    assert result["exit_code"] == 0
    assert result["child_executed"] is False
    assert result["loopback_connect_succeeded"] is None


def test_run_probe_process_verifies_only_changed_namespace_with_blocked_loopback() -> None:
    payload = (
        '{"child_executed": true, "network_namespace": "net:[2]", '
        '"loopback_connect_succeeded": false, "loopback_error": "refused"}'
    )
    result = nb._run_probe_process(
        [sys.executable, "-c", f"print({payload!r})"],
        timeout_seconds=5,
        parent_namespace="net:[1]",
    )

    assert result["namespace_changed"] is True
    assert result["isolated_loopback_blocked"] is True
    assert result["network_namespace_isolation_verified"] is True

    same_namespace = nb._run_probe_process(
        [sys.executable, "-c", f"print({payload.replace('net:[2]', 'net:[1]')!r})"],
        timeout_seconds=5,
        parent_namespace="net:[1]",
    )
    assert same_namespace["namespace_changed"] is False
    assert same_namespace["network_namespace_isolation_verified"] is False
