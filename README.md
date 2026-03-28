# OpenDream

OpenDream is a local-first memory subsystem for coding agents. It captures immutable evidence, derives typed memory candidates, consolidates durable memory with provenance, and exposes reproducible CLI workflows for bootstrap, dreaming, retrieval, evaluation, and release checks.

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
make release-check
.venv/bin/opendream-memory --help
```

## CLI
Run the memory subsystem directly from the repo root:

```bash
.venv/bin/python -m opendream_memory.cli init --workspace .tmp/workspace
.venv/bin/python -m opendream_memory.cli init --workspace ~/.opendream-global --store-kind global
.venv/bin/python -m opendream_memory.cli demo --workspace .tmp/demo
.venv/bin/python -m opendream_memory.cli bootstrap-index --workspace .tmp/workspace --events tests/fixtures/bootstrap_events.jsonl
.venv/bin/python -m opendream_memory.cli consolidate --workspace .tmp/workspace
.venv/bin/python -m opendream_memory.cli retrieve --workspace .tmp/workspace --query "package manager and workflow"
.venv/bin/python -m opendream_memory.cli emit-event --workspace .tmp/workspace --kind project_decision --content "Use pnpm in this repo" --message-ref manual-1 --tag key:package-manager
.venv/bin/python -m opendream_memory.cli maintain --workspace .tmp/workspace
.venv/bin/python -m opendream_memory.cli dream run --workspace .tmp/workspace --episodes tests/fixtures/transcript_only_dream.jsonl
.venv/bin/python -m opendream_memory.cli eval memory-quality --workspace .tmp/eval
.venv/bin/python -m opendream_memory.cli prepare-context --workspace .tmp/workspace --query "package manager and workflow"
.venv/bin/python -m opendream_memory.cli prepare-context --workspace .tmp/workspace --query "package manager and workflow" --include-global --global-workspace ~/.opendream-global
.venv/bin/python -m opendream_memory.cli status --workspace .tmp/workspace
.venv/bin/python -m opendream_memory.cli tick --workspace .tmp/workspace
.venv/bin/python -m opendream_memory.cli observe index --workspace .tmp/workspace
.venv/bin/python -m opendream_memory.cli observe serve --workspace .tmp/workspace --port 8000
```

After install, the console entrypoint is available:

```bash
opendream-memory demo --workspace .tmp/demo
```

## Verification
OpenDream is only "verified" when the scripted gate passes. The gate emits `.tmp/verification/verification_report.json` with per-stage PASS or FAIL evidence.

- `make lint`
- `make typecheck`
- `make test`
- `.venv/bin/python scripts/check_adapters.py`
- `make verify`

`make release-check` is the authoritative release gate. It is time-bounded, builds wheel and sdist artifacts, installs into a clean venv, reruns verification, and emits:

- `.tmp/release-check/release_manifest.json`
- `.tmp/release-check/release_summary.md`

## Docs
- [NORTHSTAR.md](./NORTHSTAR.md)
- [PRD.md](./PRD.md)
- [CONSTITUTION.md](./CONSTITUTION.md)
- [AGENTS.md](./AGENTS.md)

## Generated data
Memory artifacts are written under a workspace-local `memory/` directory by default. Use `--memory-dir <relative-path>` when a repo needs a non-default location, and the same path is honored by direct writes, dreaming, retrieval context, and status commands.

## Runtime integration
For real agent use, treat OpenDream as a local sidecar:
- emit memory-worthy events with `emit-event`
- run `dream run` against transcript or log episodes when you want reflective consolidation
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
`tick` is the cron-safe wrapper around maintenance, and `status` exposes pending work, last run, lock state, and dream state.

```bash
opendream-memory status --workspace "$PWD"
opendream-memory tick --workspace "$PWD"
```

Dream runs are explicit and bounded:

```bash
opendream-memory dream run \
  --workspace "$PWD" \
  --episodes tests/fixtures/transcript_only_dream.jsonl \
  --compat-mode autodream
```

Memory quality can be benchmarked locally:

```bash
opendream-memory eval memory-quality --workspace .tmp/eval
```

Cron example:

```bash
*/10 * * * * cd /path/to/repo && opendream-memory tick --workspace "$PWD" --include-global --global-workspace ~/.opendream-global
```

## Observability web app
OpenDream now ships a local-first observability stack built from the same filesystem artifacts as the runtime. The read model is derived, provenance-preserving, and never becomes the source of truth.

```bash
opendream-memory observe index --workspace "$PWD"
opendream-memory observe serve --workspace "$PWD" --port 8000
```

The server exposes:
- a read model at `memory/state/observability_index.json`
- read APIs for overview, memories, runs, retrievals, sessions, context, graph, reviews, evals, and exports
- audited write APIs for annotations, review decisions, and exports
- SSE updates at `/api/stream/status`
- a no-build desktop-first UI at routes like `/overview`, `/memories`, `/runs`, `/retrievals`, `/sessions`, `/reviews`, `/graph`, `/evals`, and `/exports`

`prepare-context` now persists context-assembly artifacts so the context viewer can reconstruct what the agent actually saw.

## Adapter packs
Thin framework examples live under `.meta/spec-adapters/`:
- `claude-code/`
- `codex/`
- `openclaw/`

They are non-normative translations of the canonical specs and README surface.
