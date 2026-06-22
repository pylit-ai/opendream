
.PHONY: help setup sync dev demo test lint typecheck package-boundaries generated-state release-artifacts docs-links adapters-check verify release-check \
	bump-patch bump-minor bump-major tag release-patch release-minor release-major clean

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
DEMO_WORKSPACE ?= .tmp/demo
FIXED_NOW ?= 2026-03-26T12:00:00Z
VERSION := $(shell grep '^version' pyproject.toml | sed 's/.*= *"\(.*\)".*/\1/')

# Default target
help:
	@echo "Targets:"
	@echo "  make sync             - uv sync --group dev (matches CI)"
	@echo "  make setup            - python3 venv + pip install -e '.[dev]'"
	@echo "  make demo             - run demo workspace"
	@echo "  make test             - unit tests"
	@echo "  make package-boundaries - package graph and contract boundary check"
	@echo "  make generated-state - generated cache/state release guard"
	@echo "  make release-artifacts - stale backup/generated artifact check"
	@echo "  make docs-links      - verify local Markdown links resolve"
	@echo "  make verify           - lint, typecheck, tests, eval, adapters, packaging smoke"
	@echo "  make release-check    - full release gate (local)"
	@echo "  make version          - print version from pyproject.toml"
	@echo "  make bump-patch       - bump patch version (updates pyproject + uv.lock)"
	@echo "  make bump-minor       - bump minor version"
	@echo "  make bump-major       - bump major version"
	@echo "  make tag              - create annotated tag v<VERSION> (no push)"
	@echo "  make release-patch    - bump patch, commit, tag, push main + tag (PyPI on tag)"
	@echo "  make release-minor    - bump minor, commit, tag, push"
	@echo "  make release-major    - bump major, commit, tag, push"
	@echo "  make clean            - remove dist, build, egg-info, __pycache__"

sync:
	uv sync --group dev

setup:
	@mkdir -p .tmp
	@python3 -m venv $(VENV)
	@$(PYTHON) --version
	@$(PYTHON) -m pip install -e '.[dev]'
	@echo "setup ok"

dev: demo

demo:
	@rm -rf $(DEMO_WORKSPACE)
	@$(PYTHON) -m opendream.cli demo --workspace $(DEMO_WORKSPACE) --now $(FIXED_NOW)

test:
	@$(PYTHON) -m unittest discover -s tests -v

lint:
	@$(PYTHON) scripts/lint.py

typecheck:
	@$(PYTHON) scripts/typecheck.py

package-boundaries:
	@$(PYTHON) scripts/check_package_boundaries.py

generated-state:
	@$(PYTHON) scripts/check_generated_state.py

release-artifacts:
	@$(PYTHON) scripts/check_release_artifacts.py

docs-links:
	@$(PYTHON) scripts/check_docs_links.py

adapters-check:
	@$(PYTHON) scripts/check_adapters.py

verify:
	@$(PYTHON) scripts/verify.py

release-check:
	@$(PYTHON) scripts/release_check.py

version:
	@uv version --short 2>/dev/null || grep '^version' pyproject.toml | sed 's/.*= *"\(.*\)".*/\1/'

bump-patch:
	uv version --bump patch

bump-minor:
	uv version --bump minor

bump-major:
	uv version --bump major

tag:
	@if [ -z "$(VERSION)" ]; then echo "Could not read version from pyproject.toml"; exit 1; fi
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@echo "Created tag v$(VERSION). Push with: git push origin v$(VERSION)"

release-patch: sync verify
	@if [ -n "$$(git status --porcelain)" ]; then echo "Working tree not clean; commit or stash first."; exit 1; fi
	uv version --bump patch
	@V=$$(grep '^version' pyproject.toml | sed 's/.*= *"\(.*\)".*/\1/'); \
	git add pyproject.toml uv.lock; \
	git commit -m "chore(release): v$$V"; \
	git tag -a v$$V -m "Release v$$V"; \
	git push origin main; \
	git push origin v$$V; \
	if command -v gh >/dev/null 2>&1; then gh release create v$$V --notes "Release v$$V"; else echo "Pushed v$$V. PyPI publish runs on tag push. Install gh to also create a GitHub Release."; fi

release-minor: sync verify
	@if [ -n "$$(git status --porcelain)" ]; then echo "Working tree not clean; commit or stash first."; exit 1; fi
	uv version --bump minor
	@V=$$(grep '^version' pyproject.toml | sed 's/.*= *"\(.*\)".*/\1/'); \
	git add pyproject.toml uv.lock; \
	git commit -m "chore(release): v$$V"; \
	git tag -a v$$V -m "Release v$$V"; \
	git push origin main; \
	git push origin v$$V; \
	if command -v gh >/dev/null 2>&1; then gh release create v$$V --notes "Release v$$V"; else echo "Pushed v$$V. PyPI publish runs on tag push."; fi

release-major: sync verify
	@if [ -n "$$(git status --porcelain)" ]; then echo "Working tree not clean; commit or stash first."; exit 1; fi
	uv version --bump major
	@V=$$(grep '^version' pyproject.toml | sed 's/.*= *"\(.*\)".*/\1/'); \
	git add pyproject.toml uv.lock; \
	git commit -m "chore(release): v$$V"; \
	git tag -a v$$V -m "Release v$$V"; \
	git push origin main; \
	git push origin v$$V; \
	if command -v gh >/dev/null 2>&1; then gh release create v$$V --notes "Release v$$V"; else echo "Pushed v$$V. PyPI publish runs on tag push."; fi

clean:
	rm -rf dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
