from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.network_boundary.v2"
PROBE_SCHEMA_VERSION = "sdetkit.network_isolation_backend_probe.v1"
DEFAULT_OUT_DIR = Path("build") / "network-boundary"
BOUNDARY_JSON = "network-boundary.json"
BOUNDARY_MD = "network-boundary.md"
DEFAULT_PROBE_TIMEOUT_SECONDS = 12

NETWORK_ISOLATION_REQUIRED = "_".join(("network", "isolation", "required"))
NETWORK_ISOLATION_ENFORCED = "_".join(("network", "isolation", "enforced"))
PROOF_EXECUTION_ALLOWED = "_".join(("proof", "execution", "allowed"))

NOT_REQUESTED = "_".join(("not", "requested"))
REQUIRED_UNAVAILABLE = "_".join(("required", "unavailable"))
VERIFIED_BACKEND_AVAILABLE = "_".join(("verified", "backend", "available"))
NO_VERIFIED_BACKEND = "_".join(("no", "verified", "backend"))
UNSHARE_USER_MAP_ROOT_NET = "_".join(("unshare", "user", "map", "root", "net"))
UNSHARE_VARIANT = "_".join(("user", "map", "root", "net"))

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class NetworkIsolationBackend:
    backend_id: str
    executable_name: str
    variant: str
    argv_prefix: tuple[str, ...]


REGISTERED_BACKENDS = {
    UNSHARE_USER_MAP_ROOT_NET: NetworkIsolationBackend(
        backend_id=UNSHARE_USER_MAP_ROOT_NET,
        executable_name="unshare",
        variant=UNSHARE_VARIANT,
        argv_prefix=("--user", "--map-root-user", "--net"),
    )
}


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _network_namespace_identity() -> str:
    try:
        return os.readlink("/proc/self/ns/net")
    except OSError:
        return "unavailable"


def _child_probe_program(port: int) -> str:
    return f"""
import json
import os
import socket
from pathlib import Path

result = {{
    "child_executed": True,
    "network_namespace": (
        os.readlink("/proc/self/ns/net")
        if Path("/proc/self/ns/net").exists()
        else "unavailable"
    ),
    "loopback_connect_succeeded": False,
    "loopback_error": "",
}}
try:
    with socket.create_connection(("127.0.0.1", {port}), timeout=1.5):
        result["loopback_connect_succeeded"] = True
except OSError as exc:
    result["loopback_error"] = type(exc).__name__ + ": " + str(exc)
print(json.dumps(result, sort_keys=True))
"""


def _run_probe_process(
    argv: Sequence[str],
    *,
    timeout_seconds: int,
    parent_namespace: str,
) -> JsonObject:
    result: JsonObject = {
        "argv_display": list(argv),
        "process_started": False,
        "exit_code": None,
        "timed_out": False,
        "stdout": "",
        "stderr": "",
        "child_executed": False,
        "parent_network_namespace": parent_namespace,
        "child_network_namespace": "unavailable",
        "namespace_changed": False,
        "loopback_connect_succeeded": None,
        "isolated_loopback_blocked": False,
        "network_namespace_isolation_verified": False,
    }
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        result["process_started"] = True
        result["timed_out"] = True
        result["stdout"] = str(exc.stdout or "")[-4000:]
        result["stderr"] = str(exc.stderr or "")[-4000:]
        return result
    except OSError as exc:
        result["stderr"] = f"{type(exc).__name__}: {_string(exc)}"
        return result

    result["process_started"] = True
    result["exit_code"] = completed.returncode
    result["stdout"] = completed.stdout[-4000:]
    result["stderr"] = completed.stderr[-4000:]

    payload: JsonObject = {}
    for line in reversed(completed.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("child_executed") is True:
            payload = candidate
            break

    if not payload:
        return result

    child_namespace = _string(payload.get("network_namespace")) or "unavailable"
    result["child_executed"] = True
    result["child_network_namespace"] = child_namespace
    result["namespace_changed"] = (
        parent_namespace != "unavailable"
        and child_namespace != "unavailable"
        and child_namespace != parent_namespace
    )
    result["loopback_connect_succeeded"] = bool(payload.get("loopback_connect_succeeded"))
    result["loopback_error"] = _string(payload.get("loopback_error"))
    result["isolated_loopback_blocked"] = payload.get("loopback_connect_succeeded") is False
    result["network_namespace_isolation_verified"] = (
        completed.returncode == 0
        and result["child_executed"] is True
        and result["namespace_changed"] is True
        and result["isolated_loopback_blocked"] is True
    )
    return result


def probe_registered_backends(
    *,
    timeout_seconds: int = DEFAULT_PROBE_TIMEOUT_SECONDS,
    python_executable: str | None = None,
) -> JsonObject:
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1")

    python_path = python_executable or sys.executable
    parent_namespace = _network_namespace_identity()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    port = int(server.getsockname()[1])
    stop = threading.Event()

    def accept_loop() -> None:
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                connection, _address = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with connection:
                try:
                    connection.sendall(b"ok")
                except OSError:
                    pass

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()

    try:
        program = _child_probe_program(port)
        baseline = _run_probe_process(
            [python_path, "-c", program],
            timeout_seconds=timeout_seconds,
            parent_namespace=parent_namespace,
        )
        baseline_ok = (
            baseline.get("exit_code") == 0
            and baseline.get("child_executed") is True
            and baseline.get("loopback_connect_succeeded") is True
        )

        candidates: list[JsonObject] = []
        for contract in REGISTERED_BACKENDS.values():
            executable = shutil.which(contract.executable_name)
            candidate: JsonObject = {
                "backend_id": contract.backend_id,
                "variant": contract.variant,
                "executable": executable or contract.executable_name,
                "executable_sha256": "",
                "available": executable is not None,
                "network_namespace_isolation_verified": False,
            }
            if executable:
                executable_path = Path(executable).resolve()
                candidate["executable"] = executable_path.as_posix()
                candidate["executable_sha256"] = _sha256_path(executable_path)
                candidate.update(
                    _run_probe_process(
                        [
                            executable_path.as_posix(),
                            *contract.argv_prefix,
                            python_path,
                            "-c",
                            program,
                        ],
                        timeout_seconds=timeout_seconds,
                        parent_namespace=parent_namespace,
                    )
                )
                candidate["network_namespace_isolation_verified"] = (
                    baseline_ok and candidate.get("network_namespace_isolation_verified") is True
                )
            candidates.append(candidate)
    finally:
        stop.set()
        server.close()
        thread.join(timeout=2)

    verified = [
        item for item in candidates if item.get("network_namespace_isolation_verified") is True
    ]
    selected = verified[0] if verified else {}

    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "baseline": baseline,
        "baseline_control_passed": baseline_ok,
        "parent_network_namespace": parent_namespace,
        "controlled_loopback_port": port,
        "candidates": candidates,
        "verified_candidate_count": len(verified),
        "verified_candidates": [
            {
                "backend_id": item["backend_id"],
                "variant": item["variant"],
                "executable": item["executable"],
                "executable_sha256": item["executable_sha256"],
            }
            for item in verified
        ],
        "selected_candidate": {
            "backend_id": selected.get("backend_id", ""),
            "variant": selected.get("variant", ""),
            "executable": selected.get("executable", ""),
            "executable_sha256": selected.get("executable_sha256", ""),
        },
        "network_isolation_scope_only": True,
        "external_filesystem_containment_enforced": False,
        "process_escape_prevention_enforced": False,
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def build_blocked_network_probe_report() -> JsonObject:
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "baseline_control_passed": True,
        "candidates": [],
        "verified_candidate_count": 0,
        "verified_candidates": [],
        "selected_candidate": {},
        "network_isolation_scope_only": True,
        "external_filesystem_containment_enforced": False,
        "process_escape_prevention_enforced": False,
        "decision_boundary": {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _verified_candidate(probe_report: Mapping[str, Any]) -> JsonObject:
    if _string(probe_report.get("schema_version")) != PROBE_SCHEMA_VERSION:
        return {}
    if probe_report.get("baseline_control_passed") is not True:
        return {}

    selected = _as_dict(probe_report.get("selected_candidate"))
    backend_id = _string(selected.get("backend_id"))
    contract = REGISTERED_BACKENDS.get(backend_id)
    if contract is None or _string(selected.get("variant")) != contract.variant:
        return {}

    matching = [
        _as_dict(item)
        for item in _as_list(probe_report.get("candidates"))
        if _string(_as_dict(item).get("backend_id")) == backend_id
        and _as_dict(item).get("network_namespace_isolation_verified") is True
    ]
    if len(matching) != 1:
        return {}

    candidate = matching[0]
    executable = Path(_string(candidate.get("executable")))
    digest = _string(candidate.get("executable_sha256"))
    if not executable.is_absolute() or not executable.is_file():
        return {}
    if not os.access(executable, os.X_OK):
        return {}
    if executable.name != contract.executable_name:
        return {}
    if not digest or _sha256_path(executable) != digest:
        return {}
    return candidate


def assess_network_boundary(
    *,
    require_network_isolation: bool,
    probe_report: Mapping[str, Any] | None = None,
) -> JsonObject:
    denied = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    if not require_network_isolation:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": NOT_REQUESTED,
            "backend": NO_VERIFIED_BACKEND,
            "backend_variant": "not_requested",
            "backend_executable": "",
            "backend_executable_sha256": "",
            "backend_verified": False,
            "verified_backends": [],
            NETWORK_ISOLATION_REQUIRED: False,
            NETWORK_ISOLATION_ENFORCED: False,
            PROOF_EXECUTION_ALLOWED: True,
            "capability_source": "registered_runtime_contract",
            "probe_report": {},
            "external_filesystem_containment_enforced": False,
            "process_escape_prevention_enforced": False,
            "reason": (
                "Network isolation was not required for this proof run; "
                "no network-containment claim is made."
            ),
            "decision_boundary": denied,
        }

    report = dict(probe_report) if probe_report is not None else probe_registered_backends()
    candidate = _verified_candidate(report)

    if candidate:
        backend_id = _string(candidate.get("backend_id"))
        return {
            "schema_version": SCHEMA_VERSION,
            "status": VERIFIED_BACKEND_AVAILABLE,
            "backend": backend_id,
            "backend_variant": _string(candidate.get("variant")),
            "backend_executable": _string(candidate.get("executable")),
            "backend_executable_sha256": _string(candidate.get("executable_sha256")),
            "backend_verified": True,
            "verified_backends": [backend_id],
            NETWORK_ISOLATION_REQUIRED: True,
            NETWORK_ISOLATION_ENFORCED: True,
            PROOF_EXECUTION_ALLOWED: True,
            "capability_source": "controlled_local_runtime_probe",
            "probe_report": report,
            "external_filesystem_containment_enforced": False,
            "process_escape_prevention_enforced": False,
            "reason": (
                "Network-isolated proof execution is allowed through a registered "
                "backend that passed the controlled loopback and namespace contract."
            ),
            "decision_boundary": denied,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": REQUIRED_UNAVAILABLE,
        "backend": NO_VERIFIED_BACKEND,
        "backend_variant": "none",
        "backend_executable": "",
        "backend_executable_sha256": "",
        "backend_verified": False,
        "verified_backends": [],
        NETWORK_ISOLATION_REQUIRED: True,
        NETWORK_ISOLATION_ENFORCED: False,
        PROOF_EXECUTION_ALLOWED: False,
        "capability_source": "controlled_local_runtime_probe",
        "probe_report": report,
        "external_filesystem_containment_enforced": False,
        "process_escape_prevention_enforced": False,
        "reason": (
            "Network-isolated proof execution was required, but no registered "
            "runtime backend passed the controlled containment contract; "
            "execution is blocked."
        ),
        "decision_boundary": denied,
    }


def build_network_isolated_argv(
    boundary: Mapping[str, Any],
    argv: Sequence[str],
) -> list[str]:
    command = [str(item) for item in argv]
    if not command or any(not item or "\x00" in item for item in command):
        raise ValueError("proof command argv must contain non-empty strings")
    if boundary.get("backend_verified") is not True:
        raise ValueError("network isolation backend is not verified")
    if boundary.get(NETWORK_ISOLATION_REQUIRED) is not True:
        raise ValueError("network isolation was not required")
    if boundary.get(NETWORK_ISOLATION_ENFORCED) is not True:
        raise ValueError("network isolation was not enforced")
    if boundary.get(PROOF_EXECUTION_ALLOWED) is not True:
        raise ValueError("proof execution is not allowed")

    backend_id = _string(boundary.get("backend"))
    contract = REGISTERED_BACKENDS.get(backend_id)
    if contract is None:
        raise ValueError(f"unsupported verified network backend: {backend_id}")
    if _string(boundary.get("backend_variant")) != contract.variant:
        raise ValueError("verified network backend variant does not match registry")

    executable = Path(_string(boundary.get("backend_executable")))
    expected_digest = _string(boundary.get("backend_executable_sha256"))
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("verified network backend executable is unavailable")
    if not os.access(executable, os.X_OK):
        raise ValueError("verified network backend executable is not executable")
    if executable.name != contract.executable_name:
        raise ValueError("verified network backend executable does not match registry")
    if not expected_digest or _sha256_path(executable) != expected_digest:
        raise ValueError("verified network backend executable identity changed")

    return [executable.as_posix(), *contract.argv_prefix, *command]


def render_markdown(boundary: Mapping[str, Any]) -> str:
    decision = _as_dict(boundary.get("decision_boundary"))
    probe = _as_dict(boundary.get("probe_report"))
    lines = [
        "# Network boundary assessment",
        "",
        f"- Schema: `{_string(boundary.get('schema_version'))}`",
        f"- Status: `{_string(boundary.get('status'))}`",
        f"- Backend: `{_string(boundary.get('backend'))}`",
        f"- Backend variant: `{_string(boundary.get('backend_variant'))}`",
        f"- Backend verified: `{str(boundary.get('backend_verified') is True).lower()}`",
        f"- Capability source: `{_string(boundary.get('capability_source'))}`",
        (
            "- Baseline loopback control passed: "
            f"`{str(probe.get('baseline_control_passed') is True).lower()}`"
        ),
        (
            "- Network isolation required: "
            f"`{str(boundary.get(NETWORK_ISOLATION_REQUIRED) is True).lower()}`"
        ),
        (
            "- Network isolation enforced: "
            f"`{str(boundary.get(NETWORK_ISOLATION_ENFORCED) is True).lower()}`"
        ),
        (
            "- Proof execution allowed: "
            f"`{str(boundary.get(PROOF_EXECUTION_ALLOWED) is True).lower()}`"
        ),
        "- External filesystem containment enforced: `false`",
        "- Process escape prevention enforced: `false`",
        "",
        "## Boundary",
        "",
        f"- Automation allowed: `{str(decision.get('automation_allowed') is True).lower()}`",
        (
            "- Patch application allowed: "
            f"`{str(decision.get('patch_application_allowed') is True).lower()}`"
        ),
        f"- Merge authorized: `{str(decision.get('merge_authorized') is True).lower()}`",
        (
            "- Semantic equivalence proven: "
            f"`{str(decision.get('semantic_equivalence_proven') is True).lower()}`"
        ),
        "",
        f"- Reason: {_string(boundary.get('reason'))}",
        "",
    ]
    return "\n".join(lines)


def write_boundary(boundary: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / BOUNDARY_JSON
    markdown_path = out_dir / BOUNDARY_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(boundary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(boundary), encoding="utf-8")
    return {
        "network_boundary_json": json_path.as_posix(),
        "network_boundary_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.network_boundary")
    parser.add_argument("--require-network-isolation", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    boundary = assess_network_boundary(
        require_network_isolation=args.require_network_isolation,
    )
    artifacts = write_boundary(boundary, out_dir=args.out_dir)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": boundary["status"],
                    "backend": boundary["backend"],
                    "backend_variant": boundary["backend_variant"],
                    "backend_verified": boundary["backend_verified"],
                    "artifacts": artifacts,
                    NETWORK_ISOLATION_REQUIRED: boundary[NETWORK_ISOLATION_REQUIRED],
                    NETWORK_ISOLATION_ENFORCED: boundary[NETWORK_ISOLATION_ENFORCED],
                    PROOF_EXECUTION_ALLOWED: boundary[PROOF_EXECUTION_ALLOWED],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
