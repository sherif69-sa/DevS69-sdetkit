from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sdetkit import cli


@pytest.mark.parametrize("args", [[], ["--dev"], ["--dev", "--ci"]])
def test_report_argument_defaults_preserve_inner_arguments(args):
    assert cli._split_doctor_report_contract_args(args) == (False, "text", None, None, None, args)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--report-contract"], (True, "text", None, None, None, [])),
        (["--json"], (False, "json", None, None, None, [])),
        (["--format", "md"], (False, "md", None, None, None, [])),
        (["--format=markdown"], (False, "markdown", None, None, None, [])),
        (["--out", "a.md"], (False, "text", "a.md", None, None, [])),
        (["--out=a.json"], (False, "text", "a.json", None, None, [])),
        (["--report-artifact-dir", "bundle"], (False, "text", None, "bundle", None, [])),
        (["--report-artifact-dir=bundle"], (False, "text", None, "bundle", None, [])),
        (["--failure-vector-bundle", "v.json"], (False, "text", None, None, "v.json", [])),
        (["--failure-vector-bundle=v.json"], (False, "text", None, None, "v.json", [])),
        (
            ["--dev", "--report-contract", "--format=json", "--out=out", "--ci"],
            (True, "json", "out", None, None, ["--dev", "--ci"]),
        ),
    ],
)
def test_report_argument_values_and_forms(args, expected):
    assert cli._split_doctor_report_contract_args(args) == expected


@pytest.mark.parametrize(
    "flag", ["--format", "--out", "--report-artifact-dir", "--failure-vector-bundle"]
)
def test_report_argument_missing_value_is_usage_error(flag):
    with pytest.raises(SystemExit) as exc:
        cli._split_doctor_report_contract_args([flag])
    assert exc.value.code == 2


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ([], (None, "auto", [])),
        (["url", "--retries", "2"], (None, "auto", ["url", "--retries", "2"])),
        (["--cassette", "c.json"], ("c.json", "auto", [])),
        (["--cassette=c.json", "url"], ("c.json", "auto", ["url"])),
        (["--cassette-mode", "record", "url"], (None, "record", ["url"])),
        (["--cassette-mode=replay"], (None, "replay", [])),
        (["--cassette", "a", "--cassette=b"], ("b", "auto", [])),
        (["--cassette-mode=record", "--cassette-mode", "replay"], (None, "replay", [])),
    ],
)
def test_cassette_argument_forms_preserve_unrelated_values(args, expected):
    assert cli._split_cassette_args(args) == expected


@pytest.mark.parametrize("value", ["", "hello", "café\n", "line1\nline2\n"])
def test_report_digest_uses_utf8_bytes(value):
    assert cli._sha256_text(value) == hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_pretty_json_is_sorted_indented_and_newline_terminated():
    assert cli._json_dumps_pretty({"z": 2, "a": 1}) == '{\n  "a": 1,\n  "z": 2\n}\n'


@pytest.mark.parametrize("payload", [[], None, "text", 42, True])
def test_failure_vector_loader_rejects_non_objects(tmp_path, payload):
    path = tmp_path / "vector.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        cli._load_failure_vector_bundle(str(path))


def test_failure_vector_loader_preserves_object(tmp_path):
    path = tmp_path / "vector.json"
    payload = {"schema_version": "test", "failures": [{"reason": "café"}]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cli._load_failure_vector_bundle(str(path)) == payload


@pytest.mark.parametrize("with_vector", [False, True])
def test_report_bundle_manifest_matches_written_bytes(tmp_path: Path, with_vector: bool):
    target = tmp_path / "nested" / "bundle"
    contract = {"schema_version": "example.v2", "status": "review_required"}
    vector = {"z": [1], "a": "café"} if with_vector else None
    cli._write_doctor_report_artifact_bundle(
        str(target), contract, '{"status":"review_required"}\n', "# Report\n", vector
    )
    manifest = json.loads((target / "doctor-report-manifest.json").read_text())
    expected_outputs = {"json": "doctor-report.json", "markdown": "doctor-report.md"}
    if with_vector:
        expected_outputs["failure_vector"] = "failure-vector.json"
    assert set(p.name for p in target.iterdir()) == {
        *expected_outputs.values(),
        "doctor-report-manifest.json",
    }
    assert manifest == {
        "schema_version": "sdetkit.doctor_report_artifact_bundle.v1",
        "report_schema_version": "example.v2",
        "status": "review_required",
        "outputs": {
            key: {"path": name, "sha256": hashlib.sha256((target / name).read_bytes()).hexdigest()}
            for key, name in expected_outputs.items()
        },
    }
    assert (target / "doctor-report.json").read_text() == '{"status":"review_required"}\n'
    assert (target / "doctor-report.md").read_text() == "# Report\n"
    if with_vector:
        assert (target / "failure-vector.json").read_text() == cli._json_dumps_pretty(vector)
