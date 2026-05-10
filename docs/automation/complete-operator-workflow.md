# Complete operator workflow (command cookbook)

Single place for **ordered CLI sequences**: feature mining + automation radar, transcript **dream** in hybrid/semantic mode, and **where a real LLM is involved** vs deterministic OpenDream code.

![OpenDream automation radar scaffold](../assets/demos/07-automation-radar.gif)

**Prerequisites:** [Dream task playbook](dream-task-playbook.md) (layers A/B/C). **Deeper detail:** [semantic-mode-and-feature-radar-setup.md](semantic-mode-and-feature-radar-setup.md) (config file shapes), [examples/feature-mining.md](examples/feature-mining.md) (job JSON and event kinds).

---

## 1. Where an LLM actually runs (read this first)

| What you are doing | Primary commands | Who/what calls a model? |
|--------------------|------------------|-------------------------|
| **Layer A — Capture** | `emit-event`, then `maintain` | **Your coding agent** (or you) when producing `emit-event` content. OpenDream only stores and consolidates. |
| **Layer B — Feature / bug / fix radar** | `automation register`, `automation run`, `tick` | **Nobody.** Projections are deterministic from durable memory. |
| **Layer C — Semantic refresh** | Paste context into an agent → `emit-event` → `maintain` → `tick` | **Your scheduled agent session** (Claude/Cursor/Codex chat) with repo + review JSON + git delta. |
| **Layer C — Delegated** | Scaffold → vendor runs task → `semantic ingest --scan-inbox` → `maintain` → `tick` | **Vendor runtime** (Claude scheduled task or Cursor Automation). OpenDream validates and ingests the envelope. |
| **Transcript dream — hybrid / semantic** | `dream run --mode hybrid` (or `semantic`) | **Not from this package today:** synthesis and semantic verification are **in-process heuristics** (`semantic_dreamer`, `semantic_verifier`). `provider_registry.json` and API keys affect **availability and health**, not outbound Anthropic/OpenAI calls from core yet. |

So: **“Semantic mode that actually uses AI”** in production today means **Layer C** (you or a vendor-delegated task), or **Layer A** (the agent emitting events). **`dream run --mode hybrid`** exercises the semantic *pipeline* and audits on disk; it does **not** substitute for a live model unless you add a future transport or run Layer C.

---

## 2. Workflow: greenfield repo → feature mining radar

Use **`WORKSPACE`** as the **repository root** everywhere.

```bash
export WORKSPACE="$PWD"
```

### 2.1 Initialize and confirm memory root

```bash
opendream init --workspace "$WORKSPACE"
opendream doctor --surface memory --workspace "$WORKSPACE"
```

Use JSON output → `memory_layout.active_memory_root` as the tree you care about (usually `.opendream/memory/`).

### 2.2 Layer A — capture mined items as events

Repeat as your skill or session discovers features/bugs/fixes (example kinds from [feature-mining.md](examples/feature-mining.md)):

```bash
opendream emit-event \
  --workspace "$WORKSPACE" \
  --kind mined_feature \
  --content "Short title: … Summary: … Phase rationale: …" \
  --message-ref "session-$(date +%Y%m%d)-1" \
  --tag key:phase:next \
  --tag key:evidence:strong_inference

opendream maintain --workspace "$WORKSPACE"
```

Until **`maintain`** has run, durable rows may not exist and **radar jobs will see nothing**.

### 2.3 Layer B — register automation jobs

Job specs ship in **this** repo under [`job-specs/`](job-specs/). From another repo, **copy** those JSON files into your tree and point `--spec` at your copy.

**If your shell is at the OpenDream repository root** (paths below match the checkout):

```bash
opendream automation register --workspace "$WORKSPACE" --spec ./docs/automation/job-specs/feature-radar.json
opendream automation register --workspace "$WORKSPACE" --spec ./docs/automation/job-specs/bug-radar.json
opendream automation register --workspace "$WORKSPACE" --spec ./docs/automation/job-specs/fix-radar.json
```

**If you are in a consumer repo**, use the copied files, for example:

```bash
opendream automation register --workspace "$WORKSPACE" --spec ./.opendream/job-specs/feature-radar.json
```

Ensure each job’s `input_selectors.memory_types_any` matches the **durable memory `type`** values your consolidator actually writes (often the same strings as `emit-event --kind`, but confirm if you customized consolidation).

### 2.4 Run projections once, then inspect

```bash
opendream automation run --workspace "$WORKSPACE" --job feature-radar
opendream automation run --workspace "$WORKSPACE" --job bug-radar
opendream automation run --workspace "$WORKSPACE" --job fix-radar

opendream automation status --workspace "$WORKSPACE"
opendream automation review --workspace "$WORKSPACE" --job feature-radar --limit 10
opendream prepare-context --workspace "$WORKSPACE" --query "upcoming features and bugs"
```

### 2.5 Schedule maintenance + due jobs (production)

Cron (or systemd, LaunchAgent, etc.) should run **the same workspace**:

```bash
opendream tick --workspace "$WORKSPACE"
```

That runs **maintenance** and any **due** automation jobs (by each job’s `trigger.interval_seconds`). For automation only:

```bash
opendream automation tick --workspace "$WORKSPACE"
```

Omit **`--now`** in production unless you are testing (see [coding-agents.md](../coding-agents.md)).

---

## 3. Workflow: transcript dream in hybrid / semantic mode (smoke)

This is **not** feature radar. It uses **`dream run`** over **episode files** under the memory root.

### 3.1 Config files (minimal)

Follow **Part A** of [semantic-mode-and-feature-radar-setup.md](semantic-mode-and-feature-radar-setup.md):

1. `opendream semantic config --workspace "$WORKSPACE"` → save full JSON to  
   `<active_memory_root>/state/semantic_config.json` and set `"mode": "hybrid"` (or `"semantic"`).
2. Add `<active_memory_root>/state/provider_registry.json` (array of providers) if you want `semantic status` → `"available": true`.
3. Export `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` if you use those transports for **health**.

```bash
opendream semantic provider-health --workspace "$WORKSPACE"
opendream semantic status --workspace "$WORKSPACE"
```

### 3.2 Run dream

From an **OpenDream git checkout** you can use the packaged fixture:

```bash
opendream dream run \
  --workspace "$WORKSPACE" \
  --episodes ./tests/fixtures/transcript_only_dream.jsonl \
  --mode hybrid \
  --compat-mode autodream
```

Else pass `--episodes` to **your** JSONL episode paths.

If semantic prerequisites are missing and `fallback_policy` is `fallback_to_deterministic`, stdout JSON includes `semantic_fallback` / `semantic_fallback_reason` and deterministic dream still runs.

### 3.3 Inspect artifacts

Under `<active_memory_root>/`:

- `audit/semantic_dream/`, `audit/semantic_verifier/`
- `state/learned_context_records.json` when promotion occurs

Support bundle for debugging only. This does not validate semantic readiness or materialize learned context:

```bash
opendream semantic bootstrap --workspace "$WORKSPACE"
```

---

## 4. Workflow: “real AI” semantic refresh (Layer C)

Use this when the **backlog must change** because the repo or world changed (Layer B alone cannot infer obsolescence).

### 4.1 Pick execution strategy (optional but recommended)

```bash
opendream semantic setup --workspace "$WORKSPACE" --prefer no-extra-key --apply
opendream semantic status --workspace "$WORKSPACE"
opendream semantic adapters status --workspace "$WORKSPACE"
opendream dream worker --workspace "$WORKSPACE" --once --mode auto   # optional manual nudge / diagnosis
```

### 4.2 Path A — Manual agent session (you paste context)

1. Gather inputs:

   ```bash
   opendream automation review --workspace "$WORKSPACE" --job feature-radar --limit 20
   opendream prepare-context --workspace "$WORKSPACE" --query "features and technical debt"
   ```

2. In **Claude / Cursor / Codex**, paste: review JSON, `prepare-context` output, a short **git diff** or dependency delta, and your Layer C instructions (supersede / defer / obsolete with evidence only).

3. Have the agent emit events only (no hand-editing durable JSON):

   ```bash
   opendream emit-event --workspace "$WORKSPACE" --kind <your_layer_a_kind> ...
   opendream maintain --workspace "$WORKSPACE"
   opendream tick --workspace "$WORKSPACE"
   ```

Full policy: [dream-task-playbook §6](dream-task-playbook.md#6-layer-c--semantic-refresh).

### 4.3 Path B — Delegated vendor task (Claude or Cursor)

1. Scaffold artifacts:

   ```bash
   opendream semantic adapters scaffold --workspace "$WORKSPACE" --adapter claude-scheduled-task
   # or: --adapter cursor-automation
   ```

2. Configure the **vendor** scheduler to run the scaffolded prompt on your cadence; the runtime writes an envelope under  
   `.opendream/inbox/semantic/<adapter>/`.

3. Ingest and refresh projections:

   ```bash
   opendream semantic ingest --workspace "$WORKSPACE" --scan-inbox
   opendream maintain --workspace "$WORKSPACE"
   opendream tick --workspace "$WORKSPACE"
   ```

### 4.4 Path C — Codex account (local subprocess)

Scaffold `codex-account`, then follow the README in the scaffolded adapter directory for how the CLI is invoked on trusted hosts. Ingest is still via the direct-report path for that strategy (see [coding-agents.md](../coding-agents.md) matrix).

---

## 5. Verification checklist (operators)

| Step | Command |
|------|---------|
| Lint / type / full gate (in OpenDream repo) | `make verify` |
| Contract and CLI inventory | `opendream contract export --workspace "$WORKSPACE" --format json` |
| Adapter / strategy | `opendream semantic adapters status --workspace "$WORKSPACE"` |
| Empty radar | Confirm `memory_types_any` matches durable types; run `maintain` after emits |

---

## 6. Related docs

| Doc | Role |
|-----|------|
| [dream-task-playbook.md](dream-task-playbook.md) | Layers A/B/C concepts, failure modes |
| [semantic-mode-and-feature-radar-setup.md](semantic-mode-and-feature-radar-setup.md) | `semantic_config.json`, `provider_registry.json`, paths |
| [examples/feature-mining.md](examples/feature-mining.md) | Job JSON templates and `emit-event` examples |
| [coding-agents.md](../coding-agents.md) | `--workspace`, hooks, execution strategy matrix |
| [FAQ.md](../FAQ.md) | API keys, semantic limitations |
| [architecture/overview.md](../architecture/overview.md) | Component boundaries |
