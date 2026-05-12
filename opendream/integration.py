from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from .automation import tick as automation_tick
from .consolidator import consolidate
from .extractor import extract_candidates, filter_by_salience
from .models import ContextAssembly, MemoryEvent, normalize_reporting_agent
from .retriever import retrieve
from .sessions import current_session_id
from .storage import STORE_KIND_PRECEDENCE, MemoryStore, store_sort_key
from .util import (
    CLI_JSON_VERSION,
    STOPWORDS,
    parse_timestamp,
    semantic_tokens,
    stable_id,
    summarize,
    to_iso,
    tokenize,
    utc_now,
)
from .validation import validate_document

GLOBAL_ROUTE_BLOCKED_SENSITIVITY = {"secret", "sensitive", "do_not_store"}
_STARTUP_PROFILE_TERMS = {"bootstrap", "context", "overview", "resume", "startup", "status"}
_TASK_PROFILE_TERMS = {
    "analysis",
    "analyze",
    "bug",
    "debug",
    "deep",
    "fix",
    "how",
    "implement",
    "investigate",
    "issue",
    "repair",
    "run",
    "task",
    "test",
    "troubleshoot",
    "update",
    "workflow",
}
_MAX_PERSISTED_LEARNED_CONTEXT_COMPARE_ITEMS = 12
_LEARNED_CONTEXT_ARCHIVE_GRACE_DAYS = 7
_LEARNED_CONTEXT_RESTORE_WINDOW_HOURS = 24
_LEARNED_CONTEXT_REASON_LABELS = {
    "selected_for_context": "Kept active in this context",
    "inactive_learned_context": "Already removed from active learned context",
    "verifier_not_ready": "Held out because verification is not ready",
    "startup_profile_keeps_learned_context_pointer_only": (
        "Suppressed in this context to keep startup output pointer-like"
    ),
    "weak_match_learned_context": "Suppressed in this context because the match was weak",
    "conflicted_learned_context": "Suppressed in this context because the record is conflicted",
    "stale_learned_context": "Suppressed in this context because the record is stale",
    "profile_budget_exceeded": "Suppressed in this context because the profile budget was exceeded",
}


def _timestamp_after(raw: str, cutoff: datetime) -> bool:
    try:
        return bool(parse_timestamp(raw) > cutoff)
    except (TypeError, ValueError):
        return False


def archive_stale_learned_context(
    store: MemoryStore,
    *,
    now: str | None = None,
    grace_days: int | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    retention = store.load_semantic_config().get("retention", {})
    if grace_days is None:
        configured = (
            retention.get("learned_context_archive_grace_days")
            if isinstance(retention, dict)
            else None
        )
        try:
            if configured is None:
                raise TypeError
            grace_days = int(configured)
        except (TypeError, ValueError):
            grace_days = _LEARNED_CONTEXT_ARCHIVE_GRACE_DAYS
    grace_days = max(0, grace_days)
    if isinstance(retention, dict):
        try:
            grace_contexts = int(retention.get("learned_context_archive_grace_contexts", 0))
        except (TypeError, ValueError):
            grace_contexts = 0
    else:
        grace_contexts = 0
    grace_contexts = max(0, grace_contexts)
    context_created_at = [
        str(row.get("created_at") or "")
        for row in store.load_context_assemblies()
        if row.get("created_at")
    ] if grace_contexts else []
    cutoff = parse_timestamp(timestamp) - timedelta(days=grace_days)
    records = store.load_learned_context_records()
    archived_ids: list[str] = []
    updated: list[dict[str, Any]] = []
    for record in records:
        next_record = dict(record)
        if record.get("status") == "active":
            fresh_until = record.get("fresh_until")
            try:
                expired_at = parse_timestamp(str(fresh_until)) if fresh_until else None
            except (TypeError, ValueError):
                expired_at = None
            if expired_at is not None and expired_at < cutoff:
                if grace_contexts:
                    active_contexts = sum(
                        1
                        for created_at in context_created_at
                        if _timestamp_after(created_at, expired_at)
                    )
                    if active_contexts < grace_contexts:
                        updated.append(next_record)
                        continue
                next_record["status"] = "archived"
                next_record["archived_at"] = timestamp
                next_record["archive_reason"] = "stale_after_grace"
                next_record["status_changed_at"] = timestamp
                next_record["restorable_until"] = to_iso(
                    parse_timestamp(timestamp) + timedelta(hours=_LEARNED_CONTEXT_RESTORE_WINDOW_HOURS)
                )
                archived_ids.append(str(record.get("record_id") or ""))
        updated.append(next_record)
    if archived_ids:
        store.save_learned_context_records(updated)
    return {
        "archived": len(archived_ids),
        "archived_record_ids": archived_ids,
        "grace_days": grace_days,
        "grace_contexts": grace_contexts,
    }


def _store_descriptor(store: MemoryStore) -> dict[str, Any]:
    return {
        "workspace": str(store.workspace),
        "store_id": store.store_id,
        "store_kind": store.store_kind,
    }


def _memory_key(record: dict[str, Any]) -> str:
    title = str(record.get("title", ""))
    _, _, suffix = title.partition(":")
    return suffix.strip().lower() or title.strip().lower()


def _content_tokens(query: str) -> set[str]:
    return tokenize(query) - STOPWORDS


def _context_profile(query: str, *, limit: int) -> dict[str, Any]:
    tokens = _content_tokens(query)
    semantic_query = semantic_tokens(query)
    startup_hint = bool(tokens & _STARTUP_PROFILE_TERMS or semantic_query & _STARTUP_PROFILE_TERMS)
    task_hint = bool(tokens & _TASK_PROFILE_TERMS or semantic_query & _TASK_PROFILE_TERMS)
    if limit >= 8:
        name = "deep_task"
        rationale = "higher limit requested, so prepare-context expands deeper task evidence"
        learned_context_budget = 2
        startup_budget = min(max(limit, 1), 8)
    elif startup_hint or (len(tokens) <= 2 and not task_hint):
        name = "startup"
        rationale = "query looks like startup orientation, so the output stays pointer-like"
        learned_context_budget = 0
        startup_budget = min(max(limit, 1), 4)
    else:
        name = "semantic_task"
        rationale = "query is task-shaped, so prepare-context includes bounded semantic expansion"
        learned_context_budget = 1
        startup_budget = min(max(limit, 1), 6)
    return {
        "name": name,
        "rationale": rationale,
        "learned_context_budget": learned_context_budget,
        "startup_budget": startup_budget,
        "pointer_like": name == "startup",
    }


def _score_learned_context(record: dict[str, Any], *, query: str, now: str) -> float:
    record_text = " ".join(
        str(record.get(field, ""))
        for field in ("summary", "details", "assumptions")
    )
    record_tokens = _content_tokens(record_text)
    query_tokens = _content_tokens(query)
    lexical_score = len(query_tokens & record_tokens) / max(1, len(query_tokens))
    semantic_score = len(semantic_tokens(query) & semantic_tokens(record_text)) / max(
        1,
        len(semantic_tokens(query) | semantic_tokens(record_text)),
    )
    score = lexical_score * 3 + semantic_score * 2 + float(record.get("confidence", 0.0))
    family_tags = {str(item).strip().lower() for item in record.get("query_family_tags", [])}
    if family_tags & semantic_tokens(query):
        score += 1.0
    fresh_until = str(record.get("fresh_until", "") or "")
    if fresh_until:
        try:
            if parse_timestamp(fresh_until) < parse_timestamp(now):
                score -= 0.3
        except (TypeError, ValueError):
            pass
    if record.get("conflict_state") in {"detected", "overridden"}:
        score -= 0.5
    return round(score, 4)


def _trim_learned_context_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("record_id"),
        "summary": record.get("summary"),
        "details": record.get("details", ""),
        "assumptions": record.get("assumptions", ""),
        "query_family_tags": record.get("query_family_tags", []),
        "fresh_until": record.get("fresh_until"),
        "confidence": record.get("confidence"),
        "verifier_status": record.get("verifier_status"),
        "conflict_state": record.get("conflict_state", "none"),
        "provider_id": record.get("provider_id"),
        "model_id": record.get("model_id"),
    }


def _learned_context_reason_label(reason_code: str) -> str:
    return _LEARNED_CONTEXT_REASON_LABELS.get(
        reason_code,
        reason_code.replace("_", " ").strip().capitalize() or "Learned-context change",
    )


def _learned_context_compare_item(
    record: dict[str, Any],
    *,
    change_class: str,
    reason_code: str,
    source_context_id: str,
    source_run_id: str,
    changed_at: str,
    after_state: str,
) -> dict[str, Any]:
    details_preview = summarize(str(record.get("details") or record.get("summary") or ""), 180)
    return {
        "record_id": str(record.get("record_id") or ""),
        "summary": str(record.get("summary") or ""),
        "details_preview": details_preview,
        "before_state": "active",
        "after_state": after_state,
        "change_class": change_class,
        "reason_code": reason_code,
        "reason_label": _learned_context_reason_label(reason_code),
        "changed_at": changed_at,
        "source_run_id": source_run_id or None,
        "source_context_id": source_context_id,
        "restore_allowed": False,
        "restorable_until": record.get("restorable_until"),
        "superseded_by": record.get("superseded_by"),
        "confidence": record.get("confidence"),
        "query_family_tags": list(record.get("query_family_tags") or []),
        "score": record.get("score"),
        "provenance_link_target": f"/context/{source_context_id}",
    }


def _representative_text_length(item: dict[str, Any], *, kind: str, pointer_like: bool = False) -> int:
    if kind == "durable":
        parts = [str(item.get("title", "")), str(item.get("summary", ""))]
        if not pointer_like:
            parts.append(str(item.get("body", "")))
    elif kind == "learned_context":
        parts = [str(item.get("summary", "")), str(item.get("details", "")), str(item.get("assumptions", ""))]
    else:
        parts = [str(item.get("title", "")), str(item.get("summary", ""))]
    return len(" ".join(parts).strip())


def emit_event(
    store: MemoryStore,
    *,
    kind: str,
    content: str,
    scope: str,
    channel: str,
    message_ref: str,
    file_refs: list[str] | None = None,
    tool_refs: list[str] | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
    tags: list[str] | None = None,
    confidence_hint: float | None = None,
    sensitivity: str = "normal",
    reporting_agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if store.store_kind == "global" and scope == "project":
        raise ValueError("project-scoped events must stay in the project store")
    if store.store_kind == "global" and sensitivity in GLOBAL_ROUTE_BLOCKED_SENSITIVITY:
        raise ValueError("sensitive events must not be routed to the global store")

    event_timestamp = timestamp or to_iso(utc_now())
    computed_session_id = (
        session_id
        or current_session_id()
        or stable_id("session", event_timestamp, store.store_kind, scope)
    )
    computed_turn_id = turn_id or stable_id("turn", event_timestamp, kind, message_ref)
    computed_event_id = event_id or stable_id("event", event_timestamp, kind, content, message_ref)
    source: dict[str, Any] = {"channel": channel, "message_ref": message_ref}
    if file_refs:
        source["file_refs"] = file_refs
    if tool_refs:
        source["tool_refs"] = tool_refs
    event = MemoryEvent(
        event_id=computed_event_id,
        session_id=computed_session_id,
        turn_id=computed_turn_id,
        timestamp=event_timestamp,
        scope=scope,
        kind=kind,
        source=source,
        content=content,
        reporting_agent=normalize_reporting_agent(reporting_agent),
        tags=tags or [],
        confidence_hint=confidence_hint,
        sensitivity=sensitivity,
    )
    payload = event.to_dict()
    validate_document("memory-event.schema.json", payload)
    before_snapshot = store.snapshot_store_text()
    path = store.append_event(event)
    audit = store.write_mutation_audit(
        action="emit-event",
        run_id=stable_id("emit", computed_event_id, event_timestamp),
        target_paths=[path],
        summary={"status": "appended", "event_id": computed_event_id, "kind": kind, "scope": scope},
        before_snapshot=before_snapshot,
    )
    return {
        "status": "appended",
        "workspace": str(store.workspace),
        "store_id": store.store_id,
        "store_kind": store.store_kind,
        "event_id": computed_event_id,
        "event_path": str(path.relative_to(store.workspace)),
        "memory_root": str(
            store.memory_root.relative_to(store.workspace)
            if store.memory_root.is_relative_to(store.workspace)
            else store.memory_root
        ),
        "audit": audit,
        "cli_output_version": CLI_JSON_VERSION,
    }


def maintain(
    store: MemoryStore,
    *,
    now: str | None = None,
    min_new_events: int | None = None,
    min_interval_seconds: int | None = None,
) -> dict[str, Any]:
    store.ensure_layout()
    timestamp = now or to_iso(utc_now())
    policy = store.scheduler_policy(
        min_new_events=min_new_events,
        min_interval_seconds=min_interval_seconds,
    )
    state = store.load_maintenance_state()
    last_run_at = state.get("last_run_at")
    if last_run_at and policy["min_interval_seconds"] > 0:
        elapsed = (parse_timestamp(timestamp) - parse_timestamp(last_run_at)).total_seconds()
        if elapsed < policy["min_interval_seconds"]:
            return {
                "status": "skipped",
                "reason": "min-interval",
                **_store_descriptor(store),
                "new_events": 0,
                "pending_candidates": len(store.load_pending_candidates()),
                "policy": policy,
                "cli_output_version": CLI_JSON_VERSION,
            }

    processed_ids = store.load_processed_event_ids()
    new_events = [event for event in store.load_events() if event["event_id"] not in processed_ids]
    pending_candidates = store.load_pending_candidates()
    learned_context_lifecycle = archive_stale_learned_context(store, now=timestamp)

    if (
        len(new_events) < policy["min_new_events"]
        and not pending_candidates
        and learned_context_lifecycle["archived"] == 0
    ):
        return {
            "status": "skipped",
            "reason": "no-work",
            **_store_descriptor(store),
            "new_events": len(new_events),
            "pending_candidates": 0,
            "learned_context_lifecycle": learned_context_lifecycle,
            "policy": policy,
            "cli_output_version": CLI_JSON_VERSION,
        }

    extract_run_id = stable_id("extract", timestamp, len(new_events), store.store_id)
    if new_events:
        existing_records = store.load_durable_records()
        candidates = extract_candidates(
            new_events, origin_mode="scheduled", now=timestamp, existing_records=existing_records,
        )
        min_salience = store.config.get("write_policy", {}).get("min_salience", {})
        if min_salience:
            candidates = filter_by_salience(candidates, min_salience)
        if candidates:
            store.append_candidates(candidates, extract_run_id)
        store.mark_events_processed(event["event_id"] for event in new_events)
    else:
        candidates = []

    consolidation = consolidate(store, now=timestamp)
    result = {
        "status": (
            "completed"
            if consolidation.get("status") != "skipped" or learned_context_lifecycle["archived"] > 0
            else "skipped"
        ),
        **_store_descriptor(store),
        "extract": {
            "run_id": extract_run_id,
            "processed_events": len(new_events),
            "created_candidates": len(candidates),
        },
        "consolidate": consolidation,
        "learned_context_lifecycle": learned_context_lifecycle,
        "policy": policy,
    }
    if result["status"] == "completed":
        store.save_maintenance_state(
            {
                "last_run_at": timestamp,
                "last_extract_run_id": extract_run_id,
                "last_consolidate_run_id": consolidation.get("run_id"),
            }
        )
    result["cli_output_version"] = CLI_JSON_VERSION
    return result


def maintain_stores(
    stores: Iterable[MemoryStore],
    *,
    now: str | None = None,
    min_new_events: int | None = None,
    min_interval_seconds: int | None = None,
) -> dict[str, Any]:
    ordered = sorted(stores, key=store_sort_key)
    results = [
        maintain(
            store,
            now=now,
            min_new_events=min_new_events,
            min_interval_seconds=min_interval_seconds,
        )
        for store in ordered
    ]
    return {
        "status": "completed" if any(item["status"] == "completed" for item in results) else "skipped",
        "store_count": len(results),
        "stores": results,
        "cli_output_version": CLI_JSON_VERSION,
    }


def status(
    store: MemoryStore,
    *,
    now: str | None = None,
    min_new_events: int | None = None,
    min_interval_seconds: int | None = None,
) -> dict[str, Any]:
    return store.status_snapshot(
        now=now,
        min_new_events=min_new_events,
        min_interval_seconds=min_interval_seconds,
    )


def status_stores(
    stores: Iterable[MemoryStore],
    *,
    now: str | None = None,
    min_new_events: int | None = None,
    min_interval_seconds: int | None = None,
) -> dict[str, Any]:
    ordered = sorted(stores, key=store_sort_key)
    snapshots = [
        status(
            store,
            now=now,
            min_new_events=min_new_events,
            min_interval_seconds=min_interval_seconds,
        )
        for store in ordered
    ]
    overall_state = "idle"
    if any(item["state"] == "locked" for item in snapshots):
        overall_state = "locked"
    elif any(item["state"] == "pending" for item in snapshots):
        overall_state = "pending"
    elif all(item["state"] == "uninitialized" for item in snapshots):
        overall_state = "uninitialized"
    return {
        "state": overall_state,
        "store_count": len(snapshots),
        "stores": snapshots,
        "cli_output_version": CLI_JSON_VERSION,
    }


def tick(
    store: MemoryStore,
    *,
    now: str | None = None,
    min_new_events: int | None = None,
    min_interval_seconds: int | None = None,
) -> dict[str, Any]:
    snapshot = status(
        store,
        now=now,
        min_new_events=min_new_events,
        min_interval_seconds=min_interval_seconds,
    )
    if not snapshot["initialized"]:
        return {
            "status": "skipped",
            "reason": "not-initialized",
            **_store_descriptor(store),
            "policy": snapshot["policy"],
            "automation": snapshot["automation"],
            "cli_output_version": CLI_JSON_VERSION,
        }
    memory_result = maintain(
        store,
        now=now,
        min_new_events=min_new_events,
        min_interval_seconds=min_interval_seconds,
    )
    automation_result = automation_tick(store, now=now)
    result = dict(memory_result)
    if memory_result["status"] != "completed" and automation_result["status"] == "completed":
        result["status"] = "completed"
        result["reason"] = "automation"
    result["automation"] = automation_result
    result["cli_output_version"] = CLI_JSON_VERSION
    return result


def tick_stores(
    stores: Iterable[MemoryStore],
    *,
    now: str | None = None,
    min_new_events: int | None = None,
    min_interval_seconds: int | None = None,
) -> dict[str, Any]:
    ordered = sorted(stores, key=store_sort_key)
    results = [
        tick(
            store,
            now=now,
            min_new_events=min_new_events,
            min_interval_seconds=min_interval_seconds,
        )
        for store in ordered
    ]
    return {
        "status": "completed" if any(item["status"] == "completed" for item in results) else "skipped",
        "store_count": len(results),
        "stores": results,
        "cli_output_version": CLI_JSON_VERSION,
    }


def prepare_context(
    stores: Iterable[MemoryStore] | MemoryStore,
    *,
    query: str,
    limit: int = 5,
    now: str | None = None,
    reporting_agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    store_list = [stores] if isinstance(stores, MemoryStore) else sorted(stores, key=store_sort_key)
    profile = _context_profile(query, limit=limit)
    merged_candidates: list[dict[str, Any]] = []
    startup_entries: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    learned_context_candidates: list[dict[str, Any]] = []
    learned_context_pool: list[dict[str, Any]] = []
    learned_context_compare_sources: dict[str, dict[str, Any]] = {}
    retrieval_run_ids: list[str] = []

    for store in store_list:
        if not store.is_initialized():
            continue
        retrieval = retrieve(
            store,
            query=query,
            limit=max(limit * 3, limit),
            now=timestamp,
            query_source="prepare_context",
            reporting_agent=reporting_agent,
        )
        retrieval_run_ids.append(str(retrieval.get("run_id", "")))
        records = {record["memory_id"]: record for record in store.load_durable_records()}
        for reason in retrieval["why"]:
            record = records.get(reason["memory_id"])
            if record is None:
                continue
            merged_candidates.append(
                {
                    "memory_id": record["memory_id"],
                    "title": record["title"],
                    "type": record["type"],
                    "summary": record["summary"],
                    "body": record["body"],
                    "score": reason["score"],
                    "reason": reason["reason"],
                    "store_id": store.store_id,
                    "store_kind": store.store_kind,
                    "workspace": str(store.workspace),
                }
            )
        for item in retrieval.get("excluded", []):
            excluded.append(
                {
                    "memory_id": item.get("memory_id"),
                    "reason": item.get("reason"),
                    "store_id": store.store_id,
                    "store_kind": store.store_kind,
                    "workspace": str(store.workspace),
                }
            )

        startup_index = store.load_startup_index()
        for entry in startup_index.get("entries", [])[: profile["startup_budget"]]:
            startup_entries.append(
                {
                    "memory_id": str(entry.get("memory_id") or ""),
                    "title": entry["title"],
                    "type": entry["type"],
                    "summary": entry["summary"],
                    "key": _memory_key(entry),
                    "store_kind": store.store_kind,
                    "workspace": str(store.workspace),
                }
            )
        for record in store.load_learned_context_records():
            if record.get("status") != "active":
                suppressed.append(
                    {
                        "kind": "learned_context",
                        "record_id": record.get("record_id"),
                        "reason": "inactive_learned_context",
                        "store_id": store.store_id,
                        "store_kind": store.store_kind,
                        "workspace": str(store.workspace),
                    }
                )
                continue
            compare_candidate = {
                **_trim_learned_context_record(record),
                "score": _score_learned_context(record, query=query, now=timestamp),
                "store_id": store.store_id,
                "store_kind": store.store_kind,
                "workspace": str(store.workspace),
            }
            learned_context_compare_sources[str(record.get("record_id") or "")] = compare_candidate
            if record.get("verifier_status") not in {"approved", "review_required"}:
                suppressed.append(
                    {
                        "kind": "learned_context",
                        "record_id": record.get("record_id"),
                        "reason": "verifier_not_ready",
                        "store_id": store.store_id,
                        "store_kind": store.store_kind,
                        "workspace": str(store.workspace),
                    }
                )
                continue
            candidate = compare_candidate
            learned_context_pool.append(candidate)
            if profile["name"] == "startup":
                suppressed.append(
                    {
                        "kind": "learned_context",
                        "record_id": record.get("record_id"),
                        "reason": "startup_profile_keeps_learned_context_pointer_only",
                        "store_id": store.store_id,
                        "store_kind": store.store_kind,
                        "workspace": str(store.workspace),
                    }
                )
                continue
            if float(candidate["score"]) <= 0:
                suppressed.append(
                    {
                        "kind": "learned_context",
                        "record_id": record.get("record_id"),
                        "reason": "weak_match_learned_context",
                        "store_id": store.store_id,
                        "store_kind": store.store_kind,
                        "workspace": str(store.workspace),
                    }
                )
                continue
            if record.get("conflict_state") in {"detected", "overridden"}:
                suppressed.append(
                    {
                        "kind": "learned_context",
                        "record_id": record.get("record_id"),
                        "reason": "conflicted_learned_context",
                        "store_id": store.store_id,
                        "store_kind": store.store_kind,
                        "workspace": str(store.workspace),
                    }
                )
                continue
            fresh_until = str(record.get("fresh_until", "") or "")
            if fresh_until:
                try:
                    if parse_timestamp(fresh_until) < parse_timestamp(timestamp):
                        suppressed.append(
                            {
                                "kind": "learned_context",
                                "record_id": record.get("record_id"),
                                "reason": "stale_learned_context",
                                "store_id": store.store_id,
                                "store_kind": store.store_kind,
                                "workspace": str(store.workspace),
                            }
                        )
                        continue
                except (TypeError, ValueError):
                    pass
            learned_context_candidates.append(candidate)

    merged_candidates.sort(
        key=lambda item: (
            STORE_KIND_PRECEDENCE.get(item["store_kind"], 99),
            -float(item["score"]),
            item["title"],
            item["workspace"],
        )
    )
    selected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for candidate in merged_candidates:
        key = _memory_key(candidate)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected.append(candidate)
        if len(selected) >= limit:
            break
    selected_ids = [item["memory_id"] for item in selected]
    selected_id_set = set(selected_ids)
    excluded_by_id = {
        str(item.get("memory_id") or ""): item
        for item in excluded
        if item.get("memory_id")
    }

    automation_candidates: list[dict[str, Any]] = []
    for store in store_list:
        if not store.is_initialized():
            continue
        for record in store.load_automation_records():
            if record.get("status") != "active":
                continue
            automation_candidates.append(
                {
                    "record_id": record["record_id"],
                    "job_id": record["job_id"],
                    "record_type": record["record_type"],
                    "title": record["title"],
                    "summary": record["summary"],
                    "priority": record["priority"],
                    "store_id": store.store_id,
                    "store_kind": store.store_kind,
                    "workspace": str(store.workspace),
                }
            )

    automation_candidates.sort(
        key=lambda item: (
            STORE_KIND_PRECEDENCE.get(item["store_kind"], 99),
            -float(item["priority"]),
            item["title"],
            item["workspace"],
        )
    )
    selected_automation = automation_candidates[:limit]
    for item in automation_candidates[limit:]:
        suppressed.append(
            {
                "kind": "automation_projection",
                "record_id": item["record_id"],
                "reason": "profile_budget_exceeded",
                "store_id": item["store_id"],
                "store_kind": item["store_kind"],
                "workspace": item["workspace"],
            }
        )

    startup_lines = ["## Startup Index"]
    startup_entries.sort(
        key=lambda item: (
            STORE_KIND_PRECEDENCE.get(item["store_kind"], 99),
            item["title"],
            item["workspace"],
        )
    )
    startup_seen_keys: set[str] = set()
    filtered_startup_entries: list[dict[str, Any]] = []
    startup_excluded_entries: list[dict[str, Any]] = []
    for entry in startup_entries:
        memory_id = str(entry.get("memory_id") or "")
        if memory_id and memory_id in excluded_by_id and memory_id not in selected_id_set:
            startup_excluded_entries.append(
                {
                    **entry,
                    "reason": excluded_by_id[memory_id].get("reason") or "retrieval_excluded",
                }
            )
            suppressed.append(
                {
                    "kind": "startup_index",
                    "memory_id": memory_id,
                    "reason": "excluded_from_selected_durable_memory",
                    "store_kind": entry["store_kind"],
                    "workspace": entry["workspace"],
                }
            )
            continue
        if entry["key"] in startup_seen_keys:
            continue
        startup_seen_keys.add(entry["key"])
        filtered_startup_entries.append(entry)
        if len(filtered_startup_entries) >= profile["startup_budget"]:
            break

    for entry in filtered_startup_entries:
        if profile["pointer_like"]:
            startup_lines.append(
                f"- [{entry['store_kind']}] [{entry['type']}] {entry['title']} ({entry['workspace']})"
            )
        else:
            startup_lines.append(
                f"- [{entry['store_kind']}] [{entry['type']}] "
                f"{entry['title']} :: {entry['summary']} ({entry['workspace']})"
            )

    learned_context_candidates.sort(
        key=lambda item: (
            STORE_KIND_PRECEDENCE.get(item["store_kind"], 99),
            -float(item["score"]),
            str(item.get("summary", "")),
            item["workspace"],
        )
    )
    selected_learned_context = learned_context_candidates[: profile["learned_context_budget"]]
    for item in learned_context_candidates[profile["learned_context_budget"]:]:
        suppressed.append(
            {
                "kind": "learned_context",
                "record_id": item["record_id"],
                "reason": "profile_budget_exceeded",
                "store_id": item["store_id"],
                "store_kind": item["store_kind"],
                "workspace": item["workspace"],
            }
        )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in selected:
        grouped[(item["store_kind"], item["workspace"])].append(item)

    selected_sections = ["## Selected Durable Memory"]
    for store_kind, workspace in sorted(grouped, key=lambda item: (STORE_KIND_PRECEDENCE.get(item[0], 99), item[1])):
        selected_sections.extend([f"### {store_kind} store :: {workspace}", ""])
        for item in grouped[(store_kind, workspace)]:
            if profile["pointer_like"]:
                selected_sections.append(
                    f"- [{item['type']}] {item['title']} :: {item['summary']} (score={item['score']})"
                )
                continue
            selected_sections.extend(
                [
                    f"#### {item['title']}",
                    f"- type: {item['type']}",
                    f"- score: {item['score']}",
                    f"- why: {item['reason']}",
                    f"- summary: {item['summary']}",
                    item["body"],
                    "",
                ]
            )

    learned_sections = ["## Learned Context"]
    if selected_learned_context:
        for item in selected_learned_context:
            learned_sections.extend(
                [
                    f"### {item['summary']}",
                    f"- score: {item['score']}",
                    f"- freshness: {item.get('fresh_until', 'unknown')}",
                    f"- query_families: {', '.join(item.get('query_family_tags', [])) or 'none'}",
                    item.get("details", ""),
                    item.get("assumptions", ""),
                    "",
                ]
            )
    else:
        learned_sections.append("- none")

    prompt_context = "\n".join(
        [
            "# OpenDream Memory Context",
            f"Query: {query}",
            f"Profile: {profile['name']}",
            "",
            *startup_lines,
            "",
            *selected_sections,
            "",
            *learned_sections,
            "",
            "## Active Automation Projections",
            *(
                [
                    f"- [{item['store_kind']}] [{item['record_type']}] "
                    f"{item['title']} :: {item['summary']} ({item['workspace']})"
                    for item in selected_automation
                ]
                or ["- none"]
            ),
        ]
    ).strip()

    primary_store = store_list[0]
    selected_learned_ids = [str(item.get("record_id") or "") for item in selected_learned_context]
    omitted = [item for item in excluded if item.get("memory_id") not in selected_ids]
    candidate_count = (
        len(merged_candidates)
        + len(filtered_startup_entries)
        + len(learned_context_pool)
        + len(automation_candidates)
    )
    injected_count = (
        len(selected)
        + len(filtered_startup_entries)
        + len(selected_learned_context)
        + len(selected_automation)
    )
    context_id = stable_id(
        "context",
        timestamp,
        query,
        profile["name"],
        ",".join(selected_ids),
        ",".join(selected_learned_ids),
    )
    retrieval_run_id = ",".join(run_id for run_id in retrieval_run_ids if run_id)
    selected_learned_context_items = [
        _learned_context_compare_item(
            item,
            change_class="kept",
            reason_code="selected_for_context",
            source_context_id=context_id,
            source_run_id=retrieval_run_id,
            changed_at=timestamp,
            after_state="active",
        )
        for item in selected_learned_context[:_MAX_PERSISTED_LEARNED_CONTEXT_COMPARE_ITEMS]
    ]
    suppressed_learned_context_items = [
        _learned_context_compare_item(
            learned_context_compare_sources[record_id],
            change_class="suppressed",
            reason_code=str(item.get("reason") or "suppressed_in_context"),
            source_context_id=context_id,
            source_run_id=retrieval_run_id,
            changed_at=timestamp,
            after_state="suppressed_in_context",
        )
        for item in suppressed
        if str(item.get("kind") or "") == "learned_context"
        for record_id in [str(item.get("record_id") or "")]
        if record_id in learned_context_compare_sources
    ][:_MAX_PERSISTED_LEARNED_CONTEXT_COMPARE_ITEMS]
    initialized = [store for store in store_list if store.is_initialized()]
    total_durable = sum(len(store.load_durable_records()) for store in initialized)
    if not initialized:
        empty_reason = "no_initialized_store"
        hints = [
            "Run `opendream init --workspace <path>` (and usually `--activate-configured`) for this workspace."
        ]
    elif not selected_ids:
        if total_durable == 0:
            empty_reason = "no_durable_memories"
            hints = [
                "Record evidence with hooks or `opendream emit-event`, "
                "then run `opendream maintain --workspace <path>`.",
            ]
        else:
            empty_reason = "no_query_matches"
            hints = [
                "Durable memories exist but none matched this query; try different keywords or "
                "`opendream retrieve --workspace <path> --query ... --limit 10` to inspect scoring.",
            ]
    else:
        empty_reason = None
        hints = []
    raw_character_count = sum(
        _representative_text_length(item, kind="durable")
        for item in merged_candidates
    ) + sum(
        _representative_text_length(item, kind="startup", pointer_like=True)
        for item in filtered_startup_entries
    ) + sum(
        _representative_text_length(item, kind="learned_context")
        for item in learned_context_pool
    ) + sum(
        _representative_text_length(item, kind="automation")
        for item in automation_candidates
    )
    injected_character_count = sum(
        _representative_text_length(item, kind="durable", pointer_like=profile["pointer_like"])
        for item in selected
    ) + sum(
        _representative_text_length(item, kind="startup", pointer_like=True)
        for item in filtered_startup_entries
    ) + sum(
        _representative_text_length(item, kind="learned_context")
        for item in selected_learned_context
    ) + sum(
        _representative_text_length(item, kind="automation")
        for item in selected_automation
    )
    suppression_counts: dict[str, int] = defaultdict(int)
    for item in [*omitted, *suppressed]:
        suppression_counts[str(item.get("reason") or "unspecified")] += 1
    startup_index_only_ids = sorted(
        {
            str(item.get("memory_id") or "")
            for item in filtered_startup_entries
            if item.get("memory_id") and item.get("memory_id") not in selected_id_set
        }
    )
    excluded_memory_ids = sorted(
        {
            str(item.get("memory_id") or "")
            for item in [*omitted, *startup_excluded_entries]
            if item.get("memory_id")
        }
    )
    prompt_context_visibility = {
        "selected": {
            "description": "Selected durable memory injected as actionable prompt context.",
            "prompt_visible": True,
            "count": len(selected_ids),
            "memory_ids": selected_ids,
        },
        "excluded": {
            "description": "Excluded from selected durable memory and actionable prompt context.",
            "prompt_visible": False,
            "count": len(excluded_memory_ids),
            "memory_ids": excluded_memory_ids,
        },
        "diagnostic-only": {
            "description": "Available in full JSON/audit diagnostics only; not injected into prompt context.",
            "prompt_visible": False,
            "count": len(suppressed),
        },
        "startup-index-only": {
            "description": "Prompt-visible startup pointers only; not selected durable memory.",
            "prompt_visible": True,
            "count": len(startup_index_only_ids),
            "memory_ids": startup_index_only_ids,
        },
    }

    assembly = ContextAssembly(
        context_id=context_id,
        session_id=current_session_id() or stable_id("session", query),
        turn_id=stable_id("turn", timestamp, query),
        retrieval_run_id=retrieval_run_id,
        startup_index_snapshot=filtered_startup_entries,
        selected_memory_ids=selected_ids,
        omitted_memory_ids=[str(item.get("memory_id") or "") for item in omitted if item.get("memory_id")],
        omission_reasons=omitted,
        assembled_text=prompt_context,
        character_count=len(prompt_context),
        token_estimate=max(1, len(prompt_context.split())),
        created_at=timestamp,
        profile=profile,
        selection={
            "startup_index": {
                "candidate_count": len(filtered_startup_entries),
                "selected": len(filtered_startup_entries),
            },
            "durable_memory": {
                "candidate_count": len(merged_candidates),
                "selected": len(selected),
            },
            "learned_context": {
                "candidate_count": len(learned_context_pool),
                "selected": len(selected_learned_context),
            },
            "automation": {
                "candidate_count": len(automation_candidates),
                "selected": len(selected_automation),
            },
        },
        context_pruning={
            "candidate_count": candidate_count,
            "injected_count": injected_count,
            "suppressed_count": max(candidate_count - injected_count, 0),
            "raw_characters": raw_character_count,
            "injected_characters": injected_character_count,
            "saved_characters": max(raw_character_count - injected_character_count, 0),
            "raw_token_estimate": max(1, raw_character_count // 4) if raw_character_count else 0,
            "injected_token_estimate": max(1, injected_character_count // 4) if injected_character_count else 0,
            "saved_token_estimate": max((raw_character_count - injected_character_count) // 4, 0),
        },
        prompt_context_visibility=prompt_context_visibility,
        selected_learned_context_items=selected_learned_context_items,
        suppressed_learned_context_items=suppressed_learned_context_items,
    )
    context_audit_path = None
    if primary_store.is_initialized():
        context_audit_path = primary_store.write_context_assembly(assembly)

    return {
        "workspace": str(store_list[0].workspace) if len(store_list) == 1 else None,
        "stores": [_store_descriptor(store) for store in store_list],
        "context_id": context_id,
        "audit": {
            "context_path": (
                str(context_audit_path.relative_to(primary_store.workspace))
                if context_audit_path is not None
                else None
            )
        },
        "profile": profile,
        "selection": {
            "startup_index": {
                "candidate_count": len(startup_entries),
                "selected": len(filtered_startup_entries),
            },
            "durable_memory": {
                "candidate_count": len(merged_candidates),
                "selected": len(selected),
            },
            "learned_context": {
                "candidate_count": len(learned_context_pool),
                "selected": len(selected_learned_context),
            },
            "automation": {
                "candidate_count": len(automation_candidates),
                "selected": len(selected_automation),
            },
        },
        "suppressed": [*omitted, *suppressed],
        "suppression_summary": dict(sorted(suppression_counts.items())),
        "context_pruning": {
            "candidate_count": candidate_count,
            "injected_count": injected_count,
            "suppressed_count": max(candidate_count - injected_count, 0),
            "saved_records": max(candidate_count - injected_count, 0),
            "raw_characters": raw_character_count,
            "injected_characters": injected_character_count,
            "saved_characters": max(raw_character_count - injected_character_count, 0),
            "raw_token_estimate": max(1, raw_character_count // 4) if raw_character_count else 0,
            "injected_token_estimate": max(1, injected_character_count // 4) if injected_character_count else 0,
            "saved_token_estimate": max((raw_character_count - injected_character_count) // 4, 0),
        },
        "prompt_context_visibility": prompt_context_visibility,
        "selected_memory_ids": selected_ids,
        "selected_learned_context_ids": selected_learned_ids,
        "selected_automation_record_ids": [item["record_id"] for item in selected_automation],
        "selected_memories": selected,
        "selected_learned_context_records": selected_learned_context,
        "selected_automation_records": selected_automation,
        "omitted": omitted,
        "why": [
            {
                "memory_id": item["memory_id"],
                "store_id": item["store_id"],
                "store_kind": item["store_kind"],
                "reason": item["reason"],
                "score": item["score"],
            }
            for item in selected
        ],
        "prompt_context": prompt_context,
        "summary": summarize(query, 80),
        "empty_reason": empty_reason,
        "hints": hints,
        "cli_output_version": CLI_JSON_VERSION,
    }
