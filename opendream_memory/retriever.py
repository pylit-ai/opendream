from __future__ import annotations

from typing import Any

from .storage import MemoryStore
from .util import parse_timestamp, stable_id, summarize, to_iso, tokenize, utc_now


QUERY_TYPE_BOOSTS = {
    "project_decision": 2.5,
    "environment_requirement": 2.2,
    "procedural_workflow": 2.0,
    "anti_pattern": 1.8,
    "user_preference": 1.5,
    "pending_item": 1.0,
}


def retrieve(
    store: MemoryStore,
    *,
    query: str,
    limit: int = 5,
    include_contested: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    records = store.load_durable_records()
    query_tokens = tokenize(query)
    scored: list[tuple[float, dict[str, Any], list[str]]] = []

    for record in records:
        if record["status"] != "active":
            continue
        if record["type"] == "contested_fact" and not include_contested:
            continue
        record_tokens = tokenize(" ".join([record["title"], record["summary"], record["body"]]))
        overlap = len(query_tokens & record_tokens)
        lexical_score = overlap / max(1, len(query_tokens))
        if lexical_score == 0 and record["type"] not in QUERY_TYPE_BOOSTS:
            continue
        recency_days = max((parse_timestamp(timestamp) - parse_timestamp(record["updated_at"])).days, 0)
        recency_bonus = 1 / (1 + recency_days)
        score = round(
            lexical_score * 5
            + QUERY_TYPE_BOOSTS.get(record["type"], 0.5)
            + float(record["confidence"])
            + float(record["salience"])
            + recency_bonus,
            4,
        )
        reasons = []
        if overlap:
            reasons.append(f"lexical overlap={overlap}")
        reasons.append(f"type boost={QUERY_TYPE_BOOSTS.get(record['type'], 0.5)}")
        reasons.append(f"recency bonus={round(recency_bonus, 3)}")
        scored.append((score, record, reasons))

    scored.sort(key=lambda item: (-item[0], item[1]["title"]))
    selected = scored[:limit]
    response = {
        "selected_memory_ids": [record["memory_id"] for _, record, _ in selected],
        "why": [
            {
                "memory_id": record["memory_id"],
                "reason": "; ".join(reasons),
                "score": score,
            }
            for score, record, reasons in selected
        ],
    }
    audit_payload = {
        "run_id": stable_id("retrieve", timestamp, query, limit),
        "timestamp": timestamp,
        "query": query,
        "selected_memory_ids": response["selected_memory_ids"],
        "why": response["why"],
        "summary": summarize(query, 80),
    }
    store.write_retrieval_audit(audit_payload["run_id"], audit_payload)
    return response
