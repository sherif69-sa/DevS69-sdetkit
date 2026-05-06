from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.public_api_parity import detect_public_api_parity


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_detects_sync_async_method_gap(tmp_path):
    _write(
        tmp_path / "src" / "sdetkit" / "netclient.py",
        "class SdetHttpClient:\n"
        "    def get_json(self):\n"
        "        return {}\n"
        "    def get_json_envelope(self):\n"
        "        return {}\n"
        "\n"
        "class SdetAsyncHttpClient:\n"
        "    async def get_json(self):\n"
        "        return {}\n",
    )
    _write(tmp_path / "tests" / "test_netclient.py", "def test_netclient():\n    assert True\n")

    payload = detect_public_api_parity(tmp_path, "netclient")

    assert payload["schema_version"] == "sdetkit.investigate.parity.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["production_files"] == ["src/sdetkit/netclient.py"]
    assert payload["test_files"] == ["tests/test_netclient.py"]
    assert payload["counts_by_kind"] == {"SYNC_ASYNC_METHOD_GAP": 1}
    assert payload["findings"] == [
        {
            "kind": "SYNC_ASYNC_METHOD_GAP",
            "severity": "warning",
            "sync_symbol": "SdetHttpClient.get_json_envelope",
            "async_symbol": "SdetAsyncHttpClient.get_json_envelope",
            "status": "missing",
            "recommended_test": "focused sync/async parity test",
        }
    ]


def test_detects_helper_gap_when_surface_has_async_context(tmp_path):
    _write(
        tmp_path / "src" / "sdetkit" / "client_helpers.py",
        "def get_json_envelope():\n"
        "    return {}\n"
        "\n"
        "class AsyncClient:\n"
        "    async def run(self):\n"
        "        return None\n",
    )
    _write(tmp_path / "tests" / "test_client_helpers.py", "def test_helpers():\n    assert True\n")

    payload = detect_public_api_parity(tmp_path, "client_helpers")

    assert payload["counts_by_kind"] == {"SYNC_ASYNC_HELPER_GAP": 1}
    assert payload["findings"][0]["kind"] == "SYNC_ASYNC_HELPER_GAP"
    assert payload["findings"][0]["status"] == "missing_async_helper"
    assert payload["findings"][0]["sync_symbol"] == "get_json_envelope"
    assert payload["findings"][0]["async_symbol"] == "async_get_json_envelope"


def test_detects_cli_backend_gap(tmp_path):
    _write(
        tmp_path / "src" / "sdetkit" / "release_room.py",
        "class ReleaseRoom:\n    def publish_summary(self):\n        return {}\n",
    )
    _write(
        tmp_path / "src" / "sdetkit" / "release_room_cli.py",
        "def main():\n    return 0\n",
    )
    _write(
        tmp_path / "tests" / "test_release_room.py", "def test_release_room():\n    assert True\n"
    )

    payload = detect_public_api_parity(tmp_path, "release_room")

    assert payload["counts_by_kind"] == {"CLI_BACKEND_PARITY_GAP": 1}
    assert payload["findings"][0]["kind"] == "CLI_BACKEND_PARITY_GAP"
    assert payload["findings"][0]["backend_symbol"] == "ReleaseRoom.publish_summary"
    assert payload["findings"][0]["status"] == "not_referenced_by_cli_surface"


def test_detects_public_mode_without_matching_tests(tmp_path):
    _write(
        tmp_path / "src" / "sdetkit" / "diagnostics.py",
        "def build_report():\n    return {}\n",
    )

    payload = detect_public_api_parity(tmp_path, "diagnostics")

    assert payload["counts_by_kind"] == {"PUBLIC_MODE_UNTESTED": 1}
    assert payload["findings"][0]["kind"] == "PUBLIC_MODE_UNTESTED"
    assert payload["findings"][0]["public_symbol"] == "build_report"


def test_detector_returns_empty_findings_for_balanced_surface(tmp_path):
    _write(
        tmp_path / "src" / "sdetkit" / "netclient.py",
        "class SdetHttpClient:\n"
        "    def get_json(self):\n"
        "        return {}\n"
        "\n"
        "class SdetAsyncHttpClient:\n"
        "    async def get_json(self):\n"
        "        return {}\n",
    )
    _write(tmp_path / "tests" / "test_netclient.py", "def test_netclient():\n    assert True\n")

    payload = detect_public_api_parity(tmp_path, "netclient")

    assert payload["finding_count"] == 0
    assert payload["counts_by_kind"] == {}
    assert payload["findings"] == []


def test_detector_rejects_missing_root(tmp_path):
    with pytest.raises(OSError, match="repository root does not exist"):
        detect_public_api_parity(tmp_path / "missing", "netclient")


def test_detector_rejects_blank_surface(tmp_path):
    with pytest.raises(OSError, match="surface name is required"):
        detect_public_api_parity(tmp_path, " ")
