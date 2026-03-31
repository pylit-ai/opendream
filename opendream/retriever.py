from __future__ import annotations

from typing import Any

from .storage import MemoryStore
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

QUERY_TYPE_BOOSTS = {
    "project_decision": 2.5,
    "environment_requirement": 2.2,
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


def retrieve(
    store: MemoryStore,
    *,
    query: str,
    limit: int = 5,
    include_contested: bool = False,
    now: str | None = None,
    embedding_enabled: bool | None = None,
    skip_retrieval: bool = False,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())

    # Retrieval gating
    min_content_tokens = int(store.config["retrieval"].get("gating_min_content_tokens", 3))
    should_run, gate_reason = should_retrieve(
        query, skip_retrieval=skip_retrieval, min_content_tokens=min_content_tokens,
    )
    if not should_run:
        run_id = stable_id("retrieve", timestamp, query, limit, "gated")
        return {
            "run_id": run_id,
            "gated": True,
            "reason": gate_reason,
            "selected_memory_ids": [],
            "lexical_only_selected_memory_ids": [],
            "why": [],
            "explanations": [],
            "excluded": [],
            "cli_output_version": CLI_JSON_VERSION,
        }

    records = store.load_durable_records()
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
            continue
        if record["status"] == "contested" and not include_contested:
            excluded.append({"memory_id": record["memory_id"], "reason": "contested excluded by default"})
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
                    excluded.append({"memory_id": record["memory_id"], "reason": "no lexical or semantic match"})
                    continue
            else:
                excluded.append({"memory_id": record["memory_id"], "reason": "no lexical or semantic match"})
                continue

        prefilter_results.append((lexical_score, record))
        if lexical_score > 0:
            lexical_only_score = round(lexical_score * 5, 4)
            lexical_only_scored.append((lexical_only_score, record))

    # Stage 2: Determine if rerank is needed
    prefilter_results.sort(key=lambda item: -item[0])
    needs_rerank = True
    if len(prefilter_results) >= 2:
        top1 = prefilter_results[0][0]
        top2 = prefilter_results[1][0]
        if top2 > 0 and (top1 / top2) > (1.0 / rerank_threshold):
            needs_rerank = False
    elif len(prefilter_results) == 1:
        needs_rerank = False

    reranked = not needs_rerank  # Track whether we skipped rerank

    for lexical_score, record in prefilter_results:
        record_text = " ".join([record["title"], record["summary"], record["body"]])
        record_tokens = tokenize(record_text) - LEXICAL_NOISE_TOKENS
        record_semantic = semantic_tokens(record_text)
        lexical_overlap = sorted(query_tokens & record_tokens)
        embedding_overlap = sorted(query_semantic & record_semantic)
        embedding_score = len(embedding_overlap) / max(1, len(query_semantic | record_semantic))
        recency_days = max((parse_timestamp(timestamp) - parse_timestamp(record["updated_at"])).days, 0)
        recency_bonus = 1 / (1 + recency_days)
        type_prior = QUERY_TYPE_BOOSTS.get(record["type"], 0.5)
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

        total_score = round(total_score, 4)

        explanation = {
            "memory_id": record["memory_id"],
            "matched_evidence": {
                "lexical_terms": lexical_overlap,
                "semantic_terms": embedding_overlap,
            },
            "score_contributions": {
                "lexical": round(lexical_score * 4, 4),
                "embedding": round(embedding_score * 3, 4) if use_embeddings else 0.0,
                "type_prior": round(type_prior, 4),
                "recency_prior": round(recency_bonus, 4),
                "scope_prior": round(scope_prior, 4) if use_embeddings else 0.0,
                "confidence": round(float(record["confidence"]), 4),
                "salience": round(float(record["salience"]), 4),
            },
            "why_included": _why_included(record, lexical_overlap, embedding_overlap),
            "why_excluded": None,
            "score": total_score,
            "status": record["status"],
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
        "reranked": not reranked,
        "memory_hurt": hurt_payload,
    }
    audit_payload = {
        "run_id": run_id,
        "timestamp": timestamp,
        "query": query,
        "selected_memory_ids": response["selected_memory_ids"],
        "lexical_only_selected_memory_ids": response["lexical_only_selected_memory_ids"],
        "why": response["why"],
        "explanations": response["explanations"],
        "excluded": response["excluded"],
        "summary": summarize(query, 80),
    }
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
