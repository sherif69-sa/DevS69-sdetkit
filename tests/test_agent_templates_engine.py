from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from sdetkit.agent.templates import (
    TemplateValidationError,
    discover_templates,
    interpolate_value,
    pack_templates,
    parse_template,
    run_template,
    template_by_id,
)


def test_template_parsing_and_validation_error(tmp_path: Path) -> None:
    good = tmp_path / "ok.yaml"
    good.write_text(
        """
metadata:
  id: x
  title: X
  version: 1.0.0
  description: desc
inputs:
  name:
    default: world
workflow:
  - action: fs.write
    with:
      path: out.txt
      content: hello
""".strip()
        + "\n",
        encoding="utf-8",
    )
    parsed = parse_template(good)
    assert parsed.metadata["id"] == "x"
    assert parsed.inputs["name"].default == "world"

    bad = tmp_path / "bad.yaml"
    bad.write_text("metadata:\n  id: missing\n", encoding="utf-8")
    with pytest.raises(TemplateValidationError):
        parse_template(bad)


def test_interpolation_is_safe_and_supports_nested_values() -> None:
    context = {"inputs": {"foo": "bar", "count": 3}, "run": {"output_dir": "out"}}
    assert interpolate_value("${{inputs.foo}}", context) == "bar"
    assert interpolate_value("result-${{inputs.count}}", context) == "result-3"
    with pytest.raises(TemplateValidationError):
        interpolate_value("${{inputs.missing}}", context)


def test_deterministic_pack_output(tmp_path: Path) -> None:
    templates = tmp_path / "templates" / "automations"
    templates.mkdir(parents=True)
    (templates / "a.yaml").write_text(
        "metadata:\n  id: a\n  title: A\n  version: 1\n  description: d\nworkflow:\n  - action: fs.write\n    with:\n      path: a\n",
        encoding="utf-8",
    )
    (templates / "b.yaml").write_text(
        "metadata:\n  id: b\n  title: B\n  version: 1\n  description: d\nworkflow:\n  - action: fs.write\n    with:\n      path: b\n",
        encoding="utf-8",
    )

    first = pack_templates(tmp_path, output=tmp_path / "pack-1.tar")
    second = pack_templates(tmp_path, output=tmp_path / "pack-2.tar")

    assert Path(first["output"]).read_bytes() == Path(second["output"]).read_bytes()
    with tarfile.open(first["output"], "r") as tf:
        assert tf.getnames() == ["templates/automations/a.yaml", "templates/automations/b.yaml"]


def test_template_run_produces_artifacts_for_two_real_templates(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    templates = discover_templates(repo_root)
    assert len(templates) >= 12

    audit_template = template_by_id(repo_root, "repo-health-audit")
    audit_out = tmp_path / "audit"
    audit_record = run_template(
        repo_root,
        template=audit_template,
        set_values={"profile": "default", "changed_only": "false"},
        output_dir=audit_out,
    )
    assert audit_record["status"] == "ok"
    assert (audit_out / "repo-audit.json").exists()
    assert (audit_out / "repo-audit.sarif.json").exists()

    bundle_template = template_by_id(repo_root, "ci-artifact-bundle")
    bundle_out = tmp_path / "bundle"
    bundle_record = run_template(
        repo_root, template=bundle_template, set_values={}, output_dir=bundle_out
    )
    assert bundle_record["status"] == "ok"
    assert (bundle_out / "artifacts.tar").exists()
    run_record = json.loads((bundle_out / "run-record.json").read_text(encoding="utf-8"))
    assert run_record["status"] == "ok"
    assert "hash" in run_record


def test_template_run_supports_repo_expansion_and_release_workers(tmp_path: Path) -> None:
    repo_root = Path.cwd()

    expansion_template = template_by_id(repo_root, "repo-expansion-control")
    expansion_out = tmp_path / "expansion"
    expansion_record = run_template(
        repo_root,
        template=expansion_template,
        set_values={"goal": "add more bots workers search and repo expansion"},
        output_dir=expansion_out,
    )
    assert expansion_record["status"] == "ok"
    assert (expansion_out / "optimize.json").exists()
    assert (expansion_out / "expand.json").exists()
    assert (expansion_out / "bundle.tar").exists()

    release_template = template_by_id(repo_root, "release-readiness-worker")
    release_out = tmp_path / "release"
    release_record = run_template(
        repo_root,
        template=release_template,
        set_values={},
        output_dir=release_out,
    )
    assert release_record["status"] == "ok"
    assert (release_out / "doctor.json").exists()
    assert (release_out / "automation-check.json").exists()
    assert (release_out / "bundle.tar").exists()


def test_template_run_supports_new_alignment_workers(tmp_path: Path) -> None:
    repo_root = Path.cwd()

    dependency_template = template_by_id(repo_root, "dependency-radar-worker")
    dependency_out = tmp_path / "dependency"
    dependency_record = run_template(
        repo_root,
        template=dependency_template,
        set_values={},
        output_dir=dependency_out,
    )
    assert dependency_record["status"] == "ok"
    assert (dependency_out / "dependency-radar.json").exists()
    assert (dependency_out / "radar.json").exists()
    assert (dependency_out / "route-map.json").exists()
    assert (dependency_out / "bundle.tar").exists()

    validation_template = template_by_id(repo_root, "validation-route-worker")
    validation_out = tmp_path / "validation"
    validation_record = run_template(
        repo_root,
        template=validation_template,
        set_values={"query": "httpx"},
        output_dir=validation_out,
    )
    assert validation_record["status"] == "ok"
    assert (validation_out / "route-map.json").exists()
    assert (validation_out / "doctor-upgrade-audit.md").exists()
    assert (validation_out / "bundle.tar").exists()

    adapter_template = template_by_id(repo_root, "adapter-smoke-worker")
    adapter_out = tmp_path / "adapter"
    adapter_record = run_template(
        repo_root,
        template=adapter_template,
        set_values={},
        output_dir=adapter_out,
    )
    assert adapter_record["status"] == "ok"
    assert (adapter_out / "adapter-smoke.json").exists()
    assert (adapter_out / "adapter-tests.log").exists()
    assert (adapter_out / "bundle.tar").exists()

    runtime_template = template_by_id(repo_root, "runtime-watchlist-worker")
    runtime_out = tmp_path / "runtime"
    runtime_record = run_template(
        repo_root,
        template=runtime_template,
        set_values={},
        output_dir=runtime_out,
    )
    assert runtime_record["status"] == "ok"
    assert (runtime_out / "runtime-watchlist.md").exists()
    assert (runtime_out / "route-map.json").exists()
    assert (runtime_out / "bundle.tar").exists()

    topology_template = template_by_id(repo_root, "integration-topology-worker")
    topology_out = tmp_path / "topology"
    topology_record = run_template(
        repo_root,
        template=topology_template,
        set_values={},
        output_dir=topology_out,
    )
    assert topology_record["status"] == "ok"
    assert (topology_out / "topology-check.json").exists()
    assert (topology_out / "optimize.json").exists()
    assert (topology_out / "bundle.tar").exists()

    alignment_template = template_by_id(repo_root, "worker-alignment-radar")
    alignment_out = tmp_path / "alignment"
    alignment_record = run_template(
        repo_root,
        template=alignment_template,
        set_values={},
        output_dir=alignment_out,
    )
    assert alignment_record["status"] == "ok"
    assert (alignment_out / "expand.json").exists()
    assert (alignment_out / "automation-check.json").exists()
    assert (alignment_out / "templates.json").exists()
    assert (alignment_out / "bundle.tar").exists()


def test_template_run_supports_path_traversal_autofix_worker(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    template = template_by_id(repo_root, "path-traversal-autofix-worker")
    output_dir = tmp_path / "path-traversal-autofix"
    record = run_template(
        repo_root,
        template=template,
        set_values={},
        output_dir=output_dir,
    )

    assert record["status"] == "ok"
    assert (output_dir / "path-traversal-optimize.json").exists()
    assert (output_dir / "path-traversal-expand.json").exists()
    kb_path = output_dir / "path-traversal-adaptive-review-kb.json"
    assert kb_path.exists()
    assert (output_dir / "path-traversal-repo-audit.json").exists()
    assert (output_dir / "path-traversal-repo-audit.sarif.json").exists()
    assert (output_dir / "path-traversal-autofix-bundle.tar").exists()
    payload = json.loads(kb_path.read_text(encoding="utf-8"))
    assert "recurring_failures" in payload
    assert "top_errors" in payload
