from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True, cwd=cwd
    )


def test_topology_check_accepts_heterogeneous_enterprise_profile() -> None:
    proc = _run(
        "integration",
        "topology-check",
        "--profile",
        "examples/kits/integration/heterogeneous-topology.json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.integration.topology-check.v1"
    assert payload["summary"]["passed"] is True
    assert payload["summary"]["passed_checks"] == payload["summary"]["total"]
    assert payload["summary"]["pass_rate"] == 100.0
    assert payload["inventory"]["languages"] == ["go", "python", "rust"]
    assert payload["inventory"]["mocked_platforms"] == [
        "segment-like-events",
        "stripe-like-payments",
    ]
    assert payload["inventory"]["protocols"] == ["graphql", "grpc", "rest"]
    assert payload["inventory"]["counts"] == {
        "application_services": 3,
        "data_services": 3,
        "mocked_platforms": 2,
        "dependency_edges": 7,
    }
    assert "api-gateway->application:ml-serving" in payload["inventory"]["dependency_edges"]
    assert "data-pipeline->mock:segment-like-events" in payload["inventory"]["dependency_edges"]
    passed = {(item["kind"], item["name"]) for item in payload["checks"] if item["passed"]}
    assert ("observability", "edge-gateway:telemetry") in passed
    assert ("deployment", "search-indexer:production-scale") in passed
    assert ("data-resilience", "orders-db:backup-strategy") in passed


def test_topology_check_flags_missing_heterogeneous_contracts(tmp_path: Path) -> None:
    profile = tmp_path / "bad-topology.json"
    profile.write_text(
        json.dumps(
            {
                "name": "bad-topology",
                "topology": {
                    "application_services": [
                        {
                            "name": "gateway",
                            "role": "api-gateway",
                            "language": "python",
                            "logging_format": "json",
                            "interfaces": [{"protocol": "rest", "audience": "external"}],
                            "dependencies": [{"kind": "mock", "target": "crm"}],
                        },
                        {
                            "name": "worker",
                            "role": "ml-serving",
                            "language": "python",
                            "error_handling": "exceptions",
                            "owner": "ml-team",
                            "interfaces": [{"protocol": "http", "audience": "internal"}],
                        },
                    ],
                    "data_services": [
                        {
                            "name": "orders",
                            "role": "transactional",
                            "technology": "mysql"
                        }
                    ],
                    "mocked_platforms": [
                        {"name": "crm", "protocol": "rest", "operations": ["sync"]}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run("integration", "topology-check", "--profile", str(profile))
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["summary"]["passed"] is False
    assert payload["summary"]["pass_rate"] < 100.0
    failed = {(item["kind"], item["name"]) for item in payload["checks"] if not item["passed"]}
    assert ("application-service", "api-gateway") in failed
    assert ("application-service", "data-pipeline") in failed
    assert ("dependency-contract", "api-gateway") in failed
    assert ("dependency-contract", "ml-serving") in failed
    assert ("dependency-contract", "data-pipeline") in failed
    assert ("interface", "internal-grpc") in failed
    assert ("data-service", "transactional") in failed
    assert ("mock-platform", "crm") in failed
    assert ("service-contract", "gateway:error-handling") in failed
    assert ("service-contract", "gateway:owner") in failed
    assert ("service-contract", "worker:logging-format") in failed
    assert ("observability", "gateway:telemetry") in failed
    assert ("deployment", "gateway:environments") in failed
    assert ("deployment", "worker:production-scale") in failed
    assert ("data-resilience", "orders:backup-strategy") in failed
    assert ("data-resilience", "orders:multi-az") in failed


def test_topology_check_requires_topology_object(tmp_path: Path) -> None:
    profile = tmp_path / "missing-topology.json"
    profile.write_text('{"name": "oops"}', encoding="utf-8")
    proc = _run("integration", "topology-check", "--profile", str(profile))
    assert proc.returncode == 2
    assert "integration error" in proc.stderr
