# --- dev targets (bootstrap) ---

.PHONY: venv install test cov lint fmt type docs-serve docs-build

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
