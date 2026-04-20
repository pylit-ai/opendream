# Dream task playbook (multi-layer automation)

Canonical guide for wiring **recurring automation dreams** in OpenDream: capture durable memory, project **radar** records via automation jobs, and optionally run a **semantic refresh** so lists track the repo without mistaking projections for truth.

**Audience:** operators and coding agents setting up feature queues, bug radar, research deltas, or similar in any repo using OpenDream.

**Related:** [README — Automation](../../README.md) (CLI examples), [`docs/coding-agents.md`](../coding-agents.md) (hooks, `tick` vs `automation tick`, `--now`). Job schema: [`opendream/schema/automation-job.schema.json`](../../opendream/schema/automation-job.schema.json). **Operator walkthrough (semantic dream vs feature radar):** [semantic-mode-and-feature-radar-setup.md](semantic-mode-and-feature-radar-setup.md). **Full command cookbook (ordered workflows + where LLMs run):** [complete-operator-workflow.md](complete-operator-workflow.md).

**Clarification:** **Transcript `dream`** (episodes → consolidation / optional semantic pipeline) and **automation radar** (`automation register|run` projecting durable memory) are different subsystems. Feature mining uses **automation** + Layer A capture; see the setup guide above.

**Semantic-first posture note:** this playbook assumes OpenDream prefers a semantic-first posture, but that posture is not a promise that semantic execution is currently ready. If the semantic path is unavailable, operators should see an explicit **degraded** state, a concrete reason, and one next action rather than a misleading "semantic" label.

If you maintain repo-local agent skills or commands for this workflow, keep them aligned with this playbook rather than duplicating policy here.

---

## 1. Intent: radar vs strategist

| Layer | Role | Uses an LLM? |
|-------|------|----------------|
| **A — Capture** | Turn conversation or skill output into **events** and, after `maintain`, **durable** memories. | Yes (the coding agent or skill that calls `emit-event`). |
| **B — Automation** | **Project** durable memories into typed records (`feature`, `bug`, `fix`, etc.), dedupe, mark **`stale`** when sources stop matching selectors. | **No** — deterministic. |
| **C — Semantic refresh** | Reconcile backlog with **git**, **dependencies**, **research**, or new decisions; emit **new** events (supersede, defer, obsolete). | Yes — a **scheduled** agent session. |

Automation is the **radar**: it surfaces what already exists in durable memory under your selectors. It does **not** read the codebase or the web to decide that an idea is obsolete. That is **Layer C**.

---

## 2. Prerequisites

1. **Workspace:** repository root; pass `--workspace` consistently (see [`docs/coding-agents.md`](../coding-agents.md)). For a **single ordered list of commands** from `init` through `tick` (and optional Layer C), use [complete-operator-workflow.md](complete-operator-workflow.md).
2. **Active memory root:** run `opendream doctor --surface memory` and use `memory_layout.active_memory_root` as the only store you reason about.
3. **Initialized store** with ingest + `maintain` working (durable memories exist) before automation jobs return useful rows.
4. **Operators:** use `opendream tick` for maintenance **and** due automation jobs; use `opendream automation tick` for automation only. Reserve `--now` for **tests and repros**, not production cron.
5. **Truthful status:** before calling a workflow semantic-ready, confirm that `opendream status`, `workspace doctor`, or `/overview` reports readiness rather than degraded fallback.

---

## 3. Single source of truth (pick one per repo)

Document the choice in your project `AGENTS.md` or runbook so skills and jobs stay aligned.

| Option | Canonical data | Automation |
|--------|------------------|------------|
| **OpenDream-native** | Events + durable records under `active_memory_root`. | Selectors use your real **`kind`** / memory types after consolidation. Optional **export** to repo YAML for humans. |
| **Repo-native** | Committed structured file (for example YAML) in the repo. | Skill must **mirror** each change with `emit-event` so `memory_types_any` still matches; otherwise projections go empty. |

**Do not** treat automation records in `prepare-context` as canonical product backlog unless you **promote** them via explicit events or accepted specs (see [`docs/coding-agents.md`](../coding-agents.md)).

---

## 4. Layer A — Capture checklist

1. **Stable event taxonomy:** define `emit-event --kind` values your consolidation promotes to durable memory (for example `project_decision`, task-specific `mined_feature`, or names your skill already uses).
2. **Structured payload:** put phase, evidence strength, and confidence in **`--content`** and **`--tag`** (for example `key:phase`, `key:evidence`) so merge and audit stay diff-friendly.
3. **On-demand skill or slash command:** heavy capture logic lives there; keep `AGENTS.md` / `CLAUDE.md` to **one operational line** (for example: after substantive product discussion, run `/capture-proposals` or your skill).
4. **Evidence policy:** do not invent durable items without a minimum bar (explicit ask, repeated need, or clear deferred consequence). If uncertain, log a **candidate** or a single `review_requested`-style event instead of polluting the canonical stream.
5. **After emits:** run `opendream maintain --workspace "$WORKSPACE"` so durable state exists for Layer B.

---

## 5. Layer B — Automation checklist

1. **Versioned job specs in git:** for example `docs/automation/job-specs/<job_id>.json` (this repo) or `.opendream/job-specs/` in a consumer repo — same content, team convention.
2. **Validate** against [`opendream/schema/automation-job.schema.json`](../../opendream/schema/automation-job.schema.json). You may omit `version`, `enabled`, and timestamps; `automation register` normalizes defaults.
3. **Align selectors:**
   - `input_selectors.memory_types_any` — must match **actual** durable memory types your pipeline produces.
   - `text_terms_any` — optional lexical filter; `[]` if unused.
   - `statuses_any` — typically `["active"]` where applicable.
   - `limit` — cap source rows per run.
4. **Output:** `output.record_type` is one of `feature`, `bug`, `fix`, `research-delta`, `generic` (schema enum).
5. **Merge:** `merge_policy.dedupe_by`: `title` or `title+summary`.
6. **Decay:** `decay_policy.stale_after_runs` — after **N** consecutive runs with no matching source memory, the projection can go **`stale`** (selector-based irrelevance, not “we adopted another framework”).
7. **Register and run:**

   ```bash
   opendream automation register --workspace "$PWD" --spec ./docs/automation/job-specs/<job_id>.json
   opendream automation run --workspace "$PWD" --job <job_id>
   opendream automation status --workspace "$PWD" --job <job_id>
   opendream automation review --workspace "$PWD" --job <job_id>
   ```

8. **Schedule:** `opendream tick --workspace "$PWD"` on cron so maintenance and **due** jobs (by `trigger.interval_seconds`) run together.

**Tuning staleness:** approximate time-to-stale ≈ `(interval_seconds × stale_after_runs)` between losses of matching source memories — adjust for how aggressively you run `tick`.

---

## 6. Layer C — Semantic refresh

Use when the backlog must track **repository reality** or **external knowledge** (new framework, superseded design).

### 6a. Local direct-provider Layer C

When you have an explicit API key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) or use `codex-account` on trusted infrastructure:

1. **Cadence:** weekly, or after large merges / dependency upgrades.
2. **Inputs (paste into the agent session):**
   - `opendream automation review --workspace "$PWD" --job <job_id>` (JSON),
   - recent `opendream prepare-context` output for the same workspace,
   - short **git diff** or dependency manifest delta,
   - optional research notes with citations.
   - inspect the context metadata, not just the prompt body: the active profile, suppressed items, and pruning deltas should show whether progressive disclosure is actually working
3. **Outputs:** only **`emit-event`** calls (or edits to repo-native canonical file **plus** mirroring events). Prefer events such as: supersede, defer, `obsolete_reason`, merge-with-id — whatever your Layer A taxonomy defines.
4. **Abstention:** if evidence is weak, emit a **single** `review_requested` (or equivalent) instead of mass-updating.
5. **Follow-up:** `opendream maintain --workspace "$PWD"` then `opendream tick --workspace "$PWD"` so projections refresh.

### 6b. Delegated Layer C (Claude / Cursor adapters)

When using `claude-scheduled-task` or `cursor-automation`, the vendor runtime owns the model call:

1. **Scaffold:** `opendream semantic adapters scaffold --workspace "$PWD" --adapter claude-scheduled-task` (or `cursor-automation`).
2. **Schedule:** Configure the vendor's task/automation system to run the scaffolded prompt on your cadence.
3. **Return path:** The vendor runtime writes a delegated semantic envelope to `.opendream/inbox/semantic/<adapter>/`.
4. **Ingest:** `opendream semantic ingest --workspace "$PWD" --scan-inbox` validates and ingests envelopes through the standard verify-promote pipeline.
5. **Follow-up:** same as 6a step 5.

**Key distinction:** In delegated mode, OpenDream does not directly call the model. The vendor runtime owns execution; OpenDream owns memory, validation, and promotion. Docs and status surfaces must reflect this accurately.

**Quality expectation:** semantic refresh is only differentiated if it improves context quality. If `prepare-context` keeps returning flat, homogeneous memory or no measurable pruning advantage, treat that as a memory-quality warning to investigate, not as a healthy semantic result.

---

## Delegated execution (Layer C)

For vendor-runtime adapters (Claude, Cursor), Layer C (semantic refresh, reconciliation) can be delegated:

```sh
# Generate scaffolds for a delegated semantic-refresh via Claude
opendream automation scaffold-dream --workspace . --adapter claude-scheduled-task --kind semantic-refresh

# Generate feature-radar scaffold for Cursor
opendream automation scaffold-dream --workspace . --adapter cursor-automation --kind feature-radar
```

Delegated results return via `.opendream/inbox/semantic/<adapter>/` as structured envelopes. Ingest with:

```sh
opendream semantic ingest --workspace . --scan-inbox
```

Projections remain non-canonical until promoted through the standard verification pipeline.

---

## 7. Verification

### In this repository

Run the full gate:

```bash
make verify
```

Automation behavior is covered by integration tests under `tests/test_memory_cli.py`, including:

- `MemoryCliIntegrationTests.test_automation_register_run_status_and_context`
- `MemoryCliIntegrationTests.test_automation_staleness_and_top_level_tick`

### In consumer repos

- Repeat the [README smoke path](../../README.md): `init`, `emit-event`, `maintain`, `automation register`, `automation run`, `prepare-context`.
- Optionally validate job JSON with the same schema file (packaged path or vendored copy).
- **If the canonical backlog is repo YAML/JSON:** add a CI step that validates your registry file against a **project schema** (jsonschema, yamale, etc.). OpenDream does not ship a backlog-YAML schema; that check is project-owned.

---

## 8. Failure modes

| Symptom | Likely cause | Mitigation |
|---------|----------------|------------|
| Empty automation section in `prepare-context` | No durable rows matching `memory_types_any` / filters | Fix kinds or tags; run `maintain`; confirm consolidation. |
| Radar never updates | `tick` not running or interval not elapsed | Use `automation run` once; then schedule `tick`. |
| Everything goes `stale` too fast | `stale_after_runs` too low or selectors too narrow | Widen types or raise N. |
| Wrong backlog promoted | Treating projections as SoT | Promote only via explicit events/specs; keep playbook §3 in team docs. |
| Stale ideas never leave | Only Layer B in use | Add Layer C; Layer B alone cannot infer “framework X obsolete.” |
| Workspace says semantic but acts deterministic | `mode=semantic` configured without a runnable semantic path | Treat as degraded semantic-first, run `semantic setup` / inspect status, and surface the next action instead of claiming readiness. |
| Context previews stay bloated | Progressive disclosure not pruning enough candidates | Check `prepare-context` metadata for profile, candidate counts, injected counts, and suppression reasons; tune selectors or semantic setup before trusting the output. |

---

## 9. Reusing this playbook for another dream

1. Rename job IDs and `record_type` for your concern (`research-delta`, `generic`, etc.).
2. Redefine Layer A **`kind`** tags and skill copy.
3. Copy a job spec template from [README Automation](../../README.md) or from [`examples/feature-mining.md`](examples/feature-mining.md).
4. Document SoT and cron in your `AGENTS.md` / operator runbook.

---

## Copy-paste: OpenDream appendix for skill prompts

When your skill prompt (for example a feature-proposal harness) should mention OpenDream explicitly, add:

- Which **`emit-event --kind`** values to use and which **tags** encode phase and evidence.
- That **automation records are non-canonical** until promoted via events or specs.
- That **semantic lifecycle** requires Layer C on a schedule, not automation alone.

For a full **registry field spec** and evaluation requirements for proposal capture skills, see your project’s planning doc or a repo-local copy of that prompt; this playbook only defines how those items connect to OpenDream’s CLI and stores.
