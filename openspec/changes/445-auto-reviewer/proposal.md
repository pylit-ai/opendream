# 436-auto-reviewer

## Why
Operators face a growing review queue (contested memory, low-confidence memory, large diff, suspicious retrieval). Manual triage does not scale. Most queue items have a deterministic resolution given thresholds and time-on-queue, but every item still demands a click. A user with dozens of pending reviews experiences inbox fatigue and stops engaging with the system, defeating the observability goal.

## Goal
Add a deterministic, auditable auto-reviewer that resolves the easy majority of queue items based on operator-tunable thresholds, leaving only ambiguous or high-impact items for human attention. Make the auto-reviewer's decisions traceable, reversible, and visible in existing surfaces.

## What changes
- add an `auto_reviewer` rule engine in `opendream/observability.py` (or sibling module) that consumes review queue items + memory snapshots and emits `ReviewDecision` records with `actor="auto-reviewer:<rule_id>"`
- add per-rule operator-tunable thresholds in store config (`auto_reviewer.toml` under workspace `.opendream/`)
- add a CLI surface: `opendream review auto-run`, `opendream review auto-status`, `opendream review auto-config`
- run the auto-reviewer as part of the existing dream cycle and on demand
- expose a Settings → Automation tab in the frontend showing rule status, last-run stats, and threshold sliders
- annotate auto-resolved items with a "why auto" trail visible in `MemoryInspector` annotations
- preserve manual override: any decision the auto-reviewer made can be reverted from the Reviews UI; reverted items are not re-auto-resolved within a cooldown window

## Non-goals
- LLM-based review judgment (rules are deterministic; LLM-backed review is a separate proposal)
- silently deleting data (auto-suppress soft-deletes; restoration path preserved)
- auto-resolving `large_diff` reviews above an absolute size threshold without human signoff

## Success criteria
- ≥80% of queue items in a steady-state workspace are auto-resolved within 24h without human input
- 0 cases where auto-reviewer decisions cannot be reverted by an operator
- every auto-decision has an audit row linking rule_id, threshold values, item snapshot, and timestamp
- operators can disable any rule with a single config toggle
- frontend shows N items auto-resolved per session as positive feedback
