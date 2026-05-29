"""Semantic dreamer - model-backed offline memory synthesis.

Implements WS5 (T21-T27): semantic dream runtime integration,
semantic run phases, hybrid run modes, cost/token budget enforcement,
semantic status metadata, and integration tests.

The semantic dreamer extends the existing four-phase dream runtime with:
  orient -> gather_recent_signal -> infer_families -> synthesize ->
  verify -> promote/archive -> prune/reindex
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from .dream import _gather_recent_signal, _orient, _rows_to_events, dream_run
from .dream_narrative import synthesize_dream_narrative
from .episodes import latest_episode_timestamp, load_episode_rows, row_text
from .integration import maintain
from .memory_quality import (
    LEARNING_EVIDENCE_MISSING_REASON,
    derive_semantic_product_state,
    next_action_for_semantic_state,
)
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
    before_snapshot = store.snapshot_store_text()

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
            signal_status = semantic_signal_status(
                store,
                episode_paths=episode_paths,
                limit=policy["max_recent_episodes"],
            )
            rows = _load_semantic_signal_rows(
                store,
                episode_paths=episode_paths,
                limit=policy["max_recent_episodes"],
            )
            orientation_tokens = _orient(store)
            gathered = _gather_recent_signal(rows, orientation_tokens, policy["max_recent_episodes"])
            phases.append("gather_recent_signal")
            trace: dict[str, Any] = {
                "signal": {
                    "source": signal_status["latest_signal_source"],
                    "latest_timestamp": signal_status["latest_signal_timestamp"],
                    "rows_scanned": signal_status["signal_row_count"],
                    "rows_gathered": len(gathered),
                    "row_limit": policy["max_recent_episodes"],
                },
                "planner": {},
                "synthesis": {
                    "family_results": [],
                    "fallback_reason": "",
                    "drop_reasons": [],
                },
                "verification": {
                    "verdict_counts": {},
                    "results": [],
                },
                "materialization": {
                    "promoted_record_ids": [],
                    "rejected_count": 0,
                    "retention_status": "not-run",
                    "no_materialization_reason": "",
                },
            }

            # Phase 3: Anticipation planning
            phases.append("infer_families")
            anticipation_plan = plan_anticipation(
                store,
                transcript_rows=gathered,
            )
            families_selected = anticipation_plan.get("families_selected", 0)
            selected_families = anticipation_plan.get("selected_families", [])
            trace["planner"] = {
                "families_considered": anticipation_plan.get("total_families_considered", 0),
                "families_selected": families_selected,
                "selected_family_ids": [
                    str(family.get("family_id") or "")
                    for family in selected_families
                    if isinstance(family, dict)
                ],
            }

            # Phase 4: Synthesize learned context proposals
            phases.append("synthesize")
            proposals = _synthesize_proposals(
                store,
                gathered_rows=gathered,
                selected_families=selected_families,
                budgets=budgets,
                now=timestamp,
                trace=trace["synthesis"],
            )
            trace["synthesis"]["proposal_count"] = len(proposals)
            trace["synthesis"]["proposal_ids"] = [
                str(proposal.get("proposal_id") or "")
                for proposal in proposals
                if proposal.get("proposal_id")
            ]

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
            trace["verification"] = _verification_trace(verification_results)

            # Phase 6: Promote approved proposals
            phases.append("promote")
            promoted = 0
            rejected = 0
            promoted_record_ids: list[str] = []
            for proposal, vresult in zip(proposals, verification_results, strict=False):
                if vresult.get("combined_verdict") in ("approve", "review_required"):
                    promotion = promote_proposal(store, proposal, vresult, now=timestamp)
                    if promotion.get("record_id"):
                        promoted_record_ids.append(str(promotion["record_id"]))
                    promoted += 1
                else:
                    rejected += 1
            no_materialization_reason = _no_materialization_reason(
                gathered_rows=gathered,
                proposals=proposals,
                verification_results=verification_results,
                synthesis_trace=trace["synthesis"],
            )
            trace["materialization"] = {
                "promoted_record_ids": promoted_record_ids,
                "created_count": promoted,
                "rejected_count": rejected,
                "retention_status": "active" if promoted else "no-new-records",
                "no_materialization_reason": no_materialization_reason,
            }

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
                promoted_record_ids=promoted_record_ids,
                duration_ms=duration_ms,
                deterministic_summary=deterministic_summary,
                semantic_summary=semantic_summary,
            )

            summary = report.to_dict()
            summary["latest_signal_source"] = signal_status["latest_signal_source"]
            summary["latest_signal_timestamp"] = signal_status["latest_signal_timestamp"]
            summary["signal_row_count"] = signal_status["signal_row_count"]
            summary["semantic_trace"] = trace
            summary["no_materialization_reason"] = no_materialization_reason
            summary["narrative"] = synthesize_dream_narrative(summary)
            summary["audit"] = store.write_semantic_dream_audit(
                run_id,
                summary,
                before_snapshot=before_snapshot,
                target_paths=[store.learned_context_path, store.dream_state_path],
            )
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
                "last_semantic_signal_timestamp": signal_status["latest_signal_timestamp"],
                "last_semantic_signal_source": signal_status["latest_signal_source"],
            })
            return summary

    except LockError:
            summary = {
                "run_id": run_id,
                "mode": mode,
                "status": "skipped",
                "reason": "lock-held",
                "phases": ["orient"],
                "trigger_class": trigger_class,
            }
            summary["narrative"] = synthesize_dream_narrative(summary)
            return summary


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
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Synthesize learned context proposals from gathered signal and query families.

    In production, this would call a model via the provider registry.
    This implementation uses deterministic heuristic synthesis.
    """
    max_proposals = int(budgets.get("max_proposals_per_run", 20))
    proposals: list[dict[str, Any]] = []
    workspace_id = store.store_id
    family_results: list[dict[str, Any]] = []
    drop_reasons: list[str] = []

    # Group gathered rows by semantic similarity to families
    for family in selected_families:
        if len(proposals) >= max_proposals:
            break

        family_tokens = set[str]()
        family_tokens.update(semantic_tokens(str(family.get("title", ""))))
        family_tokens.update(semantic_tokens(str(family.get("description", ""))))
        for example in family.get("examples", []):
            family_tokens.update(semantic_tokens(example))

        # Find rows relevant to this family
        relevant_rows: list[dict[str, Any]] = []
        best_overlap = 0.0
        for row in gathered_rows:
            text = row_text(row)
            row_tokens = semantic_tokens(text)
            if row_tokens and family_tokens:
                overlap = len(row_tokens & family_tokens) / max(1, len(row_tokens | family_tokens))
                best_overlap = max(best_overlap, overlap)
                if overlap >= 0.1:
                    relevant_rows.append(row)

        if not relevant_rows:
            family_results.append({
                "family_id": family.get("family_id", ""),
                "title": family.get("title", ""),
                "matched_rows": 0,
                "best_score": round(best_overlap, 3),
                "drop_reason": "no-row-family-token-overlap",
            })
            drop_reasons.append("no-row-family-token-overlap")
            continue

        # Synthesize a proposal from relevant content
        proposal = _proposal_from_rows(
            workspace_id,
            family=family,
            relevant_rows=relevant_rows,
            now=now,
        )
        if not proposal:
            family_results.append({
                "family_id": family.get("family_id", ""),
                "title": family.get("title", ""),
                "matched_rows": len(relevant_rows),
                "best_score": round(best_overlap, 3),
                "drop_reason": "empty-summary",
            })
            drop_reasons.append("empty-summary")
            continue

        duplicate = _equivalent_learned_context(store, proposal)
        if duplicate:
            family_results.append({
                "family_id": family.get("family_id", ""),
                "title": family.get("title", ""),
                "matched_rows": len(relevant_rows),
                "best_score": round(best_overlap, 3),
                "drop_reason": "equivalent-active-learned-context",
                "existing_record_id": duplicate,
            })
            drop_reasons.append("equivalent-active-learned-context")
            continue
        proposal["proposal_id"] = stable_id("proposal", now, proposal.get("summary", ""))
        proposals.append(proposal)
        family_results.append({
            "family_id": family.get("family_id", ""),
            "title": family.get("title", ""),
            "matched_rows": len(relevant_rows),
            "best_score": round(best_overlap, 3),
            "proposal_id": proposal["proposal_id"],
        })

    if not proposals and gathered_rows and len(proposals) < max_proposals:
        fallback_family = {
            "family_id": "recent-project-activity",
            "title": "Recent project activity",
            "description": "Bounded fallback when specific query-family matching yields no proposal",
            "freshness_window_hours": 168,
        }
        fallback_rows = gathered_rows[-min(len(gathered_rows), 8):]
        proposal = _proposal_from_rows(
            workspace_id,
            family=fallback_family,
            relevant_rows=fallback_rows,
            now=now,
        )
        if proposal:
            duplicate = _equivalent_learned_context(store, proposal)
            if duplicate:
                drop_reasons.append("equivalent-active-learned-context")
                family_results.append({
                    "family_id": fallback_family["family_id"],
                    "title": fallback_family["title"],
                    "matched_rows": len(fallback_rows),
                    "drop_reason": "equivalent-active-learned-context",
                    "existing_record_id": duplicate,
                })
            else:
                proposal["proposal_id"] = stable_id("proposal", now, proposal.get("summary", ""))
                proposals.append(proposal)
                family_results.append({
                    "family_id": fallback_family["family_id"],
                    "title": fallback_family["title"],
                    "matched_rows": len(fallback_rows),
                    "proposal_id": proposal["proposal_id"],
                    "fallback": True,
                })
                if trace is not None:
                    trace["fallback_reason"] = "no-family-proposal"
        elif trace is not None:
            trace["fallback_reason"] = "recent-project-activity-empty-summary"

    if trace is not None:
        trace["family_results"] = family_results
        trace["drop_reasons"] = sorted(set(drop_reasons))
    return proposals


def _proposal_from_rows(
    workspace_id: str,
    *,
    family: dict[str, Any],
    relevant_rows: list[dict[str, Any]],
    now: str,
) -> dict[str, Any] | None:
    content_parts = [row_text(r) for r in relevant_rows[:10]]
    combined_content = " ".join(part for part in content_parts if part.strip())
    summary = _extract_summary(combined_content, family)
    if not summary:
        return None
    freshness_hours = family.get("freshness_window_hours", 168)
    fresh_until = to_iso(parse_timestamp(now) + timedelta(hours=freshness_hours))
    event_ids: list[str] = []
    for row in relevant_rows:
        eid = row.get("event_id") or row.get("id", "")
        if eid:
            event_ids.append(str(eid))
    return {
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


def _equivalent_learned_context(store: MemoryStore, proposal: dict[str, Any]) -> str | None:
    proposal_tokens = semantic_tokens(f"{proposal.get('summary', '')} {proposal.get('details', '')}")
    proposal_sources = {str(item) for item in proposal.get("source_event_ids", [])}
    if not proposal_tokens:
        return None
    for record in store.load_learned_context_records():
        if record.get("status") != "active":
            continue
        record_tokens = semantic_tokens(f"{record.get('summary', '')} {record.get('details', '')}")
        if not record_tokens:
            continue
        overlap = len(proposal_tokens & record_tokens) / max(1, len(proposal_tokens | record_tokens))
        record_sources = {str(item) for item in record.get("source_event_ids", [])}
        if overlap >= 0.86 or (proposal_sources and proposal_sources == record_sources):
            return str(record.get("record_id") or "")
    return None


def _verification_trace(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    compact: list[dict[str, Any]] = []
    for result in results:
        verdict = str(result.get("combined_verdict") or "unknown")
        counts[verdict] = counts.get(verdict, 0) + 1
        compact.append({
            "run_id": result.get("run_id"),
            "verdict": verdict,
            "proposal_summary": result.get("proposal_summary", ""),
            "failed_checks": [
                finding.get("check")
                for verifier in result.get("verifier_results", [])
                if isinstance(verifier, dict)
                for finding in verifier.get("findings", [])
                if isinstance(finding, dict) and finding.get("status") == "fail"
            ],
        })
    return {"verdict_counts": counts, "results": compact}


def _no_materialization_reason(
    *,
    gathered_rows: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    verification_results: list[dict[str, Any]],
    synthesis_trace: dict[str, Any],
) -> str:
    if not gathered_rows:
        return "gather_recent_signal:no-signal-rows"
    if not proposals:
        fallback_reason = str(synthesis_trace.get("fallback_reason") or "")
        drops = synthesis_trace.get("drop_reasons") or []
        if fallback_reason:
            return f"synthesize:{fallback_reason}"
        if drops:
            return "synthesize:" + ",".join(str(item) for item in drops)
        return "synthesize:no-proposals"
    if verification_results and all(r.get("combined_verdict") == "reject" for r in verification_results):
        return "verify:all-proposals-rejected"
    return ""


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


def _load_semantic_signal_rows(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    limit: int,
) -> list[dict[str, Any]]:
    signal = semantic_signal_status(store, episode_paths=episode_paths, limit=limit)
    if signal["latest_signal_source"] == "transcript_episodes":
        rows = load_episode_rows(episode_paths, tail_limit=limit)
        if rows:
            return rows
    event_rows: list[dict[str, Any]] = []
    for event in store.load_events()[-limit:]:
        content = str(event.get("content") or "").strip()
        timestamp = str(event.get("timestamp") or "")
        if not content or not timestamp:
            continue
        event_rows.append(
            {
                "id": str(event.get("event_id") or ""),
                "event_id": str(event.get("event_id") or ""),
                "session_id": str(event.get("session_id") or ""),
                "timestamp": timestamp,
                "text": content,
                "message": content,
                "source_path": f"event:{event.get('event_id', '')}",
                "source_kind": "explicit_event",
            }
        )
    return event_rows


def resolve_semantic_work_mode(store: MemoryStore, requested_mode: str = "auto") -> str:
    requested = str(requested_mode or "auto")
    if requested in {"deterministic", "semantic", "hybrid"}:
        return requested
    configured = str(store.load_semantic_config().get("mode", "deterministic") or "deterministic")
    return configured if configured in {"deterministic", "semantic", "hybrid"} else "deterministic"


def semantic_signal_status(
    store: MemoryStore,
    *,
    episode_paths: list[Path] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    paths = episode_paths if episode_paths is not None else sorted(store.transcripts_dir.glob("*.jsonl"))
    tail_limit = int(limit or store.dream_policy()["max_recent_episodes"])
    latest_episode = latest_episode_timestamp(paths)
    events = store.load_events()
    latest_event = _latest_explicit_event_timestamp(events)
    latest_source = _select_latest_signal_source(latest_episode, latest_event)

    if latest_source == "transcript_episodes":
        signal_rows = load_episode_rows(paths, tail_limit=tail_limit)
        latest_timestamp = latest_episode
    elif latest_source == "explicit_events":
        signal_rows = events[-tail_limit:]
        latest_timestamp = latest_event
    else:
        signal_rows = []
        latest_timestamp = None

    return {
        "has_signal": bool(latest_timestamp),
        "latest_signal_source": latest_source,
        "latest_signal_timestamp": latest_timestamp,
        "signal_row_count": len(signal_rows),
    }


def semantic_dream_tick(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    now: str | None = None,
    mode: str = "semantic",
    max_recent_episodes: int | None = None,
    min_episode_signals: int | None = None,
    min_interval_seconds: int = 0,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    policy = store.dream_policy(
        max_recent_episodes=max_recent_episodes,
        min_episode_signals=min_episode_signals,
    )
    signal = semantic_signal_status(store, episode_paths=episode_paths, limit=policy["max_recent_episodes"])
    state = store.load_dream_state()
    last_ran_at = state.get("last_ran_at")
    if last_ran_at and min_interval_seconds > 0:
        elapsed = (parse_timestamp(timestamp) - parse_timestamp(str(last_ran_at))).total_seconds()
        if elapsed < min_interval_seconds:
            return {
                "status": "skipped",
                "reason": "min-interval",
                "mode": mode,
                "phases": ["orient"],
                "policy": policy,
                "trigger_class": "semantic-backlog",
                **signal,
            }

    if not signal["has_signal"]:
        return {
            "status": "skipped",
            "reason": "no-signal",
            "mode": mode,
            "phases": ["orient"],
            "policy": policy,
            "trigger_class": "semantic-backlog",
            **signal,
        }

    last_seen_signal = state.get("last_semantic_signal_timestamp")
    if last_seen_signal and (
        parse_timestamp(str(signal["latest_signal_timestamp"])) <= parse_timestamp(str(last_seen_signal))
    ):
        return {
            "status": "skipped",
            "reason": "no-backlog",
            "mode": mode,
            "phases": ["orient"],
            "policy": policy,
            "trigger_class": "semantic-backlog",
            **signal,
        }

    signal_episode_paths = (
        episode_paths
        if signal["latest_signal_source"] == "transcript_episodes"
        else []
    )
    result = semantic_dream_run(
        store,
        episode_paths=signal_episode_paths,
        mode=mode,
        now=timestamp,
        max_recent_episodes=max_recent_episodes,
        min_episode_signals=min_episode_signals,
        trigger_class="semantic-backlog",
    )
    result.setdefault("mode", mode)
    result.setdefault("latest_signal_source", signal["latest_signal_source"])
    result.setdefault("latest_signal_timestamp", signal["latest_signal_timestamp"])
    result.setdefault("signal_row_count", signal["signal_row_count"])
    if result.get("status") == "completed" and not result.get("semantic_fallback"):
        updated_state = {
            **store.load_dream_state(),
            "last_semantic_signal_timestamp": signal["latest_signal_timestamp"],
            "last_semantic_signal_source": signal["latest_signal_source"],
        }
        store.save_dream_state(updated_state)
    return result


def semantic_runtime_diagnosis(
    store: MemoryStore,
    *,
    now: str | None = None,
    requested_mode: str = "auto",
) -> dict[str, Any]:
    _ = now or to_iso(utc_now())
    work_mode = resolve_semantic_work_mode(store, requested_mode=requested_mode)
    availability = semantic_mode_available(store)
    semantic_status = dream_status_semantic(store)
    dream_state = store.load_dream_state()
    signal = semantic_signal_status(store, episode_paths=sorted(store.transcripts_dir.glob("*.jsonl")))
    last_seen_signal = dream_state.get("last_semantic_signal_timestamp")
    has_pending_signal = bool(signal["latest_signal_timestamp"]) and (
        not last_seen_signal
        or parse_timestamp(str(signal["latest_signal_timestamp"])) > parse_timestamp(str(last_seen_signal))
    )
    active_learned = int(semantic_status.get("learned_context", {}).get("active", 0) or 0)
    last_semantic_run = semantic_status.get("last_semantic_run")

    if work_mode == "deterministic":
        state = "deterministic_only"
        summary = "background runtime is operating in deterministic mode"
        reason = "semantic work mode is not currently selected"
    elif not availability.get("available", False):
        state = "blocked"
        reason = str(availability.get("reason") or "semantic path is not runnable")
        summary = f"semantic runtime is blocked: {reason}"
    elif active_learned > 0 and has_pending_signal:
        state = "materialized_with_pending_signal"
        reason = "learned context is active and newer signal is waiting to be processed"
        summary = "semantic runtime has materialized learned context and is waiting on newer signal"
    elif active_learned > 0:
        state = "materialized"
        reason = "learned context is active"
        summary = "semantic runtime has materialized learned context and is waiting for more signal"
    elif has_pending_signal:
        state = "awaiting_materialization"
        reason = "semantic signal is available but learned-context activity has not materialized yet"
        summary = "semantic runtime has runnable signal and is waiting to materialize learned context"
    elif last_semantic_run in {"semantic", "hybrid"}:
        state = "no_materialization"
        reason = "a semantic cycle ran but did not leave active learned-context records"
        summary = "semantic runtime consumed recent signal but did not materialize active learned context"
    else:
        state = "awaiting_signal"
        reason = "no transcript or explicit-event signal is available yet"
        summary = "semantic runtime is ready but waiting for transcript or explicit-event signal"

    return {
        "work_mode": work_mode,
        "state": state,
        "summary": summary,
        "reason": reason,
        "runnable": bool(availability.get("available", False)),
        "has_pending_signal": has_pending_signal,
        "latest_signal_source": signal["latest_signal_source"],
        "latest_signal_timestamp": signal["latest_signal_timestamp"],
        "signal_row_count": signal["signal_row_count"],
        "last_semantic_run": last_semantic_run,
        "active_learned_context": active_learned,
    }


def _latest_explicit_event_timestamp(events: list[dict[str, Any]]) -> str | None:
    latest: str | None = None
    for event in events:
        timestamp = str(event.get("timestamp") or "")
        if not timestamp:
            continue
        if latest is None or parse_timestamp(timestamp) > parse_timestamp(latest):
            latest = timestamp
    return latest


def _select_latest_signal_source(latest_episode: str | None, latest_event: str | None) -> str | None:
    if latest_episode and latest_event:
        return (
            "explicit_events"
            if parse_timestamp(latest_event) > parse_timestamp(latest_episode)
            else "transcript_episodes"
        )
    if latest_episode:
        return "transcript_episodes"
    if latest_event:
        return "explicit_events"
    return None


def _strategy_trust_boundary(strategy: str) -> str:
    """Map execution strategy to its trust boundary."""
    mapping = {
        "deterministic": "no-model-call",
        "direct-provider": "operator-managed-api-key",
        "codex-account": "trusted-local-or-controlled-infrastructure-only",
        "claude-scheduled-task": "vendor-owned-runtime",
        "cursor-automation": "vendor-owned-runtime",
    }
    return mapping.get(strategy, "unknown")


def _summary_int(summary: dict[str, Any], key: str) -> int:
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _learned_context_materialization_diagnostics(
    *,
    dream_state: dict[str, Any],
    learned_records: list[dict[str, Any]],
) -> dict[str, Any]:
    active_total = sum(1 for record in learned_records if record.get("status") == "active")
    archived_total = sum(1 for record in learned_records if record.get("status") == "archived")
    last_summary = dream_state.get("last_run_summary")
    if not isinstance(last_summary, dict):
        last_summary = {}
    last_mode = str(last_summary.get("mode") or dream_state.get("semantic_mode") or "")
    last_status = str(last_summary.get("status") or dream_state.get("last_result") or "")
    proposals_generated = _summary_int(last_summary, "proposals_generated")
    learned_context_created = _summary_int(last_summary, "learned_context_created")
    diagnostic: dict[str, Any] = {
        "state": "active" if active_total > 0 else "not_materialized",
        "active": active_total,
        "archived": archived_total,
        "total": len(learned_records),
        "last_run_id": last_summary.get("run_id") or dream_state.get("run_id"),
        "last_run_at": last_summary.get("ended_at") or dream_state.get("last_ran_at"),
        "last_run_status": last_status or None,
        "last_run_mode": last_mode or None,
        "last_proposals_generated": proposals_generated,
        "last_learned_context_created": learned_context_created,
    }
    semantic_completed = last_mode in {"semantic", "hybrid"} and last_status == "completed"
    if active_total > 0:
        diagnostic["reason"] = None
        diagnostic["next_action"] = "none"
    elif archived_total > 0:
        diagnostic["state"] = "all_archived"
        reason = f"learned context exists, but all {archived_total} record(s) are archived"
        if semantic_completed and proposals_generated == 0:
            reason = f"{reason}; latest semantic dream created 0 proposals"
        diagnostic["reason"] = reason
        diagnostic["next_action"] = (
            "adjust retention or restore relevant learned context, then run a semantic dream"
        )
    elif semantic_completed and proposals_generated == 0:
        diagnostic["state"] = "ran_no_proposals"
        diagnostic["reason"] = (
            "semantic cycles are running, but recent signal produced 0 learned-context proposals"
        )
        diagnostic["next_action"] = (
            "inspect semantic dream signal quality or query families, then run semantic dream again"
        )
    elif semantic_completed and proposals_generated > 0 and learned_context_created == 0:
        diagnostic["state"] = "proposals_not_promoted"
        diagnostic["reason"] = "semantic cycles are running, but proposals are not being promoted"
        diagnostic["next_action"] = "review semantic verifier output and promotion policy"
    else:
        diagnostic["reason"] = LEARNING_EVIDENCE_MISSING_REASON
        diagnostic["next_action"] = "run a semantic dream cycle so learned-context starts materializing"
    return diagnostic


def dream_status_semantic(store: MemoryStore) -> dict[str, Any]:
    """Get semantic dream status metadata."""
    config = store.load_semantic_config()
    availability = semantic_mode_available(store)
    learned_records = store.load_learned_context_records()
    families = store.load_query_families()
    dream_state = store.load_dream_state()

    active_learned = [r for r in learned_records if r.get("status") == "active"]
    archived_learned = [r for r in learned_records if r.get("status") == "archived"]
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
    stale_ids = {str(r.get("record_id") or "") for r in stale_learned}
    prompt_eligible = [
        r
        for r in active_learned
        if str(r.get("record_id") or "") not in stale_ids
        and r.get("verifier_status") in {"approved", "review_required"}
        and r.get("conflict_state", "none") == "none"
    ]

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
    capability_state, reason = derive_semantic_product_state(
        config,
        availability,
        active_learned_context_count=len(active_learned),
    )
    materialization = _learned_context_materialization_diagnostics(
        dream_state=dream_state,
        learned_records=learned_records,
    )
    next_action = next_action_for_semantic_state(capability_state, reason, availability)
    if (
        capability_state == "degraded"
        and reason == LEARNING_EVIDENCE_MISSING_REASON
        and materialization.get("state") != "not_materialized"
    ):
        reason = str(materialization.get("reason") or reason)
        next_action = str(materialization.get("next_action") or next_action)

    return {
        "mode": config.get("mode", "deterministic"),
        "available": availability.get("available", False),
        "semantic_capability_state": capability_state,
        "availability_reason": reason,
        "fallback_policy": config.get("fallback_policy", "fallback_to_deterministic"),
        "execution_strategy": execution_strategy,
        "preferred_auth_mode": preferred_auth_mode,
        "active_adapter": active_adapter,
        "auth_source": auth_source_map.get(execution_strategy, "none"),
        "candidate_strategies": availability.get("candidate_strategies", candidate_strategies),
        "recommended_strategy": availability.get("recommended_strategy"),
        "detected_tools": availability.get("detected_tools", []),
        "next_action": next_action,
        "materialization": materialization,
        "learned_context": {
            "total": len(learned_records),
            "active": len(active_learned),
            "stale": len(stale_learned),
            "prompt_eligible": len(prompt_eligible),
            "stale_active": len(stale_learned),
            "archived": len(archived_learned),
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
