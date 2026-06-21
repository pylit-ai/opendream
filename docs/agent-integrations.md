# OpenDream for agents in project workspaces

Codex is currently the most tested integration. Other agent integrations are
available or experimental depending on the host's support for hooks, rules,
context files, or CLI workflows. A generated target is an integration surface,
not a claim that every host executes OpenDream automatically.

Short reference for tools that drive the CLI (hooks, IDE agents, scripts, and custom runtimes).

![OpenDream agent context retrieval](./assets/demos/02-agent-context-retrieval.gif)

## Shared workspace memory across agents

Different agents can use the same OpenDream store across sessions when they
target the same workspace root. Events and prepared contexts preserve
`reporting_agent` metadata, so the Sessions view can distinguish contributions
from Codex, Claude Code, Cursor, and other integrations.

This does not merge or replace each product's built-in memory. OpenDream is the
shared project-memory layer, while each agent keeps its own runtime behavior and
private state. See the [light and dark demo](showcase/ui-demos.md#multiple-agents-one-memory-plane).

## Workspace and working directory

- Pass **`--workspace`** explicitly; it must be the **repository root** (or the root you initialized).
- Shell hooks set `WORKSPACE="${OPENDREAM_WORKSPACE:-$PWD}"`. If the agent runs from a subdirectory, set **`OPENDREAM_WORKSPACE`** to the repo root so `emit-event`, `maintain`, and `prepare-context` target the correct store.
- `opendream doctor --workspace "$WORKSPACE" --surface agents` checks generated files and drift. `opendream verify activation-capture --workspace "$WORKSPACE" --targets configured` runs generated hooks and proves memory capture.

## Where data lives (canonical root)

- The live store defaults to **`.opendream/memory/`** under the workspace (keeps repo-root **`memory/`** free for unrelated trees). If **`memory/state/store.json`** exists from an older layout, that **`memory/`** tree is used until you migrate. Override anytime with **`--memory-dir`**.
- **`opendream status`**, **`opendream doctor --surface agents`**, and **`opendream doctor --surface memory`** include **`memory_layout`**: use **`active_memory_root`** as the single source of truth. If **`shadow_memory_paths`** is non-empty (e.g. both `.opendream/memory` and `memory` exist), treat those extras as **misleading** unless they match the active root. Do not pass **`--memory`** to `doctor` (it is rejected with a hint); use **`--surface memory`** and reserve **`--memory-dir`** for the relative store path under the workspace.
- **`opendream status`** includes **`capture_verification.state`**: `never_run`, `passed`, or `failed`. Treat `passed` as the setup completion proof for the selected agents.
- **`opendream eval performance`** — **hermetic:** scores against an isolated temp workspace using the same **`--memory-dir`** / **`--compat-mode`** you pass; the JSON **`workspace`** field remains your real path.
- **`opendream eval dream-layout`** — **state- and layout-sensitive:** uses the store at `--workspace`. **`compatibility_views`** expects the project/user layout (`project.md` / `user.md`); align **`--compat-mode project-user`** (and **`--memory-dir`**) with **`demo`/init** or use a fresh workspace. On **`failed`**, stderr includes **`failing checks:`** and extra guidance for `compatibility_views`; stdout JSON is unchanged.
- **`opendream eval memory-quality`** — **mutating:** replays a packaged fixture into the **current** store; existing memories (e.g. after **`demo`**) can cause failure. Prefer a **fresh workspace** for a clean CI-style pass/fail.
- **`opendream cache info --workspace "$WORKSPACE"`** shows generated cache disk usage, byte caps, and Git tracking state. **`opendream cache prune --dry-run --full-index`** previews safe cleanup of the rebuildable full observability index. See [cache-management.md](cache-management.md).
- **`opendream retrieve`** (and **`prepare-context`**): very short queries may return **`gated: true`** with a **`reason`** (token threshold) instead of ranked hits — intentional noise gate, not a parser error.
- **Contract:** `opendream contract export --workspace "$WORKSPACE" --format json` — the first argument after **`contract`** must be **`export`**, not the workspace path.

## Multi-workspace awareness (catalog)

When an agent is coordinating across many repos, use the machine-local
workspace catalog to enumerate workspaces instead of searching the
filesystem:

- **List:** `opendream workspace list` prints a human-readable table by
  default; agents should pass `--format json` to get machine-readable
  output (fields include `workspace_path`, `status_kind`, `memory_dir`,
  `activation_state_summary`, `service_state_summary`).
- **Inspect:** `opendream workspace inspect --workspace "$WORKSPACE"` —
  one entry with full status.
- **Refresh after a CLI upgrade:** `opendream workspace upgrade --workspace "$WORKSPACE"`
  repairs managed surfaces if needed, ensures the managed background runtime for
  project workspaces unless explicitly disabled, and re-probes a known
  workspace; `--all` refreshes every catalog entry.
- **Catalog-only re-probe:** `opendream workspace doctor --workspace "$WORKSPACE"`
  updates the catalog view without the repair step; `--all` re-probes every entry.
- **Discover:** `opendream workspace scan --root <path>` or
  `--all-roots` (roots are managed via
  `opendream workspace roots add --path <path>`). Scans are strictly
  opt-in: OpenDream never crawls your home directory on its own.

The catalog is a **derived convenience index** at
`~/.opendream/catalog.json`; workspace-local `.opendream/` state remains
canonical. The local web UI exposes `/workspaces` backed by the same
index. See [ADR-017](./adr/ADR-017-machine-local-workspace-catalog.md).

Event-driven catalog updates are **sandbox-aware**: they never write the
real home catalog when running under a test runner or against a workspace
under a tempdir unless `OPENDREAM_CATALOG_HOME` is explicitly set. The
skipped status is surfaced on the command's `catalog_update` block
(`status: skipped`, `reason: sandboxed-environment|tempdir-workspace`), so
agents running inside CI or scratch sandboxes can still see that the
write was intentionally declined. Set `OPENDREAM_CATALOG_DISABLE=1` to
turn off catalog writes entirely.

**Upgrading an existing workspace:** after `pip install -U opendream`,
run `opendream workspace upgrade --workspace "$PWD"` to repair and
refresh the upgraded repo. Agents backfilling
existing repos that pre-date the catalog should prefer
`opendream workspace scan --all-roots` (after
`opendream workspace roots add --path <dir>`) or explicit
`opendream workspace doctor --workspace <path>` calls — never a
filesystem crawl.

## Typical hook sequence

For **multi-layer automation** (durable capture, deterministic automation projections, optional scheduled reconciliation), see [Dream task playbook](automation/dream-task-playbook.md).

1. **Pre-task:** `opendream prepare-context --workspace "$WORKSPACE" --query "<task>"` → JSON with `prompt_context`, `selected_memory_ids`, `empty_reason`, and `hints`. When [automations](../README.md) have produced projections, the same payload also includes `selected_automation_record_ids` / `selected_automation_records`, and `prompt_context` adds an **Active Automation Projections** section (separate from durable memory).
2. **Post-task:** `opendream emit-event --workspace "$WORKSPACE" --kind task_outcome --content "<summary>" --message-ref "<ref>"` (plus required flags; see `emit-event -h`).
3. **Maintenance:** `opendream maintain --workspace "$WORKSPACE"` (often chained after emit in hooks).
4. **Background runtime (primary for ongoing improvement):**
   `opendream service enable --workspace "$WORKSPACE"` keeps dream polling and
   semantic improvement moving in the background; `service disable|status` and
   the observe UI (`/overview`, `/settings`) manage the same runtime.
5. **Dream worker (bounded/manual):** `opendream dream worker --workspace "$WORKSPACE" --once` — transcript-driven; **`agent_summary`** explains skips such as **`no-episodes`**.

## Supported activation targets

Supported targets come from the bundled adapter manifests.

| Target | Host integration | Verification path |
|--------|------------------|-------------------|
| `claude-code` | Native Claude Code `UserPromptSubmit` / `Stop` hooks in `.claude/settings.json` | `verify activation-capture` runs the generated Claude pre/post hook scripts with fallback input. |
| `codex` | Managed wrapper plus `AGENTS.md` instructions | `verify activation-capture` runs `.opendream/bin/codex-task-wrapper.sh` around a no-op command and proves pre/post hooks. |
| `cursor` | Instruction-only Cursor rule plus shell hooks | `verify activation-capture` runs generated shell hooks directly; host auto-invocation remains instruction-only. |
| `github-copilot` | Instruction-only `.github/copilot-instructions.md` block plus shell hooks | `verify activation-capture` runs generated shell hooks directly; host auto-invocation remains instruction-only. |
| `hermes` | Instruction-only `.hermes.md` project context plus shell hooks | `verify activation-capture` runs generated shell hooks directly; host auto-invocation remains instruction-only. |
| `openclaw` | Native OpenClaw config and event map | `verify activation-capture` runs `openclaw-hooks.sh pre-plan` and `post-task`. |

Use `--targets configured` for detected surfaces and `--targets all-supported` for a sandbox or deliberate all-adapter setup.

If the repo uses automations:

- **`opendream tick --workspace "$WORKSPACE"`** runs both normal maintenance and any due automation jobs.
- **`opendream automation tick --workspace "$WORKSPACE"`** runs only due automation jobs.

## Empty context is not always a failure

![OpenDream memory safety abstention](./assets/demos/03-memory-safety-abstention.gif)

`prepare-context` JSON:

- **`empty_reason`:** `null` when memories were selected; otherwise `no_initialized_store`, `no_durable_memories`, or `no_query_matches`.
- **`hints`:** concrete next steps (e.g. run `maintain`, broaden the query).

Section headers in `prompt_context` may appear with **no body** when there is nothing to inject; use **`empty_reason`** / **`hints`** instead of inferring an error. Treat automation projections as **non-canonical** backlog/radar signal unless you explicitly promote decisions into durable memory (for example via normal `emit-event` / consolidation flows).

## JSON stability

Selected command payloads include **`cli_output_version`** (integer). Bump tolerance in your integration when this number changes.

`--now` exists to make tests, fixtures, and scripted repros deterministic. Production hooks, cron jobs, and normal CLI usage should usually omit it and rely on wall-clock time.

## Semantic execution strategies and adapter matrix

Semantic mode runs through one of five **execution strategies**:

| Strategy | Execution owner | Auth source | Extra key? | Ingest |
|----------|----------------|-------------|-----------|--------|
| `deterministic` | opendream-local | none | No | n/a |
| `direct-provider` | opendream-local | API key | Yes | direct-report |
| `codex-account` | opendream-local | ChatGPT account | No | direct-report |
| `claude-scheduled-task` | vendor-runtime | Claude account | No | delegated-envelope |
| `cursor-automation` | vendor-runtime | Cursor account | No | delegated-envelope |

**Setup quickstart:**

```bash
# Detect tools and get a recommendation
opendream semantic setup --workspace "$PWD" --prefer no-extra-key --apply

# Check semantic readiness truth
opendream semantic status --workspace "$PWD"

# Inspect adapter inventory and status
opendream semantic adapters status --workspace "$PWD"

# Ingest delegated results (for Claude/Cursor adapters)
opendream semantic ingest --workspace "$PWD" --scan-inbox
```

**Unsupported paths:** OpenDream never borrows opaque auth tokens from another tool. Untrusted CI and shared runners should not default to account-backed execution.

## Semantic dream mode vs automation radar

- **Transcript dream:** `opendream dream run … --mode hybrid|semantic` — episodes under the memory root; optional learned-context pipeline. Configuration files: `<active_memory_root>/state/semantic_config.json`, `provider_registry.json`. Operator walkthrough: [`docs/automation/semantic-mode-and-feature-radar-setup.md`](automation/semantic-mode-and-feature-radar-setup.md). **Full command sequences and where LLMs run:** [`docs/automation/complete-operator-workflow.md`](automation/complete-operator-workflow.md).
- **Feature radar (and similar):** `opendream automation register|run|tick` — projects **durable** memories into automation records; independent of `dream run`.

## Machine-readable contract export

Operators and integrators can dump a **versioned contract document** (command names, schema inventory, output version map, placeholders for future engine/package targets):

```bash
opendream contract export --workspace "$WORKSPACE" --format json
```

The payload validates against `opendream/schema/contract-export.schema.json`. **`cli_output_version`** is the same integer as command JSON (e.g. `status`) and matches the numeric meaning of **`output_version_map.cli_json`**. When the **export document** shape changes, bump **`output_version_map.contract_export`** and update consumers and golden fixtures together.

## Direct-provider vs delegated execution

- **Direct-provider**: Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, then run `opendream semantic setup --workspace . --prefer direct-provider --apply`
- **Codex account**: Install Codex CLI and sign in. Run `opendream semantic setup --workspace . --prefer no-extra-key --apply` only on a machine where you are comfortable letting local CLI tools use that account session.
- **Claude scheduled-task**: Run `opendream semantic adapters scaffold --workspace . --adapter claude-scheduled-task` to generate task templates.
- **Cursor automation**: Run `opendream semantic adapters scaffold --workspace . --adapter cursor-automation` to generate automation prompts.
- **Deterministic**: Always available. No model call, no API key needed.

## What not to hand-edit

Prefer CLI and hooks over manual edits to paths under **`active_memory_root`**, for example:

- `<active_memory_root>/state/events/*.jsonl`
- `<active_memory_root>/state/durable_records.json`, `state/index.json`, and related state
- `<active_memory_root>/state/observability_index.json` and `state/observability_compact_index.json` unless you are intentionally pruning rebuildable cache files with `opendream cache prune`

Edit **`MEMORY.md`** under that root only when you intentionally curate the human-facing index; the runtime will reconcile with consolidation rules.
