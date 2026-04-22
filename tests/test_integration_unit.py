from __future__ import annotations

import json
from pathlib import Path

from sdetkit import integration


def _topology_profile() -> dict[str, object]:
    return {
        "name": "enterprise-topology",
        "topology": {
            "application_services": [
                {
                    "name": "gateway",
                    "role": "api-gateway",
                    "language": "go",
                    "logging_format": "json",
                    "error_handling": "typed",
                    "owner": "platform",
                    "telemetry": {"logs": True, "metrics": True, "traces": True},
                    "deployments": [
                        {"environment": "staging", "region": "us-east-1", "replicas": 1},
                        {"environment": "prod", "region": "us-east-1", "replicas": 2},
                    ],
                    "interfaces": [
                        {"protocol": "rest", "audience": "external"},
                        {"protocol": "grpc", "audience": "internal"},
                    ],
                    "dependencies": [{"kind": "application", "target": "ml-serving"}],
                },
                {
                    "name": "model",
                    "role": "ml-serving",
                    "language": "python",
                    "logging_format": "json",
                    "error_handling": "structured",
                    "owner": "ml",
                    "telemetry": {"logs": "enabled", "metrics": "required", "traces": "on"},
                    "deployments": [
                        {"env": "staging", "region": "us-east-1", "replicas": 1},
                        {"env": "production", "region": "us-east-1", "replicas": 2},
                    ],
                    "interfaces": [
                        {"protocol": "graphql", "audience": "dashboard"},
                        {"protocol": "grpc", "audience": "internal"},
                    ],
                    "dependencies": ["transactional", "cache"],
                },
                {
                    "name": "pipeline",
                    "role": "data-pipeline",
                    "language": "rust",
                    "logging_format": "json",
                    "error_handling": "retry",
                    "owner": "data",
                    "telemetry": {"logs": True, "metrics": True, "traces": True},
                    "deployments": [
                        {"environment": "staging", "region": "us-east-1", "replicas": 1},
                        {"environment": "prod", "region": "us-east-1", "replicas": 2},
                    ],
                    "interfaces": [{"protocol": "grpc", "audience": "internal"}],
                    "dependencies": [{"kind": "data", "target": "blob"}, "segment-like-events"],
                },
            ],
            "data_services": [
                {
                    "name": "tx-db",
                    "role": "transactional",
                    "technology": "postgresql",
                    "backup_strategy": "pitr",
                    "multi_az": True,
                },
                {
                    "name": "cache",
                    "role": "cache",
                    "technology": "redis",
                    "backup_strategy": "snapshot",
                    "multi_az": True,
                },
                {
                    "name": "blob-store",
                    "role": "blob",
                    "technology": "s3",
                    "backup_strategy": "versioning",
                    "multi_az": True,
                },
            ],
            "mocked_platforms": [
                {
                    "name": "segment-like-events",
                    "api_style": "rest",
                    "protocol": "https",
                    "operations": ["identify", "track"],
                    "fidelity": ["schema", "latency"],
                }
            ],
        },
    }


def test_integration_evaluate_helpers_and_topology(monkeypatch, tmp_path: Path) -> None:
    marker = tmp_path / "ready.txt"
    marker.write_text("ok", encoding="utf-8")
    monkeypatch.setenv("INTEGRATION_READY", "true")
    monkeypatch.setattr(
        integration, "_probe_tcp_localhost", lambda port, timeout_s=0.2: port == 8080
    )

    profile = {
        "name": "p",
        "required_env": ["INTEGRATION_READY"],
        "required_files": [str(marker)],
        "services": [{"name": "api", "port": 8080, "expect": "open"}],
    }
    eval_payload = integration._evaluate(profile)
    assert eval_payload["summary"]["passed"] is True

    topo = integration._evaluate_topology(_topology_profile())
    assert topo["summary"]["passed"] is True
    assert topo["inventory"]["counts"]["application_services"] == 3

    assert integration._parse_replicas("3") == 3
    assert integration._parse_replicas(True) == 0
    assert integration._normalize(None) == ""
    assert integration._telemetry_signal_enabled({"logs": "enabled"}, "logs") is True


def test_integration_main_routes_and_cassette_validation(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(_topology_profile()), encoding="utf-8")
    monkeypatch.setattr(integration, "_probe_tcp_localhost", lambda *_a, **_k: False)

    rc = integration.main(["topology-check", "--profile", str(profile_path)])
    assert rc == 0
    assert "topology-check" in capsys.readouterr().out

    check_profile = tmp_path / "check.json"
    check_profile.write_text(
        json.dumps({"required_env": [], "required_files": [], "services": []}), encoding="utf-8"
    )
    rc = integration.main(["matrix", "--profile", str(check_profile)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "compatibility" in out

    cassette = tmp_path / "cassette.json"
    cassette.write_text(
        json.dumps(
            {
                "version": 1,
                "interactions": [
                    {
                        "request": {"method": "GET", "url": "https://api.example.test/v1"},
                        "response": {"status_code": 200},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rc = integration.main(["cassette-validate", "--cassette", str(cassette)])
    assert rc == 0

    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    rc = integration.main(["check", "--profile", str(bad)])
    assert rc == 2
    assert "integration error:" in capsys.readouterr().err
