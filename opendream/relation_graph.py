"""Contradiction graph and relation-edge storage.

Manages explicit relation edges between memory records for contradiction,
supersession, derivation, and verification relationships. Edges influence
retrieval ranking, review UX, and promotion decisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import RelationEdge
from .util import read_json, stable_id, to_iso, utc_now, write_json
from .validation import validate_document

RELATION_KINDS = frozenset({
    "supports",
    "conflicts_with",
    "supersedes",
    "derived_from",
    "verified_by",
    "invalidated_by",
})


class RelationStore:
    """Manages relation edges persisted as a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_edges(self) -> list[dict[str, Any]]:
        result = read_json(self.path, [])
        return result if isinstance(result, list) else []

    def save_edges(self, edges: list[dict[str, Any]]) -> None:
        write_json(self.path, edges)

    def add_edge(self, edge: RelationEdge) -> dict[str, Any]:
        payload = edge.to_dict()
        validate_document("relation-edge.schema.json", payload)
        edges = self.load_edges()
        # Deduplicate by (from_id, to_id, kind).
        key = (edge.from_id, edge.to_id, edge.kind)
        edges = [e for e in edges if (e["from_id"], e["to_id"], e["kind"]) != key]
        edges.append(payload)
        self.save_edges(edges)
        return payload

    def remove_edges_for(self, memory_id: str) -> int:
        """Remove all edges involving *memory_id*. Returns count removed."""
        edges = self.load_edges()
        remaining = [e for e in edges if e["from_id"] != memory_id and e["to_id"] != memory_id]
        removed = len(edges) - len(remaining)
        if removed:
            self.save_edges(remaining)
        return removed

    def edges_for(self, memory_id: str) -> list[dict[str, Any]]:
        return [
            e for e in self.load_edges()
            if e["from_id"] == memory_id or e["to_id"] == memory_id
        ]

    def conflicts_for(self, memory_id: str) -> list[dict[str, Any]]:
        return [
            e for e in self.load_edges()
            if e["kind"] == "conflicts_with"
            and (e["from_id"] == memory_id or e["to_id"] == memory_id)
        ]

    def supersessions_for(self, memory_id: str) -> list[dict[str, Any]]:
        return [
            e for e in self.load_edges()
            if e["kind"] == "supersedes"
            and (e["from_id"] == memory_id or e["to_id"] == memory_id)
        ]


def create_relation_store(memory_root: Path) -> RelationStore:
    """Create a RelationStore under the given memory root."""
    path = memory_root / "state" / "relation_edges.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        write_json(path, [])
    return RelationStore(path)


def backfill_edges_from_records(
    records: list[dict[str, Any]],
    store: RelationStore,
) -> list[dict[str, Any]]:
    """Create relation edges from existing supersedes/conflicts_with fields.

    Returns the list of newly created edges.
    """
    now = to_iso(utc_now())
    created: list[dict[str, Any]] = []

    for record in records:
        memory_id = record["memory_id"]
        for target_id in record.get("supersedes", []):
            edge = RelationEdge(
                edge_id=stable_id("edge", memory_id, target_id, "supersedes"),
                from_id=memory_id,
                to_id=target_id,
                kind="supersedes",
                created_at=now,
                reason="backfilled from record.supersedes",
            )
            payload = store.add_edge(edge)
            created.append(payload)

        for target_id in record.get("conflicts_with", []):
            edge = RelationEdge(
                edge_id=stable_id("edge", memory_id, target_id, "conflicts_with"),
                from_id=memory_id,
                to_id=target_id,
                kind="conflicts_with",
                created_at=now,
                reason="backfilled from record.conflicts_with",
            )
            payload = store.add_edge(edge)
            created.append(payload)

    return created


def relation_aware_score_adjustment(
    memory_id: str,
    edges: list[dict[str, Any]],
) -> float:
    """Compute a retrieval score adjustment based on relation edges.

    Superseded records get penalized. Records with active conflicts get
    a small penalty. Records with verification support get a boost.
    """
    adjustment = 0.0
    for edge in edges:
        if edge["kind"] == "supersedes" and edge["to_id"] == memory_id:
            adjustment -= 0.5  # This record was superseded.
        if edge["kind"] == "conflicts_with":
            adjustment -= 0.1  # Conflict penalty.
        if edge["kind"] == "verified_by" and edge["from_id"] == memory_id:
            adjustment += 0.15  # Verification boost.
        if edge["kind"] == "invalidated_by" and edge["from_id"] == memory_id:
            adjustment -= 0.4  # Invalidation penalty.
        if edge["kind"] == "supports" and edge["to_id"] == memory_id:
            adjustment += 0.05  # Support boost.
    return adjustment


def build_relation_explanations(
    memory_id: str,
    edges: list[dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Build human-readable explanations of relation edges for a record."""
    explanations: list[str] = []
    for edge in edges:
        other_id = edge["to_id"] if edge["from_id"] == memory_id else edge["from_id"]
        other_title = records_by_id.get(other_id, {}).get("title", other_id)
        kind = edge["kind"]
        if kind == "supersedes" and edge["from_id"] == memory_id:
            explanations.append(f"supersedes: {other_title}")
        elif kind == "supersedes" and edge["to_id"] == memory_id:
            explanations.append(f"superseded by: {other_title}")
        elif kind == "conflicts_with":
            explanations.append(f"conflicts with: {other_title}")
        elif kind == "verified_by" and edge["from_id"] == memory_id:
            explanations.append(f"verified by: {other_title}")
        elif kind == "invalidated_by" and edge["from_id"] == memory_id:
            explanations.append(f"invalidated by: {other_title}")
        elif kind == "derived_from" and edge["from_id"] == memory_id:
            explanations.append(f"derived from: {other_title}")
        elif kind == "supports":
            explanations.append(f"supports: {other_title}")
    return explanations
