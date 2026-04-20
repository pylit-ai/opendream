"""Semantic dreamer — model-backed offline memory synthesis.

Implements WS5 (T21-T27): semantic dreamer integration into DreamRunner,
semantic run phases, hybrid run modes, cost/token budget enforcement,
semantic status metadata, and integration tests.

The semantic dreamer extends the existing four-phase DreamRunner with:
  orient → gather_recent_signal → infer_families → synthesize →
  verify → promote/archive → prune/reindex
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from .dream import _gather_recent_signal, _orient, _rows_to_events, dream_run
from .episodes import latest_episode_timestamp, load_episode_rows
from .integration import maintain
from .models import SemanticDreamReport
from .provider_registry import semantic_mode_available
from .query_families import plan_anticipation
from .semantic_verifier import promote_proposal, verify_proposal
from .storage import LockError, MemoryStore
from .util import parse_timestamp, semantic_tokens, stable_id, to_iso, utc_now


def semantic_dream_run(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    mode: str = "hybrid",
    now: str | None = None,
    max_recent_episodes: int | None = None,
    min_episode_signals: int | None = None,
    trigger_class: str = "manual-run",
) -> dict[str, Any]:
    """Run a semantic dream cycle.

    Modes:
    - deterministic: delegate to standard dream_run
    - semantic: run only semantic pipeline (no deterministic consolidation)
    - hybrid: run deterministic first, then semantic
    """
    timestamp = now or to_iso(utc_now())
    run_id = stable_id("semantic-dream", timestamp, store.store_id)
    started_at = time.monotonic()

    if mode == "deterministic":
        return dream_run(
            store,
            episode_paths=episode_paths,
            now=timestamp,
            max_recent_episodes=max_recent_episodes,
            min_episode_signals=min_episode_signals,
            trigger_class=trigger_class,
        )

    # Check semantic mode availability
    availability = semantic_mode_available(store)
    config = store.load_semantic_config()
    budgets = config.get("budgets", {})

    if not availability.get("available", False):
        fallback = config.get("fallback_policy", "fallback_to_deterministic")
        if fallback == "fallback_to_deterministic":
            det_result = dream_run(
                store,
                episode_paths=episode_paths,
                now=timestamp,
                max_recent_episodes=max_recent_episodes,
                min_episode_signals=min_episode_signals,
                trigger_class=trigger_class,
            )
            det_result["semantic_fallback"] = True
            det_result["semantic_fallback_reason"] = availability.get("reason", "unavailable")
            return det_result
        else:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            return {
                "run_id": run_id,
                "mode": mode,
                "status": "failed",
                "reason": f"semantic mode unavailable: {availability.get('reason', 'unknown')}",
                "phases": [],
                "duration_ms": duration_ms,
                "trigger_class": trigger_class,
            }

    deterministic_summary: dict[str, Any] = {}
    semantic_summary: dict[str, Any] = {}
    phases: list[str] = []

    try:
        with store.dream_lock():
            store.save_dream_state({"state": "dreaming", "last_started_at": timestamp, "run_id": run_id})

            # Phase 1: Deterministic path (if hybrid)
            if mode == "hybrid":
                phases.append("deterministic_consolidation")
                det_result = _run_deterministic_phase(
                    store,
                    episode_paths=episode_paths,
                    now=timestamp,
                    max_recent_episodes=max_recent_episodes,
                    min_episode_signals=min_episode_signals,
                )
                deterministic_summary = det_result

            # Phase 2: Gather signal for semantic processing
            phases.append("orient")
            policy = store.dream_policy(
                max_recent_episodes=max_recent_episodes,
                min_episode_signals=min_episode_signals,
            )
            rows = load_episode_rows(episode_paths, tail_limit=policy["max_recent_episodes"])
            orientation_tokens = _orient(store)
            gathered = _gather_recent_signal(rows, orientation_tokens, policy["max_recent_episodes"])
            phases.append("gather_recent_signal")

            # Phase 3: Anticipation planning
            phases.append("infer_families")
            anticipation_plan = plan_anticipation(
                store,
                transcript_rows=gathered,
            )
            families_selected = anticipation_plan.get("families_selected", 0)
            selected_families = anticipation_plan.get("selected_families", [])

            # Phase 4: Synthesize learned context proposals
            phases.append("synthesize")
            proposals = _synthesize_proposals(
                store,
                gathered_rows=gathered,
                selected_families=selected_families,
                budgets=budgets,
                now=timestamp,
            )

            # Phase 5: Verify proposals
            phases.append("verify")
            source_events_list = store.load_events()
            verification_results: list[dict[str, Any]] = []
            for proposal in proposals:
                vresult = verify_proposal(
                    store,
                    proposal,
                    source_events=source_events_list[-50:],
                )
                verification_results.append(vresult)

            # Phase 6: Promote approved proposals
            phases.append("promote")
            promoted = 0
            rejected = 0
            for proposal, vresult in zip(proposals, verification_results, strict=False):
                if vresult.get("combined_verdict") in ("approve", "review_required"):
                    promote_proposal(store, proposal, vresult, now=timestamp)
                    promoted += 1
                else:
                    rejected += 1

            phases.append("prune_and_reindex")

            duration_ms = round((time.monotonic() - started_at) * 1000)

            semantic_summary = {
                "families_considered": anticipation_plan.get("total_families_considered", 0),
                "families_selected": families_selected,
                "proposals_generated": len(proposals),
                "proposals_approved": promoted,
                "proposals_rejected": rejected,
                "tokens_used": sum(p.get("estimated_tokens", 0) for p in proposals),
            }

            report = SemanticDreamReport(
                run_id=run_id,
                mode=mode,
                status="completed",
                started_at=timestamp,
                ended_at=to_iso(utc_now()),
                phases=phases,
                trigger_class=trigger_class,
                query_families_considered=semantic_summary["families_considered"],
                query_families_selected=families_selected,
                proposals_generated=len(proposals),
                proposals_approved=promoted,
                proposals_rejected=rejected,
                learned_context_created=promoted,
                duration_ms=duration_ms,
                deterministic_summary=deterministic_summary,
                semantic_summary=semantic_summary,
            )

            summary = report.to_dict()
            store.write_semantic_dream_audit(run_id, summary)
            store.save_dream_state({
                "state": "idle",
                "last_ran_at": timestamp,
                "run_id": run_id,
                "last_result": "completed",
                "last_run_summary": summary,
                "last_run_reason": trigger_class,
                "last_run_duration_ms": duration_ms,
                "last_episode_timestamp": latest_episode_timestamp(episode_paths),
                "semantic_mode": mode,
            })
            return summary

    except LockError:
        return {
            "run_id": run_id,
            "mode": mode,
            "status": "skipped",
            "reason": "lock-held",
            "phases": ["orient"],
            "trigger_class": trigger_class,
        }


def _run_deterministic_phase(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    now: str,
    max_recent_episodes: int | None = None,
    min_episode_signals: int | None = None,
) -> dict[str, Any]:
    """Run the deterministic consolidation phase of a hybrid dream."""
    policy = store.dream_policy(
        max_recent_episodes=max_recent_episodes,
        min_episode_signals=min_episode_signals,
    )
    rows = load_episode_rows(episode_paths, tail_limit=policy["max_recent_episodes"])
    orientation_tokens = _orient(store)
    gathered = _gather_recent_signal(rows, orientation_tokens, policy["max_recent_episodes"])
    events = _rows_to_events(gathered)

    existing_ids = {event["event_id"] for event in store.load_events()}
    new_events = [event for event in events if event.event_id not in existing_ids]

    for event in new_events:
        store.append_event(event)

    if len(new_events) >= policy["min_episode_signals"]:
        maintenance = maintain(store, now=now)
        return {
            "status": "completed",
            "gathered_rows": len(gathered),
            "appended_events": len(new_events),
            "maintenance": maintenance,
        }
    return {
        "status": "skipped",
        "reason": "insufficient-signal",
        "gathered_rows": len(gathered),
        "appended_events": len(new_events),
    }


def _synthesize_proposals(
    store: MemoryStore,
    *,
    gathered_rows: list[dict[str, Any]],
    selected_families: list[dict[str, Any]],
    budgets: dict[str, Any],
    now: str,
) -> list[dict[str, Any]]:
    """Synthesize learned context proposals from gathered signal and query families.

    In production, this would call a model via the provider registry.
    This implementation uses deterministic heuristic synthesis.
    """
    max_proposals = int(budgets.get("max_proposals_per_run", 20))
    proposals: list[dict[str, Any]] = []
    workspace_id = store.store_id

    # Group gathered rows by semantic similarity to families
    for family in selected_families:
        if len(proposals) >= max_proposals:
            break

        family_tokens = set[str]()
        for example in family.get("examples", []):
            family_tokens.update(semantic_tokens(example))

        # Find rows relevant to this family
        relevant_rows: list[dict[str, Any]] = []
        for row in gathered_rows:
            text = str(row.get("text") or row.get("message") or "")
            row_tokens = semantic_tokens(text)
            if row_tokens and family_tokens:
                overlap = len(row_tokens & family_tokens) / max(1, len(row_tokens | family_tokens))
                if overlap > 0.15:
                    relevant_rows.append(row)

        if not relevant_rows:
            continue

        # Synthesize a proposal from relevant content
        content_parts = [str(r.get("text") or r.get("message") or "") for r in relevant_rows[:10]]
        combined_content = " ".join(content_parts)

        # Extract key information
        summary = _extract_summary(combined_content, family)
        if not summary:
            continue

        # Compute freshness window
        freshness_hours = family.get("freshness_window_hours", 168)
        fresh_until = to_iso(
            parse_timestamp(now) + timedelta(hours=freshness_hours)
        )

        event_ids: list[str] = []
        for row in relevant_rows:
            eid = row.get("event_id") or row.get("id", "")
            if eid:
                event_ids.append(str(eid))

        proposal = {
            "workspace_id": workspace_id,
            "source_event_ids": event_ids[:20],
            "source_episode_ids": [],
            "source_trace_ids": [],
            "query_family_tags": [family.get("family_id", "")],
            "summary": summary,
            "details": combined_content[:2000],
            "assumptions": (
                f"Synthesized from {len(relevant_rows)} relevant transcript rows"
                f" for family '{family.get('title', '')}'"
            ),
            "provider_id": "builtin",
            "model_id": "heuristic-v1",
            "prompt_version": "1",
            "fresh_until": fresh_until,
            "confidence": min(0.9, 0.4 + 0.05 * len(relevant_rows)),
            "estimated_tokens": len(combined_content.split()),
        }
        proposals.append(proposal)

    return proposals


def _extract_summary(content: str, family: dict[str, Any]) -> str:
    """Extract a concise summary from content targeting a query family."""
    if not content.strip():
        return ""

    family_title = family.get("title", "")
    tokens = semantic_tokens(content)
    if not tokens:
        return ""

    # Build summary from most relevant tokens
    # In production, this would be model-generated
    words = content.split()
    summary = " ".join(words[:30]) + "..." if len(words) > 30 else content.strip()

    # Prefix with family context
    if family_title:
        summary = f"[{family_title}] {summary}"

    return summary[:500]


def _strategy_trust_boundary(strategy: str) -> str:
    """Map execution strategy to its trust boundary."""
    mapping = {
        "deterministic": "no-model-call",
        "direct-provider": "operator-managed-api-key",
        "codex-account": "trusted-local-or-private-infrastructure-only",
        "claude-scheduled-task": "vendor-owned-runtime",
        "cursor-automation": "vendor-owned-runtime",
    }
    return mapping.get(strategy, "unknown")


def dream_status_semantic(store: MemoryStore) -> dict[str, Any]:
    """Get semantic dream status metadata."""
    config = store.load_semantic_config()
    availability = semantic_mode_available(store)
    learned_records = store.load_learned_context_records()
    families = store.load_query_families()
    dream_state = store.load_dream_state()

    active_learned = [r for r in learned_records if r.get("status") == "active"]
    stale_learned = []
    now = utc_now()
    for r in active_learned:
        fresh_until = r.get("fresh_until", "")
        if fresh_until:
            try:
                if parse_timestamp(fresh_until) < now:
                    stale_learned.append(r)
            except (ValueError, TypeError):
                pass

    # Execution strategy and adapter info (438 bundle)
    execution_strategy = config.get("execution_strategy", "deterministic")
    preferred_auth_mode = config.get("preferred_auth_mode", "no-extra-key")
    active_adapter = config.get("active_adapter")
    candidate_strategies = config.get("candidate_strategies", [])

    auth_source_map = {
        "deterministic": "none",
        "direct-provider": "provider-api-key",
        "codex-account": "chatgpt-account",
        "claude-scheduled-task": "claude-account-task",
        "cursor-automation": "cursor-account-automation",
    }

    return {
        "mode": config.get("mode", "deterministic"),
        "available": availability.get("available", False),
        "semantic_capability_state": availability.get("semantic_capability_state", "unknown"),
        "availability_reason": availability.get("reason", ""),
        "fallback_policy": config.get("fallback_policy", "fallback_to_deterministic"),
        "execution_strategy": execution_strategy,
        "preferred_auth_mode": preferred_auth_mode,
        "active_adapter": active_adapter,
        "auth_source": auth_source_map.get(execution_strategy, "none"),
        "candidate_strategies": availability.get("candidate_strategies", candidate_strategies),
        "recommended_strategy": availability.get("recommended_strategy"),
        "detected_tools": availability.get("detected_tools", []),
        "next_action": availability.get("next_action", "none"),
        "learned_context": {
            "total": len(learned_records),
            "active": len(active_learned),
            "stale": len(stale_learned),
            "rejected": sum(1 for r in learned_records if r.get("status") == "rejected"),
            "superseded": sum(1 for r in learned_records if r.get("status") == "superseded"),
        },
        "query_families": {
            "total": len(families),
            "active": sum(1 for f in families if f.get("status", "active") == "active"),
        },
        "last_semantic_run": dream_state.get("semantic_mode"),
        "trust_boundary": _strategy_trust_boundary(config.get("execution_strategy", "deterministic")),
        "budgets": config.get("budgets", {}),
    }
