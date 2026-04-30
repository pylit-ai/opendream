# Tasks

## P0 — rule engine + config
- [ ] add `opendream/auto_reviewer.py` with `Rule` protocol, `RuleContext`, and `apply_rules(...)` driver
- [ ] implement `low_confidence_age` rule with unit tests on threshold edges
- [ ] implement `contested_dominant` rule with unit tests on delta + age edges
- [ ] implement `stale_diff` rule with unit tests
- [ ] implement `unused_retrieval` rule with unit tests
- [ ] add `AutoReviewerConfig` schema, default TOML, loader with fallbacks
- [ ] add `opendream review auto-run [--dry-run]` CLI command
- [ ] add `opendream review auto-status` CLI command
- [ ] add `opendream review auto-config` CLI command
- [ ] wire `auto-run` into dream cycle gated on `auto_reviewer.enabled`

## P0 — audit + reversibility
- [ ] each auto-decision writes `ReviewDecision(actor="auto-reviewer:<rule_id>")` with structured rationale carrying active thresholds
- [ ] each auto-decision writes a paired `Annotation` on the affected object so trails appear in MemoryInspector
- [ ] add cooldown set keyed by `(item_id, rule_id)` with `cooldown_hours` default 168
- [ ] revert path: operator decision on auto-resolved item populates cooldown and emits `actor=operator` decision

## P0 — verification
- [ ] integration test: seeded queue + dream cycle produces expected per-rule counts
- [ ] invariant test: every `auto-reviewer:*` decision has matching annotation + cooldown row
- [ ] reversibility test: reverted item not re-auto-resolved within cooldown window
- [ ] dry-run mode produces identical proposals without mutating store

## P1 — frontend surfaces
- [ ] add `/api/auto-reviewer/stats` endpoint exposing last-run counts + per-rule status
- [ ] add `Settings → Automation` tab with per-rule toggle + threshold inputs + "Run now (dry-run)" button
- [ ] update Reviews empty state to show "N items auto-resolved this session"
- [ ] add cooldown chip in Reviews row for items in cooldown

## P1 — docs + telemetry
- [ ] update `docs/architecture/overview.md` with auto-reviewer section
- [ ] update `docs/automation/dream-task-playbook.md` with auto-reviewer hook in dream cycle
- [ ] emit per-rule counters for 30 days post-rollout
- [ ] document `opendream review auto-config --disable-all` rollback path

## P2 — defaults tuning
- [ ] after 30-day soak, revisit threshold defaults based on dogfood telemetry
- [ ] consider enabling `contested_dominant` and `stale_diff` by default if false-positive rate < 5%
