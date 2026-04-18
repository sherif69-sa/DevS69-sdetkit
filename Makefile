# --- dev targets (bootstrap) ---

DATE_TAG ?= 2026-04-17
WINDOW_START ?= 2026-04-11
WINDOW_END ?= 2026-04-17
GENERATED_AT ?= 2026-04-17T10:00:00Z
ADAPTIVE_SCENARIO ?= balanced
PORTFOLIO_MANIFEST ?= portfolio-manifest.json

.PHONY: bootstrap max brutal venv install test cov lint fmt type docs-serve docs-build package-validate release-preflight release-verify-plan upgrade-audit upgrade-audit-ci registry golden-path-health canonical-path-drift legacy-command-analyzer legacy-burndown adoption-scorecard adoption-scorecard-contract observability-contract operator-onboarding-wizard primary-docs-map top-tier-reporting enterprise-contracts-check enterprise-assessment enterprise-assessment-contract ship-readiness ship-readiness-contract release-room portfolio-readiness premerge-release-room adaptive-scenario-db adaptive-postcheck adaptive-ops-bundle test-bootstrap test-bootstrap-contract merge-ready phase1-baseline phase1-status phase1-next phase1-complete phase2-surface-clarity phase3-quality-contract phase4-governance-contract phase5-ecosystem-contract phase6-metrics-contract

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
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .[packaging] && python scripts/release_preflight.py && python -m sdetkit doctor --release --skip clean_tree --format md && $(MAKE) package-validate'


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


adaptive-scenario-db: venv
	@bash -lc '. .venv/bin/activate && python scripts/build_adaptive_scenario_database.py . --out docs/artifacts/adaptive-scenario-database-$(DATE_TAG).json'


adaptive-ops-bundle: adaptive-postcheck enterprise-contracts-check
	@bash -lc '. .venv/bin/activate && python scripts/build_adaptive_ops_summary.py --out-md docs/artifacts/adaptive-ops-summary-$(DATE_TAG).md --out-json docs/artifacts/adaptive-ops-summary-$(DATE_TAG).json'

phase1-baseline: install
	@bash -lc '. .venv/bin/activate && bash scripts/phase1_baseline_lane.sh'

phase1-status: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_status_report.py --format json --out build/phase1-baseline/phase1-status.json'

phase1-next: venv
	@bash -lc '. .venv/bin/activate && python scripts/phase1_next_actions.py --status-json build/phase1-baseline/phase1-status.json --format json'

phase1-complete: install
	@bash -lc '. .venv/bin/activate && bash scripts/phase1_baseline_lane.sh && python scripts/check_phase1_baseline_summary_contract.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json --require-logs && python scripts/phase1_completion_gate.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json'

phase2-surface-clarity: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_operator_essentials_contract.py --format json'

phase3-quality-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase1_baseline_summary_contract.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json'

phase4-governance-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase4_governance_contract.py --format json'

phase5-ecosystem-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase5_ecosystem_contract.py --format json'

phase6-metrics-contract: venv
	@bash -lc '. .venv/bin/activate && python scripts/check_phase6_metrics_contract.py --format json'
