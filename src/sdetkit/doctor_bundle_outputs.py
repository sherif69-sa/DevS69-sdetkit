from __future__ import annotations

from pathlib import Path

REPORT_JSON = "doctor-report.json"
REPORT_MARKDOWN = "doctor-report.md"
REPORT_MANIFEST = "doctor-report-manifest.json"
EXTRA_JSON = "failure-vector.json"

BASE_OUTPUTS = (REPORT_JSON, REPORT_MARKDOWN, REPORT_MANIFEST)
EXTRA_OUTPUTS = (EXTRA_JSON,)
ALL_OUTPUTS = (*BASE_OUTPUTS, *EXTRA_OUTPUTS)


def expected_doctor_bundle_outputs(*, include_extra: bool = False) -> tuple[str, ...]:
    """Return the deterministic file set expected from a Doctor artifact bundle."""

    if include_extra:
        return ALL_OUTPUTS
    return BASE_OUTPUTS


def is_known_doctor_bundle_output(filename: str) -> bool:
    """Return whether a filename belongs to the Doctor artifact bundle contract."""

    return filename in ALL_OUTPUTS


def missing_doctor_bundle_outputs(
    filenames: set[str],
    *,
    include_extra: bool = False,
) -> tuple[str, ...]:
    """Return bundle filenames missing from an observed artifact directory."""

    expected = expected_doctor_bundle_outputs(include_extra=include_extra)
    return tuple(filename for filename in expected if filename not in filenames)


def unknown_doctor_bundle_outputs(filenames: set[str]) -> tuple[str, ...]:
    """Return unexpected filenames in stable order."""

    return tuple(sorted(filename for filename in filenames if not is_known_doctor_bundle_output(filename)))


def doctor_bundle_directory_snapshot(path: str | Path) -> set[str]:
    """Return file names directly contained in a Doctor artifact directory."""

    target = Path(path)
    if not target.exists():
        return set()
    return {entry.name for entry in target.iterdir() if entry.is_file()}


def doctor_bundle_output_summary(
    filenames: set[str],
    *,
    include_extra: bool = False,
) -> dict[str, object]:
    """Summarize observed bundle output names for logs and tests."""

    missing = missing_doctor_bundle_outputs(filenames, include_extra=include_extra)
    unknown = unknown_doctor_bundle_outputs(filenames)
    return {
        "expected": expected_doctor_bundle_outputs(include_extra=include_extra),
        "observed": tuple(sorted(filenames)),
        "missing": missing,
        "unknown": unknown,
        "complete": not missing,
        "clean": not unknown,
    }
