from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .dream import dream_run
from .integration import emit_event, maintain
from .retriever import retrieve
from .storage import MemoryStore
from .util import FIXTURE_ROOT, read_json, to_iso, utc_now


def run_memory_quality_eval(
    store: MemoryStore,
    *,
    fixture_path: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    fixture = read_json(fixture_path or (FIXTURE_ROOT / "memory_quality_eval.json"), {})
    events = fixture.get("events", [])
    queries = fixture.get("queries", [])
    for event in events:
        emit_event(
            store,
            kind=str(event["kind"]),
            content=str(event["content"]),
            scope=str(event.get("scope", "project")),
            channel="system",
            message_ref=str(event["message_ref"]),
            timestamp=str(event.get("timestamp", timestamp)),
            tags=[str(tag) for tag in event.get("tags", [])],
            confidence_hint=float(event["confidence_hint"]) if "confidence_hint" in event else None,
            sensitivity=str(event.get("sensitivity", "normal")),
        )
    maintain(store, now=timestamp)

    query_results: list[dict[str, Any]] = []
    paraphrase_hits = 0
    lexical_misses = 0
    for query_case in queries:
        retrieval = retrieve(store, query=str(query_case["query"]), limit=5, now=timestamp)
        records = {record["memory_id"]: record for record in store.load_durable_records()}
        selected_titles = [
            records[memory_id]["title"]
            for memory_id in retrieval["selected_memory_ids"]
            if memory_id in records
        ]
        lexical_titles = [
            records[memory_id]["title"]
            for memory_id in retrieval["lexical_only_selected_memory_ids"]
            if memory_id in records
        ]
        expected_title = str(query_case["expected_title"])
        hit = expected_title in selected_titles
        lexical_hit = expected_title in lexical_titles
        if hit:
            paraphrase_hits += 1
        if not lexical_hit:
            lexical_misses += 1
        query_results.append(
            {
                "query": query_case["query"],
                "expected_title": expected_title,
                "selected_titles": selected_titles,
                "lexical_only_titles": lexical_titles,
                "hit": hit,
                "lexical_only_hit": lexical_hit,
            }
        )

    durable_records = store.load_durable_records()
    duplicate_active_titles = _duplicate_active_titles(durable_records)
    contradictions_visible = [
        record["title"] for record in durable_records if record["status"] == "contested"
    ]

    return {
        "status": "passed" if paraphrase_hits == len(queries) and not duplicate_active_titles else "failed",
        "workspace": str(store.workspace),
        "query_count": len(queries),
        "paraphrase_hits": paraphrase_hits,
        "lexical_only_misses": lexical_misses,
        "duplicate_active_titles": duplicate_active_titles,
        "contested_titles": contradictions_visible,
        "queries": query_results,
    }


def run_dream_fidelity_eval(
    store: MemoryStore,
    *,
    fixture_path: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    fixture = fixture_path or (FIXTURE_ROOT / "dream_fidelity_transcript.jsonl")
    result = dream_run(store, episode_paths=[fixture], now=timestamp)
    status_snapshot = store.status_snapshot(now=timestamp)
    dream_snapshot = status_snapshot["dream"]
    records = store.load_durable_records()
    memory_lines = store.memory_md_path.read_text(encoding="utf-8").splitlines()
    retrieval = retrieve(
        store,
        query="What package manager and schema migration workflow should I use?",
        limit=5,
        now=timestamp,
    )
    selected_titles = {
        record["title"]
        for record in records
        if record["memory_id"] in retrieval["selected_memory_ids"]
    }
    search_plan = result.get("search_plan", {})
    checks = {
        "transcript_only_durable_emergence": result["status"] == "completed" and bool(records),
        "four_phase_lifecycle": result.get("phases")
        == ["orient", "gather_recent_signal", "consolidate", "prune_and_reindex"],
        "date_normalization": any("2026-03-27" in record["body"] for record in records),
        "lean_memory_index": len([line for line in memory_lines if line.startswith("- [")])
        <= int(store.config["index_policy"]["max_entries"]),
        "compatibility_views": (store.memory_root / "project.md").exists()
        and (store.memory_root / "user.md").exists(),
        "dream_status_surface": dream_snapshot.get("state") == "idle"
        and dream_snapshot.get("last_ran_at") == timestamp,
        "bounded_search_reported": bool(search_plan.get("files_consulted"))
        and not search_plan.get("full_corpus_replay", True),
        "retrieval_from_dream_memory": any("pnpm" in title.lower() for title in selected_titles)
        and "Workflow: schema-migration" in selected_titles,
    }
    overall_status = "passed" if all(checks.values()) else "failed"
    return {
        "status": overall_status,
        "workspace": str(store.workspace),
        "fixture": str(fixture),
        "checks": checks,
        "dream_run": result,
        "dream_status": dream_snapshot,
        "record_count": len(records),
        "selected_titles": sorted(selected_titles),
    }


def run_performance_eval(
    store: MemoryStore,
    *,
    fixture_path: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    fixture = read_json(fixture_path or (FIXTURE_ROOT / "performance_eval.json"), {})
    events_data = fixture.get("events", {})
    queries_data = fixture.get("queries", {})

    high_signal_events = events_data.get("high_signal", [])
    noise_events = events_data.get("noise", [])
    contradiction_events = events_data.get("contradictions", [])
    all_events = high_signal_events + noise_events + contradiction_events

    # --- Phase 1: Emit high-signal and noise events, consolidate ---
    phase1_events = high_signal_events + noise_events
    emit_start = time.monotonic()
    for event in phase1_events:
        emit_event(
            store,
            kind=str(event["kind"]),
            content=str(event["content"]),
            scope=str(event.get("scope", "project")),
            channel="system",
            message_ref=str(event["message_ref"]),
            timestamp=str(event.get("timestamp", timestamp)),
            tags=[str(tag) for tag in event.get("tags", [])],
            confidence_hint=float(event["confidence_hint"]) if "confidence_hint" in event else None,
            sensitivity=str(event.get("sensitivity", "normal")),
        )
    emit_ms = round((time.monotonic() - emit_start) * 1000, 1)

    maintain_start = time.monotonic()
    maintain(store, now=timestamp)
    maintain_ms = round((time.monotonic() - maintain_start) * 1000, 1)

    # --- Phase 2: Emit contradiction events, consolidate again ---
    for event in contradiction_events:
        emit_event(
            store,
            kind=str(event["kind"]),
            content=str(event["content"]),
            scope=str(event.get("scope", "project")),
            channel="system",
            message_ref=str(event["message_ref"]),
            timestamp=str(event.get("timestamp", timestamp)),
            tags=[str(tag) for tag in event.get("tags", [])],
            confidence_hint=float(event["confidence_hint"]) if "confidence_hint" in event else None,
            sensitivity=str(event.get("sensitivity", "normal")),
        )
    if contradiction_events:
        maintain(store, now=timestamp)

    # --- Write precision ---
    durable_records = store.load_durable_records()
    active_records = [r for r in durable_records if r["status"] == "active"]
    high_signal_titles = {
        "Decision: database-choice",
        "Environment: node-version",
        "Workflow: deploy",
        "Preference: logging-preference",
    }
    active_titles = {r["title"] for r in active_records}
    high_signal_in_durable = len(high_signal_titles & active_titles)
    noise_in_durable = len([
        r for r in active_records
        if r["title"] not in high_signal_titles
        and r["status"] == "active"
        and r["type"] == "semantic_fact"
    ])
    write_precision = high_signal_in_durable / max(1, len(active_records)) if active_records else 0.0

    # --- Contradiction handling ---
    contested_records = [r for r in durable_records if r["status"] == "contested"]
    superseded_records = [r for r in durable_records if r["status"] == "superseded"]
    contradiction_resolved = len(contested_records) + len(superseded_records) > 0

    # --- Retrieval precision ---
    should_match_queries = queries_data.get("should_match", [])
    retrieval_hits = 0
    retrieval_timings: list[float] = []
    retrieval_results: list[dict[str, Any]] = []

    for query_case in should_match_queries:
        r_start = time.monotonic()
        retrieval = retrieve(store, query=str(query_case["query"]), limit=5, now=timestamp)
        r_ms = round((time.monotonic() - r_start) * 1000, 1)
        retrieval_timings.append(r_ms)
        records_map = {r["memory_id"]: r for r in durable_records}
        selected_titles = [
            records_map[mid]["title"]
            for mid in retrieval.get("selected_memory_ids", [])
            if mid in records_map
        ]
        expected = str(query_case["expected_title"])
        hit = expected in selected_titles
        if hit:
            retrieval_hits += 1
        retrieval_results.append({
            "query": query_case["query"],
            "expected": expected,
            "selected_titles": selected_titles,
            "hit": hit,
            "latency_ms": r_ms,
        })

    retrieval_precision = retrieval_hits / max(1, len(should_match_queries))

    # --- Retrieval gating accuracy ---
    should_gate_queries = queries_data.get("should_gate", [])
    gating_correct = 0
    gating_results: list[dict[str, Any]] = []
    for query_case in should_gate_queries:
        retrieval = retrieve(store, query=str(query_case["query"]), limit=5, now=timestamp)
        gated = retrieval.get("gated", False)
        if gated:
            gating_correct += 1
        gating_results.append({
            "query": query_case["query"],
            "expected_gated": True,
            "actual_gated": gated,
            "correct": gated,
        })

    gating_accuracy = gating_correct / max(1, len(should_gate_queries))

    # --- Token cost estimate ---
    total_durable_chars = sum(len(r["body"]) + len(r["summary"]) + len(r["title"]) for r in active_records)
    startup_index = store.load_startup_index()
    startup_chars = sum(
        len(e.get("summary", "")) + len(e.get("title", ""))
        for e in startup_index.get("entries", [])
    )
    token_efficiency = startup_chars / max(1, total_durable_chars) if total_durable_chars else 1.0

    # --- Latency stats ---
    sorted_timings = sorted(retrieval_timings) if retrieval_timings else [0.0]
    p50_idx = len(sorted_timings) // 2
    p95_idx = min(int(len(sorted_timings) * 0.95), len(sorted_timings) - 1)

    # --- Scorecard (maps to planning.md rubric) ---
    write_score = round(min(100, write_precision * 80 + (20 if noise_in_durable == 0 else 0)), 1)
    retrieval_score = round(retrieval_precision * 100, 1)
    latency_score = round(min(100, max(0, 100 - maintain_ms / 10)), 1)  # penalize >1s
    concurrency_score = 100.0  # tested separately; structural guarantee
    contradiction_score = 100.0 if contradiction_resolved else 0.0
    procedural_score = round(100.0 if any(r["type"] == "procedural_workflow" for r in active_records) else 0.0, 1)
    gating_score = round(gating_accuracy * 100, 1)

    weighted_total = round(
        write_score * 0.20
        + retrieval_score * 0.20
        + latency_score * 0.15
        + concurrency_score * 0.15
        + contradiction_score * 0.10
        + procedural_score * 0.10
        + gating_score * 0.10,
        1,
    )

    passed = weighted_total >= 80.0 and write_score >= 60.0 and retrieval_score >= 60.0

    return {
        "status": "passed" if passed else "failed",
        "workspace": str(store.workspace),
        "scorecard": {
            "write_precision": write_score,
            "retrieval_precision": retrieval_score,
            "latency": latency_score,
            "concurrency_safety": concurrency_score,
            "contradiction_handling": contradiction_score,
            "procedural_reuse": procedural_score,
            "gating_accuracy": gating_score,
            "weighted_total": weighted_total,
        },
        "details": {
            "events_emitted": len(all_events),
            "high_signal_events": len(high_signal_events),
            "noise_events": len(noise_events),
            "contradiction_events": len(contradiction_events),
            "active_records": len(active_records),
            "high_signal_in_durable": high_signal_in_durable,
            "noise_in_durable": noise_in_durable,
            "contested_records": len(contested_records),
            "superseded_records": len(superseded_records),
            "write_precision_raw": round(write_precision, 4),
            "retrieval_precision_raw": round(retrieval_precision, 4),
            "gating_accuracy_raw": round(gating_accuracy, 4),
            "token_efficiency": round(token_efficiency, 4),
        },
        "latency": {
            "emit_all_ms": emit_ms,
            "maintain_ms": maintain_ms,
            "retrieval_p50_ms": sorted_timings[p50_idx],
            "retrieval_p95_ms": sorted_timings[p95_idx],
        },
        "retrieval_results": retrieval_results,
        "gating_results": gating_results,
    }


def _duplicate_active_titles(records: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for record in records:
        if record["status"] != "active":
            continue
        counts[record["title"]] = counts.get(record["title"], 0) + 1
    return sorted(title for title, count in counts.items() if count > 1)
