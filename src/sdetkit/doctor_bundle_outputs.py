from __future__ import annotations

from pathlib import Path

REPORT_JSON = "doctor-report.json"
REPORT_MARKDOWN = "doctor-report.md"
REPORT_MANIFEST = "doctor-report-manifest.json"

BASE_OUTPUTS = (REPORT_JSON, REPORT_MARKDOWN, REPORT_MANIFEST)


def expected_doctor_bundle_outputs() -> tuple[str, ...]:
    """Return the deterministic base file set expected from a Doctor artifact bundle."""

    return BASE_OUTPUTS


def is_known_doctor_bundle_output(filename: str) -> bool:
    """Return whether a filename belongs to the base Doctor artifact bundle contract."""

    return filename in BASE_OUTPUTS


def missing_doctor_bundle_outputs(filenames: set[str]) -> tuple[str, ...]:
    """Return base bundle filenames missing from an observed artifact directory."""

    return tuple(filename for filename in BASE_OUTPUTS if filename not in filenames)


def unknown_doctor_bundle_outputs(filenames: set[str]) -> tuple[str, ...]:
    """Return unexpected filenames in stable order."""

    return tuple(sorted(filename for filename in filenames if filename not in BASE_OUTPUTS))


def doctor_bundle_directory_snapshot(path: str | Path) -> set[str]:
    """Return file names directly contained in a Doctor artifact directory."""

    target = Path(path)
    if not target.exists():
        return set()
    return {entry.name for entry in target.iterdir() if entry.is_file()}


def doctor_bundle_output_summary(filenames: set[str]) -> dict[str, object]:
    """Summarize observed bundle output names for logs and tests."""

    missing = missing_doctor_bundle_outputs(filenames)
    unknown = unknown_doctor_bundle_outputs(filenames)
    return {
        "expected": expected_doctor_bundle_outputs(),
        "observed": tuple(sorted(filenames)),
        "missing": missing,
        "unknown": unknown,
        "complete": not missing,
        "clean": not unknown,
    }
