from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .consolidator import consolidate
from .extractor import extract_candidates
from .models import ContextAssembly, MemoryEvent
from .retriever import retrieve
from .storage import STORE_KIND_PRECEDENCE, MemoryStore, store_sort_key
from .util import CLI_JSON_VERSION, parse_timestamp, stable_id, summarize, to_iso, utc_now
from .validation import validate_document

GLOBAL_ROUTE_BLOCKED_SENSITIVITY = {"secret", "sensitive", "do_not_store"}


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


def emit_event(
    store: MemoryStore,
    *,
    kind: str,
    content: str,
    scope: str,
    channel: str,
    message_ref: str,
    session_id: str | None = None,
    turn_id: str | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
    tags: list[str] | None = None,
    confidence_hint: float | None = None,
    sensitivity: str = "normal",
) -> dict[str, Any]:
    if store.store_kind == "global" and scope == "project":
        raise ValueError("project-scoped events must stay in the project store")
    if store.store_kind == "global" and sensitivity in GLOBAL_ROUTE_BLOCKED_SENSITIVITY:
        raise ValueError("sensitive events must not be routed to the global store")

    event_timestamp = timestamp or to_iso(utc_now())
    computed_session_id = session_id or stable_id("session", event_timestamp, store.store_kind, scope)
    computed_turn_id = turn_id or stable_id("turn", event_timestamp, kind, message_ref)
    computed_event_id = event_id or stable_id("event", event_timestamp, kind, content, message_ref)
    event = MemoryEvent(
        event_id=computed_event_id,
        session_id=computed_session_id,
        turn_id=computed_turn_id,
        timestamp=event_timestamp,
        scope=scope,
        kind=kind,
        source={"channel": channel, "message_ref": message_ref},
        content=content,
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

    if len(new_events) < policy["min_new_events"] and not pending_candidates:
        return {
            "status": "skipped",
            "reason": "no-work",
            **_store_descriptor(store),
            "new_events": len(new_events),
            "pending_candidates": 0,
            "policy": policy,
            "cli_output_version": CLI_JSON_VERSION,
        }

    extract_run_id = stable_id("extract", timestamp, len(new_events), store.store_id)
    if new_events:
        candidates = extract_candidates(new_events, origin_mode="scheduled", now=timestamp)
        if candidates:
            store.append_candidates(candidates, extract_run_id)
        store.mark_events_processed(event["event_id"] for event in new_events)
    else:
        candidates = []

    consolidation = consolidate(store, now=timestamp)
    result = {
        "status": "completed" if consolidation.get("status") != "skipped" else "skipped",
        **_store_descriptor(store),
        "extract": {
            "run_id": extract_run_id,
            "processed_events": len(new_events),
            "created_candidates": len(candidates),
        },
        "consolidate": consolidation,
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
            "cli_output_version": CLI_JSON_VERSION,
        }
    return maintain(
        store,
        now=now,
        min_new_events=min_new_events,
        min_interval_seconds=min_interval_seconds,
    )


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
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    store_list = [stores] if isinstance(stores, MemoryStore) else sorted(stores, key=store_sort_key)
    merged_candidates: list[dict[str, Any]] = []
    startup_entries: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    retrieval_run_ids: list[str] = []

    for store in store_list:
        if not store.is_initialized():
            continue
        retrieval = retrieve(store, query=query, limit=max(limit * 3, limit), now=timestamp)
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
        for entry in startup_index.get("entries", [])[: min(4, limit)]:
            startup_entries.append(
                {
                    "title": entry["title"],
                    "type": entry["type"],
                    "summary": entry["summary"],
                    "key": _memory_key(entry),
                    "store_kind": store.store_kind,
                    "workspace": str(store.workspace),
                }
            )

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
    for entry in startup_entries:
        if entry["key"] in startup_seen_keys:
            continue
        startup_seen_keys.add(entry["key"])
        filtered_startup_entries.append(entry)
        if len(filtered_startup_entries) >= max(limit * 2, 1):
            break

    for entry in filtered_startup_entries:
        startup_lines.append(
            f"- [{entry['store_kind']}] [{entry['type']}] {entry['title']} :: {entry['summary']} ({entry['workspace']})"
        )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in selected:
        grouped[(item["store_kind"], item["workspace"])].append(item)

    selected_sections = ["## Selected Durable Memory"]
    for store_kind, workspace in sorted(grouped, key=lambda item: (STORE_KIND_PRECEDENCE.get(item[0], 99), item[1])):
        selected_sections.extend([f"### {store_kind} store :: {workspace}", ""])
        for item in grouped[(store_kind, workspace)]:
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

    prompt_context = "\n".join(
        [
            "# OpenDream Memory Context",
            f"Query: {query}",
            "",
            *startup_lines,
            "",
            *selected_sections,
        ]
    ).strip()

    primary_store = store_list[0]
    selected_ids = [item["memory_id"] for item in selected]
    omitted = [item for item in excluded if item.get("memory_id") not in selected_ids]
    context_id = stable_id("context", timestamp, query, ",".join(selected_ids))
    assembly = ContextAssembly(
        context_id=context_id,
        session_id=stable_id("session", query),
        turn_id=stable_id("turn", timestamp, query),
        retrieval_run_id=",".join(run_id for run_id in retrieval_run_ids if run_id),
        startup_index_snapshot=filtered_startup_entries,
        selected_memory_ids=selected_ids,
        omitted_memory_ids=[str(item.get("memory_id") or "") for item in omitted if item.get("memory_id")],
        omission_reasons=omitted,
        assembled_text=prompt_context,
        character_count=len(prompt_context),
        token_estimate=max(1, len(prompt_context.split())),
        created_at=timestamp,
    )
    if primary_store.is_initialized():
        primary_store.write_context_assembly(assembly)

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

    return {
        "workspace": str(store_list[0].workspace) if len(store_list) == 1 else None,
        "stores": [_store_descriptor(store) for store in store_list],
        "context_id": context_id,
        "selected_memory_ids": selected_ids,
        "selected_memories": selected,
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
