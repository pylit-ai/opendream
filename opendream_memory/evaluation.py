from __future__ import annotations

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


def _duplicate_active_titles(records: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for record in records:
        if record["status"] != "active":
            continue
        counts[record["title"]] = counts.get(record["title"], 0) + 1
    return sorted(title for title, count in counts.items() if count > 1)
