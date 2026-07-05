from __future__ import annotations

import argparse
import json
import platform
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

SCHEMA_VERSION = "sdetkit.ci_failure_summary.v1"
DEFAULT_OUT_DIR = Path("build") / "full-suite-failure-summary"
SUMMARY_JSON = "full-suite-failure-summary.json"
SUMMARY_MD = "full-suite-failure-summary.md"

JsonObject = dict[str, Any]


def _text(value: Any) -> str:
    return str(value or "").replace("\r", " ").strip()


def _compact(value: Any, *, limit: int = 600) -> str:
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _load_junit_root(path: Path) -> tuple[ET.Element | None, str | None]:
    if not path.exists():
        return None, "junit_xml_missing"
    if path.stat().st_size == 0:
        return None, "junit_xml_empty"
    try:
        return ET.parse(path).getroot(), None
    except ET.ParseError:
        return None, "junit_xml_malformed"


def _outcome(testcase: ET.Element) -> str:
    if testcase.find("failure") is not None:
        return "failed"
    if testcase.find("error") is not None:
        return "error"
    if testcase.find("skipped") is not None:
        return "skipped"
    return "passed"


def _failure_node(testcase: ET.Element) -> ET.Element | None:
    failure = testcase.find("failure")
    if failure is not None:
        return failure
    return testcase.find("error")


def _first_failure(testcases: list[ET.Element]) -> JsonObject | None:
    for index, testcase in enumerate(testcases, start=1):
        outcome = _outcome(testcase)
        if outcome not in {"failed", "error"}:
            continue
        node = _failure_node(testcase)
        return {
            "index": index,
            "outcome": outcome,
            "classname": _compact(testcase.attrib.get("classname"), limit=300),
            "name": _compact(testcase.attrib.get("name"), limit=300),
            "message": _compact(node.attrib.get("message") if node is not None else ""),
            "text_excerpt": _compact(node.text if node is not None else "", limit=1200),
        }
    return None


def build_failure_summary(
    *,
    junit_xml: Path,
    workflow: str,
    job: str,
    run_id: str,
    head_sha: str,
    command: str,
    event_name: str,
    ref_name: str,
) -> JsonObject:
    root, load_error = _load_junit_root(junit_xml)
    source = {
        "workflow": _text(workflow),
        "job": _text(job),
        "run_id": _text(run_id),
        "head_sha": _text(head_sha),
        "event_name": _text(event_name),
        "ref_name": _text(ref_name),
        "command": _text(command),
        "input_kind": "junit_xml",
        "input_read_only": True,
        "commands_executed_by_reader": False,
    }

    if load_error is not None or root is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": load_error,
            "source": source,
            "environment": _environment(),
            "summary": {
                "testcase_count": 0,
                "passed": 0,
                "failed": 0,
                "error": 0,
                "skipped": 0,
                "failure_observed": False,
            },
            "first_failure": None,
            "decision_boundary": _decision_boundary(),
        }

    testcases = list(root.iter("testcase"))
    outcomes = Counter(_outcome(testcase) for testcase in testcases)
    first_failure = _first_failure(testcases)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failure_observed" if first_failure else "no_failure_observed",
        "source": source,
        "environment": _environment(),
        "summary": {
            "testcase_count": len(testcases),
            "passed": outcomes["passed"],
            "failed": outcomes["failed"],
            "error": outcomes["error"],
            "skipped": outcomes["skipped"],
            "failure_observed": first_failure is not None,
        },
        "first_failure": first_failure,
        "decision_boundary": _decision_boundary(),
    }


def _environment() -> JsonObject:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def _decision_boundary() -> JsonObject:
    return {
        "diagnostic_only": True,
        "flaky_classification_performed": False,
        "automatic_quarantine_allowed": False,
        "automatic_rerun_allowed": False,
        "failure_suppression_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    source = dict(report.get("source", {}))
    summary = dict(report.get("summary", {}))
    first = report.get("first_failure")
    boundary = dict(report.get("decision_boundary", {}))
    lines = [
        "# Full-suite failure summary",
        "",
        f"- Status: `{_text(report.get('status'))}`",
        f"- Workflow: `{_text(source.get('workflow'))}`",
        f"- Job: `{_text(source.get('job'))}`",
        f"- Command: `{_text(source.get('command'))}`",
        f"- Testcases: `{int(summary.get('testcase_count', 0))}`",
        f"- Failed: `{int(summary.get('failed', 0))}`",
        f"- Errors: `{int(summary.get('error', 0))}`",
        f"- Skipped: `{int(summary.get('skipped', 0))}`",
        "",
    ]
    if isinstance(first, Mapping):
        lines.extend(
            [
                "## First failure",
                "",
                f"- Outcome: `{_text(first.get('outcome'))}`",
                f"- Class: `{_text(first.get('classname'))}`",
                f"- Name: `{_text(first.get('name'))}`",
                f"- Message: `{_text(first.get('message'))}`",
                "",
                "```text",
                _text(first.get("text_excerpt")),
                "```",
                "",
            ]
        )
    else:
        lines.extend(["## First failure", "", "No failed or errored testcase was observed.", ""])

    lines.extend(
        [
            "## Boundary",
            "",
            f"- Diagnostic only: `{str(bool(boundary.get('diagnostic_only'))).lower()}`",
            (
                "- Flaky classification performed: "
                f"`{str(bool(boundary.get('flaky_classification_performed'))).lower()}`"
            ),
            (
                "- Failure suppression allowed: "
                f"`{str(bool(boundary.get('failure_suppression_allowed'))).lower()}`"
            ),
            f"- Automation allowed: `{str(bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(bool(boundary.get('merge_authorized'))).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], *, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SUMMARY_JSON).write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / SUMMARY_MD).write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.ci_failure_summary")
    parser.add_argument("--junit-xml", type=Path, required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--ref-name", required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_failure_summary(
        junit_xml=args.junit_xml,
        workflow=args.workflow,
        job=args.job,
        run_id=args.run_id,
        head_sha=args.head_sha,
        command=args.command,
        event_name=args.event_name,
        ref_name=args.ref_name,
    )
    write_report(report, out_dir=args.out_dir)
    output = {
        "status": report["status"],
        "artifact_written": True,
        "failure_observed": bool(dict(report["summary"]).get("failure_observed")),
    }
    if args.format == "json":
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        for key, value in output.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
