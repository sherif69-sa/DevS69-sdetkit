from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_HTTP_TIMEOUT_SECONDS = 30
DEFAULT_REQUIRED_CHECKS = (
    "CI / Full CI lane (pull_request)",
    "maintenance-autopilot / autopilot (pull_request)",
)


def _request(
    *,
    token: str,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} {method} {url}: {body}") from exc
    if not text:
        return None
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply branch protection policy to a GitHub branch."
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--token", required=True)
    parser.add_argument(
        "--required-check",
        action="append",
        default=[],
        help="Required status check context (repeatable).",
    )
    parser.add_argument(
        "--required-approving-review-count",
        type=int,
        default=1,
        help="Number of approving reviews required before merge.",
    )
    parser.add_argument(
        "--require-code-owner-reviews",
        action="store_true",
        default=False,
        help="Require CODEOWNERS approval before merge.",
    )
    parser.add_argument(
        "--enforce-admins",
        action="store_true",
        default=False,
        help="Apply pull request restrictions to admins as well.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved branch-protection payload and skip GitHub API write.",
    )
    args = parser.parse_args(argv)

    checks = args.required_check or list(DEFAULT_REQUIRED_CHECKS)
    payload = {
        "required_status_checks": {
            "strict": True,
            "checks": [{"context": c} for c in checks],
        },
        "enforce_admins": args.enforce_admins,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": args.require_code_owner_reviews,
            "required_approving_review_count": args.required_approving_review_count,
        },
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_conversation_resolution": True,
        "lock_branch": False,
        "allow_fork_syncing": True,
    }
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    url = f"https://api.github.com/repos/{args.owner}/{args.repo}/branches/{args.branch}/protection"
    _request(token=args.token, method="PUT", url=url, payload=payload)
    print(f"Branch protection enforced for {args.owner}/{args.repo}:{args.branch}")
    print(f"Required checks: {checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
