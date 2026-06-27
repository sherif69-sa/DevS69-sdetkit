from __future__ import annotations

import re
from pathlib import Path

import pytest

from sdetkit import docs_qa

CANONICAL_FIRST_PROOF_DOCS = (
    Path("README.md"),
    Path("docs/index.md"),
    Path("docs/blank-repo-to-value-60-seconds.md"),
    Path("docs/ready-to-use.md"),
    Path("docs/release-confidence.md"),
    Path("docs/adoption.md"),
    Path("docs/choose-your-path.md"),
    Path("docs/real-repo-adoption.md"),
)

CANONICAL_FAST_COMMAND = (
    "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json"
)
CANONICAL_RELEASE_COMMAND = (
    "python -m sdetkit gate release --format json --out build/release-preflight.json"
)
NON_CANONICAL_RELEASE_STABLE_JSON = (
    "python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json"
)


def _starter_inventory_text() -> str:
    return Path("docs/starter-work-inventory.md").read_text(encoding="utf-8")


def test_docs_qa_passes_repo_docs() -> None:
    report = docs_qa.run_docs_qa(Path(".").resolve())
    assert report.files_checked >= 2
    assert report.links_checked >= 10
    assert report.ok


def test_docs_qa_detects_missing_anchor(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Title\n\n[bad](#missing)\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    report = docs_qa.run_docs_qa(tmp_path)
    assert not report.ok
    assert any("missing local anchor" in issue.message for issue in report.issues)


def test_docs_qa_handles_reference_links_and_duplicate_headings(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n"
        "## Section\n\n"
        "## Section\n\n"
        "[ok-ref][guide]\n\n"
        "[guide]: docs/guide.md#section-1\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\n## Section\n\n## Section\n", encoding="utf-8")

    report = docs_qa.run_docs_qa(tmp_path)
    assert report.ok


def test_docs_qa_ignores_links_inside_fenced_code_blocks(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n```bash\n[broken](docs/missing.md)\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()

    report = docs_qa.run_docs_qa(tmp_path)
    assert report.ok


def test_docs_qa_help_describes_product_surface(capsys):
    with pytest.raises(SystemExit) as excinfo:
        docs_qa.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "Validate markdown links and heading anchors across README.md and docs/." in out
    assert "--format {text,json,markdown}" in out
    normalized = " ".join(out.split())
    assert "Optional file path to also write the rendered QA report." in normalized


def test_docs_qa_markdown_output_is_structured(tmp_path: Path, capsys) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n[ok](docs/guide.md#section)\n", encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\n## Section\n", encoding="utf-8")

    rc = docs_qa.main(["--root", str(tmp_path), "--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Docs QA report" in out
    assert "## Summary" in out
    assert "- Status: pass" in out
    assert "## Issues" in out


def test_starter_work_inventory_keeps_first_contribution_structure() -> None:
    text = _starter_inventory_text()
    headings = {
        match.group(1).strip().lower()
        for match in re.finditer(r"^##\s+(.+)$", text, flags=re.MULTILINE)
    }

    assert "how to use this inventory" in headings
    assert "starter contribution categories" in headings
    assert "if no starter issue is available" in headings


def test_starter_work_inventory_keeps_contributor_path_references() -> None:
    text = _starter_inventory_text()

    assert "[First contribution quickstart](first-contribution-quickstart.md)" in text
    assert ".github/ISSUE_TEMPLATE/feature_request.yml" in text
    assert "docs/first-contribution-quickstart.md" in text


def test_versioning_and_stability_policy_terms_stay_aligned() -> None:
    versioning = Path("docs/versioning-and-support.md").read_text(encoding="utf-8")
    stability = Path("docs/stability-levels.md").read_text(encoding="utf-8")

    required_tiers = (
        "Public / stable",
        "Advanced but supported",
        "Experimental / incubator",
    )
    for tier in required_tiers:
        assert tier in versioning
        assert tier in stability

    assert "Stable/Core" not in versioning
    assert "Integrations" not in versioning
    assert "Playbooks" not in versioning
    assert "highest compatibility expectation" in stability
    assert "primary compatibility target" in versioning


def test_canonical_visibility_policy_keeps_compatibility_lanes_secondary() -> None:
    versioning = Path("docs/versioning-and-support.md").read_text(encoding="utf-8")

    assert "## Canonical path vs compatibility lanes (visibility policy)" in versioning
    assert "`python -m sdetkit gate fast`" in versioning
    assert "`python -m sdetkit gate release`" in versioning
    assert "`python -m sdetkit doctor`" in versioning
    assert "Compatibility surfaces remain supported" in versioning
    assert "primary first-time recommendation" in versioning
    assert "new deprecation wave" in versioning


def test_command_surface_policy_docs_avoid_legacy_primary_taxonomy() -> None:
    command_surface = Path("docs/command-surface.md").read_text(encoding="utf-8")
    boundary = Path("docs/integrations-and-extension-boundary.md").read_text(encoding="utf-8")

    assert "Stable/Core" not in command_surface
    assert "Integrations" not in command_surface
    assert "| Playbooks |" not in command_surface
    assert "Stable/Core" not in boundary
    assert "## What belongs in Integrations" not in boundary
    assert "## What belongs in Playbooks" not in boundary

    for required in (
        "Public / stable",
        "Advanced but supported",
        "Experimental / incubator",
    ):
        assert required in command_surface
        assert required in boundary

    assert "`python -m sdetkit gate fast`" in command_surface
    assert "`python -m sdetkit gate release`" in command_surface
    assert "`python -m sdetkit doctor`" in command_surface


def test_policy_chain_contract_keeps_canonical_first_time_primary() -> None:
    stability = Path("docs/stability-levels.md").read_text(encoding="utf-8")
    versioning = Path("docs/versioning-and-support.md").read_text(encoding="utf-8")
    contract = Path("src/sdetkit/public_surface_contract.py").read_text(encoding="utf-8")

    for text in (stability, versioning):
        for tier in (
            "Public / stable",
            "Advanced but supported",
            "Experimental / incubator",
        ):
            assert tier in text

    assert "Primary first-time product surface" in contract
    assert "first_time_recommended=True" in contract
    assert "first_time_recommended=False" in contract
    assert "Compatibility surfaces remain supported" in versioning
    assert "does **not** make them the primary first-time recommendation" in " ".join(
        versioning.split()
    )

    policy_chain = " ".join((stability, versioning, contract)).lower()
    assert "legacy-primary" not in policy_chain
    assert "primary recommendation for legacy" not in policy_chain


def test_front_door_story_alignment_across_readme_docs_and_cli_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    docs_home = Path("docs/index.md").read_text(encoding="utf-8")
    command_surface = Path("docs/command-surface.md").read_text(encoding="utf-8")
    cli_ref = Path("docs/cli.md").read_text(encoding="utf-8")
    contract = Path("src/sdetkit/public_surface_contract.py").read_text(encoding="utf-8")

    canonical_phrase = "deterministic ship/no-ship decisions with machine-readable evidence"
    for text in (readme, docs_home):
        assert canonical_phrase in text

    canonical_commands = (
        "`python -m sdetkit gate fast`",
        "`python -m sdetkit gate release`",
        "`python -m sdetkit doctor`",
    )
    for cmd in canonical_commands:
        assert cmd in readme
        assert cmd in docs_home
        assert cmd in command_surface
        assert cmd in cli_ref

    assert "secondary" in readme.lower()
    assert "product homepage/router" in docs_home
    assert "archive index" in docs_home.lower()
    assert "one canonical command path" in contract


def test_readme_exposes_secondary_public_stable_operator_lanes() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    canonical_index = readme.index("Canonical first path:")
    secondary_index = readme.index("| Readiness evidence |")
    assert canonical_index < secondary_index

    expected_commands = (
        "python -m sdetkit repo audit . --format json --fail-on none",
        "python -m sdetkit security scan --fail-on none "
        "--format sarif --output build/security.sarif "
        "--sbom-output build/sbom.cdx.json",
        "python -m sdetkit evidence pack --output .sdetkit/out/evidence.zip",
    )
    expected_docs = (
        "docs/repo-audit.md",
        "docs/security-gate.md",
        "docs/artifact-reference.md",
    )

    assert "| Readiness evidence |" in readme
    for command in expected_commands:
        assert f"`{command}`" in readme
    for docs_path in expected_docs:
        assert f"]({docs_path})" in readme

    assert (
        "Secondary lanes cover review, investigation, quality, maintenance, "
        "and CI automation once the primary gate decision is stable." in readme
    )


def test_cli_reference_keeps_current_surface_and_demotes_transition_appendix() -> None:
    cli_ref = Path("docs/cli.md").read_text(encoding="utf-8")

    assert "## Canonical first-time path (public / stable)" in cli_ref
    assert "`python -m sdetkit gate fast`" in cli_ref
    assert "`python -m sdetkit gate release`" in cli_ref
    assert "`python -m sdetkit doctor`" in cli_ref
    assert "## Stability-aware command discovery" in cli_ref
    assert "## Transition-era and legacy-oriented material" in cli_ref

    for appendix_heading in (
        "## reliability-evidence-pack",
        "## objection-handling",
        "## release-readiness",
        "## startup-readiness",
        "## enterprise-readiness",
        "## release-communications",
        "## trust-assets",
        "## docs-nav",
    ):
        assert appendix_heading not in cli_ref


def test_canonical_public_docs_lock_first_proof_command_contract() -> None:
    for path in CANONICAL_FIRST_PROOF_DOCS:
        text = path.read_text(encoding="utf-8")
        assert CANONICAL_FAST_COMMAND in text, f"missing canonical fast command in {path}"
        assert CANONICAL_RELEASE_COMMAND in text, f"missing canonical release command in {path}"

        assert NON_CANONICAL_RELEASE_STABLE_JSON not in text, (
            f"non-supported release --stable-json drifted into {path}"
        )


def test_canonical_public_docs_lock_first_artifact_paths() -> None:
    required_artifacts = ("build/gate-fast.json", "build/release-preflight.json")
    for path in (
        Path("README.md"),
        Path("docs/index.md"),
        Path("docs/blank-repo-to-value-60-seconds.md"),
        Path("docs/ready-to-use.md"),
        Path("docs/release-confidence.md"),
        Path("docs/real-repo-adoption.md"),
    ):
        text = path.read_text(encoding="utf-8")
        for artifact in required_artifacts:
            assert artifact in text, f"missing canonical artifact path {artifact} in {path}"


def test_case_snippet_proof_map_csv_has_eof_newline() -> None:
    proof_map = Path("docs/artifacts/case-snippet-closeout-pack/proof-map.csv")
    assert proof_map.is_file(), "proof map CSV is missing"
    assert proof_map.read_bytes().endswith(b"\n"), "proof map CSV must end with a newline"


def test_docs_information_architecture_exposes_investigation_and_artifacts() -> None:
    docs_home = Path("docs/index.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    mkdocs = Path("mkdocs.yml").read_text(encoding="utf-8")

    required_links = (
        "artifact-reference.md",
        "operator-essentials.md",
        "investigation-operator-guide.md",
        "adaptive-diagnosis.md",
        "premium-quality-gate.md",
        "remediation-cookbook.md",
    )
    for link in required_links:
        assert link in docs_home, f"missing docs home navigation link: {link}"

    for link in (
        "docs/artifact-reference.md",
        "docs/operator-essentials.md",
        "docs/investigation-operator-guide.md",
        "docs/adaptive-diagnosis.md",
    ):
        assert link in readme, f"missing README documentation map link: {link}"

    assert "Artifact reference and generated sample map: artifact-reference.md" in mkdocs
    assert "Investigation operator guide: investigation-operator-guide.md" in mkdocs
    assert "Adaptive Diagnosis Intelligence: adaptive-diagnosis.md" in mkdocs


def test_artifact_reference_documents_runtime_uploads_and_sample_boundary() -> None:
    text = Path("docs/artifact-reference.md").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/maintenance-autopilot.yml").read_text(encoding="utf-8")

    required_paths = (
        "build/gate-fast.json",
        "build/release-preflight.json",
        "build/investigation/failure.json",
        "build/maintenance/autopilot/autopilot-report.json",
        "build/maintenance/autopilot/adaptive-diagnosis.json",
        "build/maintenance/autopilot/safe-fix-plan.json",
        ".sdetkit/maintenance/failure-memory.jsonl",
        ".sdetkit/maintenance/adaptive-safe-fix-memory.jsonl",
        "docs/artifacts/",
        "artifact-contract-index.json",
    )
    for artifact_path in required_paths:
        assert artifact_path in text, f"missing artifact reference path: {artifact_path}"

    for uploaded_path in (
        "build/maintenance/autopilot/autopilot-report.json",
        "build/maintenance/autopilot/adaptive-diagnosis.json",
        "build/maintenance/autopilot/safe-fix-plan.json",
        ".sdetkit/maintenance/adaptive-safe-fix-memory.jsonl",
    ):
        assert uploaded_path in workflow
        assert uploaded_path in text

    assert "Generated/sample material" in text
    assert "Runtime artifacts" in text


def test_investigation_and_autopilot_docs_preserve_diagnostic_safety_story() -> None:
    docs = {
        "artifact-reference": Path("docs/artifact-reference.md").read_text(encoding="utf-8"),
        "operator-essentials": Path("docs/operator-essentials.md").read_text(encoding="utf-8"),
        "investigation-operator-guide": Path("docs/investigation-operator-guide.md").read_text(
            encoding="utf-8"
        ),
        "adaptive-diagnosis": Path("docs/adaptive-diagnosis.md").read_text(encoding="utf-8"),
        "pr-automation": Path("docs/pr-automation.md").read_text(encoding="utf-8"),
        "premium-quality-gate": Path("docs/premium-quality-gate.md").read_text(encoding="utf-8"),
    }

    combined = "\n".join(docs.values()).lower()
    assert "diagnostic/report-only by default" in combined
    assert "explicit guarded" in combined
    assert "guarded pr auto-fix" in combined
    assert "auto-fix is generally allowed" not in combined

    assert (
        "does not create branches, push commits, open pull requests, or apply fixes"
        in docs["investigation-operator-guide"]
    )
    assert "they do not approve mutation" in docs["operator-essentials"]
    assert "report-only by default" in docs["adaptive-diagnosis"]
    assert "explicit opt-in remediation lane" in docs["pr-automation"]
    assert "default quality-gate posture remains evidence-first" in docs["premium-quality-gate"]


def test_readme_stays_concise_front_door() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    line_count = len(readme.splitlines())

    assert line_count <= 160
    assert "## Start here" in readme
    assert "## Documentation map" in readme
    assert "## Advanced lanes live in docs" in readme
    assert "python -m sdetkit portfolio-orchestrate" not in readme
    assert "Quick ops aliases:" not in readme
    assert "Maintenance command center (issue noise control)" not in readme


def test_operator_essentials_reads_like_day_to_day_runbook() -> None:
    text = Path("docs/operator-essentials.md").read_text(encoding="utf-8")

    required_sections = (
        "## Safety baseline",
        "## Day 0 — First run and artifact handoff",
        "## Day 1 — Failed CI or PR check triage",
        "## Day 2 — Maintenance/autopilot artifact review",
        "## Day 3 — Guarded remediation review",
        "## Rollout and CI contract commands (secondary)",
    )
    for section in required_sections:
        assert section in text

    assert "they do not approve mutation" in text
    assert "A safe-fix plan is not permission to apply a fix" in text
    assert "These commands are kept here for rollout contract visibility" in text
    assert text.index("## Day 0") < text.index("## Rollout and CI contract commands")


def test_artifact_reference_maps_signals_to_safe_operator_actions() -> None:
    text = Path("docs/artifact-reference.md").read_text(encoding="utf-8")

    required_table_headers = (
        "| If you see... | Open this artifact first | Next safe action | Mutation posture |",
        "| A local release gate failed | `build/gate-fast.json` or `build/release-preflight.json` |",
        "| A CI log or PR check failed | `build/investigation/failure.json` |",
        "| A maintenance-autopilot run uploaded artifacts |",
        "| A safe-fix plan exists | `build/maintenance/autopilot/safe-fix-plan.json` |",
        "| A pattern keeps recurring | `.sdetkit/maintenance/failure-memory.jsonl` and `.sdetkit/maintenance/adaptive-safe-fix-memory.jsonl` |",
        "| You are reading committed samples | `docs/artifacts/` and [`live-adoption-product-proof.md`](live-adoption-product-proof.md) |",
    )
    for expected in required_table_headers:
        assert expected in text

    assert "Not approval to mutate" in text
    assert "Evidence for review, not auto-approval" in text
    assert text.index("## Navigation from artifacts to action") < text.index("Quick rules:")


def test_docs_map_declares_tidy_information_architecture() -> None:
    docs_map = Path("docs/docs-map.md").read_text(encoding="utf-8")
    artifacts_readme = Path("docs/artifacts/README.md").read_text(encoding="utf-8")
    docs_home = Path("docs/index.md").read_text(encoding="utf-8")
    mkdocs = Path("mkdocs.yml").read_text(encoding="utf-8")

    for section in (
        "## Read in this order",
        "## Information architecture",
        "## Directory guide",
        "## Navigation rules for future cleanup",
    ):
        assert section in docs_map

    for area in (
        "Getting started",
        "Operator guide",
        "Investigation / diagnosis",
        "Maintenance / autopilot",
        "Quality gates",
        "Artifact reference",
        "Contributor / developer docs",
        "Generated/sample artifacts",
        "Historical archive",
    ):
        assert area in docs_map

    assert "[docs/artifacts/README.md](artifacts/README.md)" not in docs_map
    assert (
        "| Generated/sample artifacts | [Artifact reference](artifact-reference.md), "
        "[Live-adoption product proof](live-adoption-product-proof.md) |"
    ) in docs_map
    assert "Do not move historical/generated artifact packs" in docs_map
    assert "diagnostic/report-only by default" in docs_map
    assert "Docs map and organization" in docs_home
    assert "Operator and evidence (primary):" in mkdocs
    assert "Docs map and organization: docs-map.md" in mkdocs
    assert "Generated and sample artifacts" in artifacts_readme
    assert "Runtime evidence" in artifacts_readme
    assert "do not authorize mutation" in artifacts_readme


def test_repository_front_doors_are_polished_and_consistent() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    root_index = Path("index.md").read_text(encoding="utf-8")
    docs_readme = Path("docs/README.md").read_text(encoding="utf-8")
    docs_map = Path("docs/docs-map.md").read_text(encoding="utf-8")

    assert "## Repository layout" in readme
    assert "docs/artifacts/" in readme
    assert "DevS69 SDETKit project index" in root_index
    assert "## First paths" in root_index
    assert "[docs/operator-essentials.md](docs/operator-essentials.md)" in root_index
    assert "diagnostic/report-only by default" in root_index
    assert "# Documentation directory" in docs_readme
    assert "## Primary path" in docs_readme
    assert "[artifacts/README.md](artifacts/README.md)" in docs_readme
    assert "reviewed guarded policy" in docs_readme
    assert "[Start here homepage](index.md)" in docs_map
    assert (
        "New primary guides must be linked from [Start here homepage](index.md) or this map."
        in docs_map
    )


def test_project_docs_are_moved_under_docs_with_root_compatibility_pointers() -> None:
    moved_docs = (
        Path("docs/project/architecture.md"),
        Path("docs/project/operator-workflow.md"),
        Path("docs/project/quality-playbook.md"),
        Path("docs/project/enterprise-offerings.md"),
        Path("docs/project/release-process.md"),
        Path("docs/roadmap/adaptive-investigation-roadmap.md"),
        Path("docs/roadmap/product-roadmap.md"),
    )
    for path in moved_docs:
        assert path.is_file(), f"missing moved project doc: {path}"

    root_pointers = {
        Path("ARCHITECTURE.md"): "docs/project/architecture.md",
        Path("WORKFLOW.md"): "docs/project/operator-workflow.md",
        Path("QUALITY_PLAYBOOK.md"): "docs/project/quality-playbook.md",
        Path("ENTERPRISE_OFFERINGS.md"): "docs/project/enterprise-offerings.md",
        Path("RELEASE.md"): "docs/project/release-process.md",
        Path("ROADMAP.md"): "docs/roadmap/product-roadmap.md",
    }
    for pointer, target in root_pointers.items():
        text = pointer.read_text(encoding="utf-8")
        assert target in text
        assert len(text.splitlines()) <= 70

    project_readme = Path("docs/project/README.md").read_text(encoding="utf-8")
    docs_readme = Path("docs/README.md").read_text(encoding="utf-8")
    root_index = Path("index.md").read_text(encoding="utf-8")
    mkdocs = Path("mkdocs.yml").read_text(encoding="utf-8")

    assert "Root compatibility pointers" in project_readme
    assert "docs/project/" in docs_readme
    assert "docs/project/" in root_index
    assert "Project documents: project/README.md" in mkdocs
    assert "Release process: project/release-process.md" in mkdocs
    assert "Adaptive investigation roadmap: roadmap/adaptive-investigation-roadmap.md" in mkdocs
    assert "Product roadmap: roadmap/product-roadmap.md" in mkdocs


def test_project_structure_explains_root_pointer_policy() -> None:
    text = Path("docs/project-structure.md").read_text(encoding="utf-8")

    assert "short compatibility pointers" in text
    assert (
        "Maintained long-form project docs live under `docs/project/` and `docs/roadmap/`" in text
    )
    assert "docs/project/release-process.md`, and `docs/roadmap/product-roadmap.md`" not in text
