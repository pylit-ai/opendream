
.PHONY: setup dev demo test lint typecheck adapters-check verify release-check

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
DEMO_WORKSPACE ?= .tmp/demo
FIXED_NOW ?= 2026-03-26T12:00:00Z

setup:
	@mkdir -p .tmp
	@python3 -m venv $(VENV)
	@$(PYTHON) --version
	@$(PYTHON) -m pip install -e '.[dev]'
	@echo "setup ok"

dev: demo

demo:
	@rm -rf $(DEMO_WORKSPACE)
	@$(PYTHON) -m opendream_memory.cli demo --workspace $(DEMO_WORKSPACE) --now $(FIXED_NOW)

test:
	@$(PYTHON) -m unittest discover -s tests -v

lint:
	@$(PYTHON) scripts/lint.py

typecheck:
	@$(PYTHON) scripts/typecheck.py

adapters-check:
	@$(PYTHON) scripts/check_adapters.py

verify:
	@$(PYTHON) scripts/verify.py

release-check:
	@$(PYTHON) scripts/release_check.py
