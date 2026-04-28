#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path


DEFAULT_CHALLENGE_PROMPT = "workflow_execution_prompt.md"
DEFAULT_GUIDELINES_ZIP = "workflow_execution_guidelines_bundle.zip"
SCRIPT_DIR = Path(__file__).resolve().parent


def _script(name: str) -> str:
    return str(SCRIPT_DIR / name)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _file_meta(path: Path) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    payload: dict[str, object] = {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": digest,
    }
    if path.suffix.lower() == ".md":
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        heading = next((line.strip("# ").strip() for line in lines if line.startswith("#")), None)
        payload["line_count"] = len(lines)
        payload["first_heading"] = heading
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = [name for name in zf.namelist() if not name.endswith("/")]
        payload["entry_count"] = len(names)
        payload["entries_preview"] = names[:10]
        if len(names) > 25:
            raise ValueError(f"Zip entry_count {len(names)} exceeds max25 policy")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run business execution week-1 pipeline end-to-end.")
    parser.add_argument("--out-dir", default="build/business-execution")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--program-owner", default=None)
    parser.add_argument("--gtm-owner", default=None)
    parser.add_argument("--commercial-owner", default=None)
    parser.add_argument("--solutions-owner", default=None)
    parser.add_argument("--ops-owner", default=None)
    parser.add_argument(
        "--single-operator",
        default=None,
        help="Assign one operator to all owner roles in the week-1 bootstrap.",
    )
    parser.add_argument("--done", action="append", default=[])
    parser.add_argument("--challenge-prompt", default=None, help="Optional path to challenge prompt markdown.")
    parser.add_argument("--guidelines-zip", default=None, help="Optional path to aligned guidelines zip.")
    args = parser.parse_args(argv)

    challenge_prompt = args.challenge_prompt
    guidelines_zip = args.guidelines_zip

    # Auto-discover canonical input files to support a one-command execution path.
    if not challenge_prompt and Path(DEFAULT_CHALLENGE_PROMPT).exists():
        challenge_prompt = DEFAULT_CHALLENGE_PROMPT
    if not guidelines_zip and Path(DEFAULT_GUIDELINES_ZIP).exists():
        guidelines_zip = DEFAULT_GUIDELINES_ZIP

    if bool(challenge_prompt) ^ bool(guidelines_zip):
        raise ValueError(
            "External input policy requires both --challenge-prompt and --guidelines-zip together"
        )

    out_dir = Path(args.out_dir)
    week1_json = out_dir / "business-execution-week1.json"
    week1_memo = out_dir / "business-execution-week1-memo.md"
    progress_json = out_dir / "business-execution-week1-progress.json"
    progress_md = out_dir / "business-execution-week1-progress.md"
    history_jsonl = out_dir / "business-execution-week1-progress-history.jsonl"
    rollup_json = out_dir / "business-execution-week1-progress-rollup.json"
    next_json = out_dir / "business-execution-week1-next.json"
    next_md = out_dir / "business-execution-week1-next.md"
    handoff_json = out_dir / "business-execution-handoff.json"
    handoff_md = out_dir / "business-execution-handoff.md"
    escalation_json = out_dir / "business-execution-escalation.json"
    escalation_md = out_dir / "business-execution-escalation.md"
    followup_json = out_dir / "business-execution-followup.json"
    followup_md = out_dir / "business-execution-followup.md"
    followup_history_jsonl = out_dir / "business-execution-followup-history.jsonl"
    followup_rollup_json = out_dir / "business-execution-followup-rollup.json"
    continue_json = out_dir / "business-execution-continue.json"
    continue_md = out_dir / "business-execution-continue.md"
    horizon_json = out_dir / "business-execution-horizon.json"
    horizon_md = out_dir / "business-execution-horizon.md"
    inputs_json = out_dir / "business-execution-inputs.json"

    if challenge_prompt and not Path(challenge_prompt).exists():
        raise FileNotFoundError(f"Missing --challenge-prompt file: {challenge_prompt}")
    if guidelines_zip and not Path(guidelines_zip).exists():
        raise FileNotFoundError(f"Missing --guidelines-zip file: {guidelines_zip}")

    input_manifest = {
        "schema_version": "sdetkit.business-execution-inputs.v1",
        "challenge_prompt": _file_meta(Path(challenge_prompt)) if challenge_prompt else None,
        "guidelines_zip": _file_meta(Path(guidelines_zip)) if guidelines_zip else None,
    }
    inputs_json.parent.mkdir(parents=True, exist_ok=True)
    inputs_json.write_text(json.dumps(input_manifest, indent=2) + "\n", encoding="utf-8")

    py = sys.executable
    _run([py, _script("check_business_execution_inputs_contract.py"), "--artifact", str(inputs_json)])

    start_cmd = [
        py,
        _script("business_execution_start.py"),
        "--out-json",
        str(week1_json),
        "--out-memo",
        str(week1_memo),
    ]
    if args.start_date:
        start_cmd.extend(["--start-date", args.start_date])
    if args.single_operator:
        start_cmd.extend(["--single-operator", args.single_operator])
    for flag, value in (
        ("--program-owner", args.program_owner),
        ("--gtm-owner", args.gtm_owner),
        ("--commercial-owner", args.commercial_owner),
        ("--solutions-owner", args.solutions_owner),
        ("--ops-owner", args.ops_owner),
    ):
        if value:
            start_cmd.extend([flag, value])
    _run(start_cmd)

    _run([py, _script("check_business_execution_start_contract.py"), "--artifact", str(week1_json)])

    progress_cmd = [
        py,
        _script("business_execution_progress.py"),
        "--week1",
        str(week1_json),
        "--out-json",
        str(progress_json),
        "--out-md",
        str(progress_md),
        "--history",
        str(history_jsonl),
        "--history-rollup-out",
        str(rollup_json),
    ]
    for done_item in args.done:
        progress_cmd.extend(["--done", done_item])
    _run(progress_cmd)
    _run([py, _script("check_business_execution_progress_contract.py"), "--artifact", str(progress_json)])

    _run(
        [
            py,
            _script("business_execution_next.py"),
            "--progress",
            str(progress_json),
            "--out-json",
            str(next_json),
            "--out-md",
            str(next_md),
        ]
    )
    _run([py, _script("check_business_execution_next_contract.py"), "--artifact", str(next_json)])

    _run(
        [
            py,
            _script("business_execution_handoff.py"),
            "--week1",
            str(week1_json),
            "--progress",
            str(progress_json),
            "--rollup",
            str(rollup_json),
            "--next",
            str(next_json),
            "--out-json",
            str(handoff_json),
            "--out-md",
            str(handoff_md),
        ]
    )
    _run([py, _script("check_business_execution_handoff_contract.py"), "--artifact", str(handoff_json)])

    _run(
        [
            py,
            _script("business_execution_escalation.py"),
            "--week1",
            str(week1_json),
            "--progress",
            str(progress_json),
            "--next",
            str(next_json),
            "--handoff",
            str(handoff_json),
            "--out-json",
            str(escalation_json),
            "--out-md",
            str(escalation_md),
        ]
    )
    _run(
        [
            py,
            _script("check_business_execution_escalation_contract.py"),
            "--artifact",
            str(escalation_json),
        ]
    )
    _run(
        [
            py,
            _script("business_execution_followup.py"),
            "--progress",
            str(progress_json),
            "--next",
            str(next_json),
            "--escalation",
            str(escalation_json),
            "--out-json",
            str(followup_json),
            "--out-md",
            str(followup_md),
            "--history",
            str(followup_history_jsonl),
            "--history-rollup-out",
            str(followup_rollup_json),
        ]
    )
    _run(
        [
            py,
            _script("check_business_execution_followup_contract.py"),
            "--artifact",
            str(followup_json),
        ]
    )
    _run(
        [
            py,
            _script("business_execution_continue.py"),
            "--followup",
            str(followup_json),
            "--out-json",
            str(continue_json),
            "--out-md",
            str(continue_md),
        ]
    )
    _run(
        [
            py,
            _script("check_business_execution_continue_contract.py"),
            "--artifact",
            str(continue_json),
        ]
    )
    _run(
        [
            py,
            _script("business_execution_horizon.py"),
            "--week1",
            str(week1_json),
            "--progress",
            str(progress_json),
            "--followup",
            str(followup_json),
            "--out-json",
            str(horizon_json),
            "--out-md",
            str(horizon_md),
        ]
    )
    _run(
        [
            py,
            _script("check_business_execution_horizon_contract.py"),
            "--artifact",
            str(horizon_json),
        ]
    )

    print(f"business-execution-pipeline: wrote artifacts to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
