# --- dev targets (bootstrap) ---

DATE_TAG ?= 2026-04-24
WINDOW_START ?= 2026-04-11
WINDOW_END ?= 2026-04-17
GENERATED_AT ?= 2026-04-17T10:00:00Z
ADAPTIVE_SCENARIO ?= balanced
PORTFOLIO_MANIFEST ?= portfolio-manifest.json
FIRST_PROOF_BRANCH ?= local
PHASE2_BASELINE_PRE_EXTRACTION ?= docs/artifacts/phase2-hotspot-baseline-pre-extraction-$(DATE_TAG).json

.PHONY: bootstrap max brutal venv install test cov lint fmt type docs-serve docs-build package-validate release-preflight release-verify-plan upgrade-audit upgrade-audit-ci registry golden-path-health canonical-path-drift legacy-command-analyzer legacy-burndown adoption-scorecard adoption-scorecard-contract observability-contract operator-onboarding-wizard primary-docs-map top-tier-reporting enterprise-contracts-check enterprise-assessment enterprise-assessment-contract ship-readiness ship-readiness-contract release-room portfolio-readiness premerge-release-room adaptive-scenario-db adaptive-postcheck owner-escalation-payload adaptive-premerge adaptive-ops-bundle repo-alignment-check test-bootstrap test-bootstrap-contract merge-ready premerge-finalize first-proof first-proof-contract first-proof-learn first-proof-control-tower first-proof-weekly-trend first-proof-trend-threshold first-proof-tests first-proof-verify phase1-baseline phase1-status phase1-next phase1-ops-snapshot phase1-dashboard phase1-weekly-pack phase1-control-loop phase1-run-all phase1-artifact-set phase1-telemetry phase1-finish-signal phase1-next-pass phase1-blocker-register phase1-do-it phase1-execution-core phase1-workflow phase1-flow-contract phase1-gate-phase2 phase1-executive-report phase1-retire-plan phase1-complete phase1-closeout phase-current phase-current-json phase2-start phase2-workflow phase2-status phase2-start-contract phase2-seed phase2-hotspot-baseline phase2-hotspot-delta phase2-complete phase2-progress phase2-surface-clarity phase3-dependency-radar phase3-quality-contract phase3-quality-report phase3-do-it phase4-governance-contract phase5-ecosystem-contract phase6-start phase6-status phase6-progress phase6-complete phase6-metrics-contract plan-status phase1-execute phase2-execute phase3-governance phase4-credibility

bootstrap: venv
	@bash -lc '. .venv/bin/activate && bash scripts/bootstrap.sh'

max: bootstrap
	@bash -lc '. .venv/bin/activate && bash quality.sh boost'

brutal: bootstrap
	@bash -lc '. .venv/bin/activate && bash quality.sh brutal'

venv:
	@test -x .venv/bin/python || bash -lc 'set -euo pipefail; if [ -x "$$HOME/.pyenv/versions/3.11.14/bin/python" ]; then "$$HOME/.pyenv/versions/3.11.14/bin/python" -m venv .venv; else python3 -m venv .venv; fi'

install: venv
	@bash -lc '. .venv/bin/activate && python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .'

test-bootstrap-contract: install
	@bash -lc '. .venv/bin/activate && python -m sdetkit.test_bootstrap_contract --strict'

test-bootstrap: install
	@bash -lc '. .venv/bin/activate && python -m sdetkit.test_bootstrap_contract --strict && python -m sdetkit.test_bootstrap_validate --strict'

merge-ready: test-bootstrap
	@bash -lc '. .venv/bin/activate && bash quality.sh verify'

premerge-finalize: install
	@bash -lc '. .venv/bin/activate && python -m pytest -q tests/test_first_proof_script.py tests/test_first_proof_contract.py tests/test_first_proof_learning_db.py tests/test_first_proof_weekly_trend.py tests/test_first_proof_control_tower.py tests/test_first_proof_trend_threshold.py tests/test_build_owner_escalation_payload.py tests/test_phase2_hotspot_baseline.py tests/test_phase2_hotspot_delta.py tests/test_phase2_utilities_extraction.py tests/test_phase3_dependency_radar.py'
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_summary_contract.py --summary build/first-proof/first-proof-summary.json --allow-missing --format json'
	@bash -lc '. .venv/bin/activate && python scripts/phase3_dependency_radar.py --policy-json config/dependency_slo_policy.json --out docs/artifacts/phase3-dependency-radar-$(DATE_TAG).json'
	@bash -lc '. .venv/bin/activate && $(MAKE) plan-status'

first-proof: venv
	@bash -lc '. .venv/bin/activate && PYTHONPATH=src python scripts/first_proof.py --strict --format json --out-dir build/first-proof'

first-proof-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_summary_contract.py --summary build/first-proof/first-proof-summary.json --wait-seconds 60 --format json'

first-proof-learn: venv
	@bash -lc '. .venv/bin/activate && python scripts/first_proof_learning_db.py --summary build/first-proof/first-proof-summary.json --db build/first-proof/first-proof-learning-db.jsonl --rollup-out build/first-proof/first-proof-learning-rollup.json --format json'

first-proof-control-tower: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_first_proof_control_tower.py --first-proof-rollup build/first-proof/first-proof-learning-rollup.json --adaptive-postcheck build/adaptive-postcheck-min.json --out-json build/first-proof/control-tower.json --out-md build/first-proof/control-tower.md --format json'

first-proof-weekly-trend: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_first_proof_weekly_trend.py --db build/first-proof/first-proof-learning-db.jsonl --adaptive-postcheck build/adaptive-postcheck-min.json --out-json build/first-proof/weekly-trend.json --out-md build/first-proof/weekly-trend.md --format json'

first-proof-trend-threshold: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_trend_threshold.py --trend build/first-proof/weekly-trend.json --branch $(FIRST_PROOF_BRANCH) --profile-config config/first_proof_threshold_profiles.json --min-ship-rate 0.50 --min-total-runs 3 --min-consecutive-breaches 2 --out build/first-proof/weekly-threshold-check.json --format json'

first-proof-tests: venv
	@bash -lc '. .venv/bin/activate && python -m pytest -q tests/test_first_proof_script.py tests/test_first_proof_contract.py tests/test_first_proof_learning_db.py tests/test_first_proof_weekly_trend.py tests/test_first_proof_control_tower.py tests/test_first_proof_trend_threshold.py tests/test_build_owner_escalation_payload.py'

first-proof-verify: first-proof
	@bash -lc '. .venv/bin/activate && $(MAKE) first-proof-contract && $(MAKE) first-proof-learn && $(MAKE) first-proof-control-tower && $(MAKE) first-proof-weekly-trend && $(MAKE) first-proof-trend-threshold && $(MAKE) first-proof-tests'

test: install
	@bash -lc '. .venv/bin/activate && bash quality.sh test'

cov: install
	@bash -lc '. .venv/bin/activate && bash quality.sh cov'

lint: install
	@bash -lc '. .venv/bin/activate && bash quality.sh lint'

fmt: install
	@bash -lc '. .venv/bin/activate && bash quality.sh fmt'

type: install
	@bash -lc '. .venv/bin/activate && bash quality.sh type'

registry: install
	@bash -lc '. .venv/bin/activate && bash quality.sh registry'

docs-serve: install
	@bash -lc '. .venv/bin/activate && mkdocs serve'

docs-build: install
	@bash -lc '. .venv/bin/activate && mkdocs build'


package-validate: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python -m pip install -c constraints-ci.txt -e .[packaging] && rm -rf dist build && python -m build && python -m twine check dist/* && python -m check_wheel_contents --ignore W009 dist/*.whl && python -m venv .venv-smoke && . .venv-smoke/bin/activate && python -m pip install --force-reinstall dist/*.whl && sdetkit --help'


release-preflight: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .[packaging] && python scripts/release_preflight.py && python scripts/check_first_proof_summary_contract.py --summary build/first-proof/first-proof-summary.json --format json && python -m sdetkit doctor --release --skip clean_tree --format md && $(MAKE) package-validate'


release-verify-plan: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python scripts/release_verify_post_publish.py --plan'


upgrade-audit: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python scripts/upgrade_audit.py'


upgrade-audit-ci: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python scripts/upgrade_audit.py --fail-on high'


golden-path-health: venv
	@bash -lc '. .venv/bin/activate && python scripts/golden_path_health.py --out .sdetkit/out/golden-path-health.json'


canonical-path-drift: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_canonical_path_drift.py --format json'


legacy-command-analyzer: venv
	@bash -lc '. .venv/bin/activate && python scripts/legacy_command_analyzer.py --format json'

legacy-burndown: venv
	@bash -lc '. .venv/bin/activate && python scripts/legacy_burndown.py --format json'


adoption-scorecard: venv
	@bash -lc '. .venv/bin/activate && python scripts/adoption_scorecard.py --format json'

adoption-scorecard-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_adoption_scorecard_v2_contract.py --format json'

observability-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_observability_v2_contract.py --format json'


operator-onboarding-wizard: venv
	@bash -lc '. .venv/bin/activate && python scripts/operator_onboarding_wizard.py --format json'


primary-docs-map: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_primary_docs_map.py --format json'


top-tier-reporting: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && \
	python scripts/build_top_tier_reporting_bundle.py --input docs/artifacts/portfolio-input-sample-$(DATE_TAG).jsonl --out-dir docs/artifacts/top-tier-bundle --window-start $(WINDOW_START) --window-end $(WINDOW_END) --generated-at $(GENERATED_AT) --schema-version 1.0.0 --program-status green --rollback-count 0 --manifest-out docs/artifacts/top-tier-bundle-manifest-$(DATE_TAG).json && \
	python scripts/check_top_tier_bundle_manifest.py --manifest docs/artifacts/top-tier-bundle-manifest-$(DATE_TAG).json --out docs/artifacts/top-tier-bundle-manifest-check-$(DATE_TAG).json && \
	python scripts/promote_top_tier_bundle.py --bundle-dir docs/artifacts/top-tier-bundle --date-tag $(DATE_TAG)'


enterprise-contracts-check: venv
	@bash -lc '. .venv/bin/activate && python scripts/validate_enterprise_contracts.py'

enterprise-assessment: venv
	@bash -lc '. .venv/bin/activate && python -m sdetkit enterprise-assessment --format json --production-profile'

enterprise-assessment-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_enterprise_assessment_contract.py --summary docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json --format json'

ship-readiness: venv
	@bash -lc '. .venv/bin/activate && python -m sdetkit ship-readiness --strict --format json --out-dir build/ship-readiness'

ship-readiness-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_ship_readiness_contract.py --summary build/ship-readiness/ship-readiness-summary.json --format json'

release-room: enterprise-assessment ship-readiness ship-readiness-contract enterprise-assessment-contract
	@bash -lc '. .venv/bin/activate && python scripts/render_release_room_summary.py --ship-summary build/ship-readiness/ship-readiness-summary.json --enterprise-summary docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json --out build/release-room-summary.md'

portfolio-readiness: venv
	@bash -lc '. .venv/bin/activate && python -m sdetkit portfolio-readiness --manifest $(PORTFOLIO_MANIFEST) --format json --out build/portfolio-readiness.json'

premerge-release-room: venv
	@bash -lc '. .venv/bin/activate && python scripts/premerge_release_room_gate.py . --strict --format json --out build/premerge-release-room-gate.json'


adaptive-postcheck: adaptive-scenario-db
	@bash -lc '. .venv/bin/activate && PYTHONPATH=src python scripts/adaptive_postcheck.py . --scenario $(ADAPTIVE_SCENARIO) --out docs/artifacts/adaptive-postcheck-$(DATE_TAG).json'


owner-escalation-payload: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_owner_escalation_payload.py --out build/owner-escalation-payload.json --first-proof-threshold build/first-proof/weekly-threshold-check.json --first-proof-threshold-policy config/first_proof_owner_escalation_profiles.json'


adaptive-premerge: adaptive-scenario-db
	@bash -lc '. .venv/bin/activate && PYTHONPATH=src python scripts/adaptive_postcheck.py . --scenario strict --out build/adaptive-postcheck-premerge.json --out-md build/adaptive-postcheck-premerge.md --history-json build/adaptive-postcheck-history.json'


adaptive-scenario-db: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_adaptive_scenario_database.py . --out docs/artifacts/adaptive-scenario-database-$(DATE_TAG).json'


adaptive-ops-bundle: adaptive-postcheck enterprise-contracts-check
	@bash -lc '. .venv/bin/activate && python scripts/build_adaptive_ops_summary.py --out-md docs/artifacts/adaptive-ops-summary-$(DATE_TAG).md --out-json docs/artifacts/adaptive-ops-summary-$(DATE_TAG).json'

repo-alignment-check: venv
	@bash -lc '. .venv/bin/activate && PYTHONPATH=src python scripts/adaptive_postcheck.py . --scenario strict --out build/repo-alignment/adaptive-postcheck.json --out-md build/repo-alignment/adaptive-postcheck.md --history-json build/repo-alignment/adaptive-history.json'
	@bash -lc '. .venv/bin/activate && python scripts/validate_enterprise_contracts.py'
	@bash -lc '. .venv/bin/activate && pytest -q'

phase1-baseline: install
	@bash -lc '. .venv/bin/activate && bash scripts/phase1_baseline_lane.sh'

phase1-status: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_status_report.py --format json --out build/phase1-baseline/phase1-status.json'

phase1-next: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_next_actions.py --status-json build/phase1-baseline/phase1-status.json --format json --out build/phase1-baseline/phase1-next-actions.json'

phase1-ops-snapshot: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_build_ops_snapshot.py --format json'

phase1-dashboard: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_completion_dashboard.py --format json'

phase1-weekly-pack: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_weekly_report_pack.py --format json'

phase1-control-loop: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_control_loop_report.py --format json'

phase1-run-all: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_run_all.py --format json'

phase1-artifact-set: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase1_artifact_set.py --format json'

phase1-telemetry: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_telemetry_history.py --format json'

phase1-finish-signal: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_finish_signal.py --format json > build/phase1-baseline/phase1-finish-signal.json'

phase1-next-pass: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_next_pass_card.py --format json'

phase1-blocker-register: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_blocker_register.py --format json'

phase1-execution-core: phase1-run-all phase1-artifact-set phase1-telemetry phase1-finish-signal
	@bash -lc 'echo phase1-execution-core: pipeline completed'

phase1-do-it: phase1-execution-core
	@bash -lc 'echo phase1-do-it is deprecated; use phase1-execution-core'

phase1-workflow: phase1-execution-core phase1-flow-contract phase1-gate-phase2 phase1-executive-report
	@bash -lc 'echo phase1-workflow: operational workflow completed'

phase1-flow-contract: venv
	@bash -lc ' . .venv/bin/activate && python scripts/check_phase1_flow_contract.py --format json'

phase1-gate-phase2: venv
	@bash -lc ' . .venv/bin/activate && python scripts/phase1_gate_phase2.py --format json > build/phase1-baseline/phase1-gate-phase2.json'

phase1-executive-report: venv
	@bash -lc ' . .venv/bin/activate && python scripts/phase1_executive_report.py --format json'

phase1-retire-plan: venv
	@bash -lc ' . .venv/bin/activate && python scripts/phase1_retire_plan_into_flow.py --format json'

phase1-closeout: venv
	@bash -lc ' . .venv/bin/activate && python scripts/phase1_closeout_and_prune_plan.py --format json'

phase1-complete: install
	@bash -lc '. .venv/bin/activate && bash scripts/phase1_baseline_lane.sh && python scripts/check_phase1_baseline_summary_contract.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json --require-logs && python scripts/phase1_completion_gate.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json'

phase-current: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase_sequential_executor.py --format text'

phase-current-json: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase_sequential_executor.py --format json'

plan-status: phase-current-json
	@bash -lc 'echo plan-status: use phase-current-json output as canonical status payload'

phase1-execute: phase1-workflow
	@bash -lc 'echo phase1-execute: canonical phase1 workflow complete'

phase2-execute: phase2-workflow
	@bash -lc 'echo phase2-execute: canonical phase2 workflow complete'

phase3-governance: phase3-quality-contract
	@bash -lc '. .venv/bin/activate && $(MAKE) phase3-dependency-radar'

phase4-credibility: venv
	@bash -lc 'echo phase4-credibility: reference packs and adoption walkthroughs are published under docs/'

phase2-start: phase2-workflow
	@bash -lc 'echo phase2-start: implementation lane initialized'

phase2-workflow: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase2_start_workflow.py --format json'
	@bash -lc '. .venv/bin/activate && python scripts/check_phase2_start_summary_contract.py --format json'
	@bash -lc '. .venv/bin/activate && python scripts/phase2_status_report.py --format json --out build/phase2-start/phase2-status.json'
	@bash -lc '. .venv/bin/activate && $(MAKE) phase2-hotspot-baseline'

phase2-status: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase2_status_report.py --format json --out build/phase2-start/phase2-status.json'

phase2-start-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase2_start_summary_contract.py --format json'

phase2-seed: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase2_seed_prerequisites.py'

phase2-hotspot-baseline: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase2_hotspot_baseline.py --paths src/sdetkit/repo.py src/sdetkit/doctor.py --out docs/artifacts/phase2-hotspot-baseline-$(DATE_TAG).json'

phase2-hotspot-delta: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase2_hotspot_delta.py --baseline $(PHASE2_BASELINE_PRE_EXTRACTION) --current docs/artifacts/phase2-hotspot-baseline-$(DATE_TAG).json --out-json docs/artifacts/phase2-hotspot-delta-$(DATE_TAG).json --out-md docs/artifacts/phase2-hotspot-delta-$(DATE_TAG).md'

phase2-complete: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase2_complete_workflow.py --format json'
	@bash -lc '. .venv/bin/activate && python scripts/phase2_progress_report.py --format json --out build/phase2-complete/phase2-progress.json'

phase2-progress: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase2_progress_report.py --format json --out build/phase2-complete/phase2-progress.json'

phase2-surface-clarity: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_operator_essentials_contract.py --format json'

phase3-dependency-radar: install
	@bash -lc '. .venv/bin/activate && python scripts/phase3_dependency_radar.py --policy-json config/dependency_slo_policy.json --out docs/artifacts/phase3-dependency-radar-$(DATE_TAG).json'

phase3-quality-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase1_baseline_summary_contract.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json && python -m scripts.check_phase3_quality_contract --summary build/phase1-baseline/phase1-baseline-summary.json --format json && python -m scripts.phase3_persist_baseline_history --summary build/phase1-baseline/phase1-baseline-summary.json --format json && $(MAKE) phase3-dependency-radar'

phase3-quality-report: phase3-quality-contract
	@bash -lc '. .venv/bin/activate && python -m scripts.build_phase3_trend_delta --current build/phase1-baseline/phase1-baseline-summary.json --out-json build/phase3-quality/phase3-trend-delta.json --out-md build/phase3-quality/phase3-trend-delta.md --format json'

phase3-do-it: phase3-quality-report
	@bash -lc 'echo "phase3-do-it is deprecated; use phase3-quality-report"'

phase4-governance-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase4_governance_contract.py --format json'

phase5-ecosystem-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase5_ecosystem_contract.py --format json'

phase6-metrics-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase6_metrics_contract.py --format json'

phase6-start: phase6-metrics-contract

phase6-status: phase6-metrics-contract

phase6-progress: phase6-metrics-contract

phase6-complete: phase6-metrics-contract
