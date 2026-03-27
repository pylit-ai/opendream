# plan.md — 404-framework-adapter-pack

## Summary
Add thin adapter packs for Claude Code, Codex, and OpenClaw under `.meta/spec-adapters/`. Keep adapters documentation-first and command-driven. Do not move canonical requirements out of `specs/`.

## Architecture impact
- touched components:
  - `.meta/spec-adapters/claude-code/`
  - `.meta/spec-adapters/codex/`
  - `.meta/spec-adapters/openclaw/`
  - `README.md`
  - `scripts/check_adapters.py`
  - `Makefile`
- unchanged components:
  - durable memory schemas
  - extractor, consolidator, and retriever semantics

## Data model / contract changes
- none to canonical runtime schemas
- adapter packs shell out to the existing CLI contract

## Interfaces
- input:
  - framework lifecycle events
  - repo path or workspace path
  - OpenDream CLI
- output:
  - emitted memory events
  - prompt-ready context injection
  - scheduled or hook-driven maintenance ticks

## Deliverables
- Claude Code adapter:
  - `.meta/spec-adapters/claude-code/README.md`
  - `.meta/spec-adapters/claude-code/hooks/example-settings.json`
  - `.meta/spec-adapters/claude-code/skills/opendream-context/SKILL.md`
  - `.meta/spec-adapters/claude-code/scripts/opendream-pre-task.sh`
  - `.meta/spec-adapters/claude-code/scripts/opendream-post-task.sh`
- Codex adapter:
  - `.meta/spec-adapters/codex/README.md`
  - `.meta/spec-adapters/codex/AGENTS.global.example.md`
  - `.meta/spec-adapters/codex/AGENTS.project.snippet.md`
  - `.meta/spec-adapters/codex/skills/opendream-context/SKILL.md`
  - `.meta/spec-adapters/codex/scripts/opendream-pre-task.sh`
  - `.meta/spec-adapters/codex/scripts/opendream-post-task.sh`
- OpenClaw adapter:
  - `.meta/spec-adapters/openclaw/README.md`
  - `.meta/spec-adapters/openclaw/event-map.md`
  - `.meta/spec-adapters/openclaw/prompt-snippets/pre-plan.md`
  - `.meta/spec-adapters/openclaw/prompt-snippets/post-task.md`
  - `.meta/spec-adapters/openclaw/scripts/opendream-hooks.sh`

## Observability
- adapter examples log invoked commands and exit cleanly
- smoke checks verify referenced CLI commands exist
- docs distinguish prompt prep from post-task maintenance

## Security / safety review
- auth changes: none in core runtime
- secret handling: adapter docs warn against routing sensitive material into durable memory
- external services: none required
- irreversible actions: none

## Rollout
1. add spec and registry entry
2. add adapter directories and READMEs
3. add example scripts and payloads
4. add adapter smoke validation
5. rerun `make verify`

## Rollback
1. remove `.meta/spec-adapters/*`
2. remove adapter smoke checks
3. keep core runtime unchanged

## Verification plan
- run: `python3 scripts/check_adapters.py`
- run: `make verify`
- manual checks:
  - run the Claude Code wrapper scripts in a temp repo
  - run the Codex wrapper scripts in a temp repo
  - inspect OpenClaw prompt snippets and hook script

## ADR needed?
- no
