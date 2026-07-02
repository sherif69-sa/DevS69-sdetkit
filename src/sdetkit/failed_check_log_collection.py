from __future__ import annotations

import json
import sys

from sdetkit import _failed_check_log_collection_core as _core
from sdetkit.pr_quality_required_terminal import (
    collect_and_merge_terminal_snapshot_from_environment,
)

# Preserve the established module-level helper surface while keeping terminal
# orchestration outside the collector implementation.
for _name in dir(_core):
    if not _name.startswith("__") and _name != "main":
        globals()[_name] = getattr(_core, _name)


def main(argv: list[str] | None = None) -> int:
    args = _core.build_parser().parse_args(argv)
    if args.sanitize_annotations_json is not None:
        if args.annotation_log_target is None or args.annotation_json_target is None:
            raise SystemExit("annotation log and JSON targets are required for sanitization")
        report = _core.sanitize_check_run_annotations(
            raw_annotations_json=args.sanitize_annotations_json,
            annotation_log_target=args.annotation_log_target,
            annotation_json_target=args.annotation_json_target,
        )
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0

    if args.checks_json is None:
        raise SystemExit("--checks-json is required unless sanitizing annotations")
    collect_and_merge_terminal_snapshot_from_environment(
        checks_json=args.checks_json,
        out_dir=args.out_dir,
    )
    manifest = _core.write_failed_check_log_artifacts(
        checks_json=args.checks_json,
        out_dir=args.out_dir,
        write_script=not bool(args.no_script),
    )
    sys.stdout.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
