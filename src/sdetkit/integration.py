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


def _load_profile(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("profile must be a JSON object")
    return obj


def _probe_tcp_localhost(port: int, timeout_s: float = 0.2) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex(("127.0.0.1", port)) == 0


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
    cassette_validate = sub.add_parser(
        "cassette-validate", help="Validate deterministic cassette contract for integration replay"
    )
    cassette_validate.add_argument("--cassette", required=True)
    ns = parser.parse_args(argv)

    try:
        if ns.cmd in {"check", "matrix"}:
            profile = _load_profile(safe_path(Path.cwd(), ns.profile, allow_absolute=True))
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
