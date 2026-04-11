# tests/fixtures/graph_fixture.py
"""Fixture builders for graph-related tests.

Each builder returns a dict shaped like ``index['entities']['graph']``:
``{"nodes": [{"id": str, "type": str, "title": str, ...}], "edges": [...]}``.
"""
from __future__ import annotations


def chain_fixture() -> dict:
    """Linear supersession chain: A -> B -> C (B supersedes A, C supersedes B)."""
    return {
        "nodes": [
            {"id": "A", "type": "memory", "title": "memory A", "created_at": "2026-01-01"},
            {"id": "B", "type": "memory", "title": "memory B", "created_at": "2026-01-02"},
            {"id": "C", "type": "memory", "title": "memory C", "created_at": "2026-01-03"},
        ],
        "edges": [
            {"source": "B", "target": "A", "type": "supersedes"},
            {"source": "C", "target": "B", "type": "supersedes"},
        ],
    }


def cycle_fixture() -> dict:
    """A 2-cycle in derived_from: A derived_from B, B derived_from A."""
    return {
        "nodes": [
            {"id": "A", "type": "memory", "title": "A", "created_at": "2026-01-01"},
            {"id": "B", "type": "memory", "title": "B", "created_at": "2026-01-02"},
        ],
        "edges": [
            {"source": "A", "target": "B", "type": "derived_from"},
            {"source": "B", "target": "A", "type": "derived_from"},
        ],
    }


def hub_fixture() -> dict:
    """One hub node H with three leaves L1/L2/L3 derived from it."""
    return {
        "nodes": [
            {"id": "H", "type": "memory", "title": "hub", "created_at": "2026-01-01"},
            {"id": "L1", "type": "memory", "title": "leaf 1", "created_at": "2026-01-02"},
            {"id": "L2", "type": "memory", "title": "leaf 2", "created_at": "2026-01-03"},
            {"id": "L3", "type": "memory", "title": "leaf 3", "created_at": "2026-01-04"},
        ],
        "edges": [
            {"source": "L1", "target": "H", "type": "derived_from"},
            {"source": "L2", "target": "H", "type": "derived_from"},
            {"source": "L3", "target": "H", "type": "derived_from"},
        ],
    }


def isolated_fixture() -> dict:
    """One node, no edges."""
    return {
        "nodes": [{"id": "X", "type": "memory", "title": "isolated", "created_at": "2026-01-01"}],
        "edges": [],
    }


def index_with(graph: dict) -> dict:
    """Wrap a graph dict in an ``index`` shape that ``build_graph`` accepts."""
    return {"entities": {"graph": graph}}
