"""Deterministic auto-reviewer for the observability review queue.

Spec: 445-auto-reviewer.

The auto-reviewer consumes review queue items + memory snapshots and emits
review decisions for items that satisfy operator-tunable thresholds. Items
that do not match any rule remain in the queue for human attention.

Public surface:
    AutoReviewerConfig    - operator-tunable thresholds + per-rule toggles
    Rule                  - protocol implemented by individual rules
    RuleProposal          - structured output of a rule
    apply_rules(...)      - driver that produces decisions for a queue snapshot
    run_auto_reviewer(...) - convenience wrapper that loads + applies + persists

Decisions are persisted via observability.create_review_decision; auto-decisions
carry actor="auto-reviewer:<rule_id>" so the trail is auditable and reversible.

Cooldown rules are tracked in <workspace>/.opendream/auto_reviewer_cooldown.json
so reverted items are not re-auto-resolved within `cooldown_hours`.

Status: P0 module skeleton with one bundled rule (low_confidence_age) and
verification fixtures. Additional rules (contested_dominant, stale_diff,
unused_retrieval) follow in the same module per plan.md.
"""
from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, Protocol

from .storage import MemoryStore
from .util import parse_timestamp, to_iso, utc_now

COOLDOWN_FILE_NAME = "auto_reviewer_cooldown.json"


@dataclass(frozen=True)
class _RuleView:
    """Per-rule view used by stats / config update endpoints."""

    enabled: bool
    thresholds: dict[str, Any]


# Public alias used by CLI tests + frontend-facing types
RuleConfig = _RuleView


@dataclass(frozen=True)
class AutoReviewerConfig:
    """Operator-tunable thresholds. Fallbacks documented in spec 445."""

    enabled: bool = True
    run_in_dream_cycle: bool = True
    cooldown_hours: int = 168
    # low_confidence_age rule
    # Threshold matches the queue trigger ceiling in _build_review_queue
    # (< 0.65). The queue itself only emits items below that threshold, so
    # the rule will only see already-flagged candidates. Default age window
    # is 0 — the queue's own filter is the gate; operators can tighten via
    # auto-config if they want only aged items auto-resolved.
    low_confidence_age_enabled: bool = True
    low_confidence_threshold: float = 0.65
    low_confidence_min_age_hours: int = 0
    # contested_dominant rule
    contested_dominant_enabled: bool = False
    contested_min_delta: float = 0.25
    contested_min_age_hours: int = 12
    # stale_diff rule
    stale_diff_enabled: bool = False
    large_diff_max_age_hours: int = 168
    # unused_retrieval rule
    unused_retrieval_enabled: bool = False
    retrieval_grace_hours: int = 48
    # fallback_mark_stale rule (off by default; preview force-enables for operator scan)
    fallback_mark_stale_enabled: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AutoReviewerConfig:
        kwargs: dict[str, Any] = {}
        for f in cls.__dataclass_fields__:
            if f in payload:
                kwargs[f] = payload[f]
        return cls(**kwargs)

    _RULE_FIELDS: ClassVar[dict[str, tuple[str, tuple[str, ...]]]] = {
        "low_confidence_age": (
            "low_confidence_age_enabled",
            ("low_confidence_threshold", "low_confidence_min_age_hours"),
        ),
        "contested_dominant": (
            "contested_dominant_enabled",
            ("contested_min_delta", "contested_min_age_hours"),
        ),
        "stale_diff": (
            "stale_diff_enabled",
            ("large_diff_max_age_hours",),
        ),
        "unused_retrieval": (
            "unused_retrieval_enabled",
            ("retrieval_grace_hours",),
        ),
        "fallback_mark_stale": (
            "fallback_mark_stale_enabled",
            (),
        ),
    }

    def rule(self, rule_id: str) -> _RuleView | None:
        spec = self._RULE_FIELDS.get(rule_id)
        if spec is None:
            return None
        enabled_field, threshold_fields = spec
        return _RuleView(
            enabled=getattr(self, enabled_field),
            thresholds={name: getattr(self, name) for name in threshold_fields},
        )


@dataclass
class RuleContext:
    config: AutoReviewerConfig
    queue_item: dict[str, Any]
    memories_by_id: dict[str, dict[str, Any]]
    runs_by_id: dict[str, dict[str, Any]]
    retrievals_by_id: dict[str, dict[str, Any]]
    contexts: list[dict[str, Any]]
    now: datetime


@dataclass
class RuleProposal:
    rule_id: str
    action: str  # one of approve | suppress | mark_stale
    rationale: str
    snapshot: dict[str, Any] = field(default_factory=dict)


class Rule(Protocol):
    rule_id: str
    description: str

    def applies(self, ctx: RuleContext) -> bool: ...

    def propose(self, ctx: RuleContext) -> RuleProposal: ...


def _hours_since(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    try:
        dt = parse_timestamp(iso)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    return delta.total_seconds() / 3600.0


class LowConfidenceAgeRule:
    """Suppress low_confidence_memory items that have aged past threshold."""

    rule_id = "low_confidence_age"
    description = "Suppress low-confidence durable memory after it ages past the threshold."

    def applies(self, ctx: RuleContext) -> bool:
        if not ctx.config.low_confidence_age_enabled:
            return False
        if ctx.queue_item.get("queue_item_type") != "low_confidence_memory":
            return False
        memory = ctx.memories_by_id.get(str(ctx.queue_item.get("object_id")))
        if memory is None:
            return False
        try:
            confidence = float(memory.get("confidence", 1.0))
        except (TypeError, ValueError):
            return False
        if confidence >= ctx.config.low_confidence_threshold:
            return False
        age = _hours_since(memory.get("created_at") or memory.get("updated_at"), ctx.now)
        return not (age is None or age < ctx.config.low_confidence_min_age_hours)

    def propose(self, ctx: RuleContext) -> RuleProposal:
        memory = ctx.memories_by_id[str(ctx.queue_item["object_id"])]
        confidence = float(memory.get("confidence", 0.0))
        age_hours = _hours_since(memory.get("created_at") or memory.get("updated_at"), ctx.now) or 0.0
        return RuleProposal(
            rule_id=self.rule_id,
            action="suppress",
            rationale=(
                f"confidence={confidence:.3f} below {ctx.config.low_confidence_threshold:.3f}; "
                f"age={age_hours:.1f}h ≥ min_age={ctx.config.low_confidence_min_age_hours}h"
            ),
            snapshot={
                "confidence": confidence,
                "age_hours": age_hours,
                "thresholds": {
                    "low_confidence_threshold": ctx.config.low_confidence_threshold,
                    "low_confidence_min_age_hours": ctx.config.low_confidence_min_age_hours,
                },
            },
        )


class ContestedDominantRule:
    """Approve the dominant side of a contested_memory pair when delta is large enough."""

    rule_id = "contested_dominant"
    description = "Approve the dominant side of a contested memory pair when the confidence gap is wide."

    def applies(self, ctx: RuleContext) -> bool:
        try:
            if not ctx.config.contested_dominant_enabled:
                return False
            if ctx.queue_item.get("queue_item_type") != "contested_memory":
                return False
            memory = ctx.memories_by_id.get(str(ctx.queue_item.get("object_id")))
            if memory is None:
                return False
            # requires a link to the opposing memory
            linked_id = str(
                memory.get("superseded_by") or memory.get("conflicts_with") or ""
            )
            if not linked_id or linked_id not in ctx.memories_by_id:
                return False
            other = ctx.memories_by_id[linked_id]
            try:
                conf_self = float(memory.get("confidence", 0.0))
                conf_other = float(other.get("confidence", 0.0))
            except (TypeError, ValueError):
                return False
            winner_conf = max(conf_self, conf_other)
            loser_conf = min(conf_self, conf_other)
            delta = winner_conf - loser_conf
            if delta <= ctx.config.contested_min_delta:
                return False
            # subject must be the winner
            if conf_self < conf_other:
                return False
            contest_ts = memory.get("contested_at") or memory.get("updated_at") or memory.get("created_at")
            age = _hours_since(contest_ts, ctx.now)
            return not (age is None or age < ctx.config.contested_min_age_hours)
        except Exception:
            return False

    def propose(self, ctx: RuleContext) -> RuleProposal:
        memory = ctx.memories_by_id[str(ctx.queue_item["object_id"])]
        linked_id = str(memory.get("superseded_by") or memory.get("conflicts_with") or "")
        other = ctx.memories_by_id[linked_id]
        conf_self = float(memory.get("confidence", 0.0))
        conf_other = float(other.get("confidence", 0.0))
        delta = conf_self - conf_other
        contest_ts = memory.get("contested_at") or memory.get("updated_at") or memory.get("created_at")
        age_hours = _hours_since(contest_ts, ctx.now) or 0.0
        return RuleProposal(
            rule_id=self.rule_id,
            action="approve",
            rationale=(
                f"subject confidence={conf_self:.3f} vs opponent={conf_other:.3f}; "
                f"delta={delta:.3f} > {ctx.config.contested_min_delta:.3f}; "
                f"age={age_hours:.1f}h ≥ {ctx.config.contested_min_age_hours}h"
            ),
            snapshot={
                "subject_confidence": conf_self,
                "opponent_confidence": conf_other,
                "delta": delta,
                "age_hours": age_hours,
                "thresholds": {
                    "contested_min_delta": ctx.config.contested_min_delta,
                    "contested_min_age_hours": ctx.config.contested_min_age_hours,
                },
            },
        )


class StaleDiffRule:
    """Mark large_diff or failed_run items stale when run age exceeds threshold."""

    rule_id = "stale_diff"
    description = "Mark large-diff or failed-run review items stale after the configured age."

    def applies(self, ctx: RuleContext) -> bool:
        try:
            if not ctx.config.stale_diff_enabled:
                return False
            if ctx.queue_item.get("queue_item_type") not in ("large_diff", "failed_run"):
                return False
            run = ctx.runs_by_id.get(str(ctx.queue_item.get("object_id")))
            if run is None:
                return False
            run_ts = run.get("started_at") or run.get("created_at") or run.get("updated_at")
            age = _hours_since(run_ts, ctx.now)
            return not (age is None or age <= ctx.config.large_diff_max_age_hours)
        except Exception:
            return False

    def propose(self, ctx: RuleContext) -> RuleProposal:
        run = ctx.runs_by_id[str(ctx.queue_item["object_id"])]
        run_ts = run.get("started_at") or run.get("created_at") or run.get("updated_at")
        age_hours = _hours_since(run_ts, ctx.now) or 0.0
        return RuleProposal(
            rule_id=self.rule_id,
            action="mark_stale",
            rationale=(
                f"run age={age_hours:.1f}h > threshold={ctx.config.large_diff_max_age_hours}h"
            ),
            snapshot={
                "age_hours": age_hours,
                "threshold": ctx.config.large_diff_max_age_hours,
            },
        )


class UnusedRetrievalRule:
    """Suppress suspicious_retrieval items that have aged out and are unreferenced."""

    rule_id = "unused_retrieval"
    description = "Suppress suspicious retrievals never referenced by a context after the grace period."

    def applies(self, ctx: RuleContext) -> bool:
        try:
            if not ctx.config.unused_retrieval_enabled:
                return False
            if ctx.queue_item.get("queue_item_type") != "suspicious_retrieval":
                return False
            rid = str(ctx.queue_item.get("object_id") or "")
            retrieval = ctx.retrievals_by_id.get(rid)
            if retrieval is None:
                return False
            ret_ts = retrieval.get("retrieved_at") or retrieval.get("created_at") or retrieval.get("updated_at")
            age = _hours_since(ret_ts, ctx.now)
            if age is None or age <= ctx.config.retrieval_grace_hours:
                return False
            # conservative reference check across contexts
            ref_count = 0
            for c in ctx.contexts:
                if (
                    str(c.get("retrieval_id") or "") == rid
                    or str(c.get("source_retrieval_id") or "") == rid
                    or rid in str(c.get("assembled_text") or "")
                ):
                    ref_count += 1
            return not ref_count > 0
        except Exception:
            return False

    def propose(self, ctx: RuleContext) -> RuleProposal:
        rid = str(ctx.queue_item["object_id"])
        retrieval = ctx.retrievals_by_id[rid]
        ret_ts = retrieval.get("retrieved_at") or retrieval.get("created_at") or retrieval.get("updated_at")
        age_hours = _hours_since(ret_ts, ctx.now) or 0.0
        ref_count = sum(
            1
            for c in ctx.contexts
            if (
                str(c.get("retrieval_id") or "") == rid
                or str(c.get("source_retrieval_id") or "") == rid
                or rid in str(c.get("assembled_text") or "")
            )
        )
        return RuleProposal(
            rule_id=self.rule_id,
            action="suppress",
            rationale=(
                f"retrieval age={age_hours:.1f}h > grace={ctx.config.retrieval_grace_hours}h; "
                f"reference_count={ref_count}"
            ),
            snapshot={
                "age_hours": age_hours,
                "reference_count": ref_count,
                "threshold": ctx.config.retrieval_grace_hours,
            },
        )


class FallbackMarkStaleRule:
    """Catch-all: defer any queue item no specific rule matched.

    Recommends ``mark_stale`` so the operator can apply a deferring action
    in bulk. Off by default in real auto-runs (operator opts in via config),
    but the recommendation preview force-enables it so every queue row gets
    a suggestion the operator can accept or override.
    """

    rule_id = "fallback_mark_stale"
    description = (
        "Catch-all: defer items no specific rule matched. "
        "Recommends mark_stale so the queue does not grow unbounded. "
        "Operator can override per-row."
    )

    _ACTION_PRIORITY = ("mark_stale", "escalate", "attach_note", "suppress")

    def _pick_action(self, ctx: RuleContext) -> str | None:
        actions = ctx.queue_item.get("actions") or []
        for candidate in self._ACTION_PRIORITY:
            if candidate in actions:
                return candidate
        return None

    def applies(self, ctx: RuleContext) -> bool:
        if not ctx.config.fallback_mark_stale_enabled:
            return False
        item_type = str(ctx.queue_item.get("queue_item_type") or "")
        if item_type not in {
            "contested_memory",
            "low_confidence_memory",
            "large_diff",
            "failed_run",
            "suspicious_retrieval",
        }:
            return False
        return self._pick_action(ctx) is not None

    def propose(self, ctx: RuleContext) -> RuleProposal:
        action = self._pick_action(ctx) or "mark_stale"
        verb = {
            "mark_stale": "Defer (mark stale)",
            "escalate": "Escalate",
            "attach_note": "Attach note",
            "suppress": "Suppress",
        }.get(action, action)
        return RuleProposal(
            rule_id=self.rule_id,
            action=action,
            rationale=(
                f"{verb} — no specific rule matched. Keeps the queue bounded; "
                "reverse with approve / suppress if needed."
            ),
            snapshot={
                "queue_item_type": ctx.queue_item.get("queue_item_type"),
                "available_actions": list(ctx.queue_item.get("actions") or []),
                "chosen_action": action,
            },
        )


# Bundled rules. Order matters: specific rules first, fallback last.
DEFAULT_RULES: tuple[Rule, ...] = (
    LowConfidenceAgeRule(),
    ContestedDominantRule(),
    StaleDiffRule(),
    UnusedRetrievalRule(),
    FallbackMarkStaleRule(),
)


def load_cooldown(store: MemoryStore) -> dict[str, str]:
    """Return mapping of `<rule_id>:<item_id>` -> ISO reverted_at."""
    path = _cooldown_path(store)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {str(k): str(v) for k, v in payload.items()}
        return {}
    except Exception:
        return {}


def save_cooldown(store: MemoryStore, data: dict[str, str]) -> None:
    path = _cooldown_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def record_revert(
    store: MemoryStore,
    *,
    rule_id: str,
    queue_item_id: str,
    now: datetime | None = None,
) -> None:
    cooldown = load_cooldown(store)
    cooldown[f"{rule_id}:{queue_item_id}"] = to_iso(now or utc_now())
    save_cooldown(store, cooldown)


def _cooldown_path(store: MemoryStore) -> Path:
    return store.memory_root / COOLDOWN_FILE_NAME


def in_cooldown(
    cooldown: dict[str, str],
    *,
    rule_id: str,
    queue_item_id: str,
    config: AutoReviewerConfig,
    now: datetime,
) -> bool:
    iso = cooldown.get(f"{rule_id}:{queue_item_id}")
    if not iso:
        return False
    try:
        dt = parse_timestamp(iso)
    except Exception:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return now - dt < timedelta(hours=config.cooldown_hours)


def force_all_enabled(cfg: AutoReviewerConfig | None = None) -> AutoReviewerConfig:
    """Return a copy of `cfg` with every rule + the global toggle enabled.

    Used by recommendation preview endpoints so rules that are off-by-default
    can still surface their suggestions for operator review.
    """
    base = cfg or AutoReviewerConfig()
    payload: dict[str, Any] = {}
    for f in AutoReviewerConfig.__dataclass_fields__:
        if f.startswith("_"):
            continue
        payload[f] = getattr(base, f)
    payload["enabled"] = True
    for _rule_id, (enabled_field, _thresholds) in AutoReviewerConfig._RULE_FIELDS.items():
        payload[enabled_field] = True
    return AutoReviewerConfig.from_dict(payload)


def preview_recommendations(
    store: MemoryStore,
    *,
    config: AutoReviewerConfig | None = None,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Run every rule against the current review queue without persisting.

    Returns:
        {
            "items": [{queue_item_id, rule_id, action, rationale, snapshot}],
            "by_action": {"approve": N, "suppress": N, ...},
            "by_rule": {<rule_id>: N, ...},
            "total_items": N,
            "total_recommended": N,
        }

    Cooldown is honored — items in cooldown for a rule do not get a
    recommendation from that rule.
    """
    from . import observability

    cfg = force_all_enabled(config)
    index = observability.load_or_build_index(store)
    entities = index.get("entities", {})
    queue = entities.get("reviews", [])
    proposals = apply_rules(
        queue=queue,
        memories=entities.get("memories", []),
        runs=entities.get("runs", []),
        retrievals=entities.get("retrievals", []),
        contexts=entities.get("contexts", []),
        config=cfg,
        cooldown=load_cooldown(store),
        now=now,
    )
    items: list[dict[str, Any]] = []
    by_action: dict[str, int] = {}
    by_rule: dict[str, int] = {}
    for queue_item, proposal in proposals:
        items.append(
            {
                "queue_item_id": str(queue_item.get("queue_item_id") or queue_item.get("id")),
                "queue_item_type": queue_item.get("queue_item_type"),
                "object_type": queue_item.get("object_type"),
                "object_id": queue_item.get("object_id"),
                "rule_id": proposal.rule_id,
                "action": proposal.action,
                "rationale": proposal.rationale,
                "snapshot": proposal.snapshot,
            }
        )
        by_action[proposal.action] = by_action.get(proposal.action, 0) + 1
        by_rule[proposal.rule_id] = by_rule.get(proposal.rule_id, 0) + 1
    return {
        "items": items,
        "by_action": by_action,
        "by_rule": by_rule,
        "total_items": len(queue),
        "total_recommended": len(items),
    }


def apply_recommendations(
    store: MemoryStore,
    *,
    config: AutoReviewerConfig | None = None,
    now: datetime | str | None = None,
    rule_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Apply every recommendation produced by ``preview_recommendations``.

    Persists ReviewDecisions + paired Annotations identical to a real
    auto-reviewer run, but with all rules enabled regardless of operator
    config. ``rule_ids`` optionally restricts to a subset of rules.
    """
    from . import observability

    cfg = force_all_enabled(config)
    if isinstance(now, str):
        try:
            now_dt = parse_timestamp(now)
        except Exception:
            now_dt = utc_now()
    else:
        now_dt = now or utc_now()
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=UTC)
    started_at = to_iso(now_dt)
    index = observability.load_or_build_index(store)
    entities = index.get("entities", {})
    rules = (
        tuple(r for r in DEFAULT_RULES if r.rule_id in set(rule_ids))
        if rule_ids is not None
        else DEFAULT_RULES
    )
    proposals = apply_rules(
        queue=entities.get("reviews", []),
        memories=entities.get("memories", []),
        runs=entities.get("runs", []),
        retrievals=entities.get("retrievals", []),
        contexts=entities.get("contexts", []),
        config=cfg,
        cooldown=load_cooldown(store),
        rules=rules,
        now=now_dt,
    )
    by_rule: dict[str, int] = {}
    decisions: list[dict[str, Any]] = []
    for item, proposal in proposals:
        rationale = (
            f"auto-reviewer:{proposal.rule_id} (operator-applied recommendation): "
            f"{proposal.rationale} snapshot={json.dumps(proposal.snapshot, sort_keys=True)}"
        )
        actor = f"auto-reviewer:{proposal.rule_id}"
        decision_now = to_iso(now_dt)
        try:
            decision = observability.create_review_decision(
                store,
                queue_item_type=str(item.get("queue_item_type", "review")),
                queue_item_id=str(item.get("queue_item_id") or item.get("id")),
                action=proposal.action,
                rationale=rationale,
                actor=actor,
                now=decision_now,
            )
            decisions.append(decision)
            by_rule[proposal.rule_id] = by_rule.get(proposal.rule_id, 0) + 1
            with contextlib.suppress(Exception):
                observability.create_annotation(
                    store,
                    object_type=str(item.get("object_type", "memory")),
                    object_id=str(item.get("object_id") or item.get("queue_item_id")),
                    actor=actor,
                    label="auto-resolved",
                    note=rationale,
                    now=decision_now,
                )
        except Exception:
            continue
    if decisions:
        observability.invalidate_index_cache(store)
    finished_at = to_iso(utc_now())
    return {
        "status": "applied",
        "started_at": started_at,
        "finished_at": finished_at,
        "applied_count": len(decisions),
        "proposed_count": len(proposals),
        "by_rule": by_rule,
        "decisions": decisions,
    }


def apply_rules(
    *,
    queue: Iterable[dict[str, Any]],
    memories: Iterable[dict[str, Any]],
    runs: Iterable[dict[str, Any]],
    retrievals: Iterable[dict[str, Any]],
    contexts: Iterable[dict[str, Any]] = (),
    config: AutoReviewerConfig | None = None,
    rules: Iterable[Rule] = DEFAULT_RULES,
    cooldown: dict[str, str] | None = None,
    now: datetime | str | None = None,
) -> list[tuple[dict[str, Any], RuleProposal]]:
    """Drive rules across queue snapshot. Returns (queue_item, proposal) pairs.

    Pure function: takes snapshots, returns decisions. Caller persists.
    """
    cfg = config or AutoReviewerConfig()
    if not cfg.enabled:
        return []
    if isinstance(now, str):
        try:
            cur = parse_timestamp(now)
        except Exception:
            cur = utc_now()
    else:
        cur = now or utc_now()
    if cur.tzinfo is None:
        cur = cur.replace(tzinfo=UTC)
    cooldown = cooldown or {}
    memories_by_id = {str(m.get("memory_id")): m for m in memories if m.get("memory_id")}
    runs_by_id = {str(r.get("run_id")): r for r in runs if r.get("run_id")}
    retrievals_by_id = {str(r.get("id")): r for r in retrievals if r.get("id")}
    contexts_list = list(contexts)
    proposals: list[tuple[dict[str, Any], RuleProposal]] = []
    for item in queue:
        for rule in rules:
            qid = str(item.get("queue_item_id") or item.get("id"))
            if in_cooldown(cooldown, rule_id=rule.rule_id, queue_item_id=qid, config=cfg, now=cur):
                continue
            ctx = RuleContext(
                config=cfg,
                queue_item=item,
                memories_by_id=memories_by_id,
                runs_by_id=runs_by_id,
                retrievals_by_id=retrievals_by_id,
                contexts=contexts_list,
                now=cur,
            )
            try:
                if rule.applies(ctx):
                    proposals.append((item, rule.propose(ctx)))
                    break  # one rule per item
            except Exception:
                # rule errors must never block the queue
                continue
    return proposals


def run_auto_reviewer(
    store: MemoryStore,
    *,
    config: AutoReviewerConfig | None = None,
    dry_run: bool = False,
    submit_decision: Callable[..., dict[str, Any]] | None = None,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Load queue snapshot from store, apply rules, persist decisions.

    Imports observability lazily to avoid a circular dependency.
    """
    from . import observability

    cfg = config or AutoReviewerConfig()
    if isinstance(now, str):
        try:
            now = parse_timestamp(now)
        except Exception:
            now = None
    started_at = to_iso(now) if now else to_iso(utc_now())
    index = observability.load_or_build_index(store)
    entities = index.get("entities", {})
    queue = entities.get("reviews", [])
    memories = entities.get("memories", [])
    runs = entities.get("runs", [])
    retrievals = entities.get("retrievals", [])
    contexts = entities.get("contexts", [])
    cooldown = load_cooldown(store)
    proposals = apply_rules(
        queue=queue,
        memories=memories,
        runs=runs,
        retrievals=retrievals,
        contexts=contexts,
        config=cfg,
        cooldown=cooldown,
        now=now,
    )
    by_rule: dict[str, int] = {}
    submitter = submit_decision or observability.create_review_decision
    decisions: list[dict[str, Any]] = []
    for item, proposal in proposals:
        by_rule[proposal.rule_id] = by_rule.get(proposal.rule_id, 0) + 1
        if dry_run:
            continue
        rationale = (
            f"auto-reviewer:{proposal.rule_id}: {proposal.rationale} "
            f"snapshot={json.dumps(proposal.snapshot, sort_keys=True)}"
        )
        actor = f"auto-reviewer:{proposal.rule_id}"
        decision_now = to_iso(now) if now else None
        decisions.append(
            submitter(
                store,
                queue_item_type=str(item.get("queue_item_type", "review")),
                queue_item_id=str(item.get("queue_item_id") or item.get("id")),
                action=proposal.action,
                rationale=rationale,
                actor=actor,
                now=decision_now,
            )
        )
        # Paired annotation makes the auto trail visible in MemoryInspector
        # without UI changes (spec 445 P0 audit invariant).
        with contextlib.suppress(Exception):
            observability.create_annotation(
                store,
                object_type=str(item.get("object_type", "memory")),
                object_id=str(item.get("object_id") or item.get("queue_item_id")),
                actor=actor,
                label="auto-resolved",
                note=rationale,
                now=decision_now,
            )
    if not dry_run and decisions:
        # rebuild on next read
        observability.invalidate_index_cache(store)
    finished_at = to_iso(now) if now else to_iso(utc_now())
    last_run_record = {
        "started_at": started_at,
        "finished_at": finished_at,
        "applied_count": 0 if dry_run else len(decisions),
        "proposed_count": len(proposals),
        "by_rule": by_rule,
        "dry_run": bool(dry_run),
    }
    with contextlib.suppress(Exception):
        _write_last_run(store, last_run_record)
    return {
        "status": "previewed" if dry_run else "applied",
        "dry_run": bool(dry_run),
        "proposed_count": len(proposals),
        "applied_count": last_run_record["applied_count"],
        "by_rule": by_rule,
        "decisions": decisions,
        "last_run": last_run_record,
    }


# ---------------------------------------------------------------------------
# Config TOML I/O + last_run helpers (spec 445 Phase 2/3)
# ---------------------------------------------------------------------------

CONFIG_FILE_NAME = "auto_reviewer.toml"
LAST_RUN_FILE_NAME = "auto_reviewer_last_run.json"


def _config_path(store: MemoryStore) -> Path:
    base = store.memory_root / ".opendream"
    return base / CONFIG_FILE_NAME


def _last_run_path(store: MemoryStore) -> Path:
    return store.memory_root / LAST_RUN_FILE_NAME


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)


def load_config(store: MemoryStore) -> AutoReviewerConfig:
    path = _config_path(store)
    if not path.exists():
        return AutoReviewerConfig()
    try:
        try:
            import tomllib
        except ImportError:  # Python < 3.11
            tomllib = None  # type: ignore[assignment]
        if tomllib is not None:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        else:
            data = _parse_simple_toml(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return AutoReviewerConfig()
        return AutoReviewerConfig.from_dict(
            {k: v for k, v in data.items() if k in AutoReviewerConfig.__dataclass_fields__}
        )
    except Exception:
        return AutoReviewerConfig()


def _parse_simple_toml(text: str) -> dict[str, Any]:
    """Tiny TOML reader for the flat key=value format we emit. No tables."""
    out: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.lower() in ("true", "false"):
            out[key] = value.lower() == "true"
            continue
        try:
            if "." in value:
                out[key] = float(value)
            else:
                out[key] = int(value)
            continue
        except ValueError:
            pass
        if value.startswith('"') and value.endswith('"'):
            out[key] = value[1:-1]
        else:
            out[key] = value
    return out


def _render_toml(cfg: AutoReviewerConfig) -> str:
    lines: list[str] = ["# auto_reviewer.toml — managed by `opendream review auto-config`"]
    for f in cfg.__dataclass_fields__:
        if f.startswith("_"):
            continue
        value = getattr(cfg, f)
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = f'"{value}"'
        lines.append(f"{f} = {rendered}")
    return "\n".join(lines) + "\n"


def save_config(store: MemoryStore, cfg: AutoReviewerConfig) -> None:
    _atomic_write(_config_path(store), _render_toml(cfg))


def apply_config_update(store: MemoryStore, update: dict[str, Any]) -> AutoReviewerConfig:
    """Apply a frontend / CLI config update payload.

    Supported shape: {rule_id, enabled?, threshold_summary?: {field: value, ...}}
    or a flat dict of AutoReviewerConfig fields.
    """
    cfg = load_config(store)
    payload: dict[str, Any] = {}
    for f in cfg.__dataclass_fields__:
        if f.startswith("_"):
            continue
        payload[f] = getattr(cfg, f)
    rule_id = update.get("rule_id")
    if rule_id and rule_id in AutoReviewerConfig._RULE_FIELDS:
        enabled_field, threshold_fields = AutoReviewerConfig._RULE_FIELDS[rule_id]
        if "enabled" in update:
            payload[enabled_field] = bool(update["enabled"])
        thresholds = update.get("threshold_summary") or {}
        for name in threshold_fields:
            if name in thresholds:
                cur = payload.get(name)
                try:
                    payload[name] = type(cur)(thresholds[name]) if cur is not None else thresholds[name]
                except (TypeError, ValueError):
                    payload[name] = thresholds[name]
    else:
        # flat passthrough for top-level fields
        for k, v in update.items():
            if k in AutoReviewerConfig.__dataclass_fields__ and not k.startswith("_"):
                payload[k] = v
    new_cfg = AutoReviewerConfig.from_dict(payload)
    save_config(store, new_cfg)
    return new_cfg


def _write_last_run(store: MemoryStore, record: dict[str, Any]) -> None:
    _atomic_write(_last_run_path(store), json.dumps(record, indent=2, sort_keys=True))


def load_last_run(store: MemoryStore) -> dict[str, Any] | None:
    path = _last_run_path(store)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None
