from __future__ import annotations

from typing import Any

from .storage import MemoryStore
from .util import parse_timestamp, semantic_tokens, stable_id, summarize, to_iso, tokenize, utc_now

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


def retrieve(
    store: MemoryStore,
    *,
    query: str,
    limit: int = 5,
    include_contested: bool = False,
    now: str | None = None,
    embedding_enabled: bool | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    records = store.load_durable_records()
    query_tokens = tokenize(query)
    query_semantic = semantic_tokens(query)
    use_embeddings = store.config["retrieval"]["embedding_enabled"] if embedding_enabled is None else embedding_enabled
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    lexical_only_scored: list[tuple[float, dict[str, Any]]] = []
    excluded: list[dict[str, Any]] = []

    for record in records:
        if record["status"] not in {"active", "contested"}:
            continue
        if record["status"] == "contested" and not include_contested:
            excluded.append({"memory_id": record["memory_id"], "reason": "contested excluded by default"})
            continue

        record_text = " ".join([record["title"], record["summary"], record["body"]])
        record_tokens = tokenize(record_text)
        record_semantic = semantic_tokens(record_text)
        lexical_overlap = sorted(query_tokens & record_tokens)
        lexical_score = len(lexical_overlap) / max(1, len(query_tokens))
        embedding_overlap = sorted(query_semantic & record_semantic)
        embedding_score = len(embedding_overlap) / max(1, len(query_semantic | record_semantic))
        recency_days = max((parse_timestamp(timestamp) - parse_timestamp(record["updated_at"])).days, 0)
        recency_bonus = 1 / (1 + recency_days)
        type_prior = QUERY_TYPE_BOOSTS.get(record["type"], 0.5)
        scope_prior = SCOPE_PRIORS.get(record["scope"], 0.5)

        if lexical_score > 0:
            lexical_only_score = round(lexical_score * 5, 4)
            lexical_only_scored.append((lexical_only_score, record))

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

        if lexical_score == 0 and (not use_embeddings or embedding_score == 0):
            excluded.append({"memory_id": record["memory_id"], "reason": "no lexical or semantic match"})
            continue

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
    response = {
        "run_id": run_id,
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
    return response


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
