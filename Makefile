# Developer entry points. CI runs quality.sh and ci.sh directly.

VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate
PIP_INSTALL = python -m pip install -c constraints-ci.txt
FIRST_PROOF_STRICT ?= false
FIRST_PROOF_RELEASE_DRY_RUN ?= true

.PHONY: help venv install test lint format-before-proof proof-after-format merge-ready \
	gate-fast gate-release doctor \
	first-proof first-proof-contract first-proof-verify package-validate \
	release-preflight docs lock clean

help:
	@echo "install            create .venv and install sdetkit with test and docs extras"
	@echo "test | lint        run the test suite or the linters (quality.sh)"
	@echo "proof-after-format format the tree, then run every pre-commit hook (the standard local proof)"
	@echo "merge-ready        bootstrap contract + full quality verification"
	@echo "gate-fast          sdetkit gate fast"
	@echo "gate-release       sdetkit gate release"
	@echo "doctor             sdetkit doctor"
	@echo "first-proof-verify run the first-proof lane and validate its summary"
	@echo "package-validate   build, twine-check and smoke-install the wheel"
	@echo "release-preflight  release checks + package validation"
	@echo "docs               build the documentation site (strict)"
	@echo "lock               refresh uv.lock after changing dependencies in pyproject.toml"

venv:
	@test -x $(VENV)/bin/python || python3 -m venv $(VENV)

install: venv
	@bash -lc '$(ACTIVATE) && $(PIP_INSTALL) -r requirements-test.txt -r requirements-docs.txt -e .'

test: install
	@bash -lc '$(ACTIVATE) && bash quality.sh test'

lint: install
	@bash -lc '$(ACTIVATE) && bash quality.sh lint'

format-before-proof: venv
	@bash -lc '$(ACTIVATE) && python -m ruff format . && python -m ruff check --fix --select I .'

proof-after-format: format-before-proof
	@bash -lc '$(ACTIVATE) && python -m pre_commit run -a'

merge-ready: install
	@bash -lc '$(ACTIVATE) && python -m sdetkit.test_bootstrap_contract --strict && python -m sdetkit.test_bootstrap_validate --strict && bash quality.sh verify'

gate-fast: install
	@bash -lc '$(ACTIVATE) && python -m sdetkit gate fast'

gate-release: install
	@bash -lc '$(ACTIVATE) && python -m sdetkit gate release'

doctor: install
	@bash -lc '$(ACTIVATE) && python -m sdetkit doctor'

first-proof: venv
	@bash -lc '$(ACTIVATE) && $(PIP_INSTALL) -r requirements-test.txt -e . && PYTHONPATH=src python scripts/first_proof.py $(if $(filter true,$(FIRST_PROOF_STRICT)),--strict,) $(if $(filter true,$(FIRST_PROOF_RELEASE_DRY_RUN)),--release-dry-run,) --format json --out-dir build/first-proof'

first-proof-contract: venv
	@bash -lc '$(ACTIVATE) && python scripts/check_first_proof_summary_contract.py --summary build/first-proof/first-proof-summary.json --wait-seconds 60 --format json'

first-proof-verify: first-proof
	@$(MAKE) first-proof-contract

package-validate: venv
	@bash -lc 'set -euo pipefail; $(ACTIVATE) && $(PIP_INSTALL) -e .[packaging] && rm -rf dist build && python -m build && python -m twine check dist/* && python -m check_wheel_contents --ignore W009 dist/*.whl && python -m venv .venv-smoke && . .venv-smoke/bin/activate && python -m pip install --force-reinstall dist/*.whl && sdetkit --help'

release-preflight: venv
	@bash -lc 'set -euo pipefail; $(ACTIVATE) && $(PIP_INSTALL) -r requirements-test.txt -r requirements-docs.txt -e .[packaging] && python scripts/release_preflight.py && python scripts/check_first_proof_summary_contract.py --summary build/first-proof/first-proof-summary.json --format json && python -m sdetkit doctor --release --skip clean_tree --format md && $(MAKE) package-validate'

docs: install
	@bash -lc '$(ACTIVATE) && NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict'

lock: venv
	@bash -lc '$(ACTIVATE) && $(PIP_INSTALL) uv && uv lock $$(sed -nE "s/^([A-Za-z0-9_.-]+)==([^ ;#]+).*/-P \1==\2/p" constraints-ci.txt | grep -v "^-P uv==")'

clean:
	rm -rf build dist .venv-smoke .pytest_cache .mypy_cache .ruff_cache
