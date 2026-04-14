from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import Annotation, ObservabilityConsolidationOp, PhaseTrace, ReviewDecision
from .storage import MemoryStore
from .util import read_json, sha256_path, stable_id, to_iso, utc_now


def index_observability(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    index = {
        "generated_at": timestamp,
        "store": store.status_snapshot(now=timestamp),
        "overview": _build_overview(store, timestamp),
        "entities": _build_entities(store),
    }
    store.save_observability_index(index)
    return index


def load_or_build_index(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    if store.observability_index_path.exists():
        payload = store.load_observability_index()
        if payload.get("entities"):
            return payload
    return index_observability(store, now=now)


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
        reverse = sort_field not in {"title", "type", "scope", "status", "memory_id"}

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
                ]
            ).lower()
        ]
    for key, value in filters.items():
        if value:
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


_VALID_RETRIEVAL_SORTS = frozenset({"timestamp", "id", "query", "selected_count"})


def _retrieval_passes_selected_count(
    row: dict[str, Any],
    lo: int | None,
    hi: int | None,
) -> bool:
    """Inclusive bounds on ``len(selected_memory_ids)``; missing list treated as []."""
    if lo is None and hi is None:
        return True
    n = len(row.get("selected_memory_ids") or [])
    if lo is not None and n < lo:
        return False
    if hi is not None and n > hi:
        return False
    return True


def _retrieval_sort_key(
    row: dict[str, Any],
    sort: str,
    *,
    reverse: bool,
) -> tuple[Any, str]:
    """Sort key with stable tie-break on ``id``."""
    rid = str(row.get("id", ""))
    if sort == "selected_count":
        primary: Any = len(row.get("selected_memory_ids") or [])
    elif sort == "timestamp":
        primary = str(row.get("timestamp", "") or "")
    elif sort == "query":
        primary = str(row.get("query", "") or "").casefold()
    else:
        primary = str(row.get("id", "") or "").casefold()

    if reverse:
        if isinstance(primary, int):
            primary = -primary
        elif sort == "timestamp":
            primary = _MemorySortStrDesc(primary)
        elif sort in {"query", "id"}:
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
) -> dict[str, Any]:
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
                ]
            ).lower()
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
    overview: dict[str, Any] = {
        "generated_at": timestamp,
        "store_health": {
            "initialized": store.is_initialized(),
            "lock": store.lock_state(),
            "dream_lock": store.dream_lock_state(),
            "memory_root": str(store.memory_root),
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
        "recent_sessions": _recent_sessions(events),
        "recent_runs": runs[:5],
        "last_consolidation_run": runs[0] if runs else None,
        "memory_excellence": _build_memory_excellence_overview(store, records),
        "execution_ownership": {
            "active_strategy": semantic_config.get("execution_strategy", "deterministic"),
            "preferred_auth_mode": semantic_config.get("preferred_auth_mode", "no-extra-key"),
            "active_adapter": semantic_config.get("active_adapter"),
            "candidate_strategies": semantic_config.get("candidate_strategies", []),
        },
    }
    return overview


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


def _build_entities(store: MemoryStore) -> dict[str, Any]:
    memories = _build_memory_entities(store)
    runs = _load_run_records(store)
    retrievals = _load_retrieval_entities(store)
    contexts = _load_context_entities(store)
    sessions = _build_session_entities(store, contexts)
    annotations = store.load_annotations()
    reviews = _build_review_queue(store, memories, retrievals, runs)
    evals = _build_eval_entities(store)
    exports = store.load_export_records()
    health = _build_health(memories, retrievals, runs, reviews)
    graph = _build_graph_entities(memories, retrievals, runs, annotations, reviews)
    relation_edges = read_json(store.relation_edges_path, [])
    verification_reports = _load_json_records(store.audit_claim_verification_dir)
    probe_reports = _load_json_records(store.audit_transcript_probe_dir)
    reconciliation_reports = _load_json_records(store.audit_reconciliation_dir)
    boundary_reports = _load_json_records(store.audit_boundary_dir)
    return {
        "memories": memories,
        "runs": runs,
        "retrievals": retrievals,
        "contexts": contexts,
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
        items.append(
            {
                **record,
                "source_count": len(record.get("source_event_ids", [])),
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


def _load_run_records(store: MemoryStore) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for summary_path in sorted(store.audit_consolidation_dir.glob("*-summary.json"), reverse=True):
        summary = read_json(summary_path, {})
        run_id = str(summary.get("run_id") or summary_path.stem.replace("-summary", ""))
        op_path = store.audit_consolidation_dir / f"{run_id}.jsonl"
        diff_path = store.audit_consolidation_dir / f"{run_id}.diff"
        operations = []
        for payload in _load_jsonl(op_path):
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
            operations.append(op)
        runs.append(
            {
                "id": run_id,
                "run_id": run_id,
                "type": "consolidation",
                "started_at": summary.get("summary", {}).get("started_at"),
                "ended_at": summary.get("summary", {}).get("completed_at"),
                "status": summary.get("summary", {}).get("status", "completed"),
                "summary": summary.get("summary", {}),
                "target_paths": summary.get("target_paths", []),
                "diff_path": str(diff_path) if diff_path.exists() else None,
                "diff_text": diff_path.read_text(encoding="utf-8") if diff_path.exists() else "",
                "operations": operations,
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
                "phase_traces": _phase_traces_for_dream(run_id, dream_summary, summary.get("target_paths", [])),
                "warnings": [dream_summary["reason"]] if "reason" in dream_summary else [],
                "source_paths": [str(summary_path), str(diff_path)],
            }
        )
    runs.sort(key=lambda item: str(item.get("ended_at") or item.get("started_at") or item["id"]), reverse=True)
    return runs


def _load_retrieval_entities(store: MemoryStore) -> list[dict[str, Any]]:
    items = []
    for path in sorted(store.audit_retrieval_dir.glob("*.json"), reverse=True):
        payload = read_json(path, {})
        payload.setdefault("id", payload.get("run_id", path.stem))
        payload.setdefault("source_path", str(path))
        payload["near_threshold"] = payload.get("excluded", [])
        payload["final_context_assembly_order"] = payload.get("selected_memory_ids", [])
        items.append(payload)
    return items


def _load_context_entities(store: MemoryStore) -> list[dict[str, Any]]:
    items = store.load_context_assemblies()
    items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
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
        for event in grouped_events.get(session_id, []):
            timeline.append(
                {
                    "timestamp": event.get("timestamp"),
                    "kind": "memory.event.emitted",
                    "label": event.get("kind"),
                    "object_id": event.get("event_id"),
                    "payload": event,
                }
            )
        for context in grouped_contexts.get(session_id, []):
            timeline.append(
                {
                    "timestamp": context.get("created_at"),
                    "kind": "memory.context.assembled",
                    "label": context.get("context_id"),
                    "object_id": context.get("context_id"),
                    "payload": context,
                }
            )
        timeline.sort(key=lambda item: str(item.get("timestamp", "")))
        sessions.append(
            {
                "id": session_id,
                "session_id": session_id,
                "event_count": len(grouped_events.get(session_id, [])),
                "context_count": len(grouped_contexts.get(session_id, [])),
                "timeline": timeline,
            }
        )
    sessions.sort(key=lambda item: item["session_id"])
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
    annotations: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    def add_node(node_id: str, node_type: str, label: str, raw: dict[str, Any]) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append({"id": node_id, "type": node_type, "label": label, "raw": raw})

    for memory in memories:
        add_node(memory["memory_id"], "memory", memory["title"], memory)
        for source_id in memory.get("source_event_ids", []):
            add_node(source_id, "event", source_id, {"event_id": source_id})
            edges.append({"source": source_id, "target": memory["memory_id"], "type": "consolidated_into"})
        for superseded_id in memory.get("supersedes", []):
            edges.append({"source": memory["memory_id"], "target": superseded_id, "type": "supersedes"})
        for conflict_id in memory.get("conflicts_with", []):
            edges.append({"source": memory["memory_id"], "target": conflict_id, "type": "conflicts_with"})
    for retrieval in retrievals:
        retrieval_id = str(retrieval["id"])
        add_node(retrieval_id, "retrieval", retrieval_id, retrieval)
        for memory_id in retrieval.get("selected_memory_ids", []):
            edges.append({"source": retrieval_id, "target": str(memory_id), "type": "selected_by"})
    for run in runs:
        add_node(run["run_id"], "run", run["run_id"], run)
        for op in run.get("operations", []):
            target_id = op.get("target_memory_id")
            if target_id:
                edges.append({"source": run["run_id"], "target": target_id, "type": "applied_to"})
    for annotation in annotations:
        annotation_id = str(annotation.get("id", stable_id("annotation", annotation)))
        add_node(annotation_id, "annotation", annotation.get("label", annotation_id), annotation)
        edges.append({"source": annotation_id, "target": str(annotation.get("object_id")), "type": "annotated_by"})
    for review in reviews:
        review_id = str(review.get("id", stable_id("review", review)))
        add_node(review_id, "review", review.get("action", review_id), review)
        edges.append({"source": review_id, "target": str(review.get("queue_item_id")), "type": "reviewed"})
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
    timestamp = str(payload.get("completed_at") or payload.get("started_at") or "")
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
                "event_count": len(rows),
                "started_at": rows[0].get("timestamp"),
                "ended_at": rows[-1].get("timestamp"),
            }
        )
    sessions.sort(key=lambda item: str(item.get("ended_at", "")), reverse=True)
    return sessions[:5]


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
