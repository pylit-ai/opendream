# OpenDream

OpenDream is a local-first memory subsystem for coding agents. It captures immutable evidence, derives typed memory candidates, consolidates durable memory with provenance, and exposes reproducible CLI workflows for bootstrap, consolidation, retrieval, and demo runs.

## What’s in this repo
- `opendream_memory/` - runtime package for events, candidates, consolidation, retrieval, and storage
- `.meta/spec-adapters/` - thin Claude Code, Codex, and OpenClaw adapter packs
- `tests/` - fixture-driven integration and validation tests
- `specs/401-autodream-style-memory-subsystem/` - canonical implementation spec
- `openspec/changes/401-autodream-style-memory-subsystem/` - proposal bundle and design artifacts
- `docs/` - repo-wide architecture and governance docs

## Quick start
```bash
make setup
make demo
make verify
python3 -m pip install .
opendream-memory --help
```

## CLI
Run the memory subsystem directly from the repo root:

```bash
python3 -m opendream_memory.cli init --workspace .tmp/workspace
python3 -m opendream_memory.cli init --workspace ~/.opendream-global --store-kind global
python3 -m opendream_memory.cli demo --workspace .tmp/demo
python3 -m opendream_memory.cli bootstrap-index --workspace .tmp/workspace --events tests/fixtures/bootstrap_events.jsonl
python3 -m opendream_memory.cli consolidate --workspace .tmp/workspace
python3 -m opendream_memory.cli retrieve --workspace .tmp/workspace --query "package manager and workflow"
python3 -m opendream_memory.cli emit-event --workspace .tmp/workspace --kind project_decision --content "Use pnpm in this repo" --message-ref manual-1 --tag key:package-manager
python3 -m opendream_memory.cli maintain --workspace .tmp/workspace
python3 -m opendream_memory.cli prepare-context --workspace .tmp/workspace --query "package manager and workflow"
python3 -m opendream_memory.cli prepare-context --workspace .tmp/workspace --query "package manager and workflow" --include-global --global-workspace ~/.opendream-global
python3 -m opendream_memory.cli status --workspace .tmp/workspace
python3 -m opendream_memory.cli tick --workspace .tmp/workspace
```

After install, the console entrypoint is available:

```bash
opendream-memory demo --workspace .tmp/demo
```

## Verification
- `make lint`
- `make typecheck`
- `make test`
- `python3 scripts/check_adapters.py`
- `make verify`
- `make release-check`

## Docs
- [NORTHSTAR.md](./NORTHSTAR.md)
- [PRD.md](./PRD.md)
- [CONSTITUTION.md](./CONSTITUTION.md)
- [AGENTS.md](./AGENTS.md)

## Generated data
Memory artifacts are written under a workspace-local `memory/` directory. The demo command creates a deterministic example workspace under `.tmp/demo` by default.

## Runtime integration
For real agent use, treat OpenDream as a local sidecar:
- emit memory-worthy events with `emit-event`
- use `prepare-context` to inject selected memory into the next planning prompt
- call `status` before prompting when you want lock and pending-work visibility
- call `tick` from cron, idle hooks, or session-end hooks

## Layered stores
Initialize a repo-local project store and an optional user-global store:

```bash
opendream-memory init --workspace "$PWD"
opendream-memory init --workspace ~/.opendream-global --store-kind global
```

Route user preferences into the global store:

```bash
opendream-memory emit-event \
  --workspace "$PWD" \
  --route global \
  --global-workspace ~/.opendream-global \
  --scope global \
  --kind preference_signal \
  --content "Prefer concise summaries across repos." \
  --message-ref manual-global-1 \
  --tag key:summary-style
```

Compose project and global context with project precedence:

```bash
opendream-memory prepare-context \
  --workspace "$PWD" \
  --query "package manager and summary style" \
  --include-global \
  --global-workspace ~/.opendream-global
```

## Scheduler surface
`tick` is the cron-safe wrapper around maintenance, and `status` exposes pending work, last run, and lock state.

```bash
opendream-memory status --workspace "$PWD"
opendream-memory tick --workspace "$PWD"
```

Cron example:

```bash
*/10 * * * * cd /path/to/repo && opendream-memory tick --workspace "$PWD" --include-global --global-workspace ~/.opendream-global
```

## Adapter packs
Thin framework examples live under `.meta/spec-adapters/`:
- `claude-code/`
- `codex/`
- `openclaw/`

They are non-normative translations of the canonical specs and README surface.
