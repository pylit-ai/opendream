# Example: feature / bug / fix mining automation

Worked example for **Layer A + B** using separate automation jobs per record type. Adapt names and `memory_types_any` to match **your** consolidation rules and mining skill.

**Prerequisites:** read [Dream task playbook](../dream-task-playbook.md) first. To run the same flow as an on-demand agent task, use the Cursor skill [`.cursor/skills/opendream-dream-automation/SKILL.md`](../../.cursor/skills/opendream-dream-automation/SKILL.md).

---

## 1. Suggested event kinds and tags (Layer A)

Your extraction skill should emit events that **`maintain` promotes** to durable memories. If your project already uses different `kind` strings, change **only** the table and the job `memory_types_any` arrays so they stay identical.

| Suggested `emit-event --kind` | Typical use | Suggested tags (examples) |
|-------------------------------|-------------|-------------------------|
| `mined_feature` | Proposed capability, deferred idea | `key:phase`, `key:evidence` (`explicit` / `strong_inference` / `weak_inference`) |
| `mined_bug` | Defect or regression risk | `key:severity`, `key:evidence` |
| `mined_fix` | Concrete fix or hardening item | `key:phase`, `key:evidence` |

**Tags** are optional but help `text_terms_any` filters and human audit. Example:

```bash
opendream emit-event \
  --workspace "$PWD" \
  --kind mined_feature \
  --content "Short title: … Summary: … Phase rationale: …" \
  --message-ref "session-2026-03-30-abc" \
  --tag key:phase:next \
  --tag key:evidence:strong_inference
```

Then:

```bash
opendream maintain --workspace "$PWD"
```

If your consolidator maps these to different **stored memory types**, put **those** type strings in `memory_types_any` (inspect `durable_records` or your consolidation config).

---

## 2. Job specs (Layer B)

In this repository, matching templates live under [`docs/automation/job-specs/`](../job-specs/). Copy or edit them for your project, or keep specs elsewhere and adjust paths when you `automation register`.

**Shared knobs:**

- `skill_ref`: use `builtin://projection-engine` unless you have a custom projection.
- `trigger.interval_seconds`: how often `tick` may run this job once due (for example `3600` hourly).
- `decay_policy.stale_after_runs`: raise if items flip stale too aggressively.

### `feature-radar.json`

```json
{
  "job_id": "feature-radar",
  "title": "Feature radar",
  "description": "Project mined feature proposals into automation records.",
  "skill_ref": "builtin://projection-engine",
  "trigger": {"type": "interval", "interval_seconds": 3600},
  "input_selectors": {
    "memory_types_any": ["mined_feature"],
    "text_terms_any": [],
    "statuses_any": ["active"],
    "limit": 25
  },
  "output": {"record_type": "feature", "max_records": 15},
  "merge_policy": {"dedupe_by": "title+summary"},
  "decay_policy": {"stale_after_runs": 4},
  "review_policy": {"require_manual_review": true, "auto_surface_limit": 5},
  "security_policy": {"allow_sensitive": false}
}
```

### `bug-radar.json`

```json
{
  "job_id": "bug-radar",
  "title": "Bug radar",
  "description": "Project mined bugs into automation records.",
  "skill_ref": "builtin://projection-engine",
  "trigger": {"type": "interval", "interval_seconds": 3600},
  "input_selectors": {
    "memory_types_any": ["mined_bug"],
    "text_terms_any": [],
    "statuses_any": ["active"],
    "limit": 25
  },
  "output": {"record_type": "bug", "max_records": 15},
  "merge_policy": {"dedupe_by": "title+summary"},
  "decay_policy": {"stale_after_runs": 3},
  "review_policy": {"require_manual_review": true, "auto_surface_limit": 5},
  "security_policy": {"allow_sensitive": false}
}
```

### `fix-radar.json`

```json
{
  "job_id": "fix-radar",
  "title": "Fix radar",
  "description": "Project mined fixes/hardening items into automation records.",
  "skill_ref": "builtin://projection-engine",
  "trigger": {"type": "interval", "interval_seconds": 3600},
  "input_selectors": {
    "memory_types_any": ["mined_fix"],
    "text_terms_any": [],
    "statuses_any": ["active"],
    "limit": 25
  },
  "output": {"record_type": "fix", "max_records": 15},
  "merge_policy": {"dedupe_by": "title+summary"},
  "decay_policy": {"stale_after_runs": 4},
  "review_policy": {"require_manual_review": true, "auto_surface_limit": 5},
  "security_policy": {"allow_sensitive": false}
}
```

### Register and smoke

```bash
opendream automation register --workspace "$PWD" --spec ./docs/automation/job-specs/feature-radar.json
opendream automation register --workspace "$PWD" --spec ./docs/automation/job-specs/bug-radar.json
opendream automation register --workspace "$PWD" --spec ./docs/automation/job-specs/fix-radar.json

opendream automation run --workspace "$PWD" --job feature-radar
opendream prepare-context --workspace "$PWD" --query "upcoming features and bugs"
```

---

## 3. Semantic refresh (Layer C) — prompt sketch

Use on a schedule: paste **automation review** JSON, a short **git / dependency delta**, and optional research notes. Instruct the agent to **only** add `emit-event` rows that **supersede, defer, or obsolete** prior items with explicit evidence; if unsure, one `review_requested` event. Then run `maintain` and `tick`. Full policy: [Dream task playbook §6](../dream-task-playbook.md).

---

## 4. Richer capture prompts

For proposal schema fields (id, status, phase rationale, confidence, evals), use a project-local **harness prompt** such as the “Objective-specific optimized prompt” in your planning notes; wire emitted content into `emit-event --content` and tags so automation and future Layer C runs stay structured.
