from __future__ import annotations

import argparse
import base64
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sdetkit.pr_quality_action_report import (
    render_pr_quality_artifact_index_html,
)

JsonObject = dict[str, Any]

_EMBEDDED_ARTIFACT_SPECS = (
    (
        "pr-review-dashboard.html",
        "text/html;charset=utf-8",
        "review_html_path",
    ),
    (
        "pr-review-summary.md",
        "text/markdown;charset=utf-8",
        "review_summary_path",
    ),
    (
        "pr-review-model.json",
        "application/json;charset=utf-8",
        "review_model_path",
    ),
    (
        "pr-review-artifacts-manifest.json",
        "application/json;charset=utf-8",
        "review_manifest_path",
    ),
    (
        "pr-comment-body.md",
        "text/markdown;charset=utf-8",
        "comment_body_path",
    ),
)


class _EvidencePayloadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_payload = False
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        self._inside_payload = (
            attributes.get("id") == "evidenceData" and attributes.get("type") == "application/json"
        )

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._inside_payload:
            self._inside_payload = False

    def handle_data(self, data: str) -> None:
        if self._inside_payload:
            self.parts.append(data)


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href:
            self.hrefs.append(href)


def _read_json_object(path: Path) -> JsonObject:
    if not path.is_file():
        raise ValueError(f"required JSON file is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"required artifact file is missing: {path}")
    return path.read_text(encoding="utf-8")


def _embedded_sources(
    *,
    review_model_path: Path,
    review_summary_path: Path,
    review_html_path: Path,
    review_manifest_path: Path,
    comment_body_path: Path,
) -> JsonObject:
    paths = {
        "review_model_path": review_model_path,
        "review_summary_path": review_summary_path,
        "review_html_path": review_html_path,
        "review_manifest_path": review_manifest_path,
        "comment_body_path": comment_body_path,
    }
    return {
        artifact_path: {
            "mime_type": mime_type,
            "content": _read_text(paths[path_key]),
        }
        for artifact_path, mime_type, path_key in _EMBEDDED_ARTIFACT_SPECS
    }


def _extract_evidence_payload(html: str) -> JsonObject:
    parser = _EvidencePayloadParser()
    parser.feed(html)
    if not parser.parts:
        raise ValueError("generated index has no evidenceData JSON payload")
    payload = json.loads("".join(parser.parts))
    if not isinstance(payload, dict):
        raise ValueError("generated evidenceData payload is not an object")
    return payload


def _relative_links(html: str) -> list[str]:
    parser = _LinkCollector()
    parser.feed(html)
    relative: list[str] = []
    for href in parser.hrefs:
        parsed = urlparse(href)
        if href.startswith("#"):
            continue
        if parsed.scheme in {"http", "https", "mailto"}:
            continue
        relative.append(href)
    return relative


def refresh_pr_quality_artifact_index(
    *,
    review_model_path: Path,
    review_summary_path: Path,
    review_html_path: Path,
    review_manifest_path: Path,
    comment_body_path: Path,
    out: Path,
) -> JsonObject:
    model = _read_json_object(review_model_path)
    sources = _embedded_sources(
        review_model_path=review_model_path,
        review_summary_path=review_summary_path,
        review_html_path=review_html_path,
        review_manifest_path=review_manifest_path,
        comment_body_path=comment_body_path,
    )
    html = render_pr_quality_artifact_index_html(
        model,
        embedded_artifacts=sources,
    )

    payload = _extract_evidence_payload(html)
    embedded = payload.get("embedded_artifacts")
    if not isinstance(embedded, dict):
        raise ValueError("generated index has no embedded_artifacts object")

    expected_paths = set(sources)
    observed_paths = set(embedded)
    if observed_paths != expected_paths:
        raise ValueError(
            "embedded artifact path mismatch: "
            f"expected={sorted(expected_paths)} "
            f"observed={sorted(observed_paths)}"
        )

    verified: list[JsonObject] = []
    for artifact_path in sorted(expected_paths):
        source = sources[artifact_path]
        item = embedded.get(artifact_path)
        if not isinstance(item, dict):
            raise ValueError(f"embedded artifact entry is invalid: {artifact_path}")

        content = str(source["content"])
        source_bytes = content.encode("utf-8")
        encoded = item.get("content_base64")
        if not isinstance(encoded, str):
            raise ValueError(f"embedded artifact has no Base64 content: {artifact_path}")
        decoded = base64.b64decode(encoded, validate=True)
        digest = hashlib.sha256(source_bytes).hexdigest()

        if decoded != source_bytes:
            raise ValueError(f"embedded artifact bytes differ from source: {artifact_path}")
        if item.get("sha256") != digest:
            raise ValueError(f"embedded artifact digest differs from source: {artifact_path}")
        if item.get("size_bytes") != len(source_bytes):
            raise ValueError(f"embedded artifact size differs from source: {artifact_path}")
        if item.get("mime_type") != source["mime_type"]:
            raise ValueError(f"embedded artifact MIME type differs from source: {artifact_path}")

        verified.append(
            {
                "path": artifact_path,
                "size_bytes": len(source_bytes),
                "sha256": digest,
                "mime_type": source["mime_type"],
                "source_match": True,
            }
        )

    relative_links = _relative_links(html)
    if relative_links:
        raise ValueError(
            "generated standalone index contains relative links: " + ", ".join(relative_links)
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8", newline="\n")

    return {
        "schema_version": ("sdetkit.pr_quality.artifact_index_refresh.v1"),
        "status": "passed",
        "out": out.as_posix(),
        "embedded_artifact_count": len(verified),
        "embedded_artifact_mismatch_count": 0,
        "relative_artifact_link_count": 0,
        "artifacts": verified,
        "reporting_only": True,
        "patch_automation": False,
        "security_dismissal": False,
        "merge_authorization": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_artifact_index")
    parser.add_argument("--review-model", type=Path, required=True)
    parser.add_argument("--review-summary", type=Path, required=True)
    parser.add_argument("--review-html", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--comment-body", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = refresh_pr_quality_artifact_index(
        review_model_path=args.review_model,
        review_summary_path=args.review_summary,
        review_html_path=args.review_html,
        review_manifest_path=args.review_manifest,
        comment_body_path=args.comment_body,
        out=args.out,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print("self_contained_index_refresh=passed")
    print(f"embedded_artifact_match_count={result['embedded_artifact_count']}")
    print("relative_artifact_link_count=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
