from __future__ import annotations

from pathlib import Path
from typing import Any

from .episodes import load_episode_rows, looks_memory_worthy, row_to_event
from .integration import maintain
from .storage import LockError, MemoryStore
from .util import semantic_tokens, stable_id, to_iso, utc_now


def dream_run(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    now: str | None = None,
    max_recent_episodes: int | None = None,
    min_episode_signals: int | None = None,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    run_id = stable_id("dream", timestamp, store.store_id)
    before_snapshot = store.snapshot_store_text()
    policy = store.dream_policy(
        max_recent_episodes=max_recent_episodes,
        min_episode_signals=min_episode_signals,
    )
    try:
        with store.dream_lock():
            store.save_dream_state({"state": "dreaming", "last_started_at": timestamp, "run_id": run_id})
            rows = load_episode_rows(episode_paths)
            orientation_tokens = _orient(store)
            gathered = _gather_recent_signal(rows, orientation_tokens, policy["max_recent_episodes"])
            events = _rows_to_events(gathered)
            existing_ids = {event["event_id"] for event in store.load_events()}
            appended_events = [event for event in events if event.event_id not in existing_ids]

            for event in appended_events:
                store.append_event(event)

            if len(appended_events) < policy["min_episode_signals"]:
                summary = {
                    "run_id": run_id,
                    "status": "skipped",
                    "reason": "insufficient-signal",
                    "phases": ["orient", "gather_recent_signal"],
                    "gathered_rows": len(gathered),
                    "appended_events": len(appended_events),
                }
                store.save_dream_state(
                    {"state": "idle", "last_ran_at": timestamp, "run_id": run_id, "last_result": summary["status"]}
                )
                store.write_dream_audit(run_id, summary, before_snapshot)
                return summary

            maintenance = maintain(store, now=timestamp)
            summary = {
                "run_id": run_id,
                "status": "completed" if maintenance["status"] == "completed" else "skipped",
                "phases": ["orient", "gather_recent_signal", "consolidate", "prune_and_reindex"],
                "gathered_rows": len(gathered),
                "appended_events": len(appended_events),
                "maintain": maintenance,
                "policy": policy,
            }
            store.save_dream_state(
                {"state": "idle", "last_ran_at": timestamp, "run_id": run_id, "last_result": summary["status"]}
            )
            store.write_dream_audit(run_id, summary, before_snapshot)
            return summary
    except LockError:
        return {
            "run_id": run_id,
            "status": "skipped",
            "reason": "lock-held",
            "phases": ["orient"],
            "policy": policy,
        }


def _orient(store: MemoryStore) -> set[str]:
    tokens: set[str] = set()
    startup_index = store.load_startup_index()
    for entry in startup_index.get("entries", []):
        tokens.update(semantic_tokens(" ".join([entry["title"], entry["summary"]])))
    for record in store.load_durable_records():
        if record["status"] == "active":
            tokens.update(semantic_tokens(" ".join([record["title"], record["summary"]])))
    return tokens


def _gather_recent_signal(rows: list[dict[str, Any]], orientation_tokens: set[str], limit: int) -> list[dict[str, Any]]:
    recent_rows = rows[-limit:]
    return [
        row
        for row in recent_rows
        if looks_memory_worthy(
            str(row.get("text") or row.get("message") or ""),
            orientation_tokens,
        )
    ]


def _rows_to_events(rows: list[dict[str, Any]]) -> list[Any]:
    events = [row_to_event(row) for row in rows]
    return [event for event in events if event is not None]
