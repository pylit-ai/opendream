
.PHONY: setup dev demo test lint typecheck adapters-check verify release-check

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

adapters-check:
	@$(PYTHON) scripts/check_adapters.py

verify: lint typecheck test adapters-check
	@echo "verify ok"

release-check: verify
	@$(PYTHON) -m unittest tests.test_release_artifact -v
	@echo "release-check ok"
