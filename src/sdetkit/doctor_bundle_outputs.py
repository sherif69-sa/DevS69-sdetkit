from __future__ import annotations

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
