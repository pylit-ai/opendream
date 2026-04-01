"""Query-family anticipation planner.

Implements WS4 (T15-T20): query-family models, inference from transcripts,
static manifests, ranking and budget-aware truncation.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .storage import MemoryStore
from .util import semantic_tokens, stable_id

# Default query families common to coding agents
DEFAULT_CODING_FAMILIES: list[dict[str, Any]] = [
    {
        "family_id": "continue-migration",
        "title": "Continue current migration or refactor",
        "description": "Questions about how to continue an in-progress migration, refactor, or multi-step change",
        "examples": [
            "how do I continue this migration?",
            "what's the next step in this refactor?",
            "where did I leave off?",
        ],
        "predicted_frequency": 0.7,
        "predicted_value": 0.8,
    },
    {
        "family_id": "what-failed",
        "title": "What failed and why",
        "description": "Questions about recent failures, errors, and their root causes",
        "examples": [
            "what failed last time?",
            "why did the tests break?",
            "what error did I see?",
        ],
        "predicted_frequency": 0.6,
        "predicted_value": 0.9,
    },
    {
        "family_id": "repo-conventions",
        "title": "Repository conventions and patterns",
        "description": "Questions about project-specific conventions, naming, architecture patterns",
        "examples": [
            "what convention applies here?",
            "how do we name files in this project?",
            "what pattern do we use for X?",
        ],
        "predicted_frequency": 0.5,
        "predicted_value": 0.7,
    },
    {
        "family_id": "unresolved-work",
        "title": "Unresolved bugs, features, and fixes",
        "description": "Questions about what work remains, known issues, and pending items",
        "examples": [
            "what are the top unresolved bugs?",
            "what features are pending?",
            "what needs to be fixed?",
        ],
        "predicted_frequency": 0.4,
        "predicted_value": 0.6,
    },
    {
        "family_id": "command-sequences",
        "title": "Working command sequences",
        "description": "Questions about command sequences that previously worked for specific tasks",
        "examples": [
            "what command sequence worked?",
            "how do I run the tests?",
            "what's the deploy process?",
        ],
        "predicted_frequency": 0.5,
        "predicted_value": 0.7,
    },
    {
        "family_id": "environment-gotchas",
        "title": "Environment and toolchain gotchas",
        "description": "Questions about environment-specific issues, toolchain quirks, setup problems",
        "examples": [
            "what are the known environment issues?",
            "why doesn't this work on my machine?",
            "what setup step did I miss?",
        ],
        "predicted_frequency": 0.3,
        "predicted_value": 0.8,
    },
]


def load_families(store: MemoryStore) -> list[dict[str, Any]]:
    """Load all query families (stored + defaults)."""
    stored = store.load_query_families()
    if stored:
        return stored
    return list(DEFAULT_CODING_FAMILIES)


def save_families(store: MemoryStore, families: list[dict[str, Any]]) -> None:
    """Persist query families."""
    store.save_query_families(families)


def infer_families_from_transcripts(
    rows: list[dict[str, Any]],
    existing_families: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Infer query families from transcript rows.

    Clusters recent user queries by semantic similarity and extracts
    recurring patterns as query families.
    """
    # Extract question-like content from rows
    questions: list[str] = []
    for row in rows:
        text = str(row.get("text") or row.get("message") or "")
        if not text.strip():
            continue
        # Look for question patterns
        if "?" in text or any(
            text.lower().strip().startswith(w)
            for w in ("how", "what", "why", "where", "when", "which", "can", "does", "is", "are")
        ):
            questions.append(text.strip())

    if not questions:
        return []

    # Cluster by token overlap
    clusters: list[list[str]] = []
    for question in questions:
        tokens = semantic_tokens(question)
        placed = False
        for cluster in clusters:
            cluster_tokens = semantic_tokens(" ".join(cluster))
            overlap = len(tokens & cluster_tokens) / max(1, len(tokens | cluster_tokens))
            if overlap > 0.3:
                cluster.append(question)
                placed = True
                break
        if not placed:
            clusters.append([question])

    # Convert clusters to families
    existing_ids = {f.get("family_id", "") for f in (existing_families or [])}
    inferred: list[dict[str, Any]] = []
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        # Use most common tokens as title
        all_tokens = Counter[str]()
        for q in cluster:
            all_tokens.update(semantic_tokens(q))
        common = [token for token, _ in all_tokens.most_common(4)]
        title = " ".join(common[:4]) if common else cluster[0][:50]
        family_id = stable_id("family", title)
        if family_id in existing_ids:
            continue
        inferred.append(
            {
                "family_id": family_id,
                "title": title,
                "description": f"Inferred from {len(cluster)} similar queries",
                "examples": cluster[:5],
                "source_signals": ["transcript_inference"],
                "predicted_frequency": min(1.0, len(cluster) / max(1, len(questions))),
                "predicted_value": 0.5,
                "status": "active",
            }
        )

    return inferred


def infer_families_from_retrieval_logs(
    retrieval_audits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Infer families from retrieval audit logs (repeated queries)."""
    query_counts = Counter[str]()
    for audit in retrieval_audits:
        query = str(audit.get("query", ""))
        if query.strip():
            # Normalize to token bag for dedup
            normalized = " ".join(sorted(semantic_tokens(query)))
            query_counts[normalized] += 1

    families: list[dict[str, Any]] = []
    for normalized, count in query_counts.most_common(10):
        if count < 2:
            break
        family_id = stable_id("family-retrieval", normalized)
        families.append(
            {
                "family_id": family_id,
                "title": normalized[:60],
                "description": f"Repeated retrieval query ({count} times)",
                "examples": [normalized],
                "source_signals": ["retrieval_log"],
                "predicted_frequency": min(1.0, count / max(1, len(retrieval_audits))),
                "predicted_value": 0.6,
                "status": "active",
            }
        )
    return families


def load_static_manifests(manifest_paths: list[str]) -> list[dict[str, Any]]:
    """Load query families from static manifest files."""
    import json
    from pathlib import Path

    families: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        path = Path(manifest_path).expanduser()
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            families.extend(data)
        elif isinstance(data, dict) and "families" in data:
            families.extend(data["families"])
    return families


def rank_and_truncate(
    families: list[dict[str, Any]],
    *,
    max_families: int = 10,
    allow_list: list[str] | None = None,
    deny_list: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank families by predicted value * frequency and truncate to budget.

    Applies allow/deny lists before ranking.
    """
    filtered = families
    if allow_list:
        allow_set = set(allow_list)
        filtered = [f for f in filtered if f.get("family_id") in allow_set]
    if deny_list:
        deny_set = set(deny_list)
        filtered = [f for f in filtered if f.get("family_id") not in deny_set]
    # Remove suppressed/expired
    filtered = [f for f in filtered if f.get("status", "active") == "active"]

    # Rank by composite score
    def score(f: dict[str, Any]) -> float:
        freq = float(f.get("predicted_frequency", 0.5))
        value = float(f.get("predicted_value", 0.5))
        return freq * value

    ranked = sorted(filtered, key=score, reverse=True)
    return ranked[:max_families]


def merge_families(
    *sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge multiple family sources, deduplicating by family_id."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for source in sources:
        for family in source:
            fid = family.get("family_id", "")
            if fid and fid not in seen:
                seen.add(fid)
                merged.append(family)
    return merged


def plan_anticipation(
    store: MemoryStore,
    *,
    transcript_rows: list[dict[str, Any]] | None = None,
    retrieval_audits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Plan which query families to target for semantic synthesis.

    Returns a planning report with selected families and rationale.
    """
    config = store.load_semantic_config()
    anticipation_config = config.get("anticipation", {})
    budgets = config.get("budgets", {})
    max_families = int(budgets.get("max_query_families", 10))

    if not anticipation_config.get("enabled", True):
        return {
            "status": "disabled",
            "reason": "anticipation disabled in config",
            "families": [],
        }

    # Gather families from all sources
    existing = load_families(store)
    manifest_families = load_static_manifests(
        anticipation_config.get("static_family_manifests", [])
    )
    transcript_families = (
        infer_families_from_transcripts(transcript_rows, existing)
        if transcript_rows
        else []
    )
    retrieval_families = (
        infer_families_from_retrieval_logs(retrieval_audits) if retrieval_audits else []
    )

    all_families = merge_families(
        existing, manifest_families, transcript_families, retrieval_families
    )

    selected = rank_and_truncate(
        all_families,
        max_families=max_families,
        allow_list=anticipation_config.get("family_allow_list"),
        deny_list=anticipation_config.get("family_deny_list"),
    )

    # Persist merged families
    save_families(store, all_families)

    return {
        "status": "planned",
        "total_families_considered": len(all_families),
        "families_selected": len(selected),
        "selected_families": selected,
        "sources": {
            "existing": len(existing),
            "manifest": len(manifest_families),
            "transcript_inferred": len(transcript_families),
            "retrieval_inferred": len(retrieval_families),
        },
        "max_families": max_families,
    }
