# Operator Guide

This guide holds the detailed operator reference that used to live in the README. The README is kept shorter for first-time readers and launch traffic.

## Multi-workspace catalog and dashboard

OpenDream keeps canonical state per workspace (under `.opendream/`). Once you
use it across many repos, a first-party machine-local index makes it easy to
see every known workspace in one place.

```bash
# List every known workspace on this machine (derived, not canonical).
opendream workspace list

# Teach the catalog where to look.
opendream workspace roots add --path ~/src
opendream workspace scan --all-roots

# Inspect, refresh, or drop an entry (the workspace itself is never touched).
opendream workspace inspect --workspace ~/src/project-a
opendream workspace doctor   --workspace ~/src/project-a
opendream workspace forget   --workspace ~/src/project-a
```

Catalog files live at `~/.opendream/catalog.json` and `~/.opendream/roots.json`
(override with `OPENDREAM_CATALOG_HOME`). The catalog is a **convenience
index** — workspace `.opendream/` state remains the source of truth, scans
only run on explicitly configured roots, and no data ever leaves your machine.
By default `workspace list` prints a human-readable table; add `--format json`
for machine output.

The local web UI exposes the same view at `/workspaces`, with per-workspace
cards that link into the existing detail pages. See
[ADR-017](./docs/adr/ADR-017-machine-local-workspace-catalog.md) for why the
catalog is derived rather than canonical.

### Upgrading an existing workspace

When you upgrade OpenDream in a repo that already has `.opendream/` state:

```bash
pip install -U opendream                 # or uv tool upgrade / pipx upgrade
opendream workspace upgrade --workspace "$PWD"
```

Your workspace `.opendream/` directory is canonical and is never rewritten by
catalog operations. `workspace upgrade` runs the safe refresh path for one
workspace: repair managed activation surfaces, ensure the managed background
runtime for project workspaces unless you have explicitly disabled it, re-probe
activation/service/semantic state, and upsert the catalog entry so the upgraded
workspace appears in `opendream workspace list` and the `/workspaces`
dashboard. `opendream repair --workspace "$PWD"` remains a shorthand for
`activate --repair` when you only need surface repair. Use
`opendream service disable --workspace "$PWD"` if a workspace should stay
manual.

### Backfilling existing workspaces into the index

The catalog only indexes workspaces it has been told about. To register repos
that existed before you upgraded:

```bash
# Option A: bulk discovery via configured scan roots (recommended).
opendream workspace roots add --path ~/src
opendream workspace roots add --path ~/work
opendream workspace scan --all-roots

# Option B: register a specific workspace explicitly.
opendream workspace doctor --workspace ~/src/project-a

# Refresh every known entry after a batch of upgrades.
opendream workspace doctor --all
```

Scans are strictly opt-in to configured roots, bounded in depth, and prune
noisy directories (`.git`, `node_modules`, `.venv`, …). Transient tempdir
workspaces are never written to the real `~/.opendream/catalog.json`.

---

## Observability UI

Nothing starts a server unless you ask. The UI reads **one** workspace’s on-disk memory store (default relative path `.opendream/memory/` under the workspace).

```bash
opendream serve
```

`opendream serve` detects the current workspace when possible, chooses an available localhost port, and opens the Workspaces UI when the current directory is not initialized yet. For explicit scripts or fixed ports, use:

```bash
opendream observe index --workspace "$PWD"
opendream observe serve --workspace "$PWD" --port 8000
```

`observe serve` blocks until Ctrl+C.
The observe server also exposes `GET /api/status` for lightweight workspace progress, `GET /api/health` for startup/readiness/liveness evidence, and `POST /api/health/live-check` for a synthetic end-to-end probe that verifies append plus index refresh without creating durable memory.
For semantic-first workspaces, `/overview` and `/settings` should expose the same truth as CLI status: readiness, setup-required vs degraded state, state reason, next action, memory-quality warnings, and pruning evidence, with raw JSON still available behind disclosure.
The same UI also exposes background-runtime controls and digestible summaries of
the current memory surface plus the latest runtime mutation effects, so you can
see what OpenDream is changing without dropping straight into raw JSON.

Watch the UI flow in both themes: [`docs/showcase/ui-demos.md`](./docs/showcase/ui-demos.md).

<details>
<summary><strong>What the observability app exposes</strong></summary>

Built from the same on-disk artifacts as the runtime (read model is derived; filesystem remains source of truth):

- Indexes at `.opendream/memory/state/observability_compact_index.json` and, when under the configured cap, `.opendream/memory/state/observability_index.json` (under your configured memory root)
- Read APIs: overview, memories, runs, retrievals, sessions, context, graph, reviews, evals, exports
- Health APIs: `/api/status`, `/api/health`, and `/api/health/live-check`
- Audited writes: annotations, review decisions, exports
- SSE at `/api/stream/status`

Use `opendream cache info --workspace "$PWD"` to inspect generated cache byte
sizes and `opendream cache prune --dry-run --full-index` before deleting
rebuildable full-index state. Details: [cache-management.md](cache-management.md).
- Desktop-first routes: `/overview`, `/memories`, `/dreams`, `/runs`, `/retrievals`, `/sessions`, `/reviews`, `/graph`, `/evals`, `/exports`

`prepare-context` persists context-assembly artifacts so the context viewer can show what the agent actually saw.

</details>

---

## Runtime integration (checklist)

Use OpenDream as an **activation-first runtime**:

- Run **`init`** for the standard path; it creates the memory layout and activates detected/configured agent surfaces by default.
- Run **`verify activation-capture`** after activation before claiming workspace setup is complete.
- Run **`status`** for the single high-signal answer covering activation, drift, queue state, and runtime health.
- Run **`activate --repair`** when `status` or `doctor` reports drift.
- Run **`deactivate`** if you want to remove OpenDream-managed repo-local surfaces while keeping your repo config intact.
- Use **`automation register|run|tick|status|review`** when you want managed recurring projections such as feature queues or bug radar without mutating durable memory. For a **reproducible multi-layer pattern** (capture → automation radar → optional semantic refresh), see [`docs/automation/dream-task-playbook.md`](./docs/automation/dream-task-playbook.md), the worked example at [`docs/automation/examples/feature-mining.md`](./docs/automation/examples/feature-mining.md), and the **ordered CLI sequences** (`init` through `tick`, hybrid `dream run` smoke, Layer C / delegated ingest) in [`docs/automation/complete-operator-workflow.md`](./docs/automation/complete-operator-workflow.md).
- Use **`doctor --surface agents`**, **`service ...`**, **`dream ...`**, **`maintain`**, and **`prepare-context`** as advanced or explicit operator paths.

<details>
<summary><strong>Layered stores</strong> (project + optional global)</summary>

```bash
opendream init --workspace .
opendream init --workspace ~/.opendream-global --store-kind global
```

Route preferences to global, then merge with project precedence via `prepare-context --include-global`:

```bash
opendream emit-event \
  --workspace "$PWD" --route global --global-workspace ~/.opendream-global \
  --scope global --kind preference_signal \
  --content "Prefer concise summaries across repos." \
  --message-ref manual-global-1 --tag key:summary-style

opendream prepare-context \
  --workspace "$PWD" --query "package manager and summary style" \
  --include-global --global-workspace ~/.opendream-global
```

</details>

<details>
<summary><strong>Advanced commands</strong></summary>

```bash
opendream status --workspace "$PWD"
opendream maintain --workspace "$PWD"
opendream automation status --workspace "$PWD"
opendream automation tick --workspace "$PWD"
opendream activate --workspace "$PWD" --repair
opendream deactivate --workspace "$PWD"
opendream doctor --workspace "$PWD" --surface agents
```

Dream (explicit, bounded):

```bash
opendream transcripts ingest --workspace "$PWD"
opendream dream run \
  --workspace "$PWD" \
  --episodes tests/fixtures/transcript_only_dream.jsonl \
  --compat-mode project-user

opendream dream status --workspace "$PWD" --compat-mode project-user
opendream dream tick --workspace "$PWD" --compat-mode project-user
opendream dream enqueue --workspace "$PWD" --episodes tests/fixtures/transcript_only_dream.jsonl
opendream dream worker --workspace "$PWD" --once
opendream dream daemon --workspace "$PWD" --interval-seconds 30 --max-polls 20
opendream install-service --workspace "$PWD" --interval-seconds 30
opendream service enable --workspace "$PWD"
opendream service disable --workspace "$PWD"
opendream service status --workspace "$PWD"
opendream service doctor --workspace "$PWD"
```

The observe UI's **Allow import and dream** action grants one-time browser
consent to import detectable local transcripts before the first manual dream run
when the transcript store is empty. The CLI keeps transcript ingest explicit so
large local session stores are scanned only when the operator asks for that data
import.

Use `dream worker --once` for a single queue drain inside hooks, scripts, or CI. Use `dream daemon` when a supervisor should keep polling over time. `install-service` renders launchd or systemd manifests, persists worker heartbeat state under the memory root, and exposes `service start|stop|restart|status|doctor` as a first-party lifecycle path. The default backend stays managed for portable verification; use `--backend native` when you want best-effort launchd or systemd activation.
For project workspaces, `workspace upgrade` and `semantic setup --apply` now
ensure the managed background runtime by default so memory improvement does not
depend on manual runs. Use `service enable|disable` or the observe UI
(`/overview`, `/settings`) to manage that runtime explicitly.

For supported configured agents, the standard operator path is:

```bash
opendream init --workspace .
opendream status --workspace .
opendream activate --workspace . --repair
opendream deactivate --workspace .
```

Use `opendream init --workspace . --no-activate-configured` only when
you need a storage-only layout and do not want OpenDream to install repo-local
agent activation surfaces.

Semantic / hybrid dream mode (optional — extends **`dream run`** with the learned-context pipeline; config on disk under `<memory-root>/state/`):

```bash
opendream semantic config --workspace "$PWD"    # defaults until semantic_config.json exists
opendream semantic status --workspace "$PWD"
opendream semantic provider-health --workspace "$PWD"
opendream dream run --workspace "$PWD" --mode hybrid --episodes tests/fixtures/transcript_only_dream.jsonl
```

Optional semantic execution adapters:

```bash
opendream semantic setup --workspace "$PWD" --prefer no-extra-key --apply
opendream semantic status --workspace "$PWD"
opendream semantic adapters list
opendream semantic adapters status --workspace "$PWD"
opendream semantic ingest --workspace "$PWD" --scan-inbox
```

OpenDream always supports deterministic local execution. Provider and
agent-runtime paths are optional integrations; OpenDream does not call external
model providers unless you explicitly configure one. The detailed strategy
matrix lives in [`docs/agent-integrations.md`](./docs/agent-integrations.md).

Run `opendream semantic setup --workspace . --apply` to detect, apply, scaffold, and validate the recommended path for your environment. If you need a manual nudge later, use `opendream dream worker --workspace . --once --mode auto`.

Semantic-first is a configuration posture, not an automatic readiness claim. If semantic posture is selected but the recommended path has not been applied yet, OpenDream should report **setup required**. If a previously applied path stops being runnable, it should report **degraded** semantic-first, explain why, keep deterministic capture explicit, and recommend one concrete next action instead of implying that `mode=semantic` is already ready.

**Feature / bug / fix radar** uses **`opendream automation`** (projection jobs), not `dream run`. Full walkthrough, file layouts, and how this differs from transcript dreaming: [`docs/automation/semantic-mode-and-feature-radar-setup.md`](./docs/automation/semantic-mode-and-feature-radar-setup.md).

**Note:** The repo is stdlib-only; hybrid/semantic mode runs the full **pipeline and audits** with **in-process heuristic** synthesis/verification today. Provider registry + API keys gate **availability** and health checks; outbound LLM calls are not implemented in this package yet (see guide).

The retrieval story is also semantic-first. `prepare-context` is expected to use **progressive disclosure** so startup context stays pointer-like, task context expands only when relevance justifies it, and machine-readable outputs can show **pruning evidence** such as raw candidate counts, injected counts, suppression reasons, and budget savings.

Eval:

```bash
opendream eval dream-layout --workspace .tmp/dream-eval --compat-mode project-user
opendream eval memory-quality --workspace .tmp/eval
opendream eval performance --workspace .tmp/eval
opendream eval semantic-benchmark --workspace .tmp/eval --mode hybrid
```

Eval commands print JSON to stdout; if the report includes `"status": "failed"`, the process exits **non-zero** (typically `1`) so scripts and CI can fail the step without parsing the payload.

**`eval performance`** — **hermetic:** uses an **isolated** empty memory store (same `--memory-dir` / `--compat-mode` as you pass in) so existing durable memory in your workspace cannot skew the scorecard; the JSON `workspace` field is still your `--workspace` path for context.

**`eval dream-layout`** — **state- and layout-sensitive:** reuses the store at `--workspace` and checks project/user **`compatibility_views`** (`project.md` / `user.md` under the active memory root). Running `demo` in **canonical** mode then `eval dream-layout` without a matching `--compat-mode project-user` (and the same `--memory-dir`) can fail that check; use a fresh workspace or align flags. On failure, stderr adds a **`failing checks: ...`** summary (and extra guidance when `compatibility_views` fails); stdout JSON is unchanged.

**`eval memory-quality`** — **mutating / not hermetic:** replays a packaged fixture into the **current** store (`emit-event` + `maintain`), then scores retrieval. Prior state (e.g. after `demo`) can make titles **contested** or create **duplicate** actives so the eval fails; use a **fresh workspace** when you want a clean CI-style verdict. On failure, stderr summarizes **duplicate/contested** context when present plus this “use a fresh workspace” hint.

**`retrieve` / `prepare-context`:** very **short queries** may be **intentionally gated** — JSON includes `"gated": true` and a **`reason`** (e.g. too few content tokens vs `gating_min_content_tokens`, default **3**) instead of ranking memories. Broader queries avoid gating.

**Contract export:** use the **`export`** subcommand — `opendream contract export --workspace "$PWD" --format json` (do not pass the workspace path as the first token after `contract`).

**`doctor`** does not accept `--memory`; use `--surface memory` for the memory surface and `--memory-dir` only for the relative memory directory.

Cron example:

```bash
*/10 * * * * cd /path/to/repo && opendream maintain --workspace "$PWD" --include-global --global-workspace ~/.opendream-global
```

</details>

---

## Generated data

By default, durable memory artifacts live under **`.opendream/memory/`** (so a repo-root `memory/` folder stays free for other tools). If `memory/state/store.json` already exists from an older layout, that tree is used automatically until you migrate. Use `--memory-dir <relative-path>` to pin a custom location; planner plans, verifier reports, dream queue state, and worker audits live under the same memory root.

Activation and compressed-status metadata (for the standard `init` / `status` path) persist under **`.opendream/`** at the workspace root — notably `targets.json` and `activation-state.json`. Add `.opendream/` to `.gitignore` if you do not want those files committed.

---
