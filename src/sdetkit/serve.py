from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import review

SERVE_CONTRACT_VERSION = "sdetkit.serve.contract.v1"
_MAX_BODY_BYTES = 1_048_576


class RequestValidationError(ValueError):
    """Raised when a review API request is syntactically valid JSON but fails validation."""


def _default_out_dir(target: Path) -> Path:
    return Path(".sdetkit") / "review" / review._safe_slug(target.resolve().name)


def _build_error(
    *, code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "error",
        "contract_version": SERVE_CONTRACT_VERSION,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        payload["error"]["details"] = details
    return payload


def _parse_review_request(body: bytes) -> dict[str, Any]:
    if not body:
        raise RequestValidationError(
            "Request body must be valid JSON object with a required 'path' field."
        )
    try:
        raw = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestValidationError(f"Invalid JSON body: {exc}") from exc
    if not isinstance(raw, dict):
        raise RequestValidationError("Request body must be a JSON object.")

    path = raw.get("path")
    if not isinstance(path, str) or not path.strip():
        raise RequestValidationError("Field 'path' is required and must be a non-empty string.")

    profile = raw.get("profile", "release")
    if profile not in review.REVIEW_PROFILES:
        raise RequestValidationError(
            "Field 'profile' must be one of: " + ", ".join(sorted(review.REVIEW_PROFILES))
        )

    response_mode = raw.get("response_mode", "full")
    if response_mode not in {"full", "operator-summary"}:
        raise RequestValidationError(
            "Field 'response_mode' must be either 'full' or 'operator-summary'."
        )

    no_workspace = raw.get("no_workspace", False)
    if not isinstance(no_workspace, bool):
        raise RequestValidationError("Field 'no_workspace' must be a boolean.")

    workspace_root = raw.get("workspace_root", ".sdetkit/workspace")
    if not isinstance(workspace_root, str) or not workspace_root.strip():
        raise RequestValidationError("Field 'workspace_root' must be a non-empty string.")

    out_dir = raw.get("out_dir")
    if out_dir is not None and (not isinstance(out_dir, str) or not out_dir.strip()):
        raise RequestValidationError("Field 'out_dir' must be a non-empty string when provided.")
    work_id = raw.get("work_id", "")
    if not isinstance(work_id, str):
        raise RequestValidationError("Field 'work_id' must be a string when provided.")
    work_context = raw.get("work_context", {})
    if not isinstance(work_context, dict):
        raise RequestValidationError("Field 'work_context' must be an object when provided.")
    normalized_work_context: dict[str, str] = {}
    for key, value in work_context.items():
        normalized_work_context[str(key)] = str(value)
    code_scan_json = raw.get("code_scan_json")
    if code_scan_json is not None and (
        not isinstance(code_scan_json, str) or not code_scan_json.strip()
    ):
        raise RequestValidationError(
            "Field 'code_scan_json' must be a non-empty string when provided."
        )

    return {
        "path": path,
        "profile": profile,
        "response_mode": response_mode,
        "no_workspace": no_workspace,
        "workspace_root": workspace_root,
        "out_dir": out_dir,
        "work_id": work_id.strip(),
        "work_context": normalized_work_context,
        "code_scan_json": code_scan_json.strip() if isinstance(code_scan_json, str) else None,
    }


def _run_review_request(req: dict[str, Any]) -> dict[str, Any]:
    target = Path(req["path"])
    if not target.exists():
        raise FileNotFoundError(f"Review target does not exist: {target}")

    out_dir = Path(req["out_dir"]) if req["out_dir"] else _default_out_dir(target)
    rc, payload, json_path, txt_path = review.run_review(
        target=target,
        out_dir=out_dir,
        workspace_root=Path(req["workspace_root"]),
        profile=req["profile"],
        no_workspace=bool(req["no_workspace"]),
        work_id=str(req.get("work_id", "")).strip(),
        work_context=dict(req.get("work_context", {})),
        code_scan_json=Path(req["code_scan_json"]) if req.get("code_scan_json") else None,
    )
    operator_summary = payload.get("operator_summary", {})
    result: dict[str, Any] = {
        "exit_code": rc,
        "review_status": payload.get("review_status"),
        "status": payload.get("status"),
        "severity": payload.get("severity"),
        "profile": payload.get("profile", {}).get("name"),
        "contract_version": payload.get("contract_version"),
        "operator_summary": operator_summary,
        "artifacts": {
            "review_json": json_path.as_posix(),
            "review_text": txt_path.as_posix(),
            **(
                payload.get("artifact_index", {})
                if isinstance(payload.get("artifact_index", {}), dict)
                else {}
            ),
        },
    }
    if "workspace" in payload:
        result["workspace"] = payload["workspace"]
    if req["response_mode"] == "full":
        result["payload"] = payload
    return {
        "status": "ok",
        "contract_version": SERVE_CONTRACT_VERSION,
        "result": result,
    }


def _make_handler() -> type[BaseHTTPRequestHandler]:
    class SdetkitHandler(BaseHTTPRequestHandler):
        server_version = "SDETKitServe/1.0"

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            wire = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(wire)))
            self.end_headers()
            self.wfile.write(wire)

        def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/healthz":
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    _build_error(code="not_found", message=f"Route not found: {self.path}"),
                )
                return
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "contract_version": SERVE_CONTRACT_VERSION,
                    "service": "sdetkit",
                    "review_contract_version": review.REVIEW_CONTRACT_VERSION,
                    "endpoints": {
                        "health": "/healthz",
                        "review": "/v1/review",
                    },
                },
            )

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/review":
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    _build_error(code="not_found", message=f"Route not found: {self.path}"),
                )
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > _MAX_BODY_BYTES:
                self._send_json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    _build_error(
                        code="request_too_large",
                        message=f"Request body exceeds {_MAX_BODY_BYTES} bytes.",
                    ),
                )
                return
            body = self.rfile.read(content_length)
            try:
                req = _parse_review_request(body)
                payload = _run_review_request(req)
            except RequestValidationError as exc:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    _build_error(code="validation_error", message=str(exc)),
                )
                return
            except FileNotFoundError as exc:
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    _build_error(code="path_not_found", message=str(exc)),
                )
                return
            except ValueError as exc:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    _build_error(code="review_invalid_request", message=str(exc)),
                )
                return
            except Exception as exc:  # pragma: no cover
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    _build_error(code="internal_error", message=str(exc)),
                )
                return

            self._send_json(HTTPStatus.OK, payload)

    return SdetkitHandler


def build_server(*, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _make_handler())


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit serve",
        description="Run SDETKit as a local deterministic review API service.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765).")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    server = build_server(host=str(ns.host), port=int(ns.port))
    print(f"sdetkit serve listening on http://{ns.host}:{ns.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
