# Execution plan

## Phase 1 — rule engine core
1. Add `opendream/auto_reviewer.py` with a `Rule` protocol, `RuleContext` (memory + queue item + workspace stats), and an `apply_rules(...)` driver that returns a list of proposed decisions.
2. Implement four bundled rules:
   - `low_confidence_age` — suppress `low_confidence_memory` when `confidence < cfg.low_confidence_threshold` AND `age_hours > cfg.low_confidence_min_age_hours`
   - `contested_dominant` — approve newer side of a `contested_memory` pair when `confidence_delta > cfg.contested_min_delta` AND `age_hours > cfg.contested_min_age_hours`
   - `stale_diff` — mark `large_diff` reviews stale after `cfg.large_diff_max_age_hours` with no operator action
   - `unused_retrieval` — suppress `suspicious_retrieval` when no downstream context assembly references it within `cfg.retrieval_grace_hours`
3. Each rule emits a `RuleProposal { rule_id, action, confidence, rationale, snapshot }` rather than directly mutating store; driver applies decisions atomically with the existing `create_review_decision` path.

## Phase 2 — config + CLI
4. Add `AutoReviewerConfig` schema with default thresholds; load from `<workspace>/.opendream/auto_reviewer.toml` with sensible fallbacks; ship a documented default file.
5. Add CLI subcommands:
   - `opendream review auto-run [--dry-run]` — execute one pass, print summary, exit non-zero on rule errors
   - `opendream review auto-status` — print last run stats, per-rule counts, disabled rules
   - `opendream review auto-config [--show | --set rule.threshold=value]`
6. Wire `auto-run` into the existing dream cycle as a post-dream step gated by `auto_reviewer.enabled` (default `true` for `low_confidence_age` and `unused_retrieval`; `false` for the others until operator opts in).

## Phase 3 — audit trail + reversibility
7. Each auto-decision creates a `ReviewDecision` with `actor="auto-reviewer:<rule_id>"` and a structured rationale containing the threshold values that were active at decision time.
8. The auto-reviewer creates a corresponding `Annotation` on the affected memory (or run) so the trail surfaces in `MemoryInspector` without UI changes.
9. Cooldown table: store a `(item_id, rule_id, reverted_at)` set so reverted decisions are not re-triggered within `cfg.cooldown_hours` (default 168h).

## Phase 4 — frontend surfaces
10. Add `Settings → Automation` tab showing per-rule toggle, threshold inputs, last-run summary, and a "Run now (dry-run)" button.
11. Update Reviews empty-state to show "N items auto-resolved this session" pulled from a new `/api/auto-reviewer/stats` endpoint.
12. Add a chip in the Reviews row when an item came from an auto-reviewer cooldown ("recently reverted, won't auto-resolve until X").

## Rollout
- ship Phase 1+2 with all rules disabled by default; enable `low_confidence_age` only after a soak period in dogfooding
- emit telemetry counts per rule for the first 30 days
- document rollback: `opendream review auto-config --disable-all` reverts the system to manual-only mode

## Verification
- unit tests per rule with fixture queue items spanning threshold edges
- integration test: dream cycle with seeded queue produces expected decisions and annotations
- audit invariant test: every `actor=auto-reviewer:*` decision has matching annotation + cooldown entry
- reversibility test: revert UI produces a `ReviewDecision` with `actor=operator` and prevents re-auto-resolution within cooldown
