from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.public_repo_eligibility.v1"

PERMISSIVE_LICENSES = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Unlicense",
        "CC0-1.0",
    }
)

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _normalized_license(value: str) -> str:
    aliases = {
        "apache": "Apache-2.0",
        "apache2": "Apache-2.0",
        "apache-2": "Apache-2.0",
        "bsd-2": "BSD-2-Clause",
        "bsd-3": "BSD-3-Clause",
        "cc0": "CC0-1.0",
        "mit": "MIT",
        "isc": "ISC",
        "unlicense": "Unlicense",
    }
    stripped = value.strip()
    return aliases.get(stripped.lower(), stripped)


def _valid_repo_url(url: str) -> bool:
    return url.startswith("https://github.com/") or url.startswith("https://gitlab.com/")


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def evaluate_public_repo_eligibility(
    *,
    repo_url: str,
    license_id: str,
    is_public: bool = True,
    repo_size: str = "small",
    has_no_ai_notice: bool = False,
    has_no_benchmark_notice: bool = False,
    has_security_sensitive_content: bool = False,
    has_malware_or_exploit_content: bool = False,
    owned_by_us: bool = False,
) -> dict[str, Any]:
    normalized_license = _normalized_license(license_id)
    blocked_reasons: list[str] = []
    reasons: list[str] = []

    if not repo_url.strip():
        blocked_reasons.append("missing repo_url")
    elif not _valid_repo_url(repo_url):
        blocked_reasons.append("repo_url must be a supported public forge URL")
    else:
        reasons.append("repo_url is a supported forge URL")

    if not is_public:
        blocked_reasons.append("repo must be public for public read-only trials")
    else:
        reasons.append("repo is public")

    if owned_by_us:
        reasons.append("repo is owned or controlled by the operator")
    elif normalized_license in PERMISSIVE_LICENSES:
        reasons.append(f"license is permissive: {normalized_license}")
    elif not normalized_license:
        blocked_reasons.append("license is missing")
    else:
        blocked_reasons.append(f"license is not in permissive allowlist: {normalized_license}")

    if repo_size not in {"small", "medium"}:
        blocked_reasons.append(f"repo size is not suitable for first trial: {repo_size}")
    else:
        reasons.append(f"repo size is suitable: {repo_size}")

    if has_no_ai_notice:
        blocked_reasons.append("repo contains no-AI usage notice")
    if has_no_benchmark_notice:
        blocked_reasons.append("repo contains no-benchmark usage notice")
    if has_security_sensitive_content:
        blocked_reasons.append("repo appears security-sensitive")
    if has_malware_or_exploit_content:
        blocked_reasons.append("repo appears to contain malware or exploit content")

    allowed = not blocked_reasons

    return {
        "schema_version": SCHEMA_VERSION,
        "repo_url": repo_url,
        "license_detected": normalized_license,
        "owned_by_us": owned_by_us,
        "is_public": is_public,
        "repo_size": repo_size,
        "allowed_for_read_only_trial": allowed,
        "reasons": reasons,
        "blocked_reasons": blocked_reasons,
        "rules": {
            "read_only_trial_only": True,
            "no_dependency_install": True,
            "no_test_execution": True,
            "no_target_repo_mutation": True,
            "no_pr_or_issue_opened_on_target": True,
            "no_endorsement_claim": True,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def write_public_repo_eligibility_artifact(
    *,
    repo_url: str,
    license_id: str,
    out: str | Path = "build/sdetkit/public-repo-eligibility.json",
    is_public: bool = True,
    repo_size: str = "small",
    has_no_ai_notice: bool = False,
    has_no_benchmark_notice: bool = False,
    has_security_sensitive_content: bool = False,
    has_malware_or_exploit_content: bool = False,
    owned_by_us: bool = False,
) -> dict[str, Any]:
    payload = evaluate_public_repo_eligibility(
        repo_url=repo_url,
        license_id=license_id,
        is_public=is_public,
        repo_size=repo_size,
        has_no_ai_notice=has_no_ai_notice,
        has_no_benchmark_notice=has_no_benchmark_notice,
        has_security_sensitive_content=has_security_sensitive_content,
        has_malware_or_exploit_content=has_malware_or_exploit_content,
        owned_by_us=owned_by_us,
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_public_repo_eligibility_text(payload: dict[str, Any]) -> str:
    lines = [
        "public_repo_eligibility_status=evaluated",
        f"repo_url={payload['repo_url']}",
        f"license_detected={payload['license_detected']}",
        f"allowed_for_read_only_trial={str(payload['allowed_for_read_only_trial']).lower()}",
        "reasons:",
        *[f"- {item}" for item in payload["reasons"]],
        "blocked_reasons:",
        *([f"- {item}" for item in payload["blocked_reasons"]] or ["- none"]),
        "rules:",
    ]
    rules = payload["rules"]
    lines.extend(f"- {name}={str(value).lower()}" for name, value in rules.items())
    lines.append("authority_boundary:")
    boundary = payload["authority_boundary"]
    lines.extend(f"- {field}={str(boundary[field]).lower()}" for field in AUTHORITY_FIELDS)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit public-repo-eligibility",
        description="Screen a public repository before any read-only adoption trial.",
    )
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--license", dest="license_id", required=True)
    parser.add_argument("--out", default="build/sdetkit/public-repo-eligibility.json")
    parser.add_argument(
        "--repo-size", choices=["small", "medium", "large", "huge"], default="small"
    )
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--owned-by-us", action="store_true")
    parser.add_argument("--has-no-ai-notice", action="store_true")
    parser.add_argument("--has-no-benchmark-notice", action="store_true")
    parser.add_argument("--has-security-sensitive-content", action="store_true")
    parser.add_argument("--has-malware-or-exploit-content", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_public_repo_eligibility_artifact(
        repo_url=ns.repo_url,
        license_id=ns.license_id,
        out=ns.out,
        is_public=not ns.private,
        repo_size=ns.repo_size,
        has_no_ai_notice=ns.has_no_ai_notice,
        has_no_benchmark_notice=ns.has_no_benchmark_notice,
        has_security_sensitive_content=ns.has_security_sensitive_content,
        has_malware_or_exploit_content=ns.has_malware_or_exploit_content,
        owned_by_us=ns.owned_by_us,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_public_repo_eligibility_text(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
