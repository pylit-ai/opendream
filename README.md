# OpenDream

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="./frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_light.svg">
    <img alt="OpenDream" src="./frontend/assets/logo/wordmark/vector/opendream_wordmark_primary_ink_light.svg" width="520">
  </picture>
</p>

[![CI](https://github.com/pylit-ai/opendream/actions/workflows/ci.yml/badge.svg)](https://github.com/pylit-ai/opendream/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/opendream?label=PyPI)](https://pypi.org/project/opendream/)
[![Python versions](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)

**Local-first memory for agents in project workspaces** — activate OpenDream inside the directory you already use, watch what memory is doing in a browser, and keep advanced runtime integrations available when you need them.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/demos/ui/opendream-ui-overview-dark.gif">
  <source media="(prefers-color-scheme: light)" srcset="./docs/assets/demos/ui/opendream-ui-overview.gif">
  <img alt="OpenDream UI overview" src="./docs/assets/demos/ui/opendream-ui-overview.gif">
</picture>

The observability UI shows recent agent activity, selected memories, context-use audit records, review decisions, and workspace health without making you read raw JSON first. Full light and dark demo cuts: [`docs/showcase/ui-demos.md`](./docs/showcase/ui-demos.md).

| If you want to… | Start here |
|-----------------|------------|
| Try it in a few commands | [Quick start](#quick-start) |
| Watch the product surface | [UI demo gallery](./docs/showcase/ui-demos.md) |
| Run the memory demo | [90-second memory showcase](./docs/showcase/memory-showcase.md) |
| Wire it into an agent runtime | [Integration at a glance](#integration-at-a-glance) |
| Browse memory in a browser | [Observability UI](#observability-ui) |
| Contribute | [Contributing](#contributing) (expandable) |

---

## Quick start

```bash
uv tool install opendream   # or: pipx install opendream
opendream init --workspace .
opendream verify activation-capture --workspace . --targets configured
opendream status --workspace .
opendream deactivate --workspace .
```

If your installed CLI does not show `activate`, `verify`, `deactivate`, `semantic`, or
`eval`, upgrade with `uv tool upgrade opendream` or reinstall from Git. After
upgrading, `opendream verify --help`, `opendream semantic --help`, and
`opendream eval --help` are quick checks that your install matches the docs.

Bleeding-edge from Git (overwrites the tool env): `uv tool install --force "opendream @ git+https://github.com/pylit-ai/opendream.git"`.

Install checks, upgrade notes, known limitations, and clean-room provenance live
in [`docs/launch-readiness.md`](./docs/launch-readiness.md),
[`docs/known-limitations.md`](./docs/known-limitations.md), and
[`docs/provenance.md`](./docs/provenance.md).

<details>
<summary><strong>CLI demos for docs and operators</strong></summary>

OpenDream's first-run path is intentionally small. These clips are useful beside command reference docs; the product UI tour above is the better first look.

| Demo | What it shows |
|------|---------------|
| ![OpenDream CLI quick start](./docs/assets/demos/01-first-run-local-memory.gif) | `init` with default activation, status, and deactivation in a local workspace. |
| ![Agent context retrieval](./docs/assets/demos/02-agent-context-retrieval.gif) | `prepare-context` turns durable repo memory into prompt-ready agent context. |
| ![Memory safety abstention](./docs/assets/demos/03-memory-safety-abstention.gif) | Unrelated prompts return an explicit no-match instead of injecting stale or irrelevant memory. |
| ![Showcase evaluation report](./docs/assets/demos/04-eval-proof.gif) | The showcase eval compares stateless vs memory-assisted answers and keeps negative controls in the report. |

UI demo gallery: [`docs/showcase/ui-demos.md`](./docs/showcase/ui-demos.md). CLI demo gallery: [`docs/showcase/cli-demos.md`](./docs/showcase/cli-demos.md).
Brand motion assets: [`frontend/assets/animation/README.md`](./frontend/assets/animation/README.md).

</details>

<details>
<summary><strong>Install options</strong> (venv, editable checkout, PEP 668)</summary>

**PyPI (recommended once published)** — use an isolated tool env to avoid system Python restrictions (PEP 668):

```bash
uv tool install opendream
# or: pipx install opendream
opendream --help
```

**From Git** (same idea; pin with `@main` / `@v0.1.0` where your installer allows):

```bash
uv tool install "opendream @ git+https://github.com/pylit-ai/opendream.git"
# or: pipx install git+https://github.com/pylit-ai/opendream.git
```

**Repo checkout** (contributors):

```bash
make setup
.venv/bin/opendream --help
```

Manual equivalent: `python3 -m venv .venv && .venv/bin/pip install -e .` from the repo root. Module fallback: `python3 -m opendream.cli --help`.

If `python3` is missing, install from [python.org](https://www.python.org/downloads/) or your OS package manager.

**System dependencies** — OpenDream uses `jq` to parse JSON in hook scripts (for Claude Code integration). Install via your OS package manager:

```bash
# macOS
brew install jq

# Ubuntu / Debian
sudo apt-get install jq

# Other systems
# See: https://jqlang.github.io/jq/download/
```

</details>

---

## Integration at a glance

OpenDream is an **activation-first CLI**. For normal use, the product contract is:

```bash
opendream init --workspace .
opendream verify activation-capture --workspace . --targets configured
opendream status --workspace .
opendream activate --workspace . --repair
opendream deactivate --workspace .
```

The lower-level runtime remains available, but it is not the main mental model.

| Command | Role |
|---------|------|
| `emit-event` | Append schema-valid evidence to the store |
| `maintain` | Run extract + consolidate when work qualifies; returns structured **`status`** / **`reason`** when skipping (not a silent no-op) |
| `automation ...` | Manage recurring projection jobs that stay separate from canonical durable memory |
| `prepare-context` | Retrieval surface for the next task (prompt-ready output) |

Agent integration details (workspace vs cwd, `memory_layout`, `empty_reason` / `hints`, JSON version): [`docs/agent-integrations.md`](./docs/agent-integrations.md).

**Recommended activation workflow**

1. `opendream init --workspace .` — create the memory layout and activate configured agent surfaces by default.
2. `opendream activation-plan --workspace . --targets configured` — optional dry-run: see which surfaces are detected. Use `--targets all-supported` to preview every built-in agent target.
3. `opendream verify activation-capture --workspace . --targets configured` — run generated hooks in the selected workspace and prove diagnostic memory capture.
4. `opendream status --workspace .` — report the latest capture verification state (`never_run`, `passed`, or `failed`) with the next action.
5. `opendream activate --workspace . --repair` — restore drifted managed files and hook entries.
6. `opendream doctor --workspace . --surface agents` — inspect managed surfaces without writing diagnostic memory.

**Compatibility matrix**

| Agent/runtime | Built-in target | Integration status | Notes |
|---------------|-----------------|--------------------|-------|
| Claude Code and Claude CoWork | `claude-code` | Native hooks | Uses Claude Code `UserPromptSubmit` / `Stop` hooks in `.claude/settings.json`; Claude CoWork should use this path when backed by Claude Code project hooks. |
| OpenAI Codex CLI | `codex` | Managed wrapper plus `AGENTS.md` | Codex is one supported example target, not a product requirement. |
| Cursor | `cursor` | Instruction-only rules plus shell hooks | OpenDream writes `.cursor/rules/opendream.mdc`; the host or agent must run the hook commands. |
| GitHub Copilot repository instructions | `github-copilot` | Instruction-only repository guidance plus shell hooks | Useful when Copilot can read repo instructions; hook execution remains operator/host-owned. |
| Hermes Agent | `hermes` | Instruction-only `.hermes.md` plus shell hooks | Hermes natively reads `.hermes.md`, `HERMES.md`, and `AGENTS.md`; OpenDream uses `.hermes.md` so it does not compete with shared repo instructions. |
| OpenClaw | `openclaw` | Native config and event map | Uses `.openclaw/config.json`, an OpenDream event map, and generated pre/post hook scripts. |
| AGENTS.md-style community agents | none yet | Generic/manual | Use `prepare-context` before work and `emit-event` + `maintain` after work, or add a small adapter once the host exposes stable hooks/config files. |
| Scripts, daemons, CI jobs, and custom runtimes | n/a | Direct CLI | Call the same CLI sequence directly; no named agent adapter is required. |

For a tool that was not detected yet, run e.g. `opendream activate --workspace . --targets cursor` once to create `.cursor/rules/opendream.mdc` and hook scripts.

Instruction-only targets (Cursor rules, `.github/copilot-instructions.md`, `.hermes.md`) ship the same generic pre/post shell hooks as the Codex example target; the agent must still run those commands when the host has no native OpenDream hooks.

Corrections worth knowing:

- Treat **`maintain`** as the documented maintenance entrypoint even if the CLI exposes more commands.
- **First-party surface** = this CLI. Hook/script glue is **operator-owned** unless you add it.
- **No first-party MCP server** in this repo; [`docs/mcp/servers.md`](./docs/mcp/servers.md) is a template for inventorying MCP, not a shipped server.

<details>
<summary><strong>Agent and architecture references</strong> (optional reading)</summary>

Human-facing behavior is described in this README and in [`AGENTS.md`](./AGENTS.md). Machine-readable runtime contracts live under [`opendream/schema/`](./opendream/schema/).

</details>

---

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
opendream observe index --workspace "$PWD"
opendream observe serve --workspace "$PWD" --port 8000
```

Then open `http://127.0.0.1:8000/overview` on the same machine. `observe serve` blocks until Ctrl+C.
The observe server also exposes `GET /api/status` for lightweight workspace progress, `GET /api/health` for startup/readiness/liveness evidence, and `POST /api/health/live-check` for a synthetic end-to-end probe that verifies append plus index refresh without creating durable memory.
For semantic-first workspaces, `/overview` and `/settings` should expose the same truth as CLI status: readiness, setup-required vs degraded state, state reason, next action, memory-quality warnings, and pruning evidence, with raw JSON still available behind disclosure.
The same UI also exposes background-runtime controls and digestible summaries of
the current memory surface plus the latest runtime mutation effects, so you can
see what OpenDream is changing without dropping straight into raw JSON.

Watch the UI flow in both themes: [`docs/showcase/ui-demos.md`](./docs/showcase/ui-demos.md).

<details>
<summary><strong>What the observability app exposes</strong></summary>

Built from the same on-disk artifacts as the runtime (read model is derived; filesystem remains source of truth):

- Index at `.opendream/memory/state/observability_index.json` (under your configured memory root)
- Read APIs: overview, memories, runs, retrievals, sessions, context, graph, reviews, evals, exports
- Health APIs: `/api/status`, `/api/health`, and `/api/health/live-check`
- Audited writes: annotations, review decisions, exports
- SSE at `/api/stream/status`
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

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/showcase/memory-showcase.md](./docs/showcase/memory-showcase.md) | 90-second memory demo |
| [docs/agent-integrations.md](./docs/agent-integrations.md) | Agent integration guide |
| [docs/automation/dream-task-playbook.md](./docs/automation/dream-task-playbook.md) | Automation and recurring memory tasks |
| [docs/architecture/overview.md](./docs/architecture/overview.md) | Architecture overview |
| [docs/benchmarks/methodology.md](./docs/benchmarks/methodology.md) | Benchmark methodology |
| [docs/claims.md](./docs/claims.md) | Evidence-backed claims |
| [docs/known-limitations.md](./docs/known-limitations.md) | Known limitations |
| [docs/provenance.md](./docs/provenance.md) | Clean-room provenance |
| [SECURITY.md](./SECURITY.md) | Security policy |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Contributor guide |

OpenDream does not send telemetry by default. Provider/API-key paths are
operator-configured execution paths and are separate from analytics or tracking.

---

## Contributing

<details>
<summary><strong>Contributor workflow</strong></summary>

```bash
make sync    # or: make setup — uv vs pip venv
make demo
make verify
make release-check
opendream --help
```

`make sync` matches CI (`uv sync --group dev`). Use `.venv/bin/opendream` if you skip activating the venv.

</details>

<details>
<summary><strong>Step-by-step smoke test</strong> (init → emit → maintain → context)</summary>

```bash
opendream init --workspace .tmp/ws
```

Expect `.opendream/memory/` with `state/durable_records.json`, `state/index.json`, and `MEMORY.md` (paths relative to the active memory root).

```bash
opendream emit-event \
  --workspace .tmp/ws \
  --kind project_decision \
  --content "Use pnpm in this repo" \
  --message-ref manual-1 \
  --tag key:package-manager
```

Expect JSON `"status": "appended"` and new JSONL under `<memory-root>/state/events/`.

```bash
opendream maintain --workspace .tmp/ws
```

Expect JSON with `extract.processed_events > 0` when pending, `consolidate.status` completed or an explicit skip, and `<memory-root>/state/maintenance_state.json` updated when work runs.

```bash
opendream prepare-context \
  --workspace .tmp/ws \
  --query "package manager and workflow"
```

Expect `selected_memory_ids`, `why`, and `prompt_context`.

```bash
make verify
make release-check
```

**Verification limits:** The gate is real for CLI and packaging behavior but bounded. PASS means “meets this repo’s bar,” not universal safety.

</details>

<details>
<summary><strong>Automation (managed projections)</strong> — register, run, schedule via tick</summary>

Automations are **projection jobs**: they read **durable** memories, write **typed records** under `<memory-root>/automation/`, and can appear in `prepare-context` under **Active Automation Projections** — they do **not** replace canonical durable memory.

**Playbook:** To wire skills, cron, and staleness the same way across projects (feature mining, bug radar, research deltas), follow [`docs/automation/dream-task-playbook.md`](./docs/automation/dream-task-playbook.md). Commit job specs under `docs/automation/job-specs/` or your own path and register from there.

**1. Prerequisite:** initialized store plus durable memories (same as the smoke test: `init`, ingest events, `maintain`).

**2. Job spec:** JSON validated against [`opendream/schema/automation-job.schema.json`](./opendream/schema/automation-job.schema.json). You may omit `version`, `enabled`, and timestamps; `automation register` normalizes defaults (`version`: 1, `enabled`: true, `created_at` / `updated_at`).

Example file `automation-release-watch.json` (adjust selectors to match your corpus):

```json
{
  "job_id": "release-watch",
  "title": "Release watch",
  "description": "Track release-affecting workflow signals.",
  "skill_ref": "builtin://projection-engine",
  "trigger": {"type": "interval", "interval_seconds": 3600},
  "input_selectors": {
    "memory_types_any": ["project_decision", "environment_requirement", "procedural_workflow", "user_preference"],
    "text_terms_any": ["redis", "migration"],
    "statuses_any": ["active"],
    "limit": 25
  },
  "output": {"record_type": "feature", "max_records": 10},
  "merge_policy": {"dedupe_by": "title"},
  "decay_policy": {"stale_after_runs": 3},
  "review_policy": {"require_manual_review": true, "auto_surface_limit": 3},
  "security_policy": {"allow_sensitive": false}
}
```

**3. Commands**

```bash
opendream automation register --workspace "$PWD" --spec ./automation-release-watch.json
opendream status --workspace "$PWD"
opendream automation run --workspace "$PWD" --job release-watch
opendream automation status --workspace "$PWD" --job release-watch
opendream automation review --workspace "$PWD" --job release-watch
opendream prepare-context --workspace "$PWD" --query "your task"
```

- **`opendream tick --workspace "$PWD"`** runs maintenance **and** any **due** automation jobs (interval elapsed since `last_run_at`). Use this from cron or a service alongside `maintain`.
- **`opendream automation tick`** runs **only** due automation jobs (no extract/consolidate pass).
- Use **`--now`** only for deterministic tests or scripted repros; normal operator flows should omit it.

**4. On-disk layout (under active memory root)**

| Path | Role |
|------|------|
| `automation/jobs/<job_id>.json` | Registered, schema-valid job |
| `automation/records/<record_type>/<job_id>.json` | Projection records |
| `automation/audit/` | Run reports and diffs |

**5. Tests in repo:** `tests.test_memory_cli.MemoryCliIntegrationTests.test_automation_register_run_status_and_context` and `test_automation_staleness_and_top_level_tick`. Consumer repos should run the same smoke path locally; extend CI with project-owned schema checks if the canonical backlog lives in git (see **Verification** in [`docs/automation/dream-task-playbook.md`](./docs/automation/dream-task-playbook.md)).

</details>

<details>
<summary><strong>What’s in this repo</strong></summary>

| Path | Contents |
|------|----------|
| `opendream/` | Runtime: events, candidates, consolidation, retrieval, storage |
| `tests/` | Fixture-driven integration and validation |
| `opendream/schema/` | Machine-readable runtime contracts |
| `docs/` | Architecture, governance, and user-facing guides |

Optional, **non-normative** framework examples may live under `.meta/spec-adapters/` (see [`AGENTS.md`](./AGENTS.md)). They are not part of the packaged product API; `scripts/check_adapters.py` keeps example paths and documented CLI strings consistent.

</details>

<details>
<summary><strong>Verification targets</strong></summary>

Authoritative when the scripted gate passes; report at `.tmp/verification/verification_report.json`.

| Target | What it runs |
|--------|----------------|
| `make lint` | Ruff (`scripts/lint.py`) |
| `make typecheck` | mypy on `opendream` and `scripts` |
| `make test` | Unit tests |
| `make verify` | Lint, typecheck, tests, `eval dream-layout` (fresh temp workspace), `scripts/check_adapters.py`, packaging smoke |
| `make release-check` | Release gate: artifacts, clean venv install, `dream run`, `eval dream-layout`, verification replay |

`make release-check` also writes `.tmp/release-check/release_manifest.json` and `release_summary.md`.

</details>

<details>
<summary><strong>Releasing (maintainers)</strong></summary>

Publishing follows the **tag push** pattern: [`.github/workflows/publish-pypi.yml`](./.github/workflows/publish-pypi.yml) runs `uv build` + `uv publish` with **PyPI Trusted Publishing (OIDC)**.

**GitHub vs PyPI binding**

- Each repo has its **own** GitHub Environment named `pypi` (the one on another org/repo does not apply here).
- On PyPI, the **opendream** project must list **repository `pylit-ai/opendream`** and workflow **`publish-pypi.yml`**. A trusted publisher row for a different repo will not publish this package.

**Checklist**

1. PyPI → **opendream** → **Publishing** → trusted publisher: owner `pylit-ai`, repository `pylit-ai/opendream`, workflow `publish-pypi.yml`, environment `pypi`.
2. GitHub → **Environments** → ensure **`pypi`** exists; add protection/reviewers if desired.
3. Bump `pyproject.toml` to a new version, then `git tag -a v0.1.0 -m "Release v0.1.0"` and `git push origin v0.1.0`, or use `make release-patch` / `release-minor` / `release-major`.

Local dry run: `uv build` → `dist/`. TestPyPI is not wired by default.

</details>

<details>
<summary><strong>Full CLI examples</strong> (copy-paste reference)</summary>

```bash
opendream init --workspace .tmp/workspace
opendream init --workspace ~/.opendream-global --store-kind global
opendream demo --workspace .tmp/demo
opendream bootstrap-index --workspace .tmp/workspace --events tests/fixtures/bootstrap_events.jsonl
opendream consolidate --workspace .tmp/workspace
opendream retrieve --workspace .tmp/workspace --query "package manager and workflow"
opendream emit-event --workspace .tmp/workspace --kind project_decision --content "Use pnpm in this repo" --message-ref manual-1 --tag key:package-manager
opendream maintain --workspace .tmp/workspace
opendream dream run --workspace .tmp/workspace --episodes tests/fixtures/transcript_only_dream.jsonl
opendream dream status --workspace .tmp/workspace
opendream dream tick --workspace .tmp/workspace --episodes tests/fixtures/transcript_only_dream.jsonl
opendream eval dream-layout --workspace .tmp/dream-eval --compat-mode project-user
opendream eval memory-quality --workspace .tmp/eval
opendream prepare-context --workspace .tmp/workspace --query "package manager and workflow"
opendream prepare-context --workspace .tmp/workspace --query "package manager and workflow" --include-global --global-workspace ~/.opendream-global
opendream automation register --workspace .tmp/workspace --spec ./path/to/job.json
opendream automation run --workspace .tmp/workspace --job my-job-id
opendream automation tick --workspace .tmp/workspace
opendream automation status --workspace .tmp/workspace
opendream status --workspace .tmp/workspace
opendream observe index --workspace .tmp/workspace
opendream observe serve --workspace .tmp/workspace --port 8000
```

Module fallback:

```bash
python3 -m opendream.cli --help
```

</details>
