from __future__ import annotations

from pathlib import Path

from sdetkit import kits


def test_blueprint_payload_exposes_upgrade_layers_and_operating_model() -> None:
    payload = kits.blueprint_payload(
        goal="upgrade umbrella architecture with agentos optimization",
        selected_kits=["release", "integration"],
        limit=3,
    )

    assert payload["selected_kits"][0]["id"] == "release-confidence"
    assert payload["architecture_layers"][0]["name"] == "experience-surface"
    assert payload["operating_model"][0]["cadence"] == "continuous"
    assert "AgentOS run success rate" in payload["metrics"]
    backlog_ids = {item["id"] for item in payload["upgrade_backlog"]}
    assert "umbrella-routing" in backlog_ids
    assert "agent-control-plane" in backlog_ids
    assert "integration-topology" in backlog_ids


def test_optimize_payload_aligns_doctor_quality_gate_agentos_and_topology(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='0.1.0'\ndependencies=['httpx>=0.28.1,<1']\n",
        encoding="utf-8",
    )
    (tmp_path / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "premium-gate.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "ci.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "constraints-ci.txt").write_text("ruff==0.15.7\n", encoding="utf-8")
    (tmp_path / ".sdetkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".sdetkit" / "gate.fast.snapshot.json").write_text("{}", encoding="utf-8")
    (tmp_path / "examples" / "kits" / "integration").mkdir(parents=True, exist_ok=True)
    (tmp_path / "examples" / "kits" / "integration" / "profile.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (tmp_path / "examples" / "kits" / "integration" / "heterogeneous-topology.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (tmp_path / "templates" / "automations").mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "automations" / "repo-health-audit.yaml").write_text(
        "metadata:\n  id: repo-health-audit\n", encoding="utf-8"
    )

    payload = kits.optimize_payload(
        root=tmp_path,
        goal="upgrade umbrella architecture with agentos optimization",
        selected_kits=["release", "integration"],
        limit=3,
    )

    assert payload["doctor_lane"]["command"].startswith("sdetkit doctor --dev --ci --repo")
    assert "--upgrade-audit" in payload["doctor_lane"]["command"]
    assert payload["quality_gate_lane"]["commands"][0] == "bash quality.sh ci"
    assert payload["quality_gate_lane"]["commands"][1] == "bash premium-gate.sh --mode full"
    assert payload["auto_fix_lane"]["commands"][0] == "bash quality.sh type"
    assert payload["quality_boost_lane"]["command"] == "bash quality.sh boost"
    assert payload["quality_boost_lane"]["phases"][0] == "doctor-first"
    assert payload["integration_lane"]["coverage"] == "topology-aware"
    assert payload["upgrade_inventory"]["status"] == "ready"
    assert payload["upgrade_inventory"]["packages_audited"] == 1
    assert payload["upgrade_inventory"]["priority_packages"][0]["name"] == "httpx"
    assert payload["upgrade_execution_lane"]["commands"][0].startswith(
        "python -m sdetkit intelligence upgrade-audit"
    )
    assert payload["upgrade_execution_lane"]["focus"]
    innovation_ids = {item["id"] for item in payload["innovation_opportunities"]}
    assert "dependency-radar" in innovation_ids
    assert "runtime-core-fast-follow" in innovation_ids
    assert "integration-topology-radar" in innovation_ids
    assert (
        payload["agentos_lane"]["commands"][1]
        == "sdetkit agent run 'template:repo-health-audit' --approve"
    )
    statuses = {item["domain"]: item["status"] for item in payload["alignment_matrix"]}
    assert statuses["doctor"] == "ready"
    assert statuses["quality-gate"] == "ready"
    assert statuses["integration-topology"] == "ready"
    booster_ids = {item["id"] for item in payload["performance_boosters"]}
    assert "ci-constraints" in booster_ids
    assert "topology-premium-loop" in booster_ids
    assert payload["doctor_quality_contract"]["auto_fix_commands"]
    assert payload["operating_sequence"][1]["stage"] == "intelligent-autofix"
    assert payload["next_boosts"][0]["id"] == "quality-boost"


def test_expand_payload_turns_optimize_signals_into_feature_candidates(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        "name='x'\n"
        "version='0.1.0'\n"
        "dependencies=['httpx>=0.28.1,<1']\n"
        "[project.optional-dependencies]\n"
        "telegram=['python-telegram-bot>=22.7,<23']\n",
        encoding="utf-8",
    )
    (tmp_path / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "premium-gate.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "ci.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "constraints-ci.txt").write_text("ruff==0.15.7\n", encoding="utf-8")
    (tmp_path / ".sdetkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".sdetkit" / "gate.fast.snapshot.json").write_text("{}", encoding="utf-8")
    (tmp_path / "examples" / "kits" / "integration").mkdir(parents=True, exist_ok=True)
    (tmp_path / "examples" / "kits" / "integration" / "profile.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (tmp_path / "examples" / "kits" / "integration" / "heterogeneous-topology.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (tmp_path / "templates" / "automations").mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "automations" / "repo-health-audit.yaml").write_text(
        "metadata:\n  id: repo-health-audit\n", encoding="utf-8"
    )

    payload = kits.expand_payload(
        root=tmp_path,
        goal="upgrade umbrella architecture with agentos optimization",
        selected_kits=["release", "integration"],
        limit=3,
    )

    candidate_ids = {item["id"] for item in payload["feature_candidates"]}
    mission_topics = {item["topic"] for item in payload["search_missions"]}
    track_names = {item["track"] for item in payload["rollout_tracks"]}
    worker_ids = {item["id"] for item in payload["recommended_workers"]}
    launch_templates = {item["template"] for item in payload["worker_launch_pack"]}

    assert payload["optimize"]["alignment_score"]["status"] in {"strong", "maximized"}
    assert "dependency-radar-dashboard" in candidate_ids
    assert "validation-route-map" in candidate_ids
    assert "adapter-smoke-pack" in candidate_ids
    assert "runtime-watchlist" in candidate_ids
    assert "integration-topology-control-loop" in candidate_ids
    assert "dependency-radar" in mission_topics
    assert "validation-route-map" in mission_topics
    assert "adapter-activation" in mission_topics
    assert "runtime-fast-follow" in mission_topics
    assert "integration-topology-control" in mission_topics
    assert "worker-adapter-smoke" in worker_ids
    assert "worker-runtime-watchlist" in worker_ids
    assert "worker-integration-topology" in worker_ids
    assert "worker-automation-alignment" in worker_ids
    assert "worker-optimization-control" in worker_ids
    assert "adapter-smoke-worker" in launch_templates
    assert "runtime-watchlist-worker" in launch_templates
    assert "integration-topology-worker" in launch_templates
    assert "dependency-radar-worker" in launch_templates
    assert "validation-route-worker" in launch_templates
    assert "worker-alignment-radar" in launch_templates
    assert "repo-expansion-control" in launch_templates
    assert payload["worker_launch_pack"]
    assert track_names == {"now", "next", "later"}


def test_route_map_payload_surfaces_primary_validation_routes(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        "name='x'\n"
        "version='0.1.0'\n"
        "dependencies=['httpx>=0.28.1,<1']\n"
        "[project.optional-dependencies]\n"
        "docs=['mkdocs==1.6.1']\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "demo"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "api.py").write_text("import httpx\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_docs.py").write_text("import mkdocs\n", encoding="utf-8")

    payload = kits.route_map_payload(
        root=tmp_path,
        query="httpx runtime",
        repo_usage_tier="edge",
        impact_area="runtime-core",
        limit=5,
    )

    assert payload["status"] == "ready"
    assert payload["total_matches"] == 1
    match = payload["matches"][0]
    assert match["package"] == "httpx"
    assert match["primary_validation"]
    assert "src/demo/api.py" in match["repo_usage_files"]


def test_radar_payload_exposes_dashboard_cards_and_watchlists(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        "name='x'\n"
        "version='0.1.0'\n"
        "dependencies=['httpx>=0.28.1,<1', 'rich>=13,<14']\n"
        "[project.optional-dependencies]\n"
        "docs=['mkdocs==1.6.1']\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "demo"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "api.py").write_text("import httpx\nimport rich\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_docs.py").write_text("import mkdocs\n", encoding="utf-8")

    payload = kits.radar_payload(
        root=tmp_path,
        query="httpx",
        repo_usage_tier="edge",
        impact_area="runtime-core",
        limit=5,
    )

    assert payload["status"] == "ready"
    assert payload["headline_metrics"]["packages_audited"] == 3
    assert payload["headline_metrics"]["filtered_matches"] == 1
    assert payload["headline_metrics"]["runtime_core_packages"] >= 1
    assert payload["dashboard_cards"]
    assert payload["hotspots"][0]["package"] == "httpx"
    assert payload["watchlists"]["runtime_core"]
    assert payload["maintenance_lanes"][0]["id"] == "route-hotspots"


def test_discover_payload_aligns_catalog_optimize_expand_and_radar(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='0.1.0'\ndependencies=['httpx>=0.28.1,<1']\n",
        encoding="utf-8",
    )
    src_dir = tmp_path / "src" / "demo"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "api.py").write_text("import httpx\n", encoding="utf-8")
    (tmp_path / "quality.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / "premium-gate.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (tmp_path / ".sdetkit").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".sdetkit" / "gate.fast.snapshot.json").write_text("{}", encoding="utf-8")

    payload = kits.discover_payload(
        root=tmp_path,
        goal="align all repo capabilities",
        query="release integration",
        selected_kits=["release", "integration"],
        limit=3,
    )

    assert payload["catalog"]["schema_version"] == kits.SCHEMA_VERSION
    assert payload["recommended_kits"]["matches"]
    assert payload["alignment_plan"]["alignment_score"]["score"] >= 0
    assert payload["expansion_plan"]["feature_candidates"]
    assert payload["dependency_radar"]["headline_metrics"]["packages_audited"] >= 1
    assert payload["surface_visibility"]["full_help"] == "sdetkit --help --show-hidden"


def test_discover_main_text_output_summarizes_alignment(tmp_path: Path, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='0.1.0'\ndependencies=['httpx>=0.28.1,<1']\n",
        encoding="utf-8",
    )
    rc = kits.main(
        [
            "discover",
            "--repo-root",
            str(tmp_path),
            "--goal",
            "align all repo capabilities",
            "--query",
            "release integration",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Repo capability discovery + alignment" in out
    assert "surface visibility:" in out
    assert "sdetkit --help --show-hidden" in out
