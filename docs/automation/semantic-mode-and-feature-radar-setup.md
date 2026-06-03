# Operator setup: semantic dream mode and feature radar

**End-to-end command order (capture → radar → optional AI refresh):** [complete-operator-workflow.md](complete-operator-workflow.md) — use that doc for copy-paste sequences; this page focuses on **config files** and **what each subsystem does**.

Step-by-step guide for two **separate** features:

1. **Transcript dream + semantic / hybrid mode** — `opendream dream run` ingests agent transcripts and can run the extended “sleep-time” pipeline (learned-context proposals, verification, promotion).
2. **Feature mining radar** — **automation jobs** project durable memories into reviewable `feature` / `bug` / `fix` records. This uses **`opendream automation`**, not `dream`.

**Canonical background:** [Dream task playbook](dream-task-playbook.md) (layers A/B/C), [feature-mining example](examples/feature-mining.md).

---

## Part A — Semantic / hybrid dream mode

### What it does

- **`dream run --mode deterministic`** (default): existing four-phase dream — transcript signal → events → `maintain` / consolidation.
- **`dream run --mode hybrid` or `--mode semantic`**: runs the **semantic pipeline** when configuration and providers satisfy [availability rules](../../opendream/provider_registry.py) (`semantic_mode_available`): query-family anticipation, proposal synthesis, verification, promotion into learned context, plus audits under `<memory-root>/audit/semantic_dream/` and related paths.

### What actually calls an LLM today?

The core runtime is **stdlib-only**. Provider entries and API keys are **real** (health checks env vars; registry on disk), but **proposal synthesis and semantic verification are still in-process heuristics** in this repository — see `opendream/semantic_dreamer.py` (`_synthesize_proposals`) and `opendream/semantic_verifier.py` (`semantic_verify`). Enabling hybrid/semantic turns on that pipeline and audit trail; it does **not** open outbound HTTP to Anthropic/OpenAI from this package yet. Outbound transports are reserved for future work while keeping the same config shapes (`opendream/schema/provider-entry.schema.json`, `semantic-dream-config.schema.json`).

### Prerequisites

- `opendream init --workspace .` from the workspace directory (or an existing initialized workspace).
- Know your **memory root** (usually `.opendream/memory` under the workspace). Config files below are relative to **`<memory-root>/state/`**.

### 1) Capture full default semantic config

With **no** `semantic_config.json` yet, the CLI shows merged defaults:

```bash
opendream semantic config --workspace "$PWD"
```

Save that JSON to:

`<workspace>/.opendream/memory/state/semantic_config.json`

(or your `--memory-dir` equivalent: `<workspace>/<memory-dir>/state/semantic_config.json`).

**Important:** If this file exists, OpenDream uses **only** what is in the file (defaults are not deep-merged). Start from the full blob above, then edit.

### 2) Set mode

In `semantic_config.json`, set:

```json
"mode": "hybrid"
```

Valid values: `deterministic`, `semantic`, `hybrid` (see schema).

Optional: adjust `budgets`, `anticipation`, `verification`, `fallback_policy`. If semantic prerequisites are missing, `fallback_policy: "fallback_to_deterministic"` keeps `dream run` useful.

### 3) Register providers

Create or edit:

`<memory-root>/state/provider_registry.json`

as a **JSON array** of provider objects. Schema: `opendream/schema/provider-entry.schema.json`. Minimal example (IDs and models are yours to choose):

```json
[
  {
    "provider_id": "anthropic-primary",
    "transport": "anthropic",
    "model_id": "claude-sonnet-4-20250514",
    "roles": ["anticipation", "synthesis", "verification"],
    "supports_structured_output": true
  }
]
```

**Roles:** availability logic requires **at least one healthy/degraded provider** covering **`synthesis`** and **`verification`** (`semantic_mode_available`). `anticipation` is used by the planner; align roles with how you intend to split work when transports exist.

**API keys (for health checks):**

- `transport: "anthropic"` → `ANTHROPIC_API_KEY`
- `transport: "openai"` → `OPENAI_API_KEY`

### 4) Health and status

```bash
export ANTHROPIC_API_KEY=...   # or OPENAI_API_KEY for openai transport

opendream semantic provider-health --workspace "$PWD"
opendream semantic status --workspace "$PWD"
```

Expect `semantic status` → `"available": true` when mode is not `deterministic`, providers exist, and health passes.

### 5) Run dream in hybrid / semantic mode

```bash
opendream dream run \
  --workspace "$PWD" \
  --episodes path/to/episodes.jsonl \
  --mode hybrid \
  --compat-mode project-user
```

Use repo fixtures for a smoke test, e.g. `tests/fixtures/transcript_only_dream.jsonl` from an OpenDream checkout.

If semantic mode is unavailable and `fallback_policy` is `fallback_to_deterministic`, stdout JSON includes `semantic_fallback` / `semantic_fallback_reason` and deterministic dream still runs.

### 6) Inspect artifacts

- Semantic dream audits: `<memory-root>/audit/semantic_dream/`
- Verifier audits: `<memory-root>/audit/semantic_verifier/`
- Learned context records: `<memory-root>/state/learned_context_records.json` (plus topic material under `topics/learned-context/` when generated)

Bootstrap snapshot for support / debugging only. This does not validate semantic readiness or materialize learned context:

```bash
opendream semantic bootstrap --workspace "$PWD"
```

---

## Part B — Feature mining automation (“feature radar dream”)

This is **Layer B** in the playbook: **deterministic** projection from **durable memory** into automation records. It does **not** use `dream run` and does not require semantic mode.

### 1) Layer A — Events and durable memory

- Emit events with kinds your consolidator promotes (example kinds from the example doc: `mined_feature`, `mined_bug`, `mined_fix`).
- Run `opendream maintain --workspace "$PWD"` so durable records exist.

See [examples/feature-mining.md](examples/feature-mining.md) §1–2 for `emit-event` examples and job JSON.

### 2) Layer B — Register automation jobs

Job specs in **this** repository live under [`docs/automation/job-specs/`](job-specs/). Copy or adapt `feature-radar.json`, `bug-radar.json`, `fix-radar.json`.

```bash
opendream automation register --workspace "$PWD" --spec ./docs/automation/job-specs/feature-radar.json
opendream automation run --workspace "$PWD" --job feature-radar
opendream automation status --workspace "$PWD"
opendream prepare-context --workspace "$PWD" --query "features and bugs"
```

Align `input_selectors.memory_types_any` with the **actual** durable memory `type` values your store uses (inspect durable records or consolidation output if projections are empty).

### 3) Schedule

Use cron or a service to run:

```bash
opendream tick --workspace "$PWD"
```

so **maintenance** and **due automation jobs** both run (or `opendream automation tick` for automation only).

### 4) Layer C — Optional semantic refresh

Human or scheduled agent session using automation review JSON + git/deps delta → new `emit-event` rows → `maintain` → `tick`. See playbook §6.

---

## Quick reference

| Goal | Command surface | Uses LLM in core today? |
|------|-----------------|-------------------------|
| Transcript dream + hybrid pipeline | `dream run --mode hybrid` | No (heuristic synthesis / verification) |
| Feature / bug / fix radar | `automation register|run|tick` | No |
| Optional backlog refresh vs repo | Layer C agent session + `emit-event` | Yes (your agent session) |

## See also

- [docs/agent-integrations.md](../agent-integrations.md) — hooks, `--workspace`, contract export
- [docs/FAQ.md](../FAQ.md) — semantic mode and limitations
- [ADR-007](../adr/ADR-007-semantic-learned-context-layer.md), [ADR-008](../adr/ADR-008-semantic-verifier-promotion-policy.md) — architecture
