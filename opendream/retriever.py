from __future__ import annotations

from typing import Any

from .memory_types import canonical_memory_type, is_workflow_memory_type
from .models import normalize_reporting_agent
from .relation_graph import build_relation_explanations, relation_aware_score_adjustment
from .storage import MemoryStore
from .util import (
    CLI_JSON_VERSION,
    STOPWORDS,
    parse_timestamp,
    read_json,
    semantic_tokens,
    stable_id,
    summarize,
    to_iso,
    tokenize,
    utc_now,
)

QUERY_TYPE_BOOSTS = {
    "project_decision": 2.5,
    "environment_requirement": 2.2,
    "workflow": 2.0,
    "procedural_workflow": 2.0,
    "anti_pattern": 1.8,
    "user_preference": 1.5,
    "pending_item": 1.0,
}
SCOPE_PRIORS = {
    "project": 1.0,
    "workspace": 0.9,
    "agent": 0.8,
    "user": 0.75,
    "global": 0.7,
}
LEXICAL_NOISE_TOKENS = {"use", "which", "should", "setup"}

# Memory-hurt thresholds
STALE_DAYS_THRESHOLD = 30
LOW_CONFIDENCE_THRESHOLD = 0.4


SCORE_COMPONENT_DESCRIPTIONS = {
    "lexical": "query terms matched memory text",
    "embedding": "semantic tokens matched memory text",
    "type_prior": "memory type priority for retrieval",
    "recency_prior": "updated memories receive more weight",
    "scope_prior": "workspace/project scope priority",
    "confidence": "record confidence",
    "salience": "record salience",
    "relation_adjustment": "relationship graph boost or penalty",
    "procedural_query_boost": "workflow memory matched a task-shaped query",
    "query_family_bonus": "learned-context query family matched the request",
    "freshness_penalty": "learned context is past fresh_until",
    "conflict_penalty": "learned context has a detected or overridden conflict",
}


def should_retrieve(
    query: str,
    *,
    skip_retrieval: bool = False,
    min_content_tokens: int = 3,
) -> tuple[bool, str]:
    """Decide whether retrieval should run. Returns (should_run, reason)."""
    if skip_retrieval:
        return False, "explicit skip_retrieval flag"
    query_tokens = tokenize(query) - STOPWORDS - LEXICAL_NOISE_TOKENS
    if len(query_tokens) < min_content_tokens:
        return False, f"too few content tokens ({len(query_tokens)} < {min_content_tokens})"
    return True, ""


def _score_component_list(contributions: dict[str, float]) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "value": value,
            "reason": SCORE_COMPONENT_DESCRIPTIONS.get(name, name.replace("_", " ")),
        }
        for name, value in contributions.items()
    ]


def _freshness_explanation(record: dict[str, Any], timestamp: str, recency_bonus: float) -> dict[str, Any]:
    updated_at = str(record.get("updated_at", ""))
    days_since_update: int | None = None
    state = "unknown"
    if updated_at:
        try:
            days_since_update = max((parse_timestamp(timestamp) - parse_timestamp(updated_at)).days, 0)
            state = "stale" if days_since_update > STALE_DAYS_THRESHOLD else "fresh"
        except (TypeError, ValueError):
            state = "unparseable"
    return {
        "state": state,
        "updated_at": updated_at,
        "days_since_update": days_since_update,
        "stale_after_days": STALE_DAYS_THRESHOLD,
        "score_effect": round(recency_bonus, 4),
    }


def _conflict_explanation(
    record: dict[str, Any],
    record_edges: list[dict[str, Any]],
    relation_notes: list[str],
    *,
    include_contested: bool,
) -> dict[str, Any]:
    conflict_ids = set(str(item) for item in record.get("conflicts_with", []))
    for edge in record_edges:
        if edge.get("kind") == "conflicts_with":
            other_id = edge.get("to_id") if edge.get("from_id") == record.get("memory_id") else edge.get("from_id")
            if other_id:
                conflict_ids.add(str(other_id))

    status = str(record.get("status", "unknown"))
    if status == "contested":
        state = "contested"
        treatment = "included with caution" if include_contested else "excluded by default"
    elif conflict_ids:
        state = "conflicting"
        treatment = "included with relation penalty"
    else:
        state = "none"
        treatment = "no conflict signal"

    return {
        "state": state,
        "status": status,
        "conflicts_with": sorted(conflict_ids),
        "relation_notes": relation_notes,
        "treatment": treatment,
    }


def _excluded_record(
    record: dict[str, Any],
    *,
    reason: str,
    reason_code: str,
    timestamp: str,
    include_contested: bool,
    lexical_overlap: list[str] | None = None,
    semantic_overlap: list[str] | None = None,
    record_edges: list[dict[str, Any]] | None = None,
    relation_notes: list[str] | None = None,
) -> dict[str, Any]:
    edges = record_edges or []
    notes = relation_notes or []
    return {
        "memory_id": record.get("memory_id"),
        "title": record.get("title"),
        "type": record.get("type"),
        "status": record.get("status"),
        "reason": reason,
        "reason_code": reason_code,
        "why_excluded": reason,
        "matched_evidence": {
            "lexical_terms": lexical_overlap or [],
            "semantic_terms": semantic_overlap or [],
        },
        "freshness": _freshness_explanation(record, timestamp, 0.0),
        "conflict": _conflict_explanation(
            record,
            edges,
            notes,
            include_contested=include_contested,
        ),
    }


def _rerank_explanation(
    prefilter_results: list[tuple[float, dict[str, Any]]],
    *,
    needs_rerank: bool,
    rerank_threshold: float,
) -> dict[str, Any]:
    top_scores = [round(score, 4) for score, _ in prefilter_results[:2]]
    threshold_ratio = round(1.0 / rerank_threshold, 4) if rerank_threshold else None
    top_score_ratio: float | None = None
    if len(prefilter_results) >= 2 and prefilter_results[1][0] > 0:
        top_score_ratio = round(prefilter_results[0][0] / prefilter_results[1][0], 4)

    if not prefilter_results:
        reason = "no prefilter candidates; rerank skipped"
    elif len(prefilter_results) == 1:
        reason = "single prefilter candidate; rerank skipped"
    elif needs_rerank:
        reason = "top prefilter scores are close enough to require full scoring"
    else:
        reason = "top prefilter candidate is separated enough to skip rerank"

    return {
        "applied": needs_rerank,
        "reason": reason,
        "rerank_ambiguity_threshold": round(rerank_threshold, 4),
        "skip_ratio_threshold": threshold_ratio,
        "top_prefilter_scores": top_scores,
        "top_score_ratio": top_score_ratio,
    }


def _learned_context_freshness_explanation(record: dict[str, Any], timestamp: str) -> dict[str, Any]:
    fresh_until = str(record.get("fresh_until", ""))
    state = "unknown"
    days_expired: int | None = None
    score_effect = 0.0
    if fresh_until:
        try:
            expired = parse_timestamp(fresh_until) < parse_timestamp(timestamp)
            state = "expired" if expired else "fresh"
            if expired:
                days_expired = max((parse_timestamp(timestamp) - parse_timestamp(fresh_until)).days, 0)
                score_effect = -LEARNED_CONTEXT_FRESHNESS_PENALTY
        except (TypeError, ValueError):
            state = "unparseable"
    return {
        "state": state,
        "fresh_until": fresh_until,
        "days_expired": days_expired,
        "score_effect": round(score_effect, 4),
    }


def _learned_context_conflict_explanation(record: dict[str, Any]) -> dict[str, Any]:
    state = str(record.get("conflict_state", "none") or "none")
    score_effect = -LEARNED_CONTEXT_CONFLICT_PENALTY if state in ("detected", "overridden") else 0.0
    return {
        "state": state,
        "score_effect": round(score_effect, 4),
        "treatment": "penalized" if score_effect else "no conflict penalty",
    }


def retrieve(
    store: MemoryStore,
    *,
    query: str,
    limit: int = 5,
    include_contested: bool = False,
    now: str | None = None,
    embedding_enabled: bool | None = None,
    skip_retrieval: bool = False,
    query_source: str | None = None,
    caller_detail: str | None = None,
    reporting_agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    normalized_agent = normalize_reporting_agent(reporting_agent)

    # Retrieval gating
    min_content_tokens = int(store.config["retrieval"].get("gating_min_content_tokens", 3))
    should_run, gate_reason = should_retrieve(
        query, skip_retrieval=skip_retrieval, min_content_tokens=min_content_tokens,
    )
    if not should_run:
        run_id = stable_id("retrieve", timestamp, query, limit, "gated")
        rerank = {
            "applied": False,
            "reason": f"retrieval gated: {gate_reason}",
            "rerank_ambiguity_threshold": None,
            "skip_ratio_threshold": None,
            "top_prefilter_scores": [],
            "top_score_ratio": None,
        }
        return {
            "run_id": run_id,
            "gated": True,
            "reason": gate_reason,
            "selected_memory_ids": [],
            "lexical_only_selected_memory_ids": [],
            "why": [],
            "explanations": [],
            "excluded": [],
            "reranked": False,
            "rerank": rerank,
            "reporting_agent": normalized_agent,
            "cli_output_version": CLI_JSON_VERSION,
        }

    records = store.load_durable_records()

    # Load relation edges for relation-aware retrieval.
    relation_edges: list[dict[str, Any]] = read_json(store.relation_edges_path, [])
    edges_by_id: dict[str, list[dict[str, Any]]] = {}
    for edge in relation_edges:
        edges_by_id.setdefault(edge["from_id"], []).append(edge)
        edges_by_id.setdefault(edge["to_id"], []).append(edge)
    records_by_id = {r["memory_id"]: r for r in records}

    query_tokens = tokenize(query) - LEXICAL_NOISE_TOKENS
    query_semantic = semantic_tokens(query)
    use_embeddings = store.config["retrieval"]["embedding_enabled"] if embedding_enabled is None else embedding_enabled
    rerank_threshold = float(store.config["retrieval"].get("rerank_ambiguity_threshold", 0.8))
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    lexical_only_scored: list[tuple[float, dict[str, Any]]] = []
    excluded: list[dict[str, Any]] = []

    # Stage 1: Fast prefilter (lexical scoring for all records)
    prefilter_results: list[tuple[float, dict[str, Any]]] = []

    for record in records:
        if record["status"] not in {"active", "contested"}:
            record_edges = edges_by_id.get(record["memory_id"], [])
            relation_notes = build_relation_explanations(record["memory_id"], record_edges, records_by_id)
            excluded.append(
                _excluded_record(
                    record,
                    reason=f"status {record['status']} excluded from retrieval",
                    reason_code="status_not_retrievable",
                    timestamp=timestamp,
                    include_contested=include_contested,
                    record_edges=record_edges,
                    relation_notes=relation_notes,
                )
            )
            continue
        if record["status"] == "contested" and not include_contested:
            record_edges = edges_by_id.get(record["memory_id"], [])
            relation_notes = build_relation_explanations(record["memory_id"], record_edges, records_by_id)
            excluded.append(
                _excluded_record(
                    record,
                    reason="contested excluded by default",
                    reason_code="contested_default_exclusion",
                    timestamp=timestamp,
                    include_contested=include_contested,
                    record_edges=record_edges,
                    relation_notes=relation_notes,
                )
            )
            continue

        record_text = " ".join([record["title"], record["summary"], record["body"]])
        record_tokens = tokenize(record_text) - LEXICAL_NOISE_TOKENS
        lexical_overlap = sorted(query_tokens & record_tokens)
        lexical_score = len(lexical_overlap) / max(1, len(query_tokens))

        if lexical_score == 0:
            # Check semantic before excluding
            if use_embeddings:
                record_semantic = semantic_tokens(record_text)
                embedding_overlap = sorted(query_semantic & record_semantic)
                embedding_score = len(embedding_overlap) / max(1, len(query_semantic | record_semantic))
                if embedding_score == 0:
                    record_edges = edges_by_id.get(record["memory_id"], [])
                    relation_notes = build_relation_explanations(record["memory_id"], record_edges, records_by_id)
                    excluded.append(
                        _excluded_record(
                            record,
                            reason="no lexical or semantic match",
                            reason_code="no_match",
                            timestamp=timestamp,
                            include_contested=include_contested,
                            lexical_overlap=lexical_overlap,
                            semantic_overlap=embedding_overlap,
                            record_edges=record_edges,
                            relation_notes=relation_notes,
                        )
                    )
                    continue
            else:
                record_edges = edges_by_id.get(record["memory_id"], [])
                relation_notes = build_relation_explanations(record["memory_id"], record_edges, records_by_id)
                excluded.append(
                    _excluded_record(
                        record,
                        reason="no lexical or semantic match",
                        reason_code="no_match",
                        timestamp=timestamp,
                        include_contested=include_contested,
                        lexical_overlap=lexical_overlap,
                        semantic_overlap=[],
                        record_edges=record_edges,
                        relation_notes=relation_notes,
                    )
                )
                continue

        prefilter_results.append((lexical_score, record))
        if lexical_score > 0:
            lexical_only_score = round(lexical_score * 5, 4)
            lexical_only_scored.append((lexical_only_score, record))

    # Stage 2: Determine if rerank is needed
    prefilter_results.sort(key=lambda item: -item[0])
    needs_rerank = len(prefilter_results) >= 2
    if len(prefilter_results) >= 2:
        top1 = prefilter_results[0][0]
        top2 = prefilter_results[1][0]
        if top2 > 0 and (top1 / top2) > (1.0 / rerank_threshold):
            needs_rerank = False

    rerank = _rerank_explanation(
        prefilter_results,
        needs_rerank=needs_rerank,
        rerank_threshold=rerank_threshold,
    )

    for lexical_score, record in prefilter_results:
        record_text = " ".join([record["title"], record["summary"], record["body"]])
        record_tokens = tokenize(record_text) - LEXICAL_NOISE_TOKENS
        record_semantic = semantic_tokens(record_text)
        lexical_overlap = sorted(query_tokens & record_tokens)
        embedding_overlap = sorted(query_semantic & record_semantic)
        embedding_score = len(embedding_overlap) / max(1, len(query_semantic | record_semantic))
        recency_days = max((parse_timestamp(timestamp) - parse_timestamp(record["updated_at"])).days, 0)
        recency_bonus = 1 / (1 + recency_days)
        type_prior = QUERY_TYPE_BOOSTS.get(canonical_memory_type(record["type"]), 0.5)
        scope_prior = SCOPE_PRIORS.get(record["scope"], 0.5)

        if needs_rerank:
            total_score = (
                lexical_score * 4
                + type_prior
                + float(record["confidence"])
                + float(record["salience"])
                + recency_bonus
            )
            if use_embeddings:
                total_score += embedding_score * 3 + scope_prior
        else:
            # Fast path: simpler scoring
            total_score = (
                lexical_score * 4
                + type_prior
                + float(record["confidence"])
                + float(record["salience"])
                + recency_bonus
            )
            if use_embeddings:
                total_score += embedding_score * 3 + scope_prior

        # Relation-aware adjustment.
        record_edges = edges_by_id.get(record["memory_id"], [])
        relation_adj = relation_aware_score_adjustment(record["memory_id"], record_edges)
        total_score += relation_adj

        # Procedural-aware boost for task-shaped queries.
        procedural_query_boost = 0.0
        if is_workflow_memory_type(record["type"]) and _is_task_shaped_query(query):
            procedural_query_boost = 1.5
            total_score += procedural_query_boost

        total_score = round(total_score, 4)

        relation_notes = build_relation_explanations(record["memory_id"], record_edges, records_by_id)
        score_contributions = {
            "lexical": round(lexical_score * 4, 4),
            "embedding": round(embedding_score * 3, 4) if use_embeddings else 0.0,
            "type_prior": round(type_prior, 4),
            "recency_prior": round(recency_bonus, 4),
            "scope_prior": round(scope_prior, 4) if use_embeddings else 0.0,
            "confidence": round(float(record["confidence"]), 4),
            "salience": round(float(record["salience"]), 4),
            "relation_adjustment": round(relation_adj, 4),
            "procedural_query_boost": round(procedural_query_boost, 4),
        }

        explanation = {
            "memory_id": record["memory_id"],
            "matched_evidence": {
                "lexical_terms": lexical_overlap,
                "semantic_terms": embedding_overlap,
            },
            "score_contributions": score_contributions,
            "score_components": _score_component_list(score_contributions),
            "freshness": _freshness_explanation(record, timestamp, recency_bonus),
            "conflict": _conflict_explanation(
                record,
                record_edges,
                relation_notes,
                include_contested=include_contested,
            ),
            "why_included": _why_included(record, lexical_overlap, embedding_overlap),
            "relation_notes": relation_notes,
            "why_excluded": None,
            "score": total_score,
            "status": record["status"],
            "provenance_tier": record.get("provenance_tier", "inferred"),
        }
        scored.append((total_score, record, explanation))

    scored.sort(key=lambda item: (-item[0], item[1]["status"] != "active", item[1]["title"]))
    lexical_only_scored.sort(key=lambda item: (-item[0], item[1]["title"]))
    selected = scored[:limit]

    run_id = stable_id("retrieve", timestamp, query, limit, use_embeddings)

    # Memory-hurt instrumentation
    hurt_payload = _build_memory_hurt(selected, timestamp)
    if any(hurt_payload[k] for k in ("stale_recalled", "contradicted_recalled", "low_confidence_recalled")):
        store.write_memory_hurt_audit(run_id, {
            "run_id": run_id,
            "timestamp": timestamp,
            "query": query,
            **hurt_payload,
        })

    response: dict[str, Any] = {
        "run_id": run_id,
        "gated": False,
        "selected_memory_ids": [record["memory_id"] for _, record, _ in selected],
        "lexical_only_selected_memory_ids": [record["memory_id"] for _, record in lexical_only_scored[:limit]],
        "why": [
            {
                "memory_id": record["memory_id"],
                "reason": explanation["why_included"],
                "score": score,
            }
            for score, record, explanation in selected
        ],
        "explanations": [explanation for _, _, explanation in selected],
        "excluded": excluded[: max(limit, 3)],
        "reranked": needs_rerank,
        "rerank": rerank,
        "memory_hurt": hurt_payload,
        "reporting_agent": normalized_agent,
    }
    audit_payload: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": timestamp,
        "query": query,
        "selected_memory_ids": response["selected_memory_ids"],
        "lexical_only_selected_memory_ids": response["lexical_only_selected_memory_ids"],
        "why": response["why"],
        "explanations": response["explanations"],
        "excluded": response["excluded"],
        "rerank": response["rerank"],
        "summary": summarize(query, 80),
        "reporting_agent": normalized_agent,
    }
    if query_source:
        audit_payload["query_source"] = query_source
    if caller_detail:
        audit_payload["caller_detail"] = caller_detail
    store.write_retrieval_audit(str(audit_payload["run_id"]), audit_payload)
    response["cli_output_version"] = CLI_JSON_VERSION
    return response


def _build_memory_hurt(
    selected: list[tuple[float, dict[str, Any], dict[str, Any]]],
    timestamp: str,
) -> dict[str, Any]:
    """Detect stale, contradicted, and low-confidence recalls in the selected set."""
    stale: list[dict[str, str]] = []
    contradicted: list[dict[str, str]] = []
    low_confidence: list[dict[str, str]] = []

    for _, record, _ in selected:
        memory_id = record["memory_id"]
        updated_days = max((parse_timestamp(timestamp) - parse_timestamp(record["updated_at"])).days, 0)
        if updated_days > STALE_DAYS_THRESHOLD:
            stale.append({"memory_id": memory_id, "days_stale": str(updated_days)})
        if record["status"] == "contested":
            contradicted.append({"memory_id": memory_id, "status": record["status"]})
        if float(record["confidence"]) < LOW_CONFIDENCE_THRESHOLD:
            low_confidence.append({"memory_id": memory_id, "confidence": str(record["confidence"])})

    return {
        "stale_recalled": stale,
        "contradicted_recalled": contradicted,
        "low_confidence_recalled": low_confidence,
    }


_TASK_PATTERNS = {
    "how", "step", "steps", "workflow", "migrate", "migration",
    "deploy", "setup", "install", "configure", "run", "fix", "debug",
}


def _is_task_shaped_query(query: str) -> bool:
    """Return True if the query looks like a task/procedure request."""
    tokens = tokenize(query)
    return bool(tokens & _TASK_PATTERNS)


def _why_included(record: dict[str, Any], lexical_overlap: list[str], semantic_overlap: list[str]) -> str:
    evidence: list[str] = []
    if lexical_overlap:
        evidence.append(f"lexical match on {', '.join(lexical_overlap[:4])}")
    if semantic_overlap:
        evidence.append(f"semantic match on {', '.join(semantic_overlap[:4])}")
    if record["status"] == "contested":
        evidence.append("record is contested and should be treated cautiously")
    evidence.append(f"type={record['type']}")
    return "; ".join(evidence)


# ── Retrieval fusion with learned context (WS7: T35-T40) ────────────────

LEARNED_CONTEXT_FRESHNESS_PENALTY = 0.3
LEARNED_CONTEXT_CONFLICT_PENALTY = 0.5


def retrieve_with_fusion(
    store: MemoryStore,
    *,
    query: str,
    limit: int = 5,
    include_contested: bool = False,
    include_learned_context: bool = True,
    include_automation: bool = True,
    now: str | None = None,
    skip_retrieval: bool = False,
) -> dict[str, Any]:
    """Extended retrieval with fusion across durable, learned context, and automation sources.

    Fuses results from:
    1. Durable fact/preference/environment records (highest priority on direct conflict)
    2. Procedural memory
    3. Learned-context records (freshness-aware, query-family-matched)
    4. Automation projections (non-canonical, labeled)

    Returns per-source attribution in the response.
    """
    timestamp = now or to_iso(utc_now())

    # Start with standard durable retrieval
    base_result = retrieve(
        store,
        query=query,
        limit=limit * 2,  # Fetch more to allow fusion ranking
        include_contested=include_contested,
        now=timestamp,
        skip_retrieval=skip_retrieval,
        query_source="retrieve_with_fusion",
    )

    if base_result.get("gated"):
        base_result["selected_learned_context_ids"] = []
        base_result["selected_automation_record_ids"] = []
        base_result["source_attribution"] = {}
        base_result["learned_context_explanations"] = []
        return base_result

    query_tokens = tokenize(query) - LEXICAL_NOISE_TOKENS
    query_semantic = semantic_tokens(query)

    # Collect learned context matches
    learned_context_results: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    if include_learned_context:
        learned_records = store.load_learned_context_records()
        for record in learned_records:
            if record.get("status") != "active":
                continue
            if record.get("verifier_status") not in ("approved", "review_required"):
                continue

            record_text = f"{record.get('summary', '')} {record.get('details', '')}"
            record_tokens = tokenize(record_text) - LEXICAL_NOISE_TOKENS
            record_semantic = semantic_tokens(record_text)
            lexical_terms = sorted(query_tokens & record_tokens)
            semantic_terms = sorted(query_semantic & record_semantic)

            lexical_score = len(query_tokens & record_tokens) / max(1, len(query_tokens))
            semantic_score = len(query_semantic & record_semantic) / max(1, len(query_semantic | record_semantic))

            if lexical_score == 0 and semantic_score == 0:
                continue

            # Base score
            confidence = float(record.get("confidence", 0.5))
            score = lexical_score * 3 + semantic_score * 2 + confidence

            # Query family bonus
            family_tags = set(record.get("query_family_tags", []))
            family_match = bool(family_tags & query_semantic)
            query_family_bonus = 0.0
            if family_match:
                query_family_bonus = 1.0
                score += query_family_bonus

            # Freshness penalty
            freshness = _learned_context_freshness_explanation(record, timestamp)
            fresh_until = record.get("fresh_until", "")
            if fresh_until:
                try:
                    if parse_timestamp(fresh_until) < parse_timestamp(timestamp):
                        score -= LEARNED_CONTEXT_FRESHNESS_PENALTY
                except (ValueError, TypeError):
                    pass

            # Conflict penalty
            conflict = _learned_context_conflict_explanation(record)
            if record.get("conflict_state") in ("detected", "overridden"):
                score -= LEARNED_CONTEXT_CONFLICT_PENALTY

            score_contributions = {
                "lexical": round(lexical_score * 3, 4),
                "embedding": round(semantic_score * 2, 4),
                "confidence": round(confidence, 4),
                "query_family_bonus": round(query_family_bonus, 4),
                "freshness_penalty": freshness["score_effect"],
                "conflict_penalty": conflict["score_effect"],
            }
            rounded_score = round(score, 4)
            explanation = {
                "record_id": record.get("record_id", ""),
                "matched_evidence": {
                    "lexical_terms": lexical_terms,
                    "semantic_terms": semantic_terms,
                },
                "score_contributions": score_contributions,
                "score_components": _score_component_list(score_contributions),
                "freshness": freshness,
                "conflict": conflict,
                "score": rounded_score,
                "verifier_status": record.get("verifier_status"),
            }
            learned_context_results.append((rounded_score, record, explanation))

    learned_context_results.sort(key=lambda x: -x[0])

    # Collect automation projection matches
    automation_results: list[tuple[float, dict[str, Any]]] = []
    if include_automation:
        automation_records = store.load_automation_records()
        for record in automation_records:
            if record.get("status") != "active":
                continue
            record_text = f"{record.get('title', '')} {record.get('summary', '')}"
            record_tokens = tokenize(record_text) - LEXICAL_NOISE_TOKENS
            lexical_score = len(query_tokens & record_tokens) / max(1, len(query_tokens))
            if lexical_score > 0:
                score = lexical_score * 2 + float(record.get("confidence", 0.5))
                automation_results.append((round(score, 4), record))

    automation_results.sort(key=lambda x: -x[0])

    # Build fused result with attribution
    selected_durable_ids = base_result.get("selected_memory_ids", [])[:limit]
    selected_learned_context = learned_context_results[:max(1, limit // 3)]
    selected_learned_ids = [
        r.get("record_id", "") for _, r, _ in selected_learned_context
    ]
    selected_automation_ids = [
        r.get("record_id", "") for _, r in automation_results[:max(1, limit // 4)]
    ]

    source_attribution = {
        "durable_records": len(selected_durable_ids),
        "learned_context": len(selected_learned_ids),
        "automation_projections": len(selected_automation_ids),
    }

    # Merge into response
    fused = dict(base_result)
    fused["selected_memory_ids"] = selected_durable_ids
    fused["selected_learned_context_ids"] = selected_learned_ids
    fused["selected_automation_record_ids"] = selected_automation_ids
    fused["source_attribution"] = source_attribution
    fused["learned_context_explanations"] = [
        explanation for _, _, explanation in selected_learned_context
    ]
    fused["fusion_enabled"] = True

    # Add harm signals for stale learned context
    harm_signals: list[str] = []
    for _, record, _ in selected_learned_context:
        fresh_until = record.get("fresh_until", "")
        if fresh_until:
            try:
                if parse_timestamp(fresh_until) < parse_timestamp(timestamp):
                    harm_signals.append(f"stale_learned_context:{record.get('record_id', '')}")
            except (ValueError, TypeError):
                pass
        if record.get("conflict_state") in ("detected", "overridden"):
            harm_signals.append(f"conflicted_learned_context:{record.get('record_id', '')}")

    if harm_signals:
        fused.setdefault("memory_hurt", {})
        fused["memory_hurt"]["learned_context_harm"] = harm_signals

    return fused
