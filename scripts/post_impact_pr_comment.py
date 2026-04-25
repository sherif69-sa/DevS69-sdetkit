from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

MARKER = "<!-- impact-release-control -->"
DEFAULT_HTTP_TIMEOUT_SECONDS = 30


def _api_request(
    url: str, token: str, method: str = "GET", payload: dict[str, object] | None = None
) -> dict[str, object] | list[dict[str, object]]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "impact-release-control-bot",
        },
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _compose_comment_body(comment_markdown: str) -> str:
    return f"{MARKER}\n{comment_markdown.strip()}\n"


def _find_existing_comment_id(comments: list[dict[str, object]]) -> int | None:
    for item in comments:
        body = item.get("body")
        if isinstance(body, str) and MARKER in body:
            raw_id = item.get("id")
            if isinstance(raw_id, int):
                return raw_id
    return None


def upsert_comment(
    repo: str, pr_number: int, token: str, comment_markdown: str, dry_run: bool
) -> str:
    body = _compose_comment_body(comment_markdown)
    comments_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    if dry_run:
        return "dry_run"

    try:
        comments = _api_request(comments_url, token)
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return "forbidden"
        raise
    if not isinstance(comments, list):
        raise ValueError("unexpected GitHub API response while listing comments")

    existing_id = _find_existing_comment_id(comments)
    if existing_id is not None:
        try:
            _api_request(
                f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}",
                token,
                method="PATCH",
                payload={"body": body},
            )
            return "updated"
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                return "forbidden"
            raise

    try:
        _api_request(comments_url, token, method="POST", payload={"body": body})
        return "created"
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return "forbidden"
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or update impact PR comment on GitHub.")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--comment-file", default="build/impact-pr-comment.md")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.repo or not args.pr_number:
        raise SystemExit("repo/pr-number are required")

    comment_markdown = Path(args.comment_file).read_text(encoding="utf-8")
    status = upsert_comment(args.repo, args.pr_number, args.token, comment_markdown, args.dry_run)
    print(f"impact PR comment status: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
