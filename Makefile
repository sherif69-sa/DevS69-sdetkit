# --- dev targets (bootstrap) ---

.PHONY: venv install test cov lint fmt type docs-serve docs-build package-validate release-preflight

venv:
	@test -x .venv/bin/python || python3 -m venv .venv

install: venv
	@bash -lc '. .venv/bin/activate && python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .'

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

docs-serve: install
	@bash -lc '. .venv/bin/activate && mkdocs serve'

docs-build: install
	@bash -lc '. .venv/bin/activate && mkdocs build'


package-validate: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python -m pip install -e .[packaging] && rm -rf dist build && python -m build && python -m twine check dist/* && python -m check_wheel_contents --ignore W009 dist/*.whl && python -m venv .venv-smoke && . .venv-smoke/bin/activate && python -m pip install --force-reinstall dist/*.whl && sdetkit --help'


release-preflight: venv
	@bash -lc 'set -euo pipefail; . .venv/bin/activate && python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .[packaging] && python scripts/release_preflight.py && python -m sdetkit doctor --release --skip clean_tree --format md && $(MAKE) package-validate'
