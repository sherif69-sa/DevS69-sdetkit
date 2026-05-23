from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.network_boundary.v1"
DEFAULT_OUT_DIR = Path("build") / "network-boundary"
BOUNDARY_JSON = "network-boundary.json"
BOUNDARY_MD = "network-boundary.md"

NETWORK_ISOLATION_REQUIRED = "_".join(("network", "isolation", "required"))
NETWORK_ISOLATION_ENFORCED = "_".join(("network", "isolation", "enforced"))
PROOF_EXECUTION_ALLOWED = "_".join(("proof", "execution", "allowed"))

NOT_REQUESTED = "_".join(("not", "requested"))
REQUIRED_UNAVAILABLE = "_".join(("required", "unavailable"))
NO_VERIFIED_BACKEND = "_".join(("no", "verified", "backend"))

JsonObject = dict[str, Any]


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def assess_network_boundary(*, require_network_isolation: bool) -> JsonObject:
    if require_network_isolation:
        status = REQUIRED_UNAVAILABLE
        proof_execution_allowed = False
        reason = (
            "Network-isolated proof execution was required, but no runtime "
            "containment backend has a verified contract; execution is blocked."
        )
    else:
        status = NOT_REQUESTED
        proof_execution_allowed = True
        reason = (
            "Network isolation was not required for this proof run; "
            "no network-containment claim is made."
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "backend": NO_VERIFIED_BACKEND,
        "backend_verified": False,
        "verified_backends": [],
        NETWORK_ISOLATION_REQUIRED: require_network_isolation,
        NETWORK_ISOLATION_ENFORCED: False,
        PROOF_EXECUTION_ALLOWED: proof_execution_allowed,
        "capability_source": "registered_runtime_contract",
        "operator_probe_observation": (
            "A separate operator probe observed partial namespace restriction, "
            "but no backend meets the verified containment contract."
        ),
        "reason": reason,
        "decision_boundary": {
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def render_markdown(boundary: Mapping[str, Any]) -> str:
    decision = boundary.get("decision_boundary", {})
    if not isinstance(decision, dict):
        decision = {}

    lines = [
        "# Network boundary assessment",
        "",
        f"- Schema: `{_string(boundary.get('schema_version'))}`",
        f"- Status: `{_string(boundary.get('status'))}`",
        f"- Backend: `{_string(boundary.get('backend'))}`",
        f"- Backend verified: `{str(_bool(boundary.get('backend_verified'))).lower()}`",
        (
            "- Network isolation required: "
            f"`{str(_bool(boundary.get(NETWORK_ISOLATION_REQUIRED))).lower()}`"
        ),
        (
            "- Network isolation enforced: "
            f"`{str(_bool(boundary.get(NETWORK_ISOLATION_ENFORCED))).lower()}`"
        ),
        (
            "- Proof execution allowed: "
            f"`{str(_bool(boundary.get(PROOF_EXECUTION_ALLOWED))).lower()}`"
        ),
        "",
        "## Boundary",
        "",
        f"- Automation allowed: `{str(_bool(decision.get('automation_allowed'))).lower()}`",
        f"- Merge authorized: `{str(_bool(decision.get('merge_authorized'))).lower()}`",
        (
            "- Semantic equivalence proven: "
            f"`{str(_bool(decision.get('semantic_equivalence_proven'))).lower()}`"
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
