# --- dev targets (bootstrap) ---

DATE_TAG ?= 2026-04-24
WINDOW_START ?= 2026-04-11
WINDOW_END ?= 2026-04-17
GENERATED_AT ?= 2026-04-17T10:00:00Z
ADAPTIVE_SCENARIO ?= balanced
PORTFOLIO_MANIFEST ?= portfolio-manifest.json
FIRST_PROOF_BRANCH ?= local
FIRST_PROOF_STRICT ?= false
FIRST_PROOF_RELEASE_DRY_RUN ?= true
FIRST_PROOF_READINESS_PROFILE ?= standard
PHASE2_BASELINE_PRE_EXTRACTION ?= docs/artifacts/phase2-hotspot-baseline-pre-extraction-$(DATE_TAG).json
BUSINESS_EXECUTION_OPERATOR ?= sherif69-sa

.PHONY: bootstrap max brutal venv runtime-install first-proof-install install ci-deps-sync test cov lint fmt type docs-serve docs-build package-validate release-preflight release-verify-plan upgrade-audit upgrade-audit-ci registry upgrade-next onboarding-next doctor-remediate first-proof-freshness first-proof-ops-bundle-contract first-proof-ops-bundle-trend first-proof-ops-bundle-trend-report first-proof-execution-report first-proof-execution-contract first-proof-schema-contract upgrade-status-line first-proof-followup-ready followup-ready-metrics first-proof-dashboard first-proof-readiness-threshold followup-changelog plan-next-10 cleanup-first-proof-artifacts golden-path-health canonical-path-drift legacy-command-analyzer legacy-burndown adoption-scorecard adoption-scorecard-contract observability-contract operator-onboarding-wizard primary-docs-map top-tier-reporting enterprise-contracts-check enterprise-assessment enterprise-assessment-contract ship-readiness ship-readiness-fast ship-readiness-contract release-room release-room-fast portfolio-readiness premerge-release-room premerge-release-room-fast adaptive-scenario-db adaptive-postcheck owner-escalation-payload adaptive-premerge adaptive-ops-bundle repo-alignment-check test-bootstrap test-bootstrap-contract merge-ready premerge-finalize first-proof first-proof-local first-proof-contract first-proof-health-score first-proof-learn first-proof-control-tower first-proof-weekly-trend first-proof-trend-threshold first-proof-tests first-proof-tests-local first-proof-verify first-proof-verify-local gate-decision-summary gate-decision-summary-contract fit-check adoption-followup adoption-followup-contract adoption-control-loop adoption-control-loop-contract adoption-posture adoption-validate adoption-control-loop-full ops-followup ops-followup-contract ops-now ops-now-lite ops-next ops-premerge-next ops-premerge-next-fast phase1-baseline phase1-status phase1-next phase1-ops-snapshot phase1-dashboard phase1-weekly-pack phase1-control-loop phase1-run-all phase1-artifact-set phase1-telemetry phase1-finish-signal phase1-next-pass phase1-blocker-register phase1-do-it phase1-execution-core phase1-workflow phase1-flow-contract phase1-gate-phase2 phase1-executive-report phase1-retire-plan phase1-complete phase1-closeout phase-current phase-current-json phase2-start phase2-workflow phase2-status phase2-start-contract phase2-seed phase2-hotspot-baseline phase2-hotspot-delta phase2-complete phase2-progress phase2-surface-clarity phase3-dependency-radar phase3-quality-contract phase3-quality-report phase3-do-it phase4-governance-contract phase5-ecosystem-contract phase6-start phase6-status phase6-progress phase6-complete phase6-metrics-contract plan-status phase1-execute phase2-execute phase3-governance phase4-credibility real-workflow-daily real-workflow-daily-fast real-workflow-weekly real-workflow-premerge real-workflow-premerge-fast real-workflow ops-daily ops-daily-fast ops-weekly ops-premerge ops-premerge-fast ops-workflow
.PHONY: business-execution-start business-execution-start-contract business-execution-go-gate business-execution-progress business-execution-progress-contract business-execution-next business-execution-next-contract business-execution-handoff business-execution-handoff-contract business-execution-escalation business-execution-escalation-contract business-execution-followup business-execution-followup-contract business-execution-continue business-execution-continue-contract business-execution-horizon business-execution-horizon-contract business-execution-inputs-contract business-execution-pipeline business-execution-week1-pipeline

bootstrap: venv
	@bash -lc '. .venv/bin/activate && bash scripts/bootstrap.sh'

max: bootstrap
	@bash -lc '. .venv/bin/activate && bash quality.sh boost'

brutal: bootstrap
	@bash -lc '. .venv/bin/activate && bash quality.sh brutal'

venv:
	@test -x .venv/bin/python || bash -lc 'set -euo pipefail; if [ -x "$$HOME/.pyenv/versions/3.11.14/bin/python" ]; then "$$HOME/.pyenv/versions/3.11.14/bin/python" -m venv .venv; else python3 -m venv .venv; fi'

runtime-install: venv
	@bash -lc '. .venv/bin/activate && python -m pip install -c constraints-ci.txt -e .'

first-proof-install: runtime-install
	@bash -lc '. .venv/bin/activate && python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .'

install: runtime-install
	@bash -lc '. .venv/bin/activate && python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .'

ci-deps-sync: venv
	@bash -lc '. .venv/bin/activate && python -m pip install --upgrade pip && python -m pip install -c constraints-ci.txt -e .[dev,test] && python -m pip install -c constraints-ci.txt -e .[dev,packaging] && python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .'

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

first-proof: first-proof-install
	@bash -lc '. .venv/bin/activate && PYTHONPATH=src python scripts/first_proof.py $(if $(filter true,$(FIRST_PROOF_STRICT)),--strict,) $(if $(filter true,$(FIRST_PROOF_RELEASE_DRY_RUN)),--release-dry-run,) --format json --out-dir build/first-proof'

first-proof-local: venv
	@bash -lc '. .venv/bin/activate && PYTHONPATH=src python scripts/first_proof.py $(if $(filter true,$(FIRST_PROOF_STRICT)),--strict,) $(if $(filter true,$(FIRST_PROOF_RELEASE_DRY_RUN)),--release-dry-run,) --format json --out-dir build/first-proof'

first-proof-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_summary_contract.py --summary build/first-proof/first-proof-summary.json --wait-seconds 60 --format json'

first-proof-health-score: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_first_proof_health_score.py --summary build/first-proof/first-proof-summary.json --out-json build/first-proof/health-score.json --out-md build/first-proof/health-score.md --format json'

first-proof-freshness: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_artifact_freshness.py --artifact-dir build/first-proof --max-age-hours 48 --out build/first-proof/artifact-freshness.json --format json'

first-proof-learn: venv
	@bash -lc '. .venv/bin/activate && python scripts/first_proof_learning_db.py --summary build/first-proof/first-proof-summary.json --db build/first-proof/first-proof-learning-db.jsonl --rollup-out build/first-proof/first-proof-learning-rollup.json --format json'

first-proof-control-tower: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_first_proof_control_tower.py --first-proof-rollup build/first-proof/first-proof-learning-rollup.json --adaptive-postcheck build/adaptive-postcheck-min.json --out-json build/first-proof/control-tower.json --out-md build/first-proof/control-tower.md --format json'

first-proof-weekly-trend: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_first_proof_weekly_trend.py --db build/first-proof/first-proof-learning-db.jsonl --adaptive-postcheck build/adaptive-postcheck-min.json --out-json build/first-proof/weekly-trend.json --out-md build/first-proof/weekly-trend.md --format json'

first-proof-trend-threshold: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_trend_threshold.py --trend build/first-proof/weekly-trend.json --branch $(FIRST_PROOF_BRANCH) --profile-config config/first_proof_threshold_profiles.json --min-ship-rate 0.50 --min-total-runs 3 --min-consecutive-breaches 2 --out build/first-proof/weekly-threshold-check.json --format json'

first-proof-tests: install
	@bash -lc '. .venv/bin/activate && python -m pytest -q tests/test_first_proof_script.py tests/test_first_proof_contract.py tests/test_first_proof_learning_db.py tests/test_first_proof_weekly_trend.py tests/test_first_proof_control_tower.py tests/test_first_proof_trend_threshold.py tests/test_build_owner_escalation_payload.py'

first-proof-tests-local: venv
	@bash -lc '. .venv/bin/activate && python -m pytest -q tests/test_first_proof_script.py tests/test_first_proof_contract.py tests/test_first_proof_learning_db.py tests/test_first_proof_weekly_trend.py tests/test_first_proof_control_tower.py tests/test_first_proof_trend_threshold.py tests/test_build_owner_escalation_payload.py'

first-proof-verify: first-proof
	@bash -lc '. .venv/bin/activate && $(MAKE) first-proof-contract && $(MAKE) first-proof-learn && $(MAKE) first-proof-ops-bundle && $(MAKE) first-proof-ops-bundle-contract && $(MAKE) first-proof-ops-bundle-trend && $(MAKE) first-proof-ops-bundle-trend-report && $(MAKE) first-proof-execution-report && $(MAKE) first-proof-execution-contract && $(MAKE) first-proof-schema-contract && $(MAKE) upgrade-status-line && $(MAKE) first-proof-followup-ready && $(MAKE) followup-ready-metrics && $(MAKE) first-proof-dashboard && $(MAKE) first-proof-readiness-threshold && $(MAKE) followup-changelog && $(MAKE) first-proof-control-tower && $(MAKE) first-proof-weekly-trend && $(MAKE) first-proof-trend-threshold && $(MAKE) first-proof-tests'

first-proof-verify-local: first-proof-local
	@bash -lc '. .venv/bin/activate && $(MAKE) first-proof-contract && $(MAKE) first-proof-learn && $(MAKE) first-proof-ops-bundle && $(MAKE) first-proof-ops-bundle-contract && $(MAKE) first-proof-ops-bundle-trend && $(MAKE) first-proof-ops-bundle-trend-report && $(MAKE) first-proof-execution-report && $(MAKE) first-proof-execution-contract && $(MAKE) first-proof-schema-contract && $(MAKE) upgrade-status-line && $(MAKE) first-proof-followup-ready && $(MAKE) followup-ready-metrics && $(MAKE) first-proof-dashboard && $(MAKE) first-proof-readiness-threshold && $(MAKE) followup-changelog && $(MAKE) first-proof-control-tower && $(MAKE) first-proof-weekly-trend && $(MAKE) first-proof-trend-threshold && $(MAKE) first-proof-tests-local'

gate-decision-summary: venv
	@bash -lc '. .venv/bin/activate && python scripts/render_gate_decision_summary.py --release build/release-preflight.json --fast build/gate-fast.json --allow-missing-fast --format json --out build/gate-decision-summary.json'
	@bash -lc '. .venv/bin/activate && python scripts/render_gate_decision_summary.py --release build/release-preflight.json --fast build/gate-fast.json --allow-missing-fast --format text --out build/gate-decision-summary.md > /dev/null'
	@bash -lc 'echo gate-decision-summary: wrote build/gate-decision-summary.json and build/gate-decision-summary.md'

gate-decision-summary-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_gate_decision_summary_contract.py --summary build/gate-decision-summary.json --release build/release-preflight.json --allow-missing-release --format json'

fit-check: venv
	@bash -lc '. .venv/bin/activate && python -m sdetkit fit --repo-size medium --team-size medium --release-frequency medium --change-failure-impact medium --compliance-pressure medium --format json --out build/sdetkit-fit-recommendation.json'
	@bash -lc 'echo fit-check: wrote build/sdetkit-fit-recommendation.json'

adoption-followup: venv
	@bash -lc '. .venv/bin/activate && python -m sdetkit adoption --fit build/sdetkit-fit-recommendation.json --summary build/gate-decision-summary.json --format json --out build/adoption-followup.json --history build/adoption-followup-history.jsonl --history-rollup-out build/adoption-followup-history-rollup.json'
	@bash -lc '. .venv/bin/activate && python -m sdetkit adoption --fit build/sdetkit-fit-recommendation.json --summary build/gate-decision-summary.json --format md --out build/adoption-followup.md --history build/adoption-followup-history.jsonl --history-rollup-out build/adoption-followup-history-rollup.json > /dev/null'
	@bash -lc 'echo adoption-followup: wrote build/adoption-followup.json, build/adoption-followup.md, build/adoption-followup-history.jsonl, and build/adoption-followup-history-rollup.json'

adoption-followup-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_adoption_followup_contract.py --followup build/adoption-followup.json --history-rollup build/adoption-followup-history-rollup.json --format json'

adoption-control-loop: fit-check gate-decision-summary gate-decision-summary-contract adoption-followup adoption-followup-contract
	@bash -lc 'echo adoption-control-loop: fit + gate summary + follow-up + contracts completed'

adoption-control-loop-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_adoption_control_loop_artifacts.py --artifact-dir build --format json'

adoption-posture: venv
	@bash -lc '. .venv/bin/activate && python scripts/render_adoption_posture.py --followup build/adoption-followup.json --rollup build/adoption-followup-history-rollup.json --format json --out build/adoption-posture.json'
	@bash -lc '. .venv/bin/activate && python scripts/render_adoption_posture.py --followup build/adoption-followup.json --rollup build/adoption-followup-history-rollup.json --format md --out build/adoption-posture.md > /dev/null'
	@bash -lc 'echo adoption-posture: wrote build/adoption-posture.json and build/adoption-posture.md'

adoption-validate: venv
	@bash -lc '. .venv/bin/activate && python scripts/run_adoption_validation_suite.py --out build/adoption-validation-summary.json'

adoption-control-loop-full: adoption-control-loop adoption-control-loop-contract adoption-posture adoption-validate
	@bash -lc 'echo adoption-control-loop-full: loop + contracts + posture + validation completed'

ops-followup: venv
	@bash -lc '. .venv/bin/activate && python scripts/real_workflow_followup.py --format json --out-json build/ops/followup.json --out-md build/ops/followup.md --history build/ops/followup-history.jsonl --history-rollup-out build/ops/followup-history-rollup.json'

ops-followup-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_real_workflow_followup_contract.py --followup build/ops/followup.json --history-rollup build/ops/followup-history-rollup.json --out build/ops/followup-contract-check.json --format json'

ops-now-lite: ops-followup ops-followup-contract
	@bash -lc 'echo ops-now-lite: follow-up generated + contract validated'
	@bash -lc 'python -c "import json; from pathlib import Path; p = Path(\"build/ops/followup.json\"); payload = json.loads(p.read_text(encoding=\"utf-8\")) if p.exists() else {}; print(\"OPS_DECISION=\" + str(payload.get(\"decision\", \"NO-DATA\"))); print(\"OPS_NEXT_COMMAND=\" + str(payload.get(\"next_command\", \"make ops-daily\")))"'

ops-now: real-workflow-daily
	@bash -lc 'echo ops-now: full daily workflow completed'
	@bash -lc 'python -c "import json; from pathlib import Path; p = Path(\"build/ops/followup.json\"); payload = json.loads(p.read_text(encoding=\"utf-8\")) if p.exists() else {}; print(\"OPS_DECISION=\" + str(payload.get(\"decision\", \"NO-DATA\"))); print(\"OPS_NEXT_COMMAND=\" + str(payload.get(\"next_command\", \"make ops-daily\")))"'

ops-next: ops-now-lite
	@bash -lc '. .venv/bin/activate && python scripts/ops_next.py --followup build/ops/followup.json --limit 3'

ops-premerge-next:
	@bash -lc '. .venv/bin/activate && $(MAKE) ops-premerge || true'
	@bash -lc '. .venv/bin/activate && python scripts/ops_premerge_next.py --gate-json build/premerge-release-room-gate.json --limit 3'

ops-premerge-next-fast:
	@bash -lc '. .venv/bin/activate && $(MAKE) ops-premerge-fast || true'
	@bash -lc '. .venv/bin/activate && python scripts/ops_premerge_next.py --gate-json build/premerge-release-room-gate.json --limit 3'

real-workflow-daily: first-proof-verify ops-followup ops-followup-contract
	@bash -lc 'echo real-workflow-daily: deterministic gate + learning loop + validated follow-up completed'

real-workflow-daily-fast: first-proof-verify-local ops-followup ops-followup-contract
	@bash -lc 'echo "real-workflow-daily-fast: deterministic gate + validated follow-up completed (no reinstall lane)"'

real-workflow-weekly: adaptive-postcheck top-tier-reporting enterprise-contracts-check
	@bash -lc 'echo real-workflow-weekly: reporting + contracts refreshed'

real-workflow-premerge: premerge-release-room release-room
	@bash -lc 'echo real-workflow-premerge: pre-merge gate + release room checks completed'

real-workflow-premerge-fast: premerge-release-room-fast release-room-fast
	@bash -lc 'echo "real-workflow-premerge-fast: pre-merge gate (release dry-run) + release room checks completed"'

real-workflow: real-workflow-daily real-workflow-weekly
	@bash -lc 'echo real-workflow: daily and weekly lanes completed'

ops-daily: real-workflow-daily
	@bash -lc 'echo ops-daily: alias completed'

ops-daily-fast: real-workflow-daily-fast
	@bash -lc 'echo ops-daily-fast: alias completed'

ops-weekly: real-workflow-weekly
	@bash -lc 'echo ops-weekly: alias completed'

ops-premerge: real-workflow-premerge
	@bash -lc 'echo ops-premerge: alias completed'

ops-premerge-fast: real-workflow-premerge-fast
	@bash -lc 'echo ops-premerge-fast: alias completed'

ops-workflow: real-workflow
	@bash -lc 'echo ops-workflow: alias completed'

upgrade-next:
	@bash -lc 'echo "=== SDETKit Upgrade Next (Guided Path) ==="'
	@bash -lc 'echo "1) make first-proof"'
	@bash -lc 'echo "2) make first-proof-verify"'
	@bash -lc 'echo "3) make ops-now-lite"'
	@bash -lc 'echo "4) make ops-next"'
	@bash -lc 'echo "5) make plan-status"'
	@bash -lc 'echo "Docs: docs/upgrade-next-commands.md"'

business-execution-start: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_start.py --single-operator "$(BUSINESS_EXECUTION_OPERATOR)"'

business-execution-start-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_start_contract.py'

business-execution-go-gate: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_start_contract.py --require-go'

business-execution-progress: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_progress.py'

business-execution-progress-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_progress_contract.py'

business-execution-next: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_next.py'

business-execution-next-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_next_contract.py'

business-execution-handoff: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_handoff.py'

business-execution-handoff-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_handoff_contract.py'

business-execution-escalation: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_escalation.py'

business-execution-escalation-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_escalation_contract.py'

business-execution-followup: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_followup.py'

business-execution-followup-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_followup_contract.py'

business-execution-continue: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_continue.py'

business-execution-continue-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_continue_contract.py'

business-execution-horizon: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_horizon.py'

business-execution-horizon-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_horizon_contract.py'

business-execution-inputs-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_business_execution_inputs_contract.py'

business-execution-pipeline: venv
	@bash -lc '. .venv/bin/activate && python scripts/business_execution_pipeline.py --single-operator "$(BUSINESS_EXECUTION_OPERATOR)"'

business-execution-week1-pipeline: business-execution-pipeline
	@bash -lc 'echo business-execution-week1-pipeline: alias completed'

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

ship-readiness-fast: venv
	@bash -lc '. .venv/bin/activate && python -m sdetkit ship-readiness --strict --release-dry-run --format json --out-dir build/ship-readiness'

ship-readiness-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_ship_readiness_contract.py --summary build/ship-readiness/ship-readiness-summary.json --format json'

release-room: enterprise-assessment ship-readiness ship-readiness-contract enterprise-assessment-contract
	@bash -lc '. .venv/bin/activate && python scripts/render_release_room_summary.py --ship-summary build/ship-readiness/ship-readiness-summary.json --enterprise-summary docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json --out build/release-room-summary.md'

release-room-fast: enterprise-assessment ship-readiness-fast ship-readiness-contract enterprise-assessment-contract
	@bash -lc '. .venv/bin/activate && python scripts/render_release_room_summary.py --ship-summary build/ship-readiness/ship-readiness-summary.json --enterprise-summary docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json --out build/release-room-summary.md'

portfolio-readiness: venv
	@bash -lc '. .venv/bin/activate && python -m sdetkit portfolio-readiness --manifest $(PORTFOLIO_MANIFEST) --format json --out build/portfolio-readiness.json'

premerge-release-room: venv
	@bash -lc '. .venv/bin/activate && python scripts/premerge_release_room_gate.py . --strict --format json --out build/premerge-release-room-gate.json'

premerge-release-room-fast: venv
	@bash -lc '. .venv/bin/activate && python scripts/premerge_release_room_gate.py . --strict --ship-release-dry-run --format json --out build/premerge-release-room-gate.json'


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

phase1-do-it: phase1-run-all phase1-artifact-set phase1-telemetry phase1-finish-signal
	@bash -lc 'echo phase1-do-it is deprecated; use phase1-execution-core'

phase1-workflow: phase1-execution-core phase1-flow-contract phase1-gate-phase2 phase1-executive-report
	@bash -lc 'echo phase1-workflow: operational workflow completed'

phase1-flow-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase1_flow_contract.py --format json'

phase1-gate-phase2: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_gate_phase2.py --format json > build/phase1-baseline/phase1-gate-phase2.json'

phase1-executive-report: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_executive_report.py --format json'

phase1-retire-plan: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_retire_plan_into_flow.py --format json'

phase1-closeout: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_closeout_and_prune_plan.py --format json'

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

phase3-do-it: phase3-quality-contract
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

.PHONY: failure-plan failure-autofix failure-workflow
failure-plan:
	python scripts/build_failure_action_plan.py

failure-autofix:
	python scripts/failure_autofix_workflow.py --max-actions 5

failure-workflow: failure-plan failure-autofix
	@echo "failure workflow complete: see examples/kits/intelligence/failure-autofix-report.json"

doctor-remediate: venv
	@bash -lc '. .venv/bin/activate && python scripts/doctor_remediate.py --summary build/first-proof/first-proof-summary.json --out-json build/first-proof/doctor-remediate.json --out-md build/first-proof/doctor-remediate.md --limit 3 --format json'

onboarding-next: venv
	@bash -lc '. .venv/bin/activate && python scripts/operator_onboarding_next.py --summary build/first-proof/first-proof-summary.json --out-json build/onboarding-next.json --out-md build/onboarding-next.md --format json'

first-proof-ops-bundle: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_first_proof_ops_bundle.py --artifact-dir build/first-proof --format json'

first-proof-ops-bundle-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_ops_bundle_contract.py --manifest build/first-proof/ops-bundle-manifest.json --out build/first-proof/ops-bundle-contract.json --format json'

first-proof-ops-bundle-trend: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_first_proof_ops_bundle_trend.py --contract build/first-proof/ops-bundle-contract.json --history build/first-proof/ops-bundle-contract-history.jsonl --out build/first-proof/ops-bundle-contract-trend.json --window 10 --branch $(FIRST_PROOF_BRANCH) --format json'

first-proof-execution-report: venv
	@bash -lc '. .venv/bin/activate && python scripts/render_first_proof_execution_report.py --artifact-dir build/first-proof --onboarding build/onboarding-next.json --out-json build/first-proof/execution-report.json --out-md build/first-proof/execution-report.md --format json'

first-proof-execution-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_execution_contract.py --artifact-dir build/first-proof --out build/first-proof/execution-contract.json --format json'

upgrade-status-line: venv
	@bash -lc '. .venv/bin/activate && python scripts/render_upgrade_status_line.py --artifact-dir build/first-proof --onboarding build/onboarding-next.json --out build/first-proof/upgrade-status-line.txt --format text'

first-proof-followup-ready: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_followup_ready.py --artifact-dir build/first-proof --onboarding build/onboarding-next.json --out build/first-proof/followup-ready.json --format json'

plan-next-10: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_next_10_followups.py --out-json build/first-proof/next-10-followups.json --out-md docs/next-10-followups.md --format json'

cleanup-first-proof-artifacts: venv
	@bash -lc '. .venv/bin/activate && python scripts/cleanup_first_proof_artifacts.py --artifact-dir build/first-proof --ttl-hours 168 --dry-run --out build/first-proof/retention-cleanup.json --format json'

followup-ready-metrics: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_followup_ready_history_metrics.py --followup build/first-proof/followup-ready.json --history build/first-proof/followup-ready-history.jsonl --out build/first-proof/followup-ready-metrics.json --format json'

first-proof-ops-bundle-trend-report: venv
	@bash -lc '. .venv/bin/activate && python scripts/render_ops_bundle_trend_report.py --trend build/first-proof/ops-bundle-contract-trend.json --history build/first-proof/ops-bundle-contract-history.jsonl --out-md build/first-proof/ops-bundle-contract-trend.md --format json'

first-proof-schema-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_schema_contract.py --artifact-dir build/first-proof --out build/first-proof/schema-contract.json --format json'

first-proof-dashboard: venv
	@bash -lc '. .venv/bin/activate && python scripts/render_first_proof_dashboard.py --artifact-dir build/first-proof --onboarding build/onboarding-next.json --out-json build/first-proof/dashboard.json --out-md build/first-proof/dashboard.md --format json'

followup-changelog: venv
	@bash -lc '. .venv/bin/activate && python scripts/append_followup_changelog.py --dashboard build/first-proof/dashboard.json --status-line build/first-proof/upgrade-status-line.txt --out build/first-proof/followup-changelog.jsonl --format json'

first-proof-readiness-threshold: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_first_proof_readiness_threshold.py --dashboard build/first-proof/dashboard.json --profiles config/first_proof_readiness_profiles.json --profile $(FIRST_PROOF_READINESS_PROFILE) --out build/first-proof/readiness-threshold.json --format json'
