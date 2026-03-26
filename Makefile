
# Stub targets; replace with real commands for your stack.
# See AGENTS.md for expected commands.

.PHONY: setup dev test lint typecheck verify

setup:
	@echo "Run your install/setup command (e.g. npm install, uv sync)"
	@exit 1

dev:
	@echo "Run your dev server command"
	@exit 1

test:
	@echo "Run your test command"
	@exit 1

lint:
	@echo "Run your linter"
	@exit 1

typecheck:
	@echo "Run your type checker"
	@exit 1

verify: lint typecheck test
	@echo "Full verify passed"

