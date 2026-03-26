
.PHONY: setup dev demo test lint typecheck verify

PYTHON ?= python3
DEMO_WORKSPACE ?= .tmp/demo
FIXED_NOW ?= 2026-03-26T12:00:00Z

setup:
	@mkdir -p .tmp
	@$(PYTHON) --version
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

verify: lint typecheck test
	@echo "verify ok"
