# --- dev targets (bootstrap) ---

DATE_TAG ?= 2026-04-17
WINDOW_START ?= 2026-04-11
WINDOW_END ?= 2026-04-17
GENERATED_AT ?= 2026-04-17T10:00:00Z

.PHONY: bootstrap max brutal venv install test cov lint fmt type docs-serve docs-build package-validate release-preflight release-verify-plan upgrade-audit upgrade-audit-ci registry golden-path-health canonical-path-drift legacy-command-analyzer legacy-burndown adoption-scorecard adoption-scorecard-contract observability-contract operator-onboarding-wizard primary-docs-map top-tier-reporting

bootstrap: venv
	@bash -lc '. .venv/bin/activate && bash scripts/bootstrap.sh'

max: bootstrap
	@bash -lc '. .venv/bin/activate && bash quality.sh boost'

brutal: bootstrap
	@bash -lc '. .venv/bin/activate && bash quality.sh brutal'

venv:
	@test -x .venv/bin/python || python3 -m venv .venv

install: venv
	@bash -lc '. .venv/bin/activate && python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .'

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
