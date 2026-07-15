from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface
from sdetkit.doctor_report import (
    build_doctor_report_contract,
    render_doctor_report_markdown,
    write_doctor_report_contract,
)
from sdetkit.failure_vector import BUNDLE_SCHEMA_VERSION, SCHEMA_VERSION
from sdetkit.failure_vector_adapters import extract_ecosystem_failure_vector
from sdetkit.safety_gate import evaluate_failure_vector

FIXTURE_ROOT = Path("tests/fixtures/adoption_repos/java_maven_vertical")
MAVEN_TEST_LOG = FIXTURE_ROOT / "artifacts" / "maven-test.log"
TEST_COMMAND = "mvn test"
SECURITY_COMMAND = "mvn org.owasp:dependency-check-maven:check"
TEST_SOURCE = "java/test/com/example/CalculatorTest.java"


def _named(items: object) -> dict[str, dict[str, object]]:
    assert isinstance(items, list)
    return {
        str(item["name"]): item for item in items if isinstance(item, dict) and item.get("name")
    }


def _commands(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    items = payload["recommended_proof_commands"]
    assert isinstance(items, list)
    return {
        str(item["command"]): item
        for item in items
        if isinstance(item, dict) and item.get("command")
    }


def _bundle(vector_payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "vector_schema_version": SCHEMA_VERSION,
        "environment": "github_actions",
        "failure_vector_count": 1,
        "summary": {
            "by_failure_class": {"test": 1},
            "by_risk": {"medium": 1},
            "safe_fix_candidate_count": 0,
            "review_first_count": 1,
        },
        "failure_vectors": [vector_payload],
    }


def test_java_adoption_to_doctor_vertical_is_review_first(tmp_path: Path) -> None:
    adoption = discover_adoption_surface(FIXTURE_ROOT)
    languages = _named(adoption["detected_languages"])
    package_managers = _named(adoption["package_managers"])
    security_tools = _named(adoption["security_tools"])
    commands = _commands(adoption)

    assert languages["java"]["evidence"] == ["pom.xml"]
    assert package_managers["maven"]["files"] == ["pom.xml"]
    assert security_tools["owasp_dependency_check"]["evidence"] == ["pom.xml"]
    assert TEST_COMMAND in commands
    assert SECURITY_COMMAND in commands
    assert commands[TEST_COMMAND]["purpose"] == "test"
    assert commands[SECURITY_COMMAND]["purpose"] == "security"
    assert commands[TEST_COMMAND]["auto_run_allowed"] is False
    assert commands[SECURITY_COMMAND]["auto_run_allowed"] is False
    assert commands[SECURITY_COMMAND]["source"] == {
        "scope": "build_configuration",
        "file": "pom.xml",
        "package_manager": "maven",
    }
    assert adoption["review_first_unknowns"] == []
    assert adoption["automation_allowed"] is False
    assert adoption["patch_application_allowed"] is False
    assert adoption["merge_authorized"] is False
    assert adoption["semantic_equivalence_proven"] is False

    result = extract_ecosystem_failure_vector(
        MAVEN_TEST_LOG.read_text(encoding="utf-8"),
        ecosystem="java",
        check="maven-test",
        log_url=MAVEN_TEST_LOG.as_posix(),
        environment="github_actions",
    )
    vector = result.vector

    assert result.ecosystem == "java"
    assert result.tool == "maven_test"
    assert result.confidence == "high"
    assert result.uncertainty == ()
    assert result.to_dict()["adapter"]["target_code_execution"] is False
    assert vector.failure_class == "test"
    assert vector.affected_files == (TEST_SOURCE,)
    assert (FIXTURE_ROOT / TEST_SOURCE).is_file()
    assert vector.exit_code == 1
    assert vector.command == TEST_COMMAND
    assert vector.local_repro_command == TEST_COMMAND
    assert vector.failing_command == TEST_COMMAND
    assert "expected:<4> but was:<3>" in str(vector.actual_failure)
    assert vector.safe_fix_allowed is False

    decision = evaluate_failure_vector(vector)
    assert decision.review_first is True
    assert decision.automation_allowed is False
    assert decision.patch_application_allowed is False
    assert decision.merge_authorized is False

    report = build_doctor_report_contract(
        {
            "ok": True,
            "score": 100,
            "quality": {"selected_checks": 1, "passed_checks": 1},
            "next_actions": [],
        },
        failure_vector_bundle=_bundle(result.to_dict()),
    )

    assert report["status"] == "review_required"
    assert report["confidence"] == "high"
    assert report["summary"]["failure_vector_count"] == 1
    evidence = report["failure_vector_evidence"]
    assert evidence["top_failure"]["check"] == "maven-test"
    assert evidence["top_failure"]["failure_type"] == "test"
    assert evidence["top_failure"]["local_repro_command"] == TEST_COMMAND
    assert "failure_diagnosis" in report["roadmap_alignment"]["lanes"]

    safety = report["safety_decision"]
    assert safety["review_first"] is True
    assert safety["automation_allowed"] is False
    assert safety["patch_application_allowed"] is False
    assert safety["security_dismissal_allowed"] is False
    assert safety["merge_authorized"] is False
    assert safety["semantic_equivalence_claim"] is False

    json_path = tmp_path / "doctor-report.json"
    markdown_path = tmp_path / "doctor-report.md"
    write_doctor_report_contract(report, json_path)
    markdown_path.write_text(render_doctor_report_markdown(report), encoding="utf-8")

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    rendered = markdown_path.read_text(encoding="utf-8")
    assert parsed["failure_vector_evidence"]["top_failure"]["check"] == "maven-test"
    assert "top_failure_signal: `maven-test: test`" in rendered
    assert "automation_allowed: `false`" in rendered
    assert "patch_application_allowed: `false`" in rendered
    assert "merge_authorized: `false`" in rendered


def test_unknown_java_vertical_evidence_stays_low_confidence() -> None:
    result = extract_ecosystem_failure_vector(
        "Java build stopped without Maven or Gradle test markers",
        ecosystem="java",
        check="java-build",
    )

    assert result.ecosystem == "java"
    assert result.tool == "unknown"
    assert result.confidence == "low"
    assert result.uncertainty == ("java_failure_not_classified",)
    assert result.to_dict()["adapter"]["target_code_execution"] is False
    assert evaluate_failure_vector(result.vector).review_first is True
