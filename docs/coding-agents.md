# OpenDream for coding agents

Short reference for tools that drive the CLI (hooks, IDE agents, scripts).

## Workspace and working directory

- Pass **`--workspace`** explicitly; it must be the **repository root** (or the root you initialized).
- Shell hooks set `WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"`. If the agent runs from a subdirectory, set **`OPENDREAM_WORKSPACE`** to the repo root so `emit-event`, `maintain`, and `prepare-context` target the correct store.

## Where data lives (canonical root)

- The live store defaults to **`.opendream/memory/`** under the workspace (keeps repo-root **`memory/`** free for unrelated trees). If **`memory/state/store.json`** exists from an older layout, that **`memory/`** tree is used until you migrate. Override anytime with **`--memory-dir`**.
- **`opendream status`**, **`opendream doctor --surface agents`**, and **`opendream doctor --surface memory`** include **`memory_layout`**: use **`active_memory_root`** as the single source of truth. If **`shadow_memory_paths`** is non-empty (e.g. both `.opendream/memory` and `memory` exist), treat those extras as **misleading** unless they match the active root.

## Typical hook sequence

For **multi-layer automation** (durable capture, deterministic automation projections, optional scheduled reconciliation), see [Dream task playbook](automation/dream-task-playbook.md). Cursor agents can follow the on-demand skill at [`.cursor/skills/opendream-dream-automation/SKILL.md`](../.cursor/skills/opendream-dream-automation/SKILL.md).

1. **Pre-task:** `opendream prepare-context --workspace "$WORKSPACE" --query "<task>"` → JSON with `prompt_context`, `selected_memory_ids`, `empty_reason`, and `hints`. When [automations](../README.md) have produced projections, the same payload also includes `selected_automation_record_ids` / `selected_automation_records`, and `prompt_context` adds an **Active Automation Projections** section (separate from durable memory).
2. **Post-task:** `opendream emit-event --workspace "$WORKSPACE" --kind task_outcome --content "<summary>" --message-ref "<ref>"` (plus required flags; see `emit-event -h`).
3. **Maintenance:** `opendream maintain --workspace "$WORKSPACE"` (often chained after emit in hooks).
4. **Dream worker (optional):** `opendream dream worker --workspace "$WORKSPACE" --once` — transcript-driven; **`agent_summary`** explains skips such as **`no-episodes`**.

If the repo uses automations:

- **`opendream tick --workspace "$WORKSPACE"`** runs both normal maintenance and any due automation jobs.
- **`opendream automation tick --workspace "$WORKSPACE"`** runs only due automation jobs.

## Empty context is not always a failure

`prepare-context` JSON:

- **`empty_reason`:** `null` when memories were selected; otherwise `no_initialized_store`, `no_durable_memories`, or `no_query_matches`.
- **`hints`:** concrete next steps (e.g. run `maintain`, broaden the query).

Section headers in `prompt_context` may appear with **no body** when there is nothing to inject; use **`empty_reason`** / **`hints`** instead of inferring an error. Treat automation projections as **non-canonical** backlog/radar signal unless you explicitly promote decisions into durable memory (for example via normal `emit-event` / consolidation flows).

## JSON stability

Selected command payloads include **`cli_output_version`** (integer). Bump tolerance in your integration when this number changes.

`--now` exists to make tests, fixtures, and scripted repros deterministic. Production hooks, cron jobs, and normal CLI usage should usually omit it and rely on wall-clock time.

## Machine-readable contract export

Operators and integrators can dump a **versioned contract document** (command names, schema inventory, output version map, placeholders for future engine/package targets):

```bash
opendream contract export --workspace "$WORKSPACE" --format json
```

The payload validates against `opendream/schema/contract-export.schema.json`. When the export shape changes, the **`cli_output_version`** field inside the document increments; update consumers and golden fixtures together.

## What not to hand-edit

Prefer CLI and hooks over manual edits to paths under **`active_memory_root`**, for example:

- `<active_memory_root>/state/events/*.jsonl`
- `<active_memory_root>/state/durable_records.json`, `state/index.json`, and related state

Edit **`MEMORY.md`** under that root only when you intentionally curate the human-facing index; the runtime will reconcile with consolidation rules.
