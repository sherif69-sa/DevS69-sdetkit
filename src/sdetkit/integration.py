from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from .atomicio import canonical_json_dumps
from .cassette import Cassette
from .security import SecurityError, safe_path

REQUIRED_APP_SERVICE_RULES = (
    ("api-gateway", "go"),
    ("ml-serving", "python"),
    ("data-pipeline", "rust"),
)
REQUIRED_DATA_SERVICE_TECH = {
    "transactional": "postgresql",
    "cache": "redis",
    "blob": "s3",
}
REQUIRED_APP_DEPENDENCIES = {
    "api-gateway": {"application": {"ml-serving"}},
    "ml-serving": {"data": {"transactional", "cache"}},
    "data-pipeline": {"data": {"transactional", "blob"}, "mock": {"segment-like-events"}},
}


def _load_profile(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("profile must be a JSON object")
    return obj


def _probe_tcp_localhost(port: int, timeout_s: float = 0.2) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _service_exposes_protocol(
    service: dict[str, Any], *, protocol: str, audience: str | None = None
) -> bool:
    interfaces = service.get("interfaces", [])
    if not isinstance(interfaces, list):
        return False
    want_protocol = _normalize(protocol)
    want_audience = _normalize(audience) if audience is not None else None
    for interface in interfaces:
        if not isinstance(interface, dict):
            continue
        if _normalize(interface.get("protocol")) != want_protocol:
            continue
        if want_audience is not None and _normalize(interface.get("audience")) != want_audience:
            continue
        return True
    return False


def _normalize_deployments(service: dict[str, Any]) -> list[dict[str, Any]]:
    deployments = service.get("deployments", [])
    if not isinstance(deployments, list):
        return []
    return [item for item in deployments if isinstance(item, dict)]


def _parse_replicas(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _telemetry_signal_enabled(telemetry: dict[str, Any], signal: str) -> bool:
    value = telemetry.get(signal)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _normalize(value) in {"enabled", "true", "required", "on"}
    return False


def _normalize_dependency_entry(
    entry: Any,
    *,
    application_names: set[str],
    data_names: set[str],
    mock_names: set[str],
) -> dict[str, str] | None:
    if isinstance(entry, str):
        name = _normalize(entry)
        if not name:
            return None
        if name in application_names:
            return {"kind": "application", "target": name}
        if name in data_names:
            return {"kind": "data", "target": name}
        if name in mock_names:
            return {"kind": "mock", "target": name}
        return {"kind": "unknown", "target": name}
    if not isinstance(entry, dict):
        return None

    target = _normalize(entry.get("target") or entry.get("name") or entry.get("service"))
    if not target:
        return None

    kind = _normalize(entry.get("kind") or entry.get("type"))
    if kind in {"service", "application-service", "application"}:
        resolved_kind = "application"
    elif kind in {"data", "data-service", "database", "store"}:
        resolved_kind = "data"
    elif kind in {"mock", "mock-platform", "platform", "external"}:
        resolved_kind = "mock"
    elif kind:
        resolved_kind = kind
    elif target in application_names:
        resolved_kind = "application"
    elif target in data_names:
        resolved_kind = "data"
    elif target in mock_names:
        resolved_kind = "mock"
    else:
        resolved_kind = "unknown"
    return {"kind": resolved_kind, "target": target}


def _evaluate(profile: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    for env_name in sorted(str(x) for x in profile.get("required_env", [])):
        present = bool(os.environ.get(env_name, ""))
        checks.append({"kind": "env", "name": env_name, "passed": present})

    for rel_file in sorted(str(x) for x in profile.get("required_files", [])):
        exists = Path(rel_file).exists()
        checks.append({"kind": "file", "name": rel_file, "passed": exists})

    services = profile.get("services", [])
    if isinstance(services, list):
        for svc in sorted(
            (x for x in services if isinstance(x, dict)), key=lambda x: str(x.get("name"))
        ):
            name = str(svc.get("name", "service"))
            port = int(svc.get("port", 0))
            expect = str(svc.get("expect", "closed"))
            if port <= 0:
                checks.append(
                    {"kind": "service", "name": name, "passed": False, "reason": "invalid-port"}
                )
                continue
            open_now = _probe_tcp_localhost(port)
            passed = open_now if expect == "open" else (not open_now)
            checks.append(
                {
                    "kind": "service",
                    "name": name,
                    "port": port,
                    "expect": expect,
                    "observed": "open" if open_now else "closed",
                    "passed": passed,
                }
            )

    checks.sort(key=lambda x: (str(x.get("kind", "")), str(x.get("name", ""))))
    failed = [item for item in checks if not bool(item.get("passed"))]
    return {
        "schema_version": "sdetkit.integration.profile-check.v1",
        "profile_name": str(profile.get("name", "default")),
        "checks": checks,
        "summary": {
            "total": len(checks),
            "failed": len(failed),
            "passed": not failed if checks else True,
            "next_step": (
                "Ready for integration lanes."
                if not failed
                else "Fix failed readiness checks before running integration suites."
            ),
        },
    }


def _evaluate_topology(profile: dict[str, Any]) -> dict[str, Any]:
    topology = profile.get("topology")
    if not isinstance(topology, dict):
        raise ValueError("profile.topology must be a JSON object")

    app_services = [
        item for item in topology.get("application_services", []) if isinstance(item, dict)
    ]
    data_services = [item for item in topology.get("data_services", []) if isinstance(item, dict)]
    mocked_platforms = [
        item for item in topology.get("mocked_platforms", []) if isinstance(item, dict)
    ]

    checks: list[dict[str, Any]] = []

    language_map = {
        str(svc.get("name", "service")): _normalize(svc.get("language")) for svc in app_services
    }
    role_map = {_normalize(svc.get("role")): svc for svc in app_services}
    app_role_aliases = {
        _normalize(svc.get("name")): _normalize(svc.get("role")) for svc in app_services
    }
    data_role_aliases = {
        _normalize(svc.get("name")): _normalize(svc.get("role")) for svc in data_services
    }
    mock_name_aliases = {
        _normalize(svc.get("name")): _normalize(svc.get("name")) for svc in mocked_platforms
    }
    distinct_languages = sorted({lang for lang in language_map.values() if lang})
    checks.append(
        {
            "kind": "architecture",
            "name": "heterogeneous-stack",
            "passed": len(distinct_languages) >= 3,
            "evidence": {"languages": distinct_languages, "service_count": len(app_services)},
            "reason": "Need at least three distinct implementation languages across application services.",
        }
    )

    for role, language in REQUIRED_APP_SERVICE_RULES:
        svc = role_map.get(role)
        actual_language = _normalize(svc.get("language")) if isinstance(svc, dict) else ""
        checks.append(
            {
                "kind": "application-service",
                "name": role,
                "passed": actual_language == language,
                "expected_language": language,
                "observed_language": actual_language or None,
            }
        )

    dependency_edges: list[str] = []
    dependency_by_role: dict[str, set[tuple[str, str]]] = {}
    protocols: set[str] = set()

    app_names = set(app_role_aliases)
    data_names = set(data_role_aliases)
    mock_names = set(mock_name_aliases)

    for svc in sorted(app_services, key=lambda item: str(item.get("name", ""))):
        name = str(svc.get("name", "service"))
        role = _normalize(svc.get("role"))
        logging_format = _normalize(svc.get("logging_format"))
        error_style = _normalize(svc.get("error_handling"))
        owner = _normalize(svc.get("owner"))
        telemetry = svc.get("telemetry")
        if not isinstance(telemetry, dict):
            telemetry = {}
        deployments = _normalize_deployments(svc)
        deployment_envs = {
            _normalize(deployment.get("environment") or deployment.get("env"))
            for deployment in deployments
            if _normalize(deployment.get("environment") or deployment.get("env"))
        }
        production_regions = {
            _normalize(deployment.get("region"))
            for deployment in deployments
            if _normalize(deployment.get("environment") or deployment.get("env"))
            in {"prod", "production"}
            and _normalize(deployment.get("region"))
        }
        production_replicas = [
            _parse_replicas(deployment.get("replicas"))
            for deployment in deployments
            if _normalize(deployment.get("environment") or deployment.get("env"))
            in {"prod", "production"}
        ]
        checks.append(
            {
                "kind": "service-contract",
                "name": f"{name}:logging-format",
                "passed": bool(logging_format),
                "observed": logging_format or None,
            }
        )
        checks.append(
            {
                "kind": "service-contract",
                "name": f"{name}:error-handling",
                "passed": bool(error_style),
                "observed": error_style or None,
            }
        )
        checks.append(
            {
                "kind": "service-contract",
                "name": f"{name}:owner",
                "passed": bool(owner),
                "observed": owner or None,
            }
        )
        checks.append(
            {
                "kind": "observability",
                "name": f"{name}:telemetry",
                "passed": all(
                    _telemetry_signal_enabled(telemetry, signal)
                    for signal in ("logs", "metrics", "traces")
                ),
                "signals": {
                    signal: _telemetry_signal_enabled(telemetry, signal)
                    for signal in ("logs", "metrics", "traces")
                },
            }
        )
        checks.append(
            {
                "kind": "deployment",
                "name": f"{name}:environments",
                "passed": {"staging", "prod"}.issubset(deployment_envs)
                or {"staging", "production"}.issubset(deployment_envs),
                "observed_environments": sorted(deployment_envs),
            }
        )
        checks.append(
            {
                "kind": "deployment",
                "name": f"{name}:production-scale",
                "passed": len(production_regions) >= 1
                and any(replicas >= 2 for replicas in production_replicas),
                "production_regions": sorted(production_regions),
                "production_replicas": production_replicas,
            }
        )

        for interface in svc.get("interfaces", []):
            if isinstance(interface, dict):
                protocol = _normalize(interface.get("protocol"))
                if protocol:
                    protocols.add(protocol)

        raw_dependencies = svc.get("dependencies", [])
        normalized_dependencies: set[tuple[str, str]] = set()
        if isinstance(raw_dependencies, list):
            for entry in raw_dependencies:
                normalized = _normalize_dependency_entry(
                    entry,
                    application_names=app_names,
                    data_names=data_names,
                    mock_names=mock_names,
                )
                if normalized is None:
                    continue
                target = normalized["target"]
                kind = normalized["kind"]
                if kind == "application":
                    target = app_role_aliases.get(target, target)
                elif kind == "data":
                    target = data_role_aliases.get(target, target)
                elif kind == "mock":
                    target = mock_name_aliases.get(target, target)
                normalized_dependencies.add((kind, target))
                dependency_edges.append(f"{role or _normalize(name)}->{kind}:{target}")
        dependency_by_role[role] = normalized_dependencies

    for role, expected_dependencies in REQUIRED_APP_DEPENDENCIES.items():
        observed_dependencies = dependency_by_role.get(role, set())
        missing: list[str] = []
        for dependency_kind, accepted_targets in expected_dependencies.items():
            if not any(
                observed_kind == dependency_kind and observed_target in accepted_targets
                for observed_kind, observed_target in observed_dependencies
            ):
                missing.append(f"{dependency_kind}:{'|'.join(sorted(accepted_targets))}")
        checks.append(
            {
                "kind": "dependency-contract",
                "name": role,
                "passed": not missing,
                "observed_dependencies": [
                    f"{dependency_kind}:{target}"
                    for dependency_kind, target in sorted(observed_dependencies)
                ],
                "missing_dependencies": missing,
            }
        )

    checks.append(
        {
            "kind": "interface",
            "name": "public-rest",
            "passed": any(
                _service_exposes_protocol(svc, protocol="rest", audience="external")
                for svc in app_services
            ),
        }
    )
    checks.append(
        {
            "kind": "interface",
            "name": "internal-grpc",
            "passed": any(
                _service_exposes_protocol(svc, protocol="grpc", audience="internal")
                for svc in app_services
            ),
        }
    )
    checks.append(
        {
            "kind": "interface",
            "name": "dashboard-graphql",
            "passed": any(
                _service_exposes_protocol(svc, protocol="graphql", audience="dashboard")
                for svc in app_services
            ),
        }
    )

    data_by_role = {
        _normalize(svc.get("role")): _normalize(svc.get("technology")) for svc in data_services
    }
    for svc in sorted(data_services, key=lambda item: str(item.get("name", ""))):
        name = str(svc.get("name", svc.get("role", "data-service")))
        role = _normalize(svc.get("role"))
        backup_strategy = _normalize(svc.get("backup_strategy"))
        multi_az = bool(svc.get("multi_az"))
        checks.append(
            {
                "kind": "data-resilience",
                "name": f"{name}:backup-strategy",
                "passed": bool(backup_strategy),
                "observed": backup_strategy or None,
                "role": role or None,
            }
        )
        checks.append(
            {
                "kind": "data-resilience",
                "name": f"{name}:multi-az",
                "passed": multi_az,
                "observed": multi_az,
                "role": role or None,
            }
        )

    for role, technology in REQUIRED_DATA_SERVICE_TECH.items():
        observed = data_by_role.get(role, "")
        matches = observed == technology or (
            role == "blob" and observed in {"s3", "s3-compatible", "s3-like"}
        )
        checks.append(
            {
                "kind": "data-service",
                "name": role,
                "passed": matches,
                "expected_technology": technology,
                "observed_technology": observed or None,
            }
        )

    platform_names = {_normalize(platform.get("name")) for platform in mocked_platforms}
    covered_platforms = {
        target
        for dependencies in dependency_by_role.values()
        for kind, target in dependencies
        if kind == "mock"
    }
    checks.append(
        {
            "kind": "mock-coverage",
            "name": "platform-dependencies",
            "passed": platform_names == covered_platforms,
            "observed_platform_dependencies": sorted(covered_platforms),
            "missing_platform_dependencies": sorted(platform_names - covered_platforms),
            "unexpected_platform_dependencies": sorted(covered_platforms - platform_names),
        }
    )

    for platform in sorted(mocked_platforms, key=lambda item: str(item.get("name", ""))):
        name = str(platform.get("name", "mocked-platform"))
        api_style = _normalize(platform.get("api_style"))
        protocol = _normalize(platform.get("protocol"))
        fidelity = sorted(
            {_normalize(item) for item in platform.get("fidelity", []) if _normalize(item)}
        )
        operations = [
            op for op in platform.get("operations", []) if isinstance(op, str) and op.strip()
        ]
        checks.append(
            {
                "kind": "mock-platform",
                "name": name,
                "passed": bool(api_style and protocol and len(operations) >= 2 and fidelity),
                "api_style": api_style or None,
                "protocol": protocol or None,
                "operation_count": len(operations),
                "fidelity": fidelity,
            }
        )

    checks.sort(key=lambda item: (str(item.get("kind", "")), str(item.get("name", ""))))
    failed = [item for item in checks if not bool(item.get("passed"))]
    total = len(checks)
    passed_count = total - len(failed)
    return {
        "schema_version": "sdetkit.integration.topology-check.v1",
        "profile_name": str(profile.get("name", "default")),
        "checks": checks,
        "summary": {
            "total": total,
            "failed": len(failed),
            "passed_checks": passed_count,
            "pass_rate": round((passed_count / total) * 100, 1) if total else 100.0,
            "passed": not failed if checks else True,
            "next_step": (
                "Topology contract is ready for enterprise integration scenarios."
                if not failed
                else (
                    "Fill the missing topology contracts before claiming "
                    "production-grade multi-service readiness."
                )
            ),
        },
        "inventory": {
            "application_services": sorted(language_map),
            "languages": distinct_languages,
            "data_services": sorted(
                str(item.get("name", item.get("role", "data-service"))) for item in data_services
            ),
            "mocked_platforms": sorted(
                str(item.get("name", "mocked-platform")) for item in mocked_platforms
            ),
            "protocols": sorted(protocols),
            "dependency_edges": sorted(dependency_edges),
            "counts": {
                "application_services": len(app_services),
                "data_services": len(data_services),
                "mocked_platforms": len(mocked_platforms),
                "dependency_edges": len(dependency_edges),
            },
        },
    }


def _validate_cassette(cassette_path: Path) -> dict[str, Any]:
    cassette = Cassette.load(cassette_path, allow_absolute=True)
    interactions = cassette.interactions
    invalid: list[dict[str, Any]] = []
    methods: dict[str, int] = {}
    hosts: set[str] = set()

    for idx, item in enumerate(interactions):
        req = item.get("request") if isinstance(item, dict) else None
        resp = item.get("response") if isinstance(item, dict) else None
        if not isinstance(req, dict) or not isinstance(resp, dict):
            invalid.append({"index": idx, "reason": "invalid-shape"})
            continue

        method = str(req.get("method", "")).upper()
        url = str(req.get("url", ""))
        if not method or not url:
            invalid.append({"index": idx, "reason": "missing-method-or-url"})
            continue
        methods[method] = methods.get(method, 0) + 1

        try:
            host = url.split("//", 1)[1].split("/", 1)[0]
        except Exception:
            host = ""
        if host:
            hosts.add(host)

        status_code = resp.get("status_code")
        if not isinstance(status_code, int) or status_code < 100 or status_code > 599:
            invalid.append({"index": idx, "reason": "invalid-status-code"})

    return {
        "schema_version": "sdetkit.integration.cassette-validate.v1",
        "cassette": str(cassette_path),
        "summary": {
            "interactions": len(interactions),
            "invalid": len(invalid),
            "hosts": sorted(hosts),
            "methods": {k: methods[k] for k in sorted(methods)},
            "passed": len(invalid) == 0,
        },
        "invalid": invalid,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit integration", description="Integration Assurance Kit (offline-first)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="Evaluate environment readiness profile")
    check.add_argument("--profile", required=True)
    matrix = sub.add_parser("matrix", help="Print compatibility summary in JSON")
    matrix.add_argument("--profile", required=True)
    topology = sub.add_parser(
        "topology-check",
        help="Validate a heterogeneous service topology contract for enterprise integration readiness",
    )
    topology.add_argument("--profile", required=True)
    cassette_validate = sub.add_parser(
        "cassette-validate", help="Validate deterministic cassette contract for integration replay"
    )
    cassette_validate.add_argument("--cassette", required=True)
    ns = parser.parse_args(argv)

    try:
        if ns.cmd in {"check", "matrix", "topology-check"}:
            profile = _load_profile(safe_path(Path.cwd(), ns.profile, allow_absolute=True))
            if ns.cmd == "topology-check":
                payload = _evaluate_topology(profile)
            else:
                payload = _evaluate(profile)
                if ns.cmd == "matrix":
                    payload["schema_version"] = "sdetkit.integration.matrix.v1"
                    payload["compatibility"] = {
                        "profile": payload["profile_name"],
                        "status": "compatible" if payload["summary"]["passed"] else "incompatible",
                    }
        else:
            payload = _validate_cassette(safe_path(Path.cwd(), ns.cassette, allow_absolute=True))
    except (ValueError, OSError, SecurityError) as exc:
        sys.stderr.write(f"integration error: {exc}\n")
        return 2

    sys.stdout.write(canonical_json_dumps(payload))
    return 0 if payload["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
