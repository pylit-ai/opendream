from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from collections import Counter, OrderedDict, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from .dream_change_points import score_dream_change_points
from .dream_narrative import synthesize_dream_narrative
from .memory_quality import LOW_SIGNAL_TYPES, analyze_memory_quality
from .models import Annotation, ObservabilityConsolidationOp, PhaseTrace, ReviewDecision
from .semantic_readiness import empty_context_pruning
from .storage import MemoryStore
from .util import parse_timestamp, read_json, sha256_path, stable_id, to_iso, utc_now

# 446-observability-perf: in-process index cache.
# Avoids per-request fingerprint computation + disk read for hot endpoints.
# Fingerprint TTL is short enough to remain near-real-time but lets request
# bursts skip redundant stat() calls.
_INDEX_CACHE_DISABLED = bool(os.environ.get("OPENDREAM_DISABLE_INDEX_CACHE"))
_FINGERPRINT_TTL_SECONDS = 2.0
_COMPACT_INDEX_SCHEMA_VERSION = 3
_INDEX_CACHE_MAX_ENTRIES = 16
_index_cache_lock = threading.Lock()
_index_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_compact_index_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
# key -> (fingerprint, expires_at, lightweight_source_hint)
_fingerprint_cache: dict[str, tuple[str, float, str]] = {}


def _store_cache_key(store: MemoryStore) -> str:
    return str(store.memory_root.resolve())


def _cached_fingerprint(store: MemoryStore) -> str:
    if _INDEX_CACHE_DISABLED:
        return _observability_source_fingerprint(store)
    key = _store_cache_key(store)
    hint = _observability_source_hint(store)
    cached = _fingerprint_cache.get(key)
    if cached and cached[1] > time.monotonic() and cached[2] == hint:
        return cached[0]
    fp = _observability_source_fingerprint(store)
    # Compute expiry AFTER the expensive call so the TTL window is measured
    # from when the cache was actually populated, not from when we entered
    # the function. Otherwise long fingerprint computations leave the cache
    # already-expired before the next caller arrives.
    _fingerprint_cache[key] = (fp, time.monotonic() + _FINGERPRINT_TTL_SECONDS, hint)
    return fp


def _cache_get(key: str, fingerprint: str) -> dict[str, Any] | None:
    if _INDEX_CACHE_DISABLED:
        return None
    with _index_cache_lock:
        entry = _index_cache.get(key)
        if entry is not None and entry.get("source_fingerprint") == fingerprint:
            _index_cache.move_to_end(key)
            return entry
        return None


def _cache_put(key: str, payload: dict[str, Any]) -> None:
    if _INDEX_CACHE_DISABLED:
        return
    with _index_cache_lock:
        _index_cache[key] = payload
        _index_cache.move_to_end(key)
        while len(_index_cache) > _INDEX_CACHE_MAX_ENTRIES:
            _index_cache.popitem(last=False)


def _compact_cache_get(key: str, fingerprint: str) -> dict[str, Any] | None:
    if _INDEX_CACHE_DISABLED:
        return None
    with _index_cache_lock:
        entry = _compact_index_cache.get(key)
        if (
            entry is not None
            and entry.get("source_fingerprint") == fingerprint
            and _compact_index_schema_current(entry)
        ):
            _compact_index_cache.move_to_end(key)
            return entry
        return None


def _compact_cache_put(key: str, payload: dict[str, Any]) -> None:
    if _INDEX_CACHE_DISABLED:
        return
    with _index_cache_lock:
        _compact_index_cache[key] = payload
        _compact_index_cache.move_to_end(key)
        while len(_compact_index_cache) > _INDEX_CACHE_MAX_ENTRIES:
            _compact_index_cache.popitem(last=False)


def invalidate_index_cache(store: MemoryStore | None = None) -> None:
    """Force a rebuild on next call. Pass a store to invalidate one entry."""
    if store is None:
        with _index_cache_lock:
            _index_cache.clear()
            _compact_index_cache.clear()
        _fingerprint_cache.clear()
        return
    key = _store_cache_key(store)
    with _index_cache_lock:
        _index_cache.pop(key, None)
        _compact_index_cache.pop(key, None)
    _fingerprint_cache.pop(key, None)

_SEMANTIC_CHANGE_COMPARE_FILTERS = ["all", "suppressed", "deactivated", "restorable", "restored"]
_SEMANTIC_CHANGE_COMPARE_MODES = ["summary", "side_by_side", "overlay"]
_LEARNED_CONTEXT_DEACTIVATED_STATUSES = frozenset({"superseded", "archived", "rejected"})
_FUNNEL_KEYS = ("considered", "selected", "generated", "approved", "created")


def index_observability(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    source_fingerprint = _observability_source_fingerprint(store)
    index = {
        "generated_at": timestamp,
        "source_fingerprint": source_fingerprint,
        "store": store.status_snapshot(now=timestamp),
        "overview": _build_overview(store, timestamp),
        "entities": _build_entities(store),
    }
    store.save_observability_index(index)
    compact = _build_compact_index_from_full(index)
    store.save_observability_compact_index(compact)
    _cache_put(_store_cache_key(store), index)
    _compact_cache_put(_store_cache_key(store), compact)
    # The fingerprint we just computed is fresh; record it so the next
    # cached read does not redo the stat sweep.
    _fingerprint_cache[_store_cache_key(store)] = (
        source_fingerprint,
        time.monotonic() + _FINGERPRINT_TTL_SECONDS,
        _observability_source_hint(store),
    )
    return index


_RUN_LIST_STRIP = frozenset({"phase_traces", "operations", "candidates", "explanations", "diff_text"})
_RETRIEVAL_LIST_STRIP = frozenset({
    "candidates",
    "explanations",
    "why",
    "excluded",
    "near_threshold",
    "final_context_assembly_order",
    "lexical_only_selected_memory_ids",
})
_SESSION_LIST_STRIP = frozenset({"timeline", "events", "raw_events"})
_MEMORY_LIST_STRIP = frozenset({
    "annotations",
    "manual_reviews",
    "lineage",
    "raw_json",
    "source_paths",
    "provenance",
    "compare_candidates",
})
_MEMORY_LIST_BODY_LIMIT = 280


def project_run_list_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: value for key, value in row.items() if key not in _RUN_LIST_STRIP}
    if isinstance(out.get("summary"), dict):
        out.pop("summary")
    elif isinstance(out.get("summary"), str) and len(out["summary"]) > 200:
        out["summary"] = out["summary"][:200]
    phase_durations = out.get("phase_durations")
    if isinstance(phase_durations, dict) and phase_durations:
        out["phase_durations"] = {"count": len(phase_durations)}
    return out


def project_retrieval_list_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: value for key, value in row.items() if key not in _RETRIEVAL_LIST_STRIP}
    selected_memory_ids = out.get("selected_memory_ids")
    if isinstance(selected_memory_ids, list):
        out["selected_memory_ids_count"] = len(selected_memory_ids)
        out.pop("selected_memory_ids")
    return out


def project_session_list_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in _SESSION_LIST_STRIP}


def project_memory_list_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: value for key, value in row.items() if key not in _MEMORY_LIST_STRIP}
    body = out.get("body")
    if isinstance(body, str) and len(body) > _MEMORY_LIST_BODY_LIMIT:
        out["body"] = body[:_MEMORY_LIST_BODY_LIMIT].rstrip() + "..."
    agents = out.get("reporting_agents")
    if isinstance(agents, list):
        out["reporting_agents"] = [
            {
                key: agent.get(key)
                for key in ("agent_id", "agent_label", "runtime", "adapter_id")
                if isinstance(agent, dict) and agent.get(key)
            }
            for agent in agents
            if isinstance(agent, dict)
        ]
    return out


def project_context_list_row(row: dict[str, Any]) -> dict[str, Any]:
    selected_ids = row.get("selected_memory_ids")
    selected_count = len(selected_ids) if isinstance(selected_ids, list) else None
    query = _context_query_text(row)
    context_id = row.get("context_id")
    out = {
        "context_id": context_id,
        "session_id": row.get("session_id"),
        "created_at": row.get("created_at"),
        "character_count": row.get("character_count"),
        "token_estimate": row.get("token_estimate"),
        "selected_memory_ids_count": selected_count,
        "context_use_count": row.get("context_use_count"),
        "latest_memory_use_state": row.get("latest_memory_use_state"),
        "latest_context_use_id": row.get("latest_context_use_id"),
        "query": query,
        "display_name": _compact_display_label(query, str(context_id or "context")),
    }
    return {key: value for key, value in out.items() if value is not None}


def project_context_use_list_row(row: dict[str, Any]) -> dict[str, Any]:
    selected_ids = row.get("selected_memory_ids")
    used_ids = row.get("used_memory_ids")
    selected_count = row.get("selected_memory_ids_count")
    if not isinstance(selected_count, int):
        selected_count = len(selected_ids) if isinstance(selected_ids, list) else None
    used_count = row.get("used_memory_ids_count")
    if not isinstance(used_count, int):
        used_count = len(used_ids) if isinstance(used_ids, list) else None
    reporting_agent = row.get("reporting_agent")
    if not isinstance(reporting_agent, dict):
        reporting_agent = {}
    context_id = row.get("context_id")
    usage_id = row.get("usage_id")
    out = {
        "usage_id": usage_id,
        "context_id": context_id,
        "timestamp": row.get("timestamp"),
        "memory_use_state": row.get("memory_use_state") or "unknown",
        "selected_memory_ids_count": selected_count,
        "used_memory_ids_count": used_count,
        "used_memory_ids": used_ids if isinstance(used_ids, list) else None,
        "usage_note": row.get("usage_note"),
        "visible_attestation": row.get("visible_attestation"),
        "reporting_agent": reporting_agent if reporting_agent else None,
        "reporting_agent_label": reporting_agent.get("agent_label") or reporting_agent.get("agent_id"),
        "context_query": row.get("context_query"),
        "context_display_name": row.get("context_display_name"),
        "display_name": _compact_display_label(
            str(row.get("context_query") or row.get("usage_note") or ""),
            str(usage_id or context_id or "context-use"),
        ),
    }
    return {key: value for key, value in out.items() if value is not None}


def _context_query_text(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    query = row.get("query") or row.get("request") or row.get("prompt")
    if isinstance(query, str) and query.strip():
        return query.strip()
    assembled_text = row.get("assembled_text")
    if isinstance(assembled_text, str):
        for line in assembled_text.splitlines()[:20]:
            if line.lower().startswith("query:"):
                return line.partition(":")[2].strip() or None
    return None


def _compact_display_label(value: str | None, fallback: str) -> str:
    if value:
        label = " ".join(value.split())
        if label:
            return label[:77] + "..." if len(label) > 80 else label
    return fallback


def _compact_run_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: value for key, value in row.items() if key not in _RUN_LIST_STRIP}
    out.pop("target_paths", None)
    out.pop("source_paths", None)
    return out


def _project_overview_for_list(overview: dict[str, Any]) -> dict[str, Any]:
    projected = dict(overview)
    projected["recent_runs"] = [
        project_run_list_row(row)
        for row in (overview.get("recent_runs") or [])[:5]
        if isinstance(row, dict)
    ]
    projected["recent_sessions"] = [
        project_session_list_row(row)
        for row in (overview.get("recent_sessions") or [])[:5]
        if isinstance(row, dict)
    ]
    last_run = overview.get("last_consolidation_run")
    if isinstance(last_run, dict):
        projected["last_consolidation_run"] = project_run_list_row(last_run)
    return projected


def _build_compact_entities_from_full(entities: dict[str, Any]) -> dict[str, Any]:
    runs = [row for row in entities.get("runs", []) if isinstance(row, dict)]
    retrievals = [row for row in entities.get("retrievals", []) if isinstance(row, dict)]
    sessions = [row for row in entities.get("sessions", []) if isinstance(row, dict)]
    contexts = [row for row in entities.get("contexts", []) if isinstance(row, dict)]
    context_use = [row for row in entities.get("context_use", []) if isinstance(row, dict)]
    dream_cycles = [
        _build_dream_cycle_projection(row, include_detail=False)
        for row in runs
        if _is_dream_run(row)
    ]
    return {
        "memories": [
            project_memory_list_row(row)
            for row in entities.get("memories", [])
            if isinstance(row, dict)
        ],
        "runs": [_compact_run_row(row) for row in runs],
        "retrievals": [project_retrieval_list_row(row) for row in retrievals],
        "contexts": [project_context_list_row(row) for row in contexts],
        "context_use": [project_context_use_list_row(row) for row in context_use],
        "sessions": [project_session_list_row(row) for row in sessions],
        "dream_cycles": dream_cycles,
    }


def _build_compact_index_from_full(index: dict[str, Any]) -> dict[str, Any]:
    entities = index.get("entities") if isinstance(index.get("entities"), dict) else {}
    overview = index.get("overview") if isinstance(index.get("overview"), dict) else {}
    return {
        "generated_at": index.get("generated_at"),
        "source_fingerprint": index.get("source_fingerprint"),
        "compact_schema_version": _COMPACT_INDEX_SCHEMA_VERSION,
        "store": index.get("store", {}),
        "overview": _project_overview_for_list(overview),
        "entities": _build_compact_entities_from_full(entities),
    }


def _compact_index_schema_current(payload: dict[str, Any]) -> bool:
    return payload.get("compact_schema_version") == _COMPACT_INDEX_SCHEMA_VERSION


def index_observability_compact(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    source_fingerprint = _observability_source_fingerprint(store)
    runs = _load_run_records(store)
    retrievals = _load_retrieval_entities(store)
    contexts = _load_context_entities(store)
    context_use = _load_context_use_entities(store, contexts)
    sessions = _build_session_entities(store, contexts)
    full_like_entities = {
        "memories": _build_memory_entities(store),
        "runs": runs,
        "retrievals": retrievals,
        "contexts": contexts,
        "context_use": context_use,
        "sessions": sessions,
    }
    compact = {
        "generated_at": timestamp,
        "source_fingerprint": source_fingerprint,
        "compact_schema_version": _COMPACT_INDEX_SCHEMA_VERSION,
        "store": store.status_snapshot(now=timestamp),
        "overview": _project_overview_for_list(_build_overview(store, timestamp)),
        "entities": _build_compact_entities_from_full(full_like_entities),
    }
    store.save_observability_compact_index(compact)
    _compact_cache_put(_store_cache_key(store), compact)
    _fingerprint_cache[_store_cache_key(store)] = (
        source_fingerprint,
        time.monotonic() + _FINGERPRINT_TTL_SECONDS,
        _observability_source_hint(store),
    )
    return compact


def load_or_build_list_index(
    store: MemoryStore,
    *,
    now: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if force:
        invalidate_index_cache(store)
        return index_observability_compact(store, now=now)
    fingerprint = _cached_fingerprint(store)
    key = _store_cache_key(store)
    cached = _compact_cache_get(key, fingerprint)
    if cached is not None:
        return cached
    if store.observability_compact_index_path.exists():
        payload = store.load_observability_compact_index()
        if (
            payload.get("entities")
            and payload.get("source_fingerprint") == fingerprint
            and _compact_index_schema_current(payload)
        ):
            _compact_cache_put(key, payload)
            return payload
    return index_observability_compact(store, now=now)


def load_or_build_index(
    store: MemoryStore,
    *,
    now: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if force:
        invalidate_index_cache(store)
        return index_observability(store, now=now)
    fingerprint = _cached_fingerprint(store)
    key = _store_cache_key(store)
    cached = _cache_get(key, fingerprint)
    if cached is not None:
        return cached
    if store.observability_index_path.exists():
        payload = store.load_observability_index()
        if payload.get("entities") and payload.get("source_fingerprint") == fingerprint:
            if not store.observability_compact_index_path.exists():
                compact = _build_compact_index_from_full(payload)
                store.save_observability_compact_index(compact)
                _compact_cache_put(key, compact)
            _cache_put(key, payload)
            return payload
    return index_observability(store, now=now)


def _build_overview_lite(store: MemoryStore) -> dict[str, Any]:
    """Cheap overview projection for /api/overview/lite.

    Reads only the minimal fields needed: memory count by status, a small
    recent-runs projection (no phase_traces/operations/candidates), and
    recent sessions.  Reuses the in-process index cache when available so
    the hot path avoids any disk I/O.
    """
    timestamp = to_iso(utc_now())
    key = _store_cache_key(store)
    fingerprint = _cached_fingerprint(store)
    cached = _cache_get(key, fingerprint)
    if cached is not None:
        overview = cached["overview"]
        generated_at = cached.get("generated_at", timestamp)
    else:
        # Build cheap projection without touching entities
        records = store.load_durable_records()
        status_counts: dict[str, int] = {}
        for rec in records:
            s = str(rec.get("status", "unknown"))
            status_counts[s] = status_counts.get(s, 0) + 1
        overview = {
            "generated_at": timestamp,
            "store_health": {
                "state": "locked" if store.lock_state().get("present") else "ready",
                "memory_root": str(store.memory_root),
                "pending_events": store.pending_event_count(),
            },
            "memory_counts": {
                "total": len(records),
                "by_status": dict(sorted(status_counts.items())),
            },
        }
        generated_at = timestamp

    # 446-observability-perf: slim recent_runs — strip heavy fields and cap summary string.
    raw_runs = (overview.get("recent_runs") or [])[:5]
    _RUN_LITE_STRIP = frozenset({
        "phase_traces", "operations", "candidates", "explanations",
        "diff_text", "phase_durations",
    })
    def _lite_run_row(run: dict[str, Any]) -> dict[str, Any]:
        row = {k: v for k, v in run.items() if k not in _RUN_LITE_STRIP}
        # summary may be a large dict or a long string — keep only short string form
        s = run.get("summary")
        if isinstance(s, dict):
            row.pop("summary", None)
        elif isinstance(s, str) and len(s) > 200:
            row["summary"] = s[:200]
        return row
    recent_runs = [_lite_run_row(run) for run in raw_runs]

    # Slim recent_sessions: keep only cheap fields
    raw_sessions = (overview.get("recent_sessions") or [])[:5]
    recent_sessions = [
        {
            "session_id": s.get("session_id"),
            "event_count": s.get("event_count"),
            "started_at": s.get("started_at"),
        }
        for s in raw_sessions
    ]

    store_health_full = overview.get("store_health", {})
    result: dict[str, Any] = {
        "generated_at": generated_at,
        "store_health": {
            "state": store_health_full.get("state"),
            "memory_root": store_health_full.get("memory_root"),
            "pending_events": store_health_full.get("pending_events"),
        },
        "memory_counts": {
            "total": overview.get("memory_counts", {}).get("total", 0),
            "by_status": overview.get("memory_counts", {}).get("by_status", {}),
        },
        "recent_runs": recent_runs,
        "recent_sessions": recent_sessions,
    }
    # Include posture if available
    posture = overview.get("product_posture")
    if posture:
        result["posture"] = posture
    return result


def _observability_source_fingerprint(store: MemoryStore) -> str:
    digest = hashlib.sha256()
    workspace = store.workspace.resolve()
    for path in _iter_observability_source_paths(store):
        stat = path.stat()
        try:
            rel = path.resolve().relative_to(workspace)
            label = str(rel)
        except ValueError:
            label = str(path.resolve())
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b":")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _observability_source_hint(store: MemoryStore) -> str:
    digest = hashlib.sha256()
    paths = [
        store.durable_records_path,
        store.index_json_path,
        store.memory_md_path,
        store.relation_edges_path,
        store.events_dir,
        store.audit_retrieval_dir,
        store.audit_context_dir,
        store.audit_context_use_dir,
        store.audit_consolidation_dir,
        store.audit_dream_dir,
        store.annotations_dir,
        store.reviews_dir,
    ]
    for path in paths:
        if not path.exists():
            continue
        stat = path.stat()
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b":")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _iter_observability_source_paths(store: MemoryStore) -> list[Path]:
    paths: list[Path] = []
    explicit_files = [
        store.durable_records_path,
        store.index_json_path,
        store.memory_md_path,
        store.relation_edges_path,
        store.semantic_config_path,
        store.learned_context_path,
        store.provider_registry_path,
        store.worker_health_path,
        store.service_manifest_path,
        store.service_runtime_path,
    ]
    for path in explicit_files:
        if path.exists():
            paths.append(path)
    roots = [
        store.events_dir,
        store.audit_retrieval_dir,
        store.audit_context_dir,
        store.audit_context_use_dir,
        store.audit_consolidation_dir,
        store.audit_dream_dir,
        store.annotations_dir,
        store.reviews_dir,
        store.exports_dir,
        store.audit_claim_verification_dir,
        store.audit_transcript_probe_dir,
        store.audit_reconciliation_dir,
        store.audit_boundary_dir,
    ]
    # Spec 446: per-directory stat instead of per-file rglob.
    # The audit dirs contain thousands of append-only files. append_jsonl()
    # touches the parent directory after same-file appends, so directory stats
    # remain a cheap invalidation signal without recursing every audit file.
    for root in roots:
        if not root.exists():
            continue
        paths.append(root)
        # Include immediate sub-directories too so daily-rotated audit folders
        # invalidate the cache when their own contents change.
        try:
            for child in root.iterdir():
                if child.is_dir():
                    paths.append(child)
        except OSError:
            pass
    paths.sort(key=lambda item: str(item))
    return paths


_VALID_MEMORY_SORTS = frozenset(
    {
        "title",
        "type",
        "scope",
        "status",
        "memory_id",
        "created_at",
        "updated_at",
        "salience",
        "confidence",
        "retrieval_frequency",
        "reporting_agent",
    }
)


def _memory_scalar_float(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _memory_passes_range(
    value: float | None,
    lo: float | None,
    hi: float | None,
) -> bool:
    """Inclusive bounds; rows missing the value fail when any bound is set."""
    if lo is None and hi is None:
        return True
    if value is None:
        return False
    return not (lo is not None and value < lo) and not (hi is not None and value > hi)


def _memory_passes_time_bound(
    ts: str | None,
    after: str | None,
    before: str | None,
) -> bool:
    """ISO-8601 strings compare lexicographically when normalized."""
    if not after and not before:
        return True
    if not ts:
        return False
    s = str(ts)
    return not (after and s < after) and not (before and s > before)


def _memory_sort_key(
    row: dict[str, Any],
    sort: str,
    *,
    reverse: bool,
) -> tuple[Any, str]:
    """Return a tuple sortable with ``reverse=``; tie-break on ``memory_id``."""
    memory_id = str(row.get("memory_id", ""))
    if sort in {"salience", "confidence"}:
        v = _memory_scalar_float(row, sort)
        primary: Any = -math.inf if v is None else v
    elif sort == "retrieval_frequency":
        raw = row.get("retrieval_frequency", 0)
        try:
            primary = int(raw)
        except (TypeError, ValueError):
            primary = 0
    elif sort in {"created_at", "updated_at"}:
        primary = str(row.get(sort, "") or "")
    elif sort == "reporting_agent":
        primary = str(row.get("reporting_agent_label", "") or "").casefold()
    else:
        primary = str(row.get(sort, "") or "").casefold()

    if reverse:
        primary = (
            -primary if isinstance(primary, (float, int)) else _MemorySortStrDesc(primary)
        )
    return (primary, memory_id)


class _MemorySortStrDesc:
    """Wrap strings so descending lexicographic order uses ``reverse=False``."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _MemorySortStrDesc):
            return NotImplemented
        return self.value > other.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _MemorySortStrDesc):
            return NotImplemented
        return self.value == other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, _MemorySortStrDesc):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, _MemorySortStrDesc):
            return NotImplemented
        return self.value >= other.value

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, _MemorySortStrDesc):
            return NotImplemented
        return self.value <= other.value


def query_memories(
    index: dict[str, Any],
    *,
    search: str = "",
    filters: dict[str, str] | None = None,
    sort: str = "updated_at",
    sort_dir: str | None = None,
    offset: int = 0,
    limit: int = 50,
    salience_min: float | None = None,
    salience_max: float | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    sort_field = sort if sort in _VALID_MEMORY_SORTS else "updated_at"
    if sort_dir == "asc":
        reverse = False
    elif sort_dir == "desc":
        reverse = True
    else:
        reverse = sort_field not in {
            "title",
            "type",
            "scope",
            "status",
            "memory_id",
            "reporting_agent",
        }

    rows = list(index["entities"]["memories"])
    lowered_search = search.strip().lower()
    if lowered_search:
        rows = [
            row
            for row in rows
            if lowered_search in " ".join(
                [
                    str(row.get("title", "")),
                    str(row.get("summary", "")),
                    str(row.get("body", "")),
                    str(row.get("memory_id", "")),
                    str(row.get("reporting_agent_label", "")),
                    " ".join(
                        str(agent.get("agent_id", "")) + " " + str(agent.get("agent_label", ""))
                        for agent in row.get("reporting_agents", [])
                        if isinstance(agent, dict)
                    ),
                ]
            ).lower()
        ]
    for key, value in filters.items():
        if value:
            if key == "agent_id":
                rows = [
                    row
                    for row in rows
                    if any(
                        str(agent.get("agent_id", "")) == value
                        for agent in row.get("reporting_agents", [])
                        if isinstance(agent, dict)
                    )
                ]
            else:
                rows = [row for row in rows if str(row.get(key, "")) == value]

    if salience_min is not None or salience_max is not None:
        rows = [
            row
            for row in rows
            if _memory_passes_range(
                _memory_scalar_float(row, "salience"),
                salience_min,
                salience_max,
            )
        ]
    if confidence_min is not None or confidence_max is not None:
        rows = [
            row
            for row in rows
            if _memory_passes_range(
                _memory_scalar_float(row, "confidence"),
                confidence_min,
                confidence_max,
            )
        ]

    if updated_after or updated_before:
        rows = [
            row
            for row in rows
            if _memory_passes_time_bound(
                row.get("updated_at") if isinstance(row.get("updated_at"), str) else None,
                updated_after,
                updated_before,
            )
        ]
    if created_after or created_before:
        rows = [
            row
            for row in rows
            if _memory_passes_time_bound(
                row.get("created_at") if isinstance(row.get("created_at"), str) else None,
                created_after,
                created_before,
            )
        ]

    rows.sort(key=lambda row: _memory_sort_key(row, sort_field, reverse=reverse))
    total = len(rows)
    return {"total": total, "items": rows[offset : offset + limit]}


_VALID_RETRIEVAL_SORTS = frozenset({"timestamp", "id", "query", "selected_count", "reporting_agent"})


def _retrieval_passes_selected_count(
    row: dict[str, Any],
    lo: int | None,
    hi: int | None,
) -> bool:
    """Inclusive bounds on ``len(selected_memory_ids)``; missing list treated as []."""
    if lo is None and hi is None:
        return True
    n = _retrieval_selected_count(row)
    if lo is not None and n < lo:
        return False
    return not (hi is not None and n > hi)


def _retrieval_selected_count(row: dict[str, Any]) -> int:
    selected = row.get("selected_memory_ids")
    if isinstance(selected, list):
        return len(selected)
    count = row.get("selected_memory_ids_count", row.get("selected_count", 0))
    try:
        return int(count or 0)
    except (TypeError, ValueError):
        return 0


def _retrieval_sort_key(
    row: dict[str, Any],
    sort: str,
    *,
    reverse: bool,
) -> tuple[Any, str]:
    """Sort key with stable tie-break on ``id``."""
    rid = str(row.get("id", ""))
    if sort == "selected_count":
        primary: Any = _retrieval_selected_count(row)
    elif sort == "timestamp":
        primary = str(row.get("timestamp", "") or "")
    elif sort == "query":
        primary = str(row.get("query", "") or "").casefold()
    elif sort == "reporting_agent":
        primary = str((row.get("reporting_agent") or {}).get("agent_label", "") or "").casefold()
    else:
        primary = str(row.get("id", "") or "").casefold()

    if reverse:
        if isinstance(primary, int):
            primary = -primary
        elif sort in {"timestamp", "query", "id", "reporting_agent"}:
            primary = _MemorySortStrDesc(primary)
    return (primary, rid)


def query_retrievals(
    index: dict[str, Any],
    *,
    search: str = "",
    sort: str = "timestamp",
    sort_dir: str | None = None,
    offset: int = 0,
    limit: int = 50,
    timestamp_after: str | None = None,
    timestamp_before: str | None = None,
    min_selected: int | None = None,
    max_selected: int | None = None,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    sort_field = sort if sort in _VALID_RETRIEVAL_SORTS else "timestamp"
    if sort_dir == "asc":
        reverse = False
    elif sort_dir == "desc":
        reverse = True
    else:
        reverse = sort_field in {"timestamp", "selected_count"}

    rows = list(index["entities"]["retrievals"])
    lowered_search = search.strip().lower()
    if lowered_search:
        rows = [
            row
            for row in rows
            if lowered_search
            in " ".join(
                [
                    str(row.get("id", "")),
                    str(row.get("run_id", "")),
                    str(row.get("query", "")),
                    str(row.get("summary", "")),
                    _agent_search_text(row.get("reporting_agent")),
                    " ".join(_agent_search_text(agent) for agent in row.get("source_reporting_agents", [])),
                ]
            ).lower()
        ]
    for key, value in filters.items():
        if not value:
            continue
        if key == "agent_id":
            rows = [
                row
                for row in rows
                if _row_has_agent(row, value, fields=("reporting_agent", "source_reporting_agents"))
            ]

    if timestamp_after or timestamp_before:
        rows = [
            row
            for row in rows
            if _memory_passes_time_bound(
                row.get("timestamp") if isinstance(row.get("timestamp"), str) else None,
                timestamp_after,
                timestamp_before,
            )
        ]

    if min_selected is not None or max_selected is not None:
        rows = [
            row
            for row in rows
            if _retrieval_passes_selected_count(row, min_selected, max_selected)
        ]

    rows.sort(key=lambda row: _retrieval_sort_key(row, sort_field, reverse=reverse))
    total = len(rows)
    return {"total": total, "items": rows[offset : offset + limit]}


_VALID_RUN_SORTS = frozenset({"ended_at", "started_at", "run_id", "type", "status"})


def _run_effective_time(row: dict[str, Any]) -> str | None:
    """Prefer ``ended_at`` for ordering/filtering; fall back to ``started_at``."""
    for key in ("ended_at", "started_at"):
        raw = row.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw
    return None


def _run_sort_key(
    row: dict[str, Any],
    sort: str,
    *,
    reverse: bool,
) -> tuple[Any, str]:
    rid = str(row.get("run_id", row.get("id", "")))
    if sort == "run_id":
        primary = str(row.get("run_id", "") or "").casefold()
    elif sort == "type":
        primary = str(row.get("type", "") or "").casefold()
    elif sort == "status":
        primary = str(row.get("status", "") or "").casefold()
    elif sort == "started_at":
        primary = str(row.get("started_at", "") or "")
    else:
        primary = str(row.get("ended_at", "") or "")

    if reverse:
        if sort in {"ended_at", "started_at"}:
            primary = _MemorySortStrDesc(primary) if primary else _MemorySortStrDesc("")
        elif sort in {"run_id", "type", "status"}:
            primary = _MemorySortStrDesc(primary)
    return (primary, rid)


def query_runs(
    index: dict[str, Any],
    *,
    search: str = "",
    sort: str = "ended_at",
    sort_dir: str | None = None,
    offset: int = 0,
    limit: int = 50,
    ended_after: str | None = None,
    ended_before: str | None = None,
) -> dict[str, Any]:
    """Filter/sort/paginate consolidation and dream run summaries from the index."""
    sort_field = sort if sort in _VALID_RUN_SORTS else "ended_at"
    if sort_dir == "asc":
        reverse = False
    elif sort_dir == "desc":
        reverse = True
    else:
        reverse = sort_field in {"ended_at", "started_at"}

    rows = list(index["entities"]["runs"])
    lowered_search = search.strip().lower()
    if lowered_search:
        rows = [
            row
            for row in rows
            if lowered_search
            in " ".join(
                [
                    str(row.get("run_id", "")),
                    str(row.get("id", "")),
                    str(row.get("type", "")),
                    str(row.get("status", "")),
                    str(row.get("reporting_agent_label", "")),
                    " ".join(_agent_search_text(agent) for agent in row.get("source_reporting_agents", [])),
                ]
            ).lower()
        ]

    if ended_after or ended_before:
        rows = [
            row
            for row in rows
            if _memory_passes_time_bound(_run_effective_time(row), ended_after, ended_before)
        ]

    rows.sort(key=lambda row: _run_sort_key(row, sort_field, reverse=reverse))
    total = len(rows)
    return {"total": total, "items": rows[offset : offset + limit]}


def query_dream_cycles(
    index: dict[str, Any],
    *,
    limit: int = 50,
    since: str | None = None,
) -> dict[str, Any]:
    entities = index["entities"]
    if isinstance(entities.get("dream_cycles"), list):
        rows = [dict(row) for row in entities["dream_cycles"] if isinstance(row, dict)]
    else:
        rows = [
            _build_dream_cycle_projection(run, include_detail=False)
            for run in entities["runs"]
            if _is_dream_run(run)
        ]
    if since:
        rows = [
            row
            for row in rows
            if _memory_passes_time_bound(
                row.get("ended_at") if isinstance(row.get("ended_at"), str) else row.get("started_at"),
                since,
                None,
            )
        ]
    rows.sort(key=lambda row: str(row.get("ended_at") or row.get("started_at") or row.get("run_id")), reverse=True)
    rows = score_dream_change_points(rows, newest_first=True)
    return {"total": len(rows), "items": rows[:limit]}


def get_dream_cycle(index: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    run = _find_row_by_id(index["entities"]["runs"], "run_id", run_id)
    if not run or not _is_dream_run(run):
        return None
    rows = [
        _build_dream_cycle_projection(candidate, include_detail=False)
        for candidate in index["entities"]["runs"]
        if _is_dream_run(candidate)
    ]
    rows.sort(key=lambda row: str(row.get("ended_at") or row.get("started_at") or row.get("run_id")), reverse=True)
    scored = score_dream_change_points(rows, newest_first=True)
    change_point = next(
        (row.get("change_point") for row in scored if str(row.get("run_id")) == run_id),
        None,
    )
    detail = _build_dream_cycle_projection(run, include_detail=True)
    if isinstance(change_point, dict):
        detail["change_point"] = change_point
    return detail


def build_dream_funnel(index: dict[str, Any], *, window: str = "7d") -> dict[str, Any]:
    entities = index.get("entities", {})
    if isinstance(entities.get("dream_cycles"), list):
        cutoff = _window_cutoff_iso(window)
        cycles = [
            dict(row)
            for row in entities["dream_cycles"]
            if isinstance(row, dict)
            and (not cutoff or str(row.get("ended_at") or row.get("started_at") or "") >= cutoff)
        ]
        totals = {key: 0 for key in _FUNNEL_KEYS}
        for row in cycles:
            funnel = row.get("funnel") if isinstance(row.get("funnel"), dict) else {}
            for key in _FUNNEL_KEYS:
                totals[key] += int(funnel.get(key, 0) or 0)
        return {
            "window": window,
            "total_cycles": len(cycles),
            "funnel": totals,
            "cycles": [
                {
                    "run_id": row.get("run_id"),
                    "started_at": row.get("started_at"),
                    "ended_at": row.get("ended_at"),
                    "funnel": row.get("funnel", {}),
                }
                for row in cycles
            ],
        }
    rows = _dream_runs_in_window(index, window)
    totals = {key: 0 for key in _FUNNEL_KEYS}
    cycles: list[dict[str, Any]] = []
    for run in rows:
        projection = _build_dream_cycle_projection(run, include_detail=False)
        funnel = projection["funnel"]
        for key in _FUNNEL_KEYS:
            totals[key] += int(funnel.get(key, 0) or 0)
        cycles.append(
            {
                "run_id": projection["run_id"],
                "started_at": projection.get("started_at"),
                "ended_at": projection.get("ended_at"),
                "funnel": funnel,
            }
        )
    return {
        "window": window,
        "total_cycles": len(rows),
        "funnel": totals,
        "cycles": cycles,
    }


def build_dream_coverage(store: MemoryStore, *, window: str = "7d") -> dict[str, Any]:
    cutoff = _window_cutoff_iso(window)
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for event in store.load_events():
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str) or (cutoff and timestamp < cutoff):
            continue
        bucket = timestamp[:10] if len(timestamp) >= 10 else "unknown"
        buckets[bucket][_signal_source_class(event)] += 1
    items = []
    for bucket in sorted(buckets):
        counts = dict(buckets[bucket])
        total = sum(counts.values())
        items.append(
            {
                "bucket": bucket,
                "total": total,
                "explicit_events": counts.get("explicit_events", 0),
                "transcript_episodes": counts.get("transcript_episodes", 0),
                "automation": counts.get("automation", 0),
                "shares": {
                    "explicit_events": round(counts.get("explicit_events", 0) / max(total, 1), 4),
                    "transcript_episodes": round(counts.get("transcript_episodes", 0) / max(total, 1), 4),
                    "automation": round(counts.get("automation", 0) / max(total, 1), 4),
                },
            }
        )
    return {"window": window, "items": items}


def _is_dream_run(run: dict[str, Any]) -> bool:
    kind = str(run.get("type") or run.get("kind") or "").lower()
    run_id = str(run.get("run_id") or run.get("id") or "").lower()
    return "dream" in kind or run_id.startswith("dream") or run_id.startswith("semantic-dream")


def _find_row_by_id(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get(key, "")) == value:
            return row
    return None


def _build_dream_cycle_projection(run: dict[str, Any], *, include_detail: bool) -> dict[str, Any]:
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    assert isinstance(summary, dict)
    phase_traces = _phase_traces_with_duration(run)
    phase_durations = {
        str(trace.get("phase") or "unknown"): int(trace.get("duration_ms", 0) or 0)
        for trace in phase_traces
    }
    narrative = str(run.get("narrative") or summary.get("narrative") or "").strip()
    stale_semantic_noop_narrative = (
        str(summary.get("mode") or run.get("mode") or run.get("type")) in {"semantic", "hybrid"}
        and _int(summary.get("proposals_generated")) == 0
        and _int(summary.get("learned_context_created")) == 0
        and "deterministic memory maintenance" in narrative
    )
    if not narrative or stale_semantic_noop_narrative:
        narrative = synthesize_dream_narrative({**summary, "status": run.get("status"), "type": run.get("type")})
    projection: dict[str, Any] = {
        "id": run.get("id") or run.get("run_id"),
        "run_id": run.get("run_id"),
        "type": run.get("type"),
        "mode": summary.get("mode") or run.get("mode") or run.get("type"),
        "status": run.get("status") or summary.get("status"),
        "reason": summary.get("reason") or run.get("reason"),
        "started_at": run.get("started_at") or summary.get("started_at") or summary.get("last_started_at"),
        "ended_at": run.get("ended_at") or summary.get("ended_at") or summary.get("last_ran_at"),
        "duration_ms": _run_duration_ms(run, summary),
        "model_id": summary.get("model_id") or summary.get("provider_id"),
        "cost_usd": summary.get("cost_usd"),
        "tokens_used": summary.get("tokens_used"),
        "signal_source": summary.get("latest_signal_source") or summary.get("trigger_class"),
        "latest_signal_timestamp": summary.get("latest_signal_timestamp"),
        "signal_row_count": _int(summary.get("signal_row_count") or summary.get("gathered_rows")),
        "appended_events": _int(summary.get("appended_events") or summary.get("staged_events")),
        "funnel": _dream_funnel_counts(summary),
        "phase_durations": phase_durations,
        "phase_traces": phase_traces if include_detail else [],
        "phases": summary.get("phases") or [trace.get("phase") for trace in phase_traces],
        "trace_summary": _semantic_trace_summary(summary),
        "narrative": narrative,
        "reporting_agent_label": run.get("reporting_agent_label"),
        "warnings": run.get("warnings", []),
    }
    if include_detail:
        projection["summary"] = summary
        projection["target_paths"] = run.get("target_paths", [])
        projection["source_paths"] = run.get("source_paths", [])
        projection["diff_path"] = run.get("diff_path")
        projection["diff_text"] = run.get("diff_text", "")
    return projection


def _phase_traces_with_duration(run: dict[str, Any]) -> list[dict[str, Any]]:
    traces = [dict(item) for item in run.get("phase_traces", []) if isinstance(item, dict)]
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    total = _run_duration_ms(run, summary if isinstance(summary, dict) else {})
    known_total = 0
    missing: list[dict[str, Any]] = []
    for trace in traces:
        phase = str(trace.get("phase") or trace.get("name") or "unknown")
        trace.setdefault("name", phase)
        trace.setdefault("summary_short", phase.replace("_", " "))
        duration = _phase_duration_ms(trace)
        if duration <= 0:
            missing.append(trace)
        else:
            trace["duration_ms"] = duration
            known_total += duration
    fallback = max(total - known_total, 0)
    share = round(fallback / max(len(missing), 1)) if missing else 0
    for trace in missing:
        trace["duration_ms"] = share
    return traces


def _phase_duration_ms(trace: dict[str, Any]) -> int:
    explicit = trace.get("duration_ms")
    if isinstance(explicit, (int, float)):
        return max(0, round(explicit))
    started = trace.get("started_at")
    ended = trace.get("ended_at")
    if isinstance(started, str) and isinstance(ended, str) and started and ended:
        try:
            return max(0, round((parse_timestamp(ended) - parse_timestamp(started)).total_seconds() * 1000))
        except (ValueError, TypeError):
            return 0
    return 0


def _run_duration_ms(run: dict[str, Any], summary: dict[str, Any]) -> int:
    for value in (run.get("duration_ms"), summary.get("duration_ms")):
        if isinstance(value, (int, float)):
            return max(0, round(value))
    started = run.get("started_at") or summary.get("started_at") or summary.get("last_started_at")
    ended = run.get("ended_at") or summary.get("ended_at") or summary.get("last_ran_at")
    if isinstance(started, str) and isinstance(ended, str) and started and ended:
        try:
            return max(0, round((parse_timestamp(ended) - parse_timestamp(started)).total_seconds() * 1000))
        except (ValueError, TypeError):
            return 0
    return 0


def _dream_funnel_counts(summary: dict[str, Any]) -> dict[str, int]:
    considered = _int(
        summary.get("query_families_considered")
        or summary.get("families_considered")
        or summary.get("signal_row_count")
        or summary.get("gathered_rows")
    )
    selected = _int(
        summary.get("query_families_selected")
        or summary.get("families_selected")
        or summary.get("appended_events")
    )
    generated = _int(summary.get("proposals_generated"))
    approved = _int(summary.get("proposals_approved"))
    created = _int(summary.get("learned_context_created") or summary.get("memories_created"))
    return {
        "considered": considered,
        "selected": selected,
        "generated": generated,
        "approved": approved,
        "created": created,
    }


def _semantic_trace_summary(summary: dict[str, Any]) -> dict[str, Any]:
    trace = summary.get("semantic_trace")
    if not isinstance(trace, dict):
        return {
            "input_consumed": bool(summary.get("latest_signal_source")),
            "signal_source": summary.get("latest_signal_source"),
            "latest_signal_timestamp": summary.get("latest_signal_timestamp"),
            "rows_scanned": _int(summary.get("signal_row_count") or summary.get("gathered_rows")),
            "families_selected": _int(summary.get("query_families_selected")),
            "proposals_generated": _int(summary.get("proposals_generated")),
            "verifier_verdicts": {},
            "learned_context_created": _int(summary.get("learned_context_created")),
            "no_materialization_reason": summary.get("no_materialization_reason") or summary.get("reason") or "",
        }
    signal = trace.get("signal") if isinstance(trace.get("signal"), dict) else {}
    planner = trace.get("planner") if isinstance(trace.get("planner"), dict) else {}
    synthesis = trace.get("synthesis") if isinstance(trace.get("synthesis"), dict) else {}
    verification = trace.get("verification") if isinstance(trace.get("verification"), dict) else {}
    materialization = trace.get("materialization") if isinstance(trace.get("materialization"), dict) else {}
    family_results = synthesis.get("family_results") if isinstance(synthesis.get("family_results"), list) else []
    rows_gathered = _int(signal.get("rows_gathered") or signal.get("rows_scanned"))
    selected_family_ids = (
        planner.get("selected_family_ids")
        if isinstance(planner.get("selected_family_ids"), list)
        else []
    )
    return {
        "input_consumed": bool(signal.get("source") and rows_gathered > 0),
        "signal_source": signal.get("source"),
        "latest_signal_timestamp": signal.get("latest_timestamp"),
        "rows_scanned": _int(signal.get("rows_scanned")),
        "rows_gathered": _int(signal.get("rows_gathered")),
        "families_considered": _int(planner.get("families_considered")),
        "families_selected": _int(planner.get("families_selected")),
        "selected_family_ids": selected_family_ids,
        "family_result_count": len(family_results),
        "drop_reasons": (
            synthesis.get("drop_reasons")
            if isinstance(synthesis.get("drop_reasons"), list)
            else []
        ),
        "fallback_reason": synthesis.get("fallback_reason") or "",
        "proposal_ids": (
            synthesis.get("proposal_ids")
            if isinstance(synthesis.get("proposal_ids"), list)
            else []
        ),
        "proposals_generated": _int(synthesis.get("proposal_count") or summary.get("proposals_generated")),
        "verifier_verdicts": (
            verification.get("verdict_counts")
            if isinstance(verification.get("verdict_counts"), dict)
            else {}
        ),
        "learned_context_created": _int(materialization.get("created_count") or summary.get("learned_context_created")),
        "promoted_record_ids": (
            materialization.get("promoted_record_ids")
            if isinstance(materialization.get("promoted_record_ids"), list)
            else []
        ),
        "retention_status": materialization.get("retention_status") or "",
        "no_materialization_reason": (
            materialization.get("no_materialization_reason")
            or summary.get("no_materialization_reason")
            or ""
        ),
    }


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dream_runs_in_window(index: dict[str, Any], window: str) -> list[dict[str, Any]]:
    cutoff = _window_cutoff_iso(window)
    rows = [run for run in index["entities"]["runs"] if _is_dream_run(run)]
    if cutoff:
        rows = [
            run
            for run in rows
            if str(run.get("ended_at") or run.get("started_at") or "") >= cutoff
        ]
    return rows


def _window_cutoff_iso(window: str) -> str | None:
    value = str(window or "").strip().lower()
    if not value:
        return None
    try:
        if value.endswith("d"):
            delta = timedelta(days=int(value[:-1]))
        elif value.endswith("h"):
            delta = timedelta(hours=int(value[:-1]))
        else:
            return None
    except ValueError:
        return None
    return to_iso(utc_now() - delta)


def _signal_source_class(event: dict[str, Any]) -> str:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    assert isinstance(source, dict)
    channel = str(event.get("channel") or source.get("channel") or "").lower()
    refs = source.get("file_refs")
    if isinstance(refs, list) and refs:
        return "transcript_episodes"
    if "automation" in channel or str(source.get("adapter_id") or "").strip():
        return "automation"
    return "explicit_events"


def _select_subgraph(
    graph: dict[str, Any],
    *,
    focus: str | None,
    limit: int,
    depth: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """BFS up to ``depth`` hops from ``focus``, capped at ``limit`` nodes.

    Adjacency is undirected so neighborhood expansion crosses edge direction
    (a node is reachable from both its ancestors and its descendants).

    If ``focus`` is None, returns the first ``limit`` nodes from the graph.
    If ``focus`` is unknown, returns ``([], [])``. When ``limit`` would truncate
    the visited set, the focus node is always retained at position 0.
    """
    all_nodes = graph.get("nodes", [])
    all_edges = graph.get("edges", [])
    by_id = {n["id"]: n for n in all_nodes}

    if focus is None:
        selected = all_nodes[:limit]
        ids = {n["id"] for n in selected}
        edges = [e for e in all_edges if e["source"] in ids and e["target"] in ids]
        return list(selected), edges

    if focus not in by_id:
        return [], []

    adjacency: dict[str, set[str]] = {nid: set() for nid in by_id}
    for edge in all_edges:
        if edge["source"] in by_id and edge["target"] in by_id:
            adjacency[edge["source"]].add(edge["target"])
            adjacency[edge["target"]].add(edge["source"])

    visited = {focus}
    frontier = {focus}
    for _ in range(max(depth, 0)):
        next_frontier: set[str] = set()
        for nid in frontier:
            next_frontier.update(adjacency[nid] - visited)
        if not next_frontier:
            break
        visited.update(next_frontier)
        frontier = next_frontier
        if len(visited) >= limit:
            break

    # Always retain the focus node at position 0, then fill remaining slots
    # from the rest of ``visited``. Without this pin, a ``limit``-triggered
    # early break could drop the focus during set-iteration slicing.
    selected_ids = [focus] + [nid for nid in visited if nid != focus]
    selected_ids = selected_ids[:limit]
    selected_set = set(selected_ids)
    nodes = [by_id[nid] for nid in selected_ids]
    edges = [e for e in all_edges if e["source"] in selected_set and e["target"] in selected_set]
    return nodes, edges


_LAYOUT_RANK_EDGE_KINDS = frozenset({"supersedes", "derived_from"})


def _layered_positions(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, tuple[float, float]]:
    """Topologically rank nodes by supersedes/derived_from edges.

    Y is the rank (top-down: rank 0 is the oldest ancestor). X orders siblings
    within a rank by ``created_at`` (or ``id`` as fallback). Cycles short-circuit
    to a stable fallback rank rather than raising.
    """
    node_ids = [node["id"] for node in nodes]
    id_set = set(node_ids)
    parents: dict[str, set[str]] = {nid: set() for nid in node_ids}
    children: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for edge in edges:
        if edge.get("type") not in _LAYOUT_RANK_EDGE_KINDS:
            continue
        src = edge["source"]
        tgt = edge["target"]
        if src not in id_set or tgt not in id_set:
            continue
        # ``B supersedes A`` means B is deeper than A => parent edge A -> B.
        parents[src].add(tgt)
        children[tgt].add(src)

    rank: dict[str, int] = {}
    queue = [nid for nid in node_ids if not parents[nid]]
    while queue:
        next_queue: list[str] = []
        for nid in queue:
            ancestor_ranks = [rank[p] for p in parents[nid] if p in rank]
            rank[nid] = max(ancestor_ranks) + 1 if ancestor_ranks else 0
            for child in children[nid]:
                if all(p in rank for p in parents[child]):
                    next_queue.append(child)
        queue = next_queue

    # Cycle break: any node not yet ranked goes to max_rank + 1.
    if any(nid not in rank for nid in node_ids):
        fallback = max(rank.values(), default=-1) + 1
        for nid in node_ids:
            rank.setdefault(nid, fallback)

    by_rank: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_rank.setdefault(rank[node["id"]], []).append(node)

    positions: dict[str, tuple[float, float]] = {}
    for r, group in by_rank.items():
        group.sort(key=lambda n: (str(n.get("created_at") or ""), n["id"]))
        for i, node in enumerate(group):
            x = float(i) - (len(group) - 1) / 2.0
            positions[node["id"]] = (x, float(r))
    return positions


_VALID_LAYOUTS = frozenset({"hierarchical", "forceatlas2"})


def build_graph(
    index: dict[str, Any],
    *,
    focus: str | None = None,
    limit: int = 24,
    depth: int = 1,
    layout: str = "hierarchical",
) -> dict[str, Any]:
    graph = index["entities"]["graph"]
    if layout not in _VALID_LAYOUTS:
        layout = "hierarchical"
    nodes, edges = _select_subgraph(graph, focus=focus, limit=limit, depth=depth)
    # Copy nodes so we don't mutate the underlying index when assigning x/y.
    nodes = [dict(node) for node in nodes]
    if layout == "hierarchical":
        positions = _layered_positions(nodes, edges)
        for node in nodes:
            x, y = positions[node["id"]]
            node["x"] = x
            node["y"] = y
    return {
        "nodes": nodes,
        "edges": edges,
        "focus": focus,
        "depth": depth,
        "layout": layout,
    }


def _build_overview(store: MemoryStore, timestamp: str) -> dict[str, Any]:
    records = store.load_durable_records()
    events = store.load_events()
    status_counts: dict[str, int] = defaultdict(int)
    type_counts: dict[str, int] = defaultdict(int)
    scope_counts: dict[str, int] = defaultdict(int)
    for record in records:
        status_counts[str(record.get("status", "unknown"))] += 1
        type_counts[str(record.get("type", "unknown"))] += 1
        scope_counts[str(record.get("scope", "unknown"))] += 1
    retrievals = _load_json_records(store.audit_retrieval_dir)
    runs = _load_run_records(store)
    recent_sessions = _recent_sessions(events)
    last_event_at = _max_iso_timestamp(event.get("timestamp") for event in events)
    last_retrieval_at = _max_iso_timestamp(item.get("timestamp") for item in retrievals)
    last_run_at = _max_iso_timestamp(_effective_run_timestamp(item) for item in runs)
    pending_events = store.pending_event_count()
    pending_candidates = len(store.load_pending_candidates())
    transcript_events = 0
    explicit_events = 0
    for event in events:
        source = event.get("source", {})
        file_refs = source.get("file_refs", [])
        if isinstance(file_refs, list) and file_refs:
            transcript_events += 1
        else:
            explicit_events += 1
    # Execution ownership (440 bundle)
    semantic_config = store.load_semantic_config()
    semantic_surface = _semantic_quality_surface(store, now=timestamp)
    runtime_management = _build_runtime_management_overview(store, timestamp)
    memory_surface = _build_memory_surface(store, records, now=timestamp)
    last_runtime_effects = _build_last_runtime_effects(runs)
    overview: dict[str, Any] = {
        "generated_at": timestamp,
        "store_health": {
            "initialized": store.is_initialized(),
            "state": "locked" if store.lock_state().get("present") else "ready",
            "lock": store.lock_state(),
            "dream_lock": store.dream_lock_state(),
            "memory_root": str(store.memory_root),
            "pending_events": pending_events,
            "pending_candidates": pending_candidates,
        },
        "memory_counts": {
            "total": len(records),
            "by_status": dict(sorted(status_counts.items())),
            "by_type": dict(sorted(type_counts.items())),
            "by_scope": dict(sorted(scope_counts.items())),
        },
        "contested_memories": status_counts.get("contested", 0),
        "startup_index": {
            "path": str(store.memory_md_path),
            "size_bytes": store.memory_md_path.stat().st_size if store.memory_md_path.exists() else 0,
            "entries": len(store.load_startup_index().get("entries", [])),
        },
        "activation_diagnostics": {
            "auto_mode": True,
            "dream_state": store.load_dream_state(),
            "manual_trigger": "opendream dream run --workspace <path> --episodes <jsonl...>",
            "queued_triggers": 0,
            "suppressed_trigger_reasons": [],
        },
        "signal_coverage": {
            "transcript_events": transcript_events,
            "explicit_events": explicit_events,
            "transcript_share": round(transcript_events / max(len(events), 1), 4) if events else 0.0,
            "event_share": round(explicit_events / max(len(events), 1), 4) if events else 0.0,
        },
        "retrievals": {
            "total": len(retrievals),
            "successful": sum(1 for item in retrievals if item.get("selected_memory_ids")),
            "failed": sum(1 for item in retrievals if not item.get("selected_memory_ids")),
        },
        "recent_sessions": recent_sessions,
        "recent_runs": runs[:5],
        "last_consolidation_run": runs[0] if runs else None,
        "freshness": {
            "index_generated_at": timestamp,
            "last_event_at": last_event_at,
            "last_session_activity_at": recent_sessions[0].get("ended_at") if recent_sessions else None,
            "last_retrieval_at": last_retrieval_at,
            "last_run_at": last_run_at,
        },
        "memory_excellence": _build_memory_excellence_overview(store, records),
        "execution_ownership": {
            "active_strategy": semantic_config.get("execution_strategy", "deterministic"),
            "preferred_auth_mode": semantic_config.get("preferred_auth_mode", "no-extra-key"),
            "active_adapter": semantic_config.get("active_adapter"),
            "candidate_strategies": semantic_config.get("candidate_strategies", []),
        },
        "runtime_management": runtime_management,
        "memory_surface": memory_surface,
        "last_runtime_effects": last_runtime_effects,
        "semantic_change_summary": _build_semantic_change_summary(store, timestamp),
        **semantic_surface,
        "context_pruning": _latest_context_pruning(store),
    }
    return overview


def build_semantic_change_review(
    store: MemoryStore,
    *,
    source_id: str | None = None,
    now: str | None = None,
) -> dict[str, Any] | None:
    timestamp = now or to_iso(utc_now())
    context = _resolve_semantic_change_context(store, source_id=source_id)
    if context is None:
        return None
    kept = list(context.get("selected_learned_context_items") or [])
    suppressed = list(context.get("suppressed_learned_context_items") or [])
    transitions = _learned_context_transition_items(
        store,
        now=timestamp,
        source_context_id=str(context.get("context_id") or ""),
        source_run_id=str(context.get("retrieval_run_id") or ""),
    )
    items = [
        _semantic_change_enrich_item(item, context=context)
        for item in [*kept, *suppressed, *transitions]
    ]
    summary_counts = {
        "kept_count": len(kept),
        "suppressed_count": len(suppressed),
        "deactivated_count": sum(1 for item in transitions if item.get("change_class") == "deactivated"),
        "restorable_count": sum(
            1
            for item in transitions
            if item.get("change_class") == "deactivated" and item.get("restore_allowed")
        ),
        "restored_count": sum(1 for item in transitions if item.get("change_class") == "restored"),
    }
    return {
        "change_review_id": str(context.get("context_id") or ""),
        "source_kind": "context_assembly",
        "source_id": str(context.get("context_id") or ""),
        "source_run_id": str(context.get("retrieval_run_id") or "") or None,
        "created_at": context.get("created_at"),
        "summary_counts": summary_counts,
        "items": items,
        "view_hints": {
            "default_view_mode": "summary",
            "available_filters": list(_SEMANTIC_CHANGE_COMPARE_FILTERS),
            "available_compare_modes": list(_SEMANTIC_CHANGE_COMPARE_MODES),
        },
    }


def build_semantic_change_unavailable(
    store: MemoryStore,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    contexts = store.load_context_assemblies()
    comparable_contexts = [
        item
        for item in contexts
        if item.get("selected_learned_context_items") or item.get("suppressed_learned_context_items")
    ]
    learned_context_records = store.load_learned_context_records()
    semantic_config = store.load_semantic_config()
    semantic_quality = analyze_memory_quality(store, now=timestamp)
    learned_total = len(learned_context_records)
    context_total = len(contexts)
    comparable_total = len(comparable_contexts)
    semantic_mode = str(semantic_config.get("mode", "deterministic") or "deterministic")
    semantic_state = str(semantic_quality.get("semantic_capability_state") or "unknown")

    if learned_total == 0:
        reason_code = "no_learned_context"
        details = (
            "durable memory exists, but OpenDream has not materialized any learned-context "
            "records for this workspace yet."
        )
    elif context_total == 0:
        reason_code = "no_context_assembly"
        details = (
            "Learned-context records exist, but no prompt context assembly has been recorded yet."
        )
    elif comparable_total == 0:
        reason_code = "no_comparable_context"
        details = (
            "Context has been assembled, but the recorded assemblies do so without "
            "learned-context kept or suppressed items."
        )
    else:
        reason_code = "not_available"
        details = "No comparable learned-context change review is available for the current workspace."

    next_actions = [
        "Inspect durable memory in Memory Explorer.",
        "Run semantic setup if learned-context materialization should be enabled.",
        "Run a semantic refresh or prepare-context after semantic materialization completes.",
    ]
    if semantic_mode == "deterministic" or semantic_state == "disabled_by_choice":
        next_actions.insert(1, "Semantic mode is currently deterministic or disabled by choice.")

    return {
        "status": "not_available",
        "reason_code": reason_code,
        "headline": "Learned-context comparison is not available yet.",
        "details": details,
        "semantic_mode": semantic_mode,
        "semantic_capability_state": semantic_state,
        "learned_context_total": learned_total,
        "context_assembly_total": context_total,
        "comparable_context_total": comparable_total,
        "next_actions": next_actions,
        "review_href": "/memories/changes",
    }


def _build_semantic_change_summary(store: MemoryStore, timestamp: str) -> dict[str, Any]:
    review = build_semantic_change_review(store, now=timestamp)
    if review is None:
        unavailable = build_semantic_change_unavailable(store, now=timestamp)
        return {
            "status": "not_available",
            "headline": unavailable["headline"],
            "reason_code": unavailable["reason_code"],
            "details": unavailable["details"],
            "semantic_mode": unavailable["semantic_mode"],
            "semantic_capability_state": unavailable["semantic_capability_state"],
            "learned_context_total": unavailable["learned_context_total"],
            "context_assembly_total": unavailable["context_assembly_total"],
            "comparable_context_total": unavailable["comparable_context_total"],
            "next_actions": unavailable["next_actions"],
            "latest_run_id": None,
            "latest_context_id": None,
            "kept_count": 0,
            "suppressed_count": 0,
            "deactivated_count": 0,
            "restorable_count": 0,
            "review_href": "/memories/changes",
        }
    counts = review["summary_counts"]
    return {
        "status": "available",
        "headline": "Review the latest semantic context changes.",
        "latest_run_id": review.get("source_run_id"),
        "latest_context_id": review.get("source_id"),
        "kept_count": int(counts.get("kept_count", 0) or 0),
        "suppressed_count": int(counts.get("suppressed_count", 0) or 0),
        "deactivated_count": int(counts.get("deactivated_count", 0) or 0),
        "restorable_count": int(counts.get("restorable_count", 0) or 0),
        "review_href": f"/memories/changes/{review['source_id']}",
    }


def _resolve_semantic_change_context(
    store: MemoryStore,
    *,
    source_id: str | None = None,
) -> dict[str, Any] | None:
    contexts = store.load_context_assemblies()
    comparable = [
        item
        for item in contexts
        if item.get("selected_learned_context_items") or item.get("suppressed_learned_context_items")
    ]
    comparable.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    if source_id:
        for item in comparable:
            if str(item.get("context_id") or "") == source_id:
                return item
            if str(item.get("retrieval_run_id") or "") == source_id:
                return item
        return None
    return comparable[0] if comparable else None


def _semantic_change_reason_label(reason_code: str) -> str:
    labels = {
        "selected_for_context": "Kept active in this context",
        "profile_budget_exceeded": "Suppressed in this context because the profile budget was exceeded",
        "startup_profile_keeps_learned_context_pointer_only": (
            "Suppressed in this context to keep startup output pointer-like"
        ),
        "weak_match_learned_context": "Suppressed in this context because the match was weak",
        "conflicted_learned_context": "Suppressed in this context because the record is conflicted",
        "stale_learned_context": "Suppressed in this context because the record is stale",
        "verifier_not_ready": "Suppressed in this context because verification is not ready",
        "inactive_learned_context": "Removed from active learned context",
        "superseded": "Removed from active learned context because a newer record superseded it",
        "archived": "Removed from active learned context because it was archived",
        "rejected": "Removed from active learned context because verification rejected it",
        "record_restored": "Record restored to active learned context",
    }
    return labels.get(reason_code, reason_code.replace("_", " ").capitalize())


def _semantic_change_enrich_item(item: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    reason_code = str(enriched.get("reason_code") or "")
    change_class = str(enriched.get("change_class") or "")
    record_id = str(enriched.get("record_id") or "")
    context_id = str(enriched.get("source_context_id") or context.get("context_id") or "")
    profile = context.get("profile") if isinstance(context.get("profile"), dict) else {}
    selection = context.get("selection") if isinstance(context.get("selection"), dict) else {}
    learned_selection = (
        selection.get("learned_context")
        if isinstance(selection.get("learned_context"), dict)
        else {}
    )
    profile_name = str(profile.get("name") or "current")
    learned_selected = int(learned_selection.get("selected", 0) or 0)
    learned_candidates = int(learned_selection.get("candidate_count", 0) or 0)
    if context_id and record_id:
        enriched["memory_detail_href"] = f"/memories/changes/{context_id}?item={record_id}"
    else:
        enriched["memory_detail_href"] = "/memories/changes"

    if change_class == "suppressed" and reason_code == "profile_budget_exceeded":
        enriched.update(
            {
                "retention_effect": "still_active_not_purged",
                "operator_summary": (
                    "Not purged: this learned-context record is still active. It was only left out "
                    f"of this assembled context because the {profile_name} profile had room for "
                    f"{learned_selected} of {learned_candidates} learned-context candidates."
                ),
                "operator_severity": "info",
                "operator_next_actions": [
                    "Usually no action is required; this is normal context-budget pruning.",
                    "Use a more specific query if this item should outrank nearby learned context.",
                    "Run prepare-context with --limit 8 or higher when you need the deeper task profile.",
                ],
            }
        )
    elif change_class == "suppressed":
        enriched.update(
            {
                "retention_effect": "still_active_not_purged",
                "operator_summary": (
                    "Not purged: this learned-context record is still active, but this context did "
                    f"not inject it because {enriched.get('reason_label') or reason_code}."
                ),
                "operator_severity": "info",
                "operator_next_actions": [
                    "Inspect the reason and source context before changing memory.",
                    "Refine the query or semantic setup if this item should appear more often.",
                ],
            }
        )
    elif change_class == "kept":
        enriched.update(
            {
                "retention_effect": "included_in_context",
                "operator_summary": (
                    "Included: this learned-context record was active and injected into the assembled context."
                ),
                "operator_severity": "good",
                "operator_next_actions": ["No action is required unless the content looks stale or misleading."],
            }
        )
    elif change_class == "deactivated":
        enriched.update(
            {
                "retention_effect": "removed_from_active_learned_context",
                "operator_summary": (
                    "Removed from active learned context; it will not be injected unless restored or replaced."
                ),
                "operator_severity": "warn" if enriched.get("restore_allowed") else "bad",
                "operator_next_actions": [
                    "Restore it if the removal was wrong and it is still inside the restore window.",
                    "Inspect superseding or verifier evidence before restoring stale content.",
                ],
            }
        )
    elif change_class == "restored":
        enriched.update(
            {
                "retention_effect": "restored_to_active_learned_context",
                "operator_summary": "Restored: this learned-context record is active again.",
                "operator_severity": "good",
                "operator_next_actions": ["No action is required unless it should be superseded by fresher evidence."],
            }
        )
    else:
        enriched.update(
            {
                "retention_effect": "unknown",
                "operator_summary": "Open the source context to inspect this learned-context change.",
                "operator_severity": "info",
                "operator_next_actions": ["Inspect source context and provenance before changing memory."],
            }
        )
    return enriched


def _learned_context_transition_items(
    store: MemoryStore,
    *,
    now: str,
    source_context_id: str,
    source_run_id: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    now_ts = parse_timestamp(now)
    for record in store.load_learned_context_records():
        status = str(record.get("status") or "")
        if status in _LEARNED_CONTEXT_DEACTIVATED_STATUSES:
            restorable_until = str(record.get("restorable_until") or "")
            restore_allowed = False
            if restorable_until:
                try:
                    restore_allowed = parse_timestamp(restorable_until) >= now_ts
                except (TypeError, ValueError):
                    restore_allowed = False
            items.append(
                {
                    "record_id": str(record.get("record_id") or ""),
                    "summary": str(record.get("summary") or ""),
                    "details_preview": str(record.get("details") or record.get("summary") or "")[:180],
                    "before_state": "active",
                    "after_state": status,
                    "change_class": "deactivated",
                    "reason_code": status,
                    "reason_label": _semantic_change_reason_label(status),
                    "changed_at": record.get("status_changed_at") or record.get("created_at"),
                    "source_run_id": source_run_id or None,
                    "source_context_id": source_context_id or None,
                    "restore_allowed": restore_allowed,
                    "restorable_until": record.get("restorable_until"),
                    "superseded_by": record.get("superseded_by"),
                    "confidence": record.get("confidence"),
                    "query_family_tags": list(record.get("query_family_tags") or []),
                    "score": None,
                    "provenance_link_target": "/overview",
                }
            )
            continue
        if status == "active" and record.get("restored_at"):
            items.append(
                {
                    "record_id": str(record.get("record_id") or ""),
                    "summary": str(record.get("summary") or ""),
                    "details_preview": str(record.get("details") or record.get("summary") or "")[:180],
                    "before_state": str(record.get("restored_from_status") or "unknown"),
                    "after_state": "active",
                    "change_class": "restored",
                    "reason_code": "record_restored",
                    "reason_label": _semantic_change_reason_label("record_restored"),
                    "changed_at": record.get("restored_at") or record.get("created_at"),
                    "source_run_id": source_run_id or None,
                    "source_context_id": source_context_id or None,
                    "restore_allowed": False,
                    "restorable_until": None,
                    "superseded_by": None,
                    "confidence": record.get("confidence"),
                    "query_family_tags": list(record.get("query_family_tags") or []),
                    "score": None,
                    "provenance_link_target": "/overview",
                }
            )
    items.sort(
        key=lambda item: (
            str(item.get("changed_at") or ""),
            str(item.get("record_id") or ""),
        ),
        reverse=True,
    )
    return items[:24]


def _latest_context_pruning(store: MemoryStore) -> dict[str, Any]:
    contexts = store.load_context_assemblies()
    if not contexts:
        return empty_context_pruning()
    latest = max(contexts, key=lambda item: str(item.get("created_at", "")))
    pruning = latest.get("context_pruning")
    if not isinstance(pruning, dict) or not pruning:
        return empty_context_pruning()
    profile = latest.get("profile")
    profile_name = profile.get("name") if isinstance(profile, dict) else profile
    return {
        "status": "available",
        "profile": str(profile_name or pruning.get("profile") or ""),
        "raw_candidate_count": int(pruning.get("candidate_count", pruning.get("raw_candidate_count", 0)) or 0),
        "injected_count": int(pruning.get("injected_count", 0) or 0),
        "suppressed_count": int(pruning.get("suppressed_count", 0) or 0),
        "saved_characters": int(pruning.get("saved_characters", 0) or 0),
        "saved_token_estimate": int(pruning.get("saved_token_estimate", 0) or 0),
        "observed_at": latest.get("created_at"),
    }


def _build_memory_excellence_overview(store: MemoryStore, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build memory-excellence summary for observability overview."""
    provenance_counts: dict[str, int] = defaultdict(int)
    claim_class_counts: dict[str, int] = defaultdict(int)
    for record in records:
        provenance_counts[record.get("provenance_tier", "inferred")] += 1
        claim_class_counts[record.get("claim_class", "derived_abstraction")] += 1

    relation_edges = read_json(store.relation_edges_path, [])
    edge_kind_counts: dict[str, int] = defaultdict(int)
    for edge in relation_edges:
        edge_kind_counts[edge.get("kind", "unknown")] += 1

    verification_reports = _load_json_records(store.audit_claim_verification_dir)
    reconciliation_reports = _load_json_records(store.audit_reconciliation_dir)
    boundary_reports = _load_json_records(store.audit_boundary_dir)
    probe_reports = _load_json_records(store.audit_transcript_probe_dir)

    return {
        "provenance_tiers": dict(sorted(provenance_counts.items())),
        "claim_classes": dict(sorted(claim_class_counts.items())),
        "relation_edges": {
            "total": len(relation_edges),
            "by_kind": dict(sorted(edge_kind_counts.items())),
        },
        "verification_reports": len(verification_reports),
        "reconciliation_reports": len(reconciliation_reports),
        "boundary_reports": len(boundary_reports),
        "boundary_violations": sum(
            1 for r in boundary_reports if not r.get("passed", True) and r.get("violations")
        ),
        "probe_reports": len(probe_reports),
    }


def _build_runtime_management_overview(store: MemoryStore, timestamp: str) -> dict[str, Any]:
    from .service import service_status

    status = service_status(store, now=timestamp) if store.is_initialized() else {
        "installed": False,
        "running": False,
        "health": "not-installed",
        "backlog": 0,
        "active_phase": None,
        "last_success_at": None,
        "semantic_runtime": {
            "state": "awaiting_signal",
            "work_mode": "deterministic",
            "summary": "semantic runtime is not available because the workspace is not initialized",
            "reason": "workspace is not initialized",
            "has_pending_signal": False,
            "latest_signal_source": None,
            "latest_signal_timestamp": None,
            "signal_row_count": 0,
            "active_learned_context": 0,
            "last_semantic_run": None,
        },
        "policy": {"management_mode": "disabled", "auto_ensure": False, "source": "default"},
    }
    policy = status.get("policy") or {}
    semantic_runtime = status.get("semantic_runtime") or {}
    return {
        "policy_mode": policy.get("management_mode", "unknown"),
        "auto_ensure": bool(policy.get("auto_ensure", False)),
        "policy_source": policy.get("source", "unknown"),
        "installed": bool(status.get("installed", False)),
        "running": bool(status.get("running", False)),
        "health": str(status.get("health", "unknown")),
        "backlog": int(status.get("backlog", 0) or 0),
        "active_phase": status.get("active_phase"),
        "last_success_at": status.get("last_success_at"),
        "semantic_runtime": semantic_runtime,
        "summary": _runtime_management_summary(status, semantic_runtime),
    }


def _runtime_management_summary(status: dict[str, Any], semantic_runtime: dict[str, Any]) -> str:
    policy = status.get("policy") or {}
    mode = str(policy.get("management_mode", "unknown"))
    if mode == "disabled":
        return "background runtime is disabled by operator choice"
    if not status.get("installed"):
        return "background runtime is managed but not installed yet"
    semantic_state = str(semantic_runtime.get("state") or "")
    semantic_summary = str(semantic_runtime.get("summary") or "")
    if status.get("running"):
        if semantic_state in {"awaiting_materialization", "no_materialization", "blocked"} and semantic_summary:
            return semantic_summary
        return f"background runtime is running with health {status.get('health', 'unknown')}"
    return "background runtime is installed but not currently running"


def _build_memory_surface(
    store: MemoryStore,
    records: list[dict[str, Any]],
    *,
    now: str,
) -> dict[str, Any]:
    active_durable = [record for record in records if record.get("status") == "active"]
    contested = [record for record in records if record.get("status") == "contested"]
    learned_context_records = store.load_learned_context_records()
    learned_context = [record for record in learned_context_records if record.get("status") == "active"]
    recent_pruned_learned_context = _recent_pruned_learned_context(learned_context_records, now=now)
    type_counts = Counter(str(record.get("type", "unknown")) for record in active_durable)
    type_mix = [
        {"type": memory_type, "count": count}
        for memory_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    recent_highlights = [
        {
            "memory_id": record.get("memory_id"),
            "title": record.get("title"),
            "type": record.get("type"),
            "status": record.get("status"),
            "updated_at": record.get("updated_at") or record.get("created_at"),
            "summary": record.get("summary"),
        }
        for record in sorted(
            active_durable,
            key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
            reverse=True,
        )[:5]
    ]
    startup_entries = store.load_startup_index().get("entries", [])
    low_signal_count = sum(1 for record in active_durable if str(record.get("type", "")) in LOW_SIGNAL_TYPES)
    return {
        "durable_active_total": len(active_durable),
        "durable_contested_total": len(contested),
        "learned_context_active_total": len(learned_context),
        "learned_context_recently_pruned_total": len(recent_pruned_learned_context),
        "low_signal_share": round(low_signal_count / max(len(active_durable), 1), 3) if active_durable else 0.0,
        "type_mix": type_mix,
        "recent_highlights": recent_highlights,
        "recent_pruned_learned_context": recent_pruned_learned_context,
        "startup_highlights": [
            {
                "memory_id": entry.get("memory_id"),
                "title": entry.get("title"),
                "type": entry.get("type"),
                "summary": entry.get("summary"),
            }
            for entry in startup_entries[:5]
        ],
    }


def _recent_pruned_learned_context(records: list[dict[str, Any]], *, now: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    now_ts = parse_timestamp(now)
    for record in records:
        status = str(record.get("status") or "")
        if status == "active":
            continue
        changed_at = str(record.get("status_changed_at") or record.get("created_at") or "")
        restorable_until = str(record.get("restorable_until") or "")
        restore_allowed = False
        if restorable_until:
            try:
                restore_allowed = parse_timestamp(restorable_until) >= now_ts
            except (TypeError, ValueError):
                restore_allowed = False
        items.append(
            {
                "record_id": record.get("record_id"),
                "summary": record.get("summary"),
                "status": status or "unknown",
                "status_changed_at": changed_at or None,
                "restorable_until": restorable_until or None,
                "restore_allowed": restore_allowed,
                "superseded_by": record.get("superseded_by"),
                "confidence": record.get("confidence"),
            }
        )
    items.sort(
        key=lambda item: (
            str(item.get("status_changed_at") or ""),
            str(item.get("record_id") or ""),
        ),
        reverse=True,
    )
    return items[:5]


def _build_last_runtime_effects(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {
            "status": "not_available",
            "run_id": None,
            "run_type": None,
            "ended_at": None,
            "summary_line": "no runtime mutations recorded yet",
            "change_counts": {},
            "target_memory_ids": [],
            "target_paths": [],
        }

    latest = runs[0]
    summary = latest.get("summary", {}) if isinstance(latest.get("summary"), dict) else {}
    run_type = str(latest.get("type") or "unknown")
    change_counts: dict[str, Any]
    if run_type == "consolidation":
        change_counts = {
            "created": int(summary.get("created", 0) or 0),
            "updated": int(summary.get("updated", 0) or 0),
            "superseded": int(summary.get("superseded", 0) or 0),
            "contested": int(summary.get("contested", 0) or 0),
            "quarantined": int(summary.get("quarantined", 0) or 0),
        }
    elif run_type == "dream":
        maintain = summary.get("maintain", {}) if isinstance(summary.get("maintain"), dict) else {}
        change_counts = {
            "appended_events": int(summary.get("appended_events", 0) or 0),
            "gathered_rows": int(summary.get("gathered_rows", 0) or 0),
            "created": int(maintain.get("consolidate", {}).get("created", 0) or 0),
            "updated": int(maintain.get("consolidate", {}).get("updated", 0) or 0),
            "superseded": int(maintain.get("consolidate", {}).get("superseded", 0) or 0),
        }
    else:
        semantic_summary = (
            summary.get("semantic_summary", {})
            if isinstance(summary.get("semantic_summary"), dict)
            else {}
        )
        change_counts = {
            "learned_context_created": int(summary.get("learned_context_created", 0) or 0),
            "families_selected": int(
                summary.get("query_families_selected", 0) or semantic_summary.get("families_selected", 0) or 0
            ),
            "proposals_generated": int(
                summary.get("proposals_generated", 0) or semantic_summary.get("proposals_generated", 0) or 0
            ),
            "proposals_approved": int(
                summary.get("proposals_approved", 0) or semantic_summary.get("proposals_approved", 0) or 0
            ),
        }
    target_memory_ids = [
        str(op.get("target_memory_id"))
        for op in latest.get("operations", [])
        if op.get("target_memory_id")
    ]
    return {
        "status": "available",
        "run_id": latest.get("run_id"),
        "run_type": run_type,
        "ended_at": latest.get("ended_at"),
        "summary_line": _runtime_effect_summary(run_type, change_counts),
        "change_counts": change_counts,
        "target_memory_ids": sorted(set(target_memory_ids)),
        "target_paths": latest.get("target_paths", []),
        "diff_available": bool(latest.get("diff_text")),
    }


def _runtime_effect_summary(run_type: str, change_counts: dict[str, Any]) -> str:
    if run_type == "consolidation":
        return (
            f"consolidation created {change_counts.get('created', 0)}, "
            f"updated {change_counts.get('updated', 0)}, "
            f"and superseded {change_counts.get('superseded', 0)} memories"
        )
    if run_type == "dream":
        return (
            f"dream appended {change_counts.get('appended_events', 0)} events and "
            f"created {change_counts.get('created', 0)} durable memories"
        )
    return (
        f"semantic dream created {change_counts.get('learned_context_created', 0)} learned-context records "
        f"from {change_counts.get('proposals_generated', 0)} proposals"
    )


def _semantic_quality_surface(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    report = analyze_memory_quality(store, now=now)
    posture_map = {
        "semantic_first": "semantic-first",
        "deterministic_only": "deterministic-by-choice",
    }
    return {
        "product_posture": posture_map.get(report["product_posture"], str(report["product_posture"])),
        "semantic_capability_state": report["semantic_capability_state"],
        "semantic_unavailability_reason": report["semantic_unavailability_reason"],
        "memory_quality": report["memory_quality"],
        "next_action": report["next_action"],
    }


def _build_entities(store: MemoryStore) -> dict[str, Any]:
    memories = _build_memory_entities(store)
    runs = _load_run_records(store)
    retrievals = _load_retrieval_entities(store)
    contexts = _load_context_entities(store)
    context_use = _load_context_use_entities(store, contexts)
    sessions = _build_session_entities(store, contexts)
    annotations = store.load_annotations()
    reviews = _build_review_queue(store, memories, retrievals, runs)
    evals = _build_eval_entities(store)
    exports = store.load_export_records()
    health = _build_health(memories, retrievals, runs, reviews)
    relation_edges = read_json(store.relation_edges_path, [])
    graph = _build_graph_entities(
        memories,
        retrievals,
        runs,
        contexts,
        context_use,
        annotations,
        reviews,
        relation_edges,
    )
    verification_reports = _load_json_records(store.audit_claim_verification_dir)
    probe_reports = _load_json_records(store.audit_transcript_probe_dir)
    reconciliation_reports = _load_json_records(store.audit_reconciliation_dir)
    boundary_reports = _load_json_records(store.audit_boundary_dir)
    return {
        "memories": memories,
        "runs": runs,
        "retrievals": retrievals,
        "contexts": contexts,
        "context_use": context_use,
        "sessions": sessions,
        "annotations": annotations,
        "reviews": reviews,
        "evals": evals,
        "exports": exports,
        "health": health,
        "graph": graph,
        "relation_edges": relation_edges,
        "verification_reports": verification_reports,
        "probe_reports": probe_reports,
        "reconciliation_reports": reconciliation_reports,
        "boundary_reports": boundary_reports,
    }


def _build_memory_entities(store: MemoryStore) -> list[dict[str, Any]]:
    records = store.load_durable_records()
    events_by_id = {str(event.get("event_id", "")): event for event in store.load_events()}
    retrievals = _load_json_records(store.audit_retrieval_dir)
    annotations = store.load_annotations()
    reviews = store.load_review_decisions()
    retrieval_counts: dict[str, int] = defaultdict(int)
    for retrieval in retrievals:
        for memory_id in retrieval.get("selected_memory_ids", []):
            retrieval_counts[str(memory_id)] += 1
    annotation_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        annotation_map[str(annotation.get("object_id", ""))].append(annotation)
    review_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        review_map[str(review.get("queue_item_id", ""))].append(review)
    items: list[dict[str, Any]] = []
    by_id = {record["memory_id"]: record for record in records}
    for record in records:
        memory_id = str(record["memory_id"])
        reporting_agents = _agents_for_event_ids(
            events_by_id,
            [str(event_id) for event_id in record.get("source_event_ids", [])],
        )
        reporting_agent_label = ", ".join(agent["agent_label"] for agent in reporting_agents)
        items.append(
            {
                **record,
                "source_count": len(record.get("source_event_ids", [])),
                "reporting_agents": reporting_agents,
                "reporting_agent_label": reporting_agent_label,
                "retrieval_frequency": retrieval_counts.get(memory_id, 0),
                "annotations": annotation_map.get(memory_id, []),
                "manual_reviews": review_map.get(memory_id, []),
                "superseded_by": [
                    candidate["memory_id"]
                    for candidate in records
                    if memory_id in candidate.get("supersedes", [])
                ],
                "lineage": {
                    "supersedes": record.get("supersedes", []),
                    "conflicts_with": record.get("conflicts_with", []),
                },
                "raw_json": record,
                "source_paths": _find_source_paths(store, record),
                "provenance": {
                    "source_event_ids": record.get("source_event_ids", []),
                    "topic_path": str(store.topics_dir / f"{memory_id}.md"),
                },
            }
        )
    for item in items:
        item["contended"] = item["status"] == "contested" or bool(item.get("conflicts_with"))
        item["compare_candidates"] = [
            by_id[memory_id]
            for memory_id in item.get("conflicts_with", []) + item.get("supersedes", [])
            if memory_id in by_id
        ]
    return items


def get_memory_detail(store: MemoryStore, memory_id: str) -> dict[str, Any] | None:
    records = store.load_durable_records()
    by_id = {
        str(record.get("memory_id")): record
        for record in records
        if isinstance(record, dict) and record.get("memory_id")
    }
    record = by_id.get(memory_id)
    if record is None:
        return None
    events_by_id = {str(event.get("event_id", "")): event for event in store.load_events()}
    annotations = [
        annotation
        for annotation in store.load_annotations()
        if str(annotation.get("object_id", "")) == memory_id
    ]
    reviews = [
        review
        for review in store.load_review_decisions()
        if str(review.get("queue_item_id", "")) == memory_id
    ]
    source_event_ids = [str(event_id) for event_id in record.get("source_event_ids", [])]
    reporting_agents = _agents_for_event_ids(events_by_id, source_event_ids)
    item = {
        **record,
        "source_count": len(source_event_ids),
        "reporting_agents": reporting_agents,
        "reporting_agent_label": ", ".join(agent["agent_label"] for agent in reporting_agents),
        "annotations": annotations,
        "manual_reviews": reviews,
        "superseded_by": [
            candidate_id
            for candidate_id, candidate in by_id.items()
            if memory_id in candidate.get("supersedes", [])
        ],
        "lineage": {
            "supersedes": record.get("supersedes", []),
            "conflicts_with": record.get("conflicts_with", []),
        },
        "raw_json": record,
        "source_paths": _find_source_paths(store, record),
        "provenance": {
            "source_event_ids": record.get("source_event_ids", []),
            "topic_path": str(store.topics_dir / f"{memory_id}.md"),
        },
    }
    item["contended"] = item.get("status") == "contested" or bool(item.get("conflicts_with"))
    item["compare_candidates"] = [
        by_id[candidate_id]
        for candidate_id in item.get("conflicts_with", []) + item.get("supersedes", [])
        if candidate_id in by_id
    ]
    return item


def get_memory_lineage(store: MemoryStore, memory_id: str) -> dict[str, Any]:
    memory = get_memory_detail(store, memory_id)
    if memory is None:
        return {}
    lineage = dict(memory.get("lineage", {}))
    if memory.get("superseded_by"):
        lineage["superseded_by"] = memory.get("superseded_by")
    return lineage


def get_context_detail(store: MemoryStore, context_id: str) -> dict[str, Any] | None:
    if not context_id or "/" in context_id or "\\" in context_id:
        return None
    path = store.audit_context_dir / f"{context_id}.json"
    if not path.exists():
        return None
    context = read_json(path, {})
    if not isinstance(context, dict):
        return None
    context.setdefault("source_path", str(path))
    context_use_records = [
        record
        for record in _load_context_use_entities(store, [context])
        if str(record.get("context_id") or "") == context_id
    ]
    context_use_records.sort(
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("usage_id") or "")),
        reverse=True,
    )
    latest_use = context_use_records[0] if context_use_records else None
    return {
        **context,
        "display_name": project_context_list_row(context).get("display_name"),
        "context_use_records": context_use_records,
        "context_use_count": len(context_use_records),
        "latest_memory_use_state": latest_use.get("memory_use_state") if latest_use else "not-recorded",
        "latest_context_use_id": latest_use.get("usage_id") if latest_use else None,
    }


def get_context_use_detail(store: MemoryStore, usage_id: str) -> dict[str, Any] | None:
    if not usage_id or "/" in usage_id or "\\" in usage_id:
        return None
    path = store.audit_context_use_dir / f"{usage_id}.json"
    if not path.exists():
        return None
    record = read_json(path, {})
    if not isinstance(record, dict):
        return None
    contexts = _load_context_entities(store)
    enriched = _load_context_use_entities(store, contexts, records=[record])
    if not enriched:
        return None
    enriched[0].setdefault("source_path", str(path))
    return enriched[0]


def _normalize_event_reporting_agent(event: dict[str, Any]) -> dict[str, str]:
    raw = event.get("reporting_agent")
    source = event.get("source")
    if not isinstance(raw, dict):
        raw = {}
    raw_agent_id = str(raw.get("agent_id") or "").strip()
    raw_agent_label = str(raw.get("agent_label") or "").strip()
    inferred = _infer_reporting_agent_from_source(source) if raw_agent_id in {"", "unknown"} else {}
    agent_id = raw_agent_id if raw_agent_id and raw_agent_id != "unknown" else str(
        inferred.get("agent_id") or "unknown"
    )
    agent_label = raw_agent_label if raw_agent_label and raw_agent_label != "Unknown" else str(
        inferred.get("agent_label") or agent_id or "Unknown"
    )
    result = {"agent_id": agent_id, "agent_label": agent_label}
    for key in ("runtime", "adapter_id"):
        value = str(raw.get(key) or inferred.get(key) or "")
        if value:
            result[key] = value
    for key in ("model_id", "model_version"):
        value = str(raw.get(key) or "")
        if value:
            result[key] = value
    result.setdefault("model_id", "unknown")
    result.setdefault("model_version", "unknown")
    return result


def _infer_reporting_agent_from_source(source: Any) -> dict[str, str]:
    if not isinstance(source, dict):
        return {}
    message_ref = str(source.get("message_ref") or "").casefold()
    tool_refs = " ".join(str(item).casefold() for item in source.get("tool_refs", []) if item)
    haystack = f"{message_ref} {tool_refs}"
    if "codex" in haystack:
        return {
            "agent_id": "codex",
            "agent_label": "Codex",
            "runtime": "codex-cli",
            "adapter_id": "codex-account",
        }
    if "claude" in haystack:
        return {
            "agent_id": "claude-code",
            "agent_label": "Claude Code",
            "runtime": "claude-code",
            "adapter_id": "claude-code",
        }
    if "cursor" in haystack:
        return {
            "agent_id": "cursor",
            "agent_label": "Cursor",
            "runtime": "cursor",
            "adapter_id": "cursor-automation",
        }
    if "openclaw" in haystack:
        return {
            "agent_id": "openclaw",
            "agent_label": "OpenClaw",
            "runtime": "openclaw",
            "adapter_id": "openclaw",
        }
    return {}


def _agent_search_text(agent: Any) -> str:
    if not isinstance(agent, dict):
        return ""
    return " ".join(
        str(agent.get(key, ""))
        for key in ("agent_id", "agent_label", "runtime", "adapter_id", "model_id", "model_version")
    )


def _row_has_agent(row: dict[str, Any], agent_id: str, *, fields: tuple[str, ...]) -> bool:
    for field in fields:
        value = row.get(field)
        if isinstance(value, dict) and str(value.get("agent_id", "")) == agent_id:
            return True
        if isinstance(value, list) and any(
            isinstance(agent, dict) and str(agent.get("agent_id", "")) == agent_id for agent in value
        ):
            return True
    return False


def _agents_for_event_ids(
    events_by_id: dict[str, dict[str, Any]],
    event_ids: list[str],
) -> list[dict[str, str]]:
    agents_by_id: dict[str, dict[str, str]] = {}
    for event_id in event_ids:
        event = events_by_id.get(event_id)
        if not event:
            agent = {"agent_id": "unknown", "agent_label": "Unknown"}
        else:
            agent = _normalize_event_reporting_agent(event)
        agents_by_id.setdefault(agent["agent_id"], agent)
    if not agents_by_id:
        agents_by_id["unknown"] = {"agent_id": "unknown", "agent_label": "Unknown"}
    return sorted(agents_by_id.values(), key=lambda item: (item["agent_label"].casefold(), item["agent_id"]))


def _load_run_records(store: MemoryStore) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    events_by_id = {str(event.get("event_id", "")): event for event in store.load_events()}
    for summary_path in sorted(store.audit_consolidation_dir.glob("*-summary.json"), reverse=True):
        summary = read_json(summary_path, {})
        run_id = str(summary.get("run_id") or summary_path.stem.replace("-summary", ""))
        op_path = store.audit_consolidation_dir / f"{run_id}.jsonl"
        diff_path = store.audit_consolidation_dir / f"{run_id}.diff"
        operations = []
        run_event_ids: list[str] = []
        for payload in _load_jsonl(op_path):
            source_event_ids = [str(event_id) for event_id in payload.get("source_event_ids", [])]
            run_event_ids.extend(source_event_ids)
            op = ObservabilityConsolidationOp(
                id=str(payload.get("op_id", stable_id("op", run_id, payload))),
                run_id=run_id,
                phase="consolidation",
                op_type=str(payload.get("op", "unknown")),
                target_memory_id=str(payload.get("target_id")) if payload.get("target_id") else None,
                source_candidate_ids=[],
                before_snapshot={},
                after_snapshot=dict(payload.get("payload", {})),
                reason=str(payload.get("reason", "")),
                created_at=str(payload.get("timestamp", "")),
            ).to_dict()
            op["source_event_ids"] = source_event_ids
            op["source_reporting_agents"] = _agents_for_event_ids(events_by_id, source_event_ids)
            operations.append(op)
        source_reporting_agents = _agents_for_event_ids(events_by_id, run_event_ids)
        summary_payload = summary.get("summary", {})
        started_at = (
            summary_payload.get("started_at")
            or summary_payload.get("generated_at")
        )
        ended_at = (
            summary_payload.get("completed_at")
            or summary_payload.get("generated_at")
            or started_at
        )
        runs.append(
            {
                "id": run_id,
                "run_id": run_id,
                "type": "consolidation",
                "started_at": started_at,
                "ended_at": ended_at,
                "status": summary_payload.get("status", "completed"),
                "summary": summary_payload,
                "target_paths": summary.get("target_paths", []),
                "diff_path": str(diff_path) if diff_path.exists() else None,
                "diff_text": diff_path.read_text(encoding="utf-8") if diff_path.exists() else "",
                "operations": operations,
                "source_reporting_agents": source_reporting_agents,
                "reporting_agent_label": ", ".join(agent["agent_label"] for agent in source_reporting_agents),
                "phase_traces": _phase_traces_for_consolidation(run_id, summary, operations),
                "warnings": _collect_run_warnings(summary, operations),
                "source_paths": [str(summary_path), str(op_path), str(diff_path)],
            }
        )
    for summary_path in sorted(store.audit_dream_dir.glob("*-summary.json"), reverse=True):
        summary = read_json(summary_path, {})
        run_id = str(summary.get("run_id") or summary_path.stem.replace("-summary", ""))
        diff_path = store.audit_dream_dir / f"{run_id}.diff"
        dream_summary = summary.get("summary", {})
        runs.append(
            {
                "id": run_id,
                "run_id": run_id,
                "type": "dream",
                "started_at": dream_summary.get("last_started_at"),
                "ended_at": dream_summary.get("last_ran_at"),
                "status": dream_summary.get("status", summary.get("action", "completed")),
                "summary": dream_summary,
                "target_paths": summary.get("target_paths", []),
                "diff_path": str(diff_path) if diff_path.exists() else None,
                "diff_text": diff_path.read_text(encoding="utf-8") if diff_path.exists() else "",
                "operations": [],
                "source_reporting_agents": [{"agent_id": "opendream", "agent_label": "OpenDream"}],
                "reporting_agent_label": "OpenDream",
                "phase_traces": _phase_traces_for_dream(run_id, dream_summary, summary.get("target_paths", [])),
                "warnings": [dream_summary["reason"]] if "reason" in dream_summary else [],
                "source_paths": [str(summary_path), str(diff_path)],
            }
        )
    for summary_path in sorted(store.audit_semantic_dream_dir.glob("*-summary.json"), reverse=True):
        summary = read_json(summary_path, {})
        run_id = str(summary.get("run_id") or summary_path.stem.replace("-summary", ""))
        diff_path = store.audit_semantic_dream_dir / f"{run_id}.diff"
        semantic_summary = summary.get("summary", {})
        runs.append(
            {
                "id": run_id,
                "run_id": run_id,
                "type": "semantic_dream",
                "started_at": semantic_summary.get("started_at"),
                "ended_at": semantic_summary.get("ended_at"),
                "status": semantic_summary.get("status", summary.get("action", "completed")),
                "summary": semantic_summary,
                "target_paths": summary.get("target_paths", []),
                "diff_path": str(diff_path) if diff_path.exists() else None,
                "diff_text": diff_path.read_text(encoding="utf-8") if diff_path.exists() else "",
                "operations": [],
                "source_reporting_agents": [{"agent_id": "opendream", "agent_label": "OpenDream"}],
                "reporting_agent_label": "OpenDream",
                "phase_traces": _phase_traces_for_dream(run_id, semantic_summary, summary.get("target_paths", [])),
                "warnings": [semantic_summary["reason"]] if "reason" in semantic_summary else [],
                "source_paths": [str(summary_path), str(diff_path)],
            }
        )
    runs.sort(key=lambda item: str(item.get("ended_at") or item.get("started_at") or item["id"]), reverse=True)
    return runs


def _load_retrieval_entities(store: MemoryStore) -> list[dict[str, Any]]:
    items = []
    events_by_id = {str(event.get("event_id", "")): event for event in store.load_events()}
    records_by_id = {str(record.get("memory_id", "")): record for record in store.load_durable_records()}
    for path in sorted(store.audit_retrieval_dir.glob("*.json"), reverse=True):
        payload = read_json(path, {})
        payload.setdefault("id", payload.get("run_id", path.stem))
        payload.setdefault("source_path", str(path))
        payload.setdefault("reporting_agent", {"agent_id": "unknown", "agent_label": "Unknown"})
        source_event_ids: list[str] = []
        for memory_id in payload.get("selected_memory_ids", []):
            record = records_by_id.get(str(memory_id))
            if record:
                source_event_ids.extend(str(event_id) for event_id in record.get("source_event_ids", []))
        payload["source_reporting_agents"] = _agents_for_event_ids(events_by_id, source_event_ids)
        payload["reporting_agent_label"] = str(payload.get("reporting_agent", {}).get("agent_label", "Unknown"))
        payload["near_threshold"] = payload.get("excluded", [])
        payload["final_context_assembly_order"] = payload.get("selected_memory_ids", [])
        items.append(payload)
    return items


def _load_context_entities(store: MemoryStore) -> list[dict[str, Any]]:
    items = store.load_context_assemblies()
    context_use_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in store.load_context_use_records():
        if isinstance(record, dict):
            context_use_by_id[str(record.get("context_id") or "")].append(record)
    for records in context_use_by_id.values():
        records.sort(
            key=lambda item: (str(item.get("timestamp") or ""), str(item.get("usage_id") or "")),
            reverse=True,
        )
    for item in items:
        context_id = str(item.get("context_id") or "")
        records = context_use_by_id.get(context_id, [])
        latest = records[0] if records else None
        item["context_use_count"] = len(records)
        item["latest_memory_use_state"] = latest.get("memory_use_state") if latest else "not-recorded"
        if latest and latest.get("usage_id"):
            item["latest_context_use_id"] = latest.get("usage_id")
    items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return items


def _load_context_use_entities(
    store: MemoryStore,
    contexts: list[dict[str, Any]],
    *,
    records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    context_by_id = {str(item.get("context_id") or ""): item for item in contexts}
    items: list[dict[str, Any]] = []
    source_records = records if records is not None else store.load_context_use_records()
    for record in source_records:
        if not isinstance(record, dict):
            continue
        context_id = str(record.get("context_id") or "")
        context = context_by_id.get(context_id)
        enriched = dict(record)
        enriched.setdefault("usage_id", stable_id("context_use", record))
        enriched.setdefault("memory_use_state", "unknown")
        if context:
            enriched["context_query"] = _context_query_text(context)
            enriched["context_display_name"] = project_context_list_row(context).get("display_name")
            selected_ids = context.get("selected_memory_ids")
            if "selected_memory_ids" not in enriched and isinstance(selected_ids, list):
                enriched["selected_memory_ids"] = selected_ids
        items.append(enriched)
    items.sort(
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("usage_id") or "")),
        reverse=True,
    )
    return items


def _build_session_entities(store: MemoryStore, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in store.load_events():
        grouped_events[str(event.get("session_id", "unknown"))].append(event)
    grouped_contexts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for context in contexts:
        grouped_contexts[str(context.get("session_id", "unknown"))].append(context)
    sessions: list[dict[str, Any]] = []
    session_ids = sorted(set(grouped_events) | set(grouped_contexts))
    for session_id in session_ids:
        timeline = []
        session_agents: dict[str, dict[str, str]] = {}
        for event in grouped_events.get(session_id, []):
            agent = _normalize_event_reporting_agent(event)
            session_agents.setdefault(agent["agent_id"], agent)
            timeline.append(
                {
                    "timestamp": event.get("timestamp"),
                    "kind": "memory.event.emitted",
                    "label": event.get("kind"),
                    "object_id": event.get("event_id"),
                    "reporting_agent": agent,
                    "payload": event,
                }
            )
        for context in grouped_contexts.get(session_id, []):
            context_id = str(context.get("context_id") or "")
            context_query = _context_query_text(context)
            context_label = _compact_display_label(context_query, context_id or "context")
            timeline.append(
                {
                    "timestamp": context.get("created_at"),
                    "kind": "memory.context.assembled",
                    "label": context_label,
                    "object_id": context_id,
                    "payload": {**context, "display_name": context_label},
                }
            )
        timeline.sort(key=lambda item: str(item.get("timestamp", "")))
        started_at = timeline[0].get("timestamp") if timeline else None
        ended_at = timeline[-1].get("timestamp") if timeline else None
        latest_contexts = sorted(
            grouped_contexts.get(session_id, []),
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("context_id") or ""),
            ),
            reverse=True,
        )
        latest_context = latest_contexts[0] if latest_contexts else None
        latest_context_query = _context_query_text(latest_context)
        session_display_name = _compact_display_label(latest_context_query, session_id)
        sessions.append(
            {
                "id": session_id,
                "session_id": session_id,
                "display_name": session_display_name,
                "event_count": len(grouped_events.get(session_id, [])),
                "context_count": len(grouped_contexts.get(session_id, [])),
                "started_at": started_at,
                "ended_at": ended_at,
                "last_activity_at": ended_at,
                "reporting_agents": sorted(
                    session_agents.values(),
                    key=lambda item: (item["agent_label"].casefold(), item["agent_id"]),
                )
                or [{"agent_id": "unknown", "agent_label": "Unknown"}],
                "latest_context_id": latest_context.get("context_id") if latest_context else None,
                "latest_context_query": latest_context_query,
                "timeline": timeline,
            }
        )
    sessions.sort(
        key=lambda item: (
            str(item.get("last_activity_at") or ""),
            str(item.get("session_id") or ""),
        ),
        reverse=True,
    )
    return sessions


def _build_review_queue(
    store: MemoryStore,
    memories: list[dict[str, Any]],
    retrievals: list[dict[str, Any]],
    runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions = store.load_review_decisions()
    decided_ids = {str(item.get("queue_item_id", "")) for item in decisions}
    queue: list[dict[str, Any]] = []
    for memory in memories:
        if memory["memory_id"] in decided_ids:
            continue
        reason = None
        queue_type = None
        if memory["status"] == "contested":
            queue_type = "contested_memory"
            reason = "Memory is contested"
        elif float(memory.get("confidence", 0.0)) < 0.65:
            queue_type = "low_confidence_memory"
            reason = "Low confidence durable memory"
        if queue_type:
            queue.append(
                {
                    "id": stable_id("review", queue_type, memory["memory_id"]),
                    "queue_item_type": queue_type,
                    "queue_item_id": memory["memory_id"],
                    "reason": reason,
                    "object_type": "memory",
                    "object_id": memory["memory_id"],
                    "actions": ["approve", "suppress", "merge", "split", "mark_stale", "attach_note", "escalate"],
                }
            )
    for run in runs[:10]:
        if run["run_id"] in decided_ids:
            continue
        if run.get("warnings") or run.get("diff_text"):
            queue.append(
                {
                    "id": stable_id("review", "run", run["run_id"]),
                    "queue_item_type": "large_diff" if run.get("diff_text") else "failed_run",
                    "queue_item_id": run["run_id"],
                    "reason": "; ".join(str(item) for item in run["warnings"]) or "Run produced an inspectable diff",
                    "object_type": "run",
                    "object_id": run["run_id"],
                    "actions": ["approve", "suppress", "attach_note", "escalate"],
                }
            )
    for retrieval in retrievals[:10]:
        if str(retrieval.get("id")) in decided_ids:
            continue
        if retrieval.get("excluded"):
            queue.append(
                {
                    "id": stable_id("review", "retrieval", retrieval["id"]),
                    "queue_item_type": "suspicious_retrieval",
                    "queue_item_id": retrieval["id"],
                    "reason": "Retrieval omitted near-threshold memories",
                    "object_type": "retrieval",
                    "object_id": retrieval["id"],
                    "actions": ["approve", "suppress", "attach_note", "escalate"],
                }
            )
    return queue


def _build_eval_entities(store: MemoryStore) -> list[dict[str, Any]]:
    items = []
    for path in sorted(store.exports_dir.glob("eval-*.json"), reverse=True):
        payload = read_json(path, {})
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _build_health(
    memories: list[dict[str, Any]],
    retrievals: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    contested = sum(1 for item in memories if item.get("status") == "contested")
    active = sum(1 for item in memories if item.get("status") == "active")
    hit_rate = 0.0
    if retrievals:
        hit_rate = round(
            sum(1 for item in retrievals if item.get("selected_memory_ids")) / len(retrievals),
            4,
        )
    contradiction_rate = 0.0 if not memories else round(contested / len(memories), 4)
    return {
        "retrieval_hit_rate": hit_rate,
        "contradiction_rate": contradiction_rate,
        "contested_memory_backlog": contested,
        "active_memory_count": active,
        "manual_review_backlog": len(reviews),
        "consolidation_runs": len([item for item in runs if item.get("type") == "consolidation"]),
        "dream_runs": len([item for item in runs if item.get("type") == "dream"]),
    }


def _build_graph_entities(
    memories: list[dict[str, Any]],
    retrievals: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    context_use: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    relation_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, node_type: str, label: str, raw: dict[str, Any]) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append({"id": node_id, "type": node_type, "label": label, "raw": raw})

    def add_edge(source: str, target: str, edge_type: str) -> None:
        key = (source, target, edge_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"source": source, "target": target, "type": edge_type})

    for memory in memories:
        add_node(memory["memory_id"], "memory", memory["title"], memory)
    memory_ids = {str(memory["memory_id"]) for memory in memories}
    for edge in relation_edges:
        source = str(edge.get("from_id", ""))
        target = str(edge.get("to_id", ""))
        edge_type = str(edge.get("kind", ""))
        if source in memory_ids and target in memory_ids and edge_type:
            add_edge(source, target, edge_type)
    for memory in memories:
        for source_id in memory.get("source_event_ids", []):
            add_node(source_id, "event", source_id, {"event_id": source_id})
            add_edge(str(source_id), memory["memory_id"], "consolidated_into")
        for superseded_id in memory.get("supersedes", []):
            add_edge(memory["memory_id"], str(superseded_id), "supersedes")
        for conflict_id in memory.get("conflicts_with", []):
            add_edge(memory["memory_id"], str(conflict_id), "conflicts_with")
    for retrieval in retrievals:
        retrieval_id = str(retrieval["id"])
        add_node(retrieval_id, "retrieval", retrieval_id, retrieval)
        for memory_id in retrieval.get("selected_memory_ids", []):
            add_edge(retrieval_id, str(memory_id), "selected_by")
    for context in contexts:
        context_id = str(context.get("context_id") or "")
        if not context_id:
            continue
        label = str(project_context_list_row(context).get("display_name") or context_id)
        add_node(context_id, "context", label, context)
        for memory_id in context.get("selected_memory_ids", []):
            add_edge(context_id, str(memory_id), "selected_for_context")
    for usage in context_use:
        usage_id = str(usage.get("usage_id") or stable_id("context_use", usage))
        context_id = str(usage.get("context_id") or "")
        state = str(usage.get("memory_use_state") or "unknown")
        add_node(usage_id, "context_use", f"{state}: {usage_id}", usage)
        if context_id:
            add_edge(usage_id, context_id, "acknowledges_context")
        for memory_id in usage.get("used_memory_ids", []):
            add_edge(usage_id, str(memory_id), "used_memory")
    for run in runs:
        add_node(run["run_id"], "run", run["run_id"], run)
        for op in run.get("operations", []):
            target_id = op.get("target_memory_id")
            if target_id:
                add_edge(run["run_id"], str(target_id), "applied_to")
    for annotation in annotations:
        annotation_id = str(annotation.get("id", stable_id("annotation", annotation)))
        add_node(annotation_id, "annotation", annotation.get("label", annotation_id), annotation)
        add_edge(annotation_id, str(annotation.get("object_id")), "annotated_by")
    for review in reviews:
        review_id = str(review.get("id", stable_id("review", review)))
        add_node(review_id, "review", review.get("action", review_id), review)
        add_edge(review_id, str(review.get("queue_item_id")), "reviewed")
    return {"nodes": nodes, "edges": edges}


def _phase_traces_for_consolidation(
    run_id: str,
    summary: dict[str, Any],
    operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    payload = summary.get("summary", {})
    created = int(payload.get("created", 0))
    updated = int(payload.get("updated", 0))
    contested = int(payload.get("contested", 0))
    pruned = int(payload.get("pruned", 0))
    timestamp = str(payload.get("completed_at") or payload.get("started_at") or payload.get("generated_at") or "")
    return [
        PhaseTrace(
            id=stable_id("phase", run_id, "orientation"),
            run_id=run_id,
            phase="orientation",
            started_at=timestamp,
            ended_at=timestamp,
            inputs_count=payload.get("candidate_count", 0),
            outputs_count=payload.get("candidate_count", 0),
            warning_count=0,
            error_count=0,
            files_consulted=summary.get("target_paths", []),
        ).to_dict(),
        PhaseTrace(
            id=stable_id("phase", run_id, "consolidation"),
            run_id=run_id,
            phase="consolidation",
            started_at=timestamp,
            ended_at=timestamp,
            inputs_count=payload.get("candidate_count", 0),
            outputs_count=created + updated + contested,
            warning_count=1 if contested else 0,
            error_count=0,
            files_consulted=summary.get("target_paths", []),
        ).to_dict(),
        PhaseTrace(
            id=stable_id("phase", run_id, "pruning_indexing"),
            run_id=run_id,
            phase="pruning_indexing",
            started_at=timestamp,
            ended_at=timestamp,
            inputs_count=created + updated,
            outputs_count=max(created + updated - pruned, 0),
            warning_count=0,
            error_count=0,
            files_consulted=summary.get("target_paths", []),
        ).to_dict(),
    ]


def _phase_traces_for_dream(run_id: str, summary: dict[str, Any], files_consulted: list[str]) -> list[dict[str, Any]]:
    timestamp = str(summary.get("last_ran_at") or summary.get("last_started_at") or "")
    phases = summary.get("phases", ["orient", "gather_recent_signal", "consolidate", "prune_and_reindex"])
    gathered = int(summary.get("gathered_rows", 0))
    appended = int(summary.get("appended_events", 0))
    traces = []
    outputs = [gathered, appended, appended, appended]
    for idx, phase in enumerate(phases):
        traces.append(
            PhaseTrace(
                id=stable_id("phase", run_id, phase),
                run_id=run_id,
                phase=str(phase),
                started_at=timestamp,
                ended_at=timestamp,
                inputs_count=gathered if idx else 0,
                outputs_count=outputs[min(idx, len(outputs) - 1)],
                warning_count=1 if summary.get("reason") and idx == len(phases) - 1 else 0,
                error_count=0,
                files_consulted=files_consulted,
            ).to_dict()
        )
    return traces


def _collect_run_warnings(summary: dict[str, Any], operations: list[dict[str, Any]]) -> list[str]:
    warnings = []
    payload = summary.get("summary", {})
    if payload.get("contested", 0):
        warnings.append("contested results present")
    if not operations:
        warnings.append("no structured operations captured")
    return warnings


def _find_source_paths(store: MemoryStore, record: dict[str, Any]) -> list[str]:
    source_paths = [str(store.topics_dir / f"{record['memory_id']}.md")]
    for event in store.load_events():
        if event["event_id"] in record.get("source_event_ids", []):
            source = event.get("source", {})
            file_refs = source.get("file_refs", [])
            if isinstance(file_refs, list):
                source_paths.extend(str(item) for item in file_refs if item)
    return sorted(set(source_paths))


def _recent_sessions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event.get("session_id", "unknown"))].append(event)
    sessions = []
    for session_id, rows in grouped.items():
        rows.sort(key=lambda item: str(item.get("timestamp", "")))
        sessions.append(
            {
                "session_id": session_id,
                "display_name": _compact_display_label(None, session_id),
                "event_count": len(rows),
                "started_at": rows[0].get("timestamp"),
                "ended_at": rows[-1].get("timestamp"),
            }
        )
    sessions.sort(key=lambda item: str(item.get("ended_at", "")), reverse=True)
    return sessions[:5]


_DIAG_SAMPLE_CAP = 25


def _session_diagnostics(store: MemoryStore) -> dict[str, Any]:
    """Read-only diagnostics: orphan events, count mismatches, zero-event sessions.

    Compares the live event log against the freshly-built session entity list so
    that orphan and mismatch signals are always current.  Never mutates the store.

    Orphan events: events whose session_id does not appear in any session entity.
    Because session entities are built from events AND context assemblies, an
    event can be orphaned only when its session_id is missing from *all* other
    evidence — practically this surfaces events injected with a session_id that
    was never tracked through a maintain/index cycle (e.g. raw file injection,
    a now-deleted event file, or a session_id that was pruned).

    The implementation rebuilds session entities from scratch (matching what
    maintain + index_observability would produce) rather than reading a cached
    index, so the diagnostics remain accurate even on a stale index.
    """
    events = store.load_events()
    contexts = store.load_context_assemblies()

    # Group events by session_id
    grouped: dict[str, list[str]] = {}
    for event in events:
        sid = str(event.get("session_id") or "")
        if not sid:
            continue
        grouped.setdefault(sid, []).append(str(event.get("event_id", "")))

    # Build session entity map from contexts only (independent of events).
    # A session_id appearing *only* in events but not in contexts or a prior
    # index is the orphan signal.
    context_sessions: set[str] = set()
    for ctx in contexts:
        sid = str(ctx.get("session_id") or "")
        if sid:
            context_sessions.add(sid)

    # Also load the saved index sessions (if available) as additional known ids.
    index_sessions: set[str] = set()
    if store.observability_index_path.exists():
        try:
            saved = store.load_observability_index()
            for s in (saved.get("entities") or {}).get("sessions") or []:
                sid = str(s.get("session_id") or "")
                if sid:
                    index_sessions.add(sid)
        except Exception:
            pass

    known_session_ids: set[str] = context_sessions | index_sessions

    # Orphan events: session_id not in known_session_ids
    orphan_events_all: list[dict[str, str]] = []
    for sid, eids in grouped.items():
        if sid not in known_session_ids:
            for eid in eids:
                orphan_events_all.append({"event_id": eid, "session_id": sid})
    orphan_total = len(orphan_events_all)

    # Mismatch records: compare index event_count vs actual grouped count.
    # Only meaningful when the saved index exists.
    mismatch_all: list[dict[str, Any]] = []
    if index_sessions:
        index_entity_counts: dict[str, int] = {}
        try:
            saved = store.load_observability_index()
            for s in (saved.get("entities") or {}).get("sessions") or []:
                sid = str(s.get("session_id") or "")
                cnt = int(s.get("event_count") or 0)
                if sid:
                    index_entity_counts[sid] = cnt
        except Exception:
            pass
        for sid, recorded in index_entity_counts.items():
            actual = len(grouped.get(sid, []))
            if recorded != actual:
                mismatch_all.append(
                    {
                        "session_id": sid,
                        "recorded_event_count": recorded,
                        "actual_event_count": actual,
                    }
                )
    mismatch_total = len(mismatch_all)

    # Zero-event sessions: known sessions with no events in the live log.
    zero_all = [sid for sid in known_session_ids if not grouped.get(sid)]
    zero_total = len(zero_all)

    return {
        "orphan_events": orphan_events_all[:_DIAG_SAMPLE_CAP],
        "orphan_events_total": orphan_total,
        "mismatch_records": mismatch_all[:_DIAG_SAMPLE_CAP],
        "mismatch_records_total": mismatch_total,
        "zero_event_sessions": zero_all[:_DIAG_SAMPLE_CAP],
        "zero_event_sessions_total": zero_total,
        "total_sessions": len(known_session_ids | set(grouped.keys())),
        "total_events": len(events),
    }


def _max_iso_timestamp(values: Any) -> str | None:
    usable = [str(value) for value in values if value]
    return max(usable) if usable else None


def _effective_run_timestamp(run: dict[str, Any]) -> str | None:
    return str(run.get("ended_at") or run.get("started_at") or "") or None


def create_annotation(
    store: MemoryStore,
    *,
    object_type: str,
    object_id: str,
    actor: str,
    label: str,
    note: str,
    score: float | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    annotation = Annotation(
        id=stable_id("annotation", object_type, object_id, actor, label, timestamp),
        object_type=object_type,
        object_id=object_id,
        actor=actor,
        label=label,
        score=score,
        note=note,
        created_at=timestamp,
    )
    store.append_annotation(annotation)
    return annotation.to_dict()


def create_review_decision(
    store: MemoryStore,
    *,
    queue_item_type: str,
    queue_item_id: str,
    action: str,
    rationale: str,
    actor: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    decision = ReviewDecision(
        id=stable_id("review", queue_item_type, queue_item_id, action, actor, timestamp),
        queue_item_type=queue_item_type,
        queue_item_id=queue_item_id,
        action=action,
        rationale=rationale,
        actor=actor,
        created_at=timestamp,
    )
    store.append_review_decision(decision)
    return decision.to_dict()


def create_export(
    store: MemoryStore,
    *,
    export_type: str,
    actor: str,
    include: list[str],
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    index = load_or_build_index(store, now=timestamp)
    export_id = stable_id("export", export_type, actor, timestamp)
    payload = {
        "id": export_id,
        "export_type": export_type,
        "actor": actor,
        "created_at": timestamp,
        "include": include,
        "artifact_hashes": {
            str(path.relative_to(store.workspace)): sha256_path(path)
            for path in store.iter_memory_paths()
            if path.is_file()
        },
        "snapshot": {
            key: index["entities"][key]
            for key in include
            if key in index["entities"]
        },
    }
    store.write_export_record(export_id, payload)
    return payload


def _load_json_records(directory: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        payload = read_json(path, {})
        if isinstance(payload, dict):
            payload.setdefault("source_path", str(path))
            rows.append(payload)
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
