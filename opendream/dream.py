from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .episodes import latest_episode_timestamp, load_episode_rows, looks_memory_worthy, row_to_event
from .integration import maintain
from .storage import LockError, MemoryStore
from .util import parse_timestamp, semantic_tokens, stable_id, to_iso, utc_now
from .validation import validate_document


def dream_run(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    now: str | None = None,
    max_recent_episodes: int | None = None,
    min_episode_signals: int | None = None,
    trigger_class: str = "manual-run",
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    run_id = stable_id("dream", timestamp, store.store_id)
    before_snapshot = store.snapshot_store_text()
    policy = store.dream_policy(
        max_recent_episodes=max_recent_episodes,
        min_episode_signals=min_episode_signals,
    )
    started_at = time.monotonic()
    summary: dict[str, Any]
    try:
        with store.dream_lock():
            if not episode_paths:
                summary = {
                    "run_id": run_id,
                    "status": "skipped",
                    "reason": "no-episodes",
                    "phases": ["orient"],
                    "policy": policy,
                    "trigger_class": trigger_class,
                    "search_plan": {
                        "strategy": "bounded-tail-search",
                        "full_corpus_replay": False,
                        "max_recent_episodes": policy["max_recent_episodes"],
                        "orientation_token_sample": [],
                        "files_consulted": [],
                    },
                    "files_consulted": [],
                    "latest_episode_timestamp": None,
                }
                store.save_dream_state(
                    {
                        "state": "idle",
                        "last_ran_at": timestamp,
                        "run_id": run_id,
                        "last_result": summary["status"],
                        "last_run_summary": summary,
                        "last_run_reason": summary["reason"],
                        "last_run_duration_ms": 0,
                        "last_episode_timestamp": None,
                    }
                )
                store.write_dream_audit(run_id, summary, before_snapshot)
                return summary
            store.save_dream_state({"state": "dreaming", "last_started_at": timestamp, "run_id": run_id})
            rows = load_episode_rows(episode_paths, tail_limit=policy["max_recent_episodes"])
            orientation_tokens = _orient(store)
            gathered = _gather_recent_signal(rows, orientation_tokens, policy["max_recent_episodes"])
            events = _rows_to_events(gathered)
            existing_ids = {event["event_id"] for event in store.load_events()}
            appended_events = [event for event in events if event.event_id not in existing_ids]
            search_plan = _build_search_plan(
                episode_paths=episode_paths,
                rows=rows,
                gathered=gathered,
                orientation_tokens=orientation_tokens,
                limit=policy["max_recent_episodes"],
            )
            latest_input_timestamp = latest_episode_timestamp(episode_paths)

            for event in appended_events:
                store.append_event(event)

            if len(appended_events) < policy["min_episode_signals"]:
                duration_ms = round((time.monotonic() - started_at) * 1000)
                summary = {
                    "run_id": run_id,
                    "status": "skipped",
                    "reason": "insufficient-signal",
                    "phases": ["orient", "gather_recent_signal"],
                    "gathered_rows": len(gathered),
                    "appended_events": len(appended_events),
                    "duration_ms": duration_ms,
                    "search_plan": search_plan,
                    "files_consulted": [item["path"] for item in search_plan["files_consulted"]],
                    "latest_episode_timestamp": latest_input_timestamp,
                    "trigger_class": trigger_class,
                }
                store.save_dream_state(
                    {
                        "state": "idle",
                        "last_ran_at": timestamp,
                        "run_id": run_id,
                        "last_result": summary["status"],
                        "last_run_summary": summary,
                        "last_run_reason": summary.get("reason") or trigger_class,
                        "last_run_duration_ms": duration_ms,
                        "last_episode_timestamp": latest_input_timestamp,
                    }
                )
                store.write_dream_audit(run_id, summary, before_snapshot)
                return summary

            maintenance = maintain(store, now=timestamp)
            duration_ms = round((time.monotonic() - started_at) * 1000)
            summary = {
                "run_id": run_id,
                "status": "completed" if maintenance["status"] == "completed" else "skipped",
                "phases": ["orient", "gather_recent_signal", "consolidate", "prune_and_reindex"],
                "gathered_rows": len(gathered),
                "appended_events": len(appended_events),
                "maintain": maintenance,
                "policy": policy,
                "duration_ms": duration_ms,
                "search_plan": search_plan,
                "files_consulted": [item["path"] for item in search_plan["files_consulted"]],
                "latest_episode_timestamp": latest_input_timestamp,
                "trigger_class": trigger_class,
            }
            store.save_dream_state(
                {
                    "state": "idle",
                    "last_ran_at": timestamp,
                    "run_id": run_id,
                    "last_result": summary["status"],
                    "last_run_summary": summary,
                    "last_run_reason": summary["trigger_class"],
                    "last_run_duration_ms": duration_ms,
                    "last_episode_timestamp": latest_input_timestamp,
                }
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
            "trigger_class": trigger_class,
        }


def dream_tick(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    now: str | None = None,
    max_recent_episodes: int | None = None,
    min_episode_signals: int | None = None,
    min_interval_seconds: int = 0,
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    policy = store.dream_policy(
        max_recent_episodes=max_recent_episodes,
        min_episode_signals=min_episode_signals,
    )
    state = store.load_dream_state()
    if not episode_paths:
        return {
            "status": "skipped",
            "reason": "no-episodes",
            "phases": ["orient"],
            "policy": policy,
            "trigger_class": "transcript-backlog",
        }
    last_ran_at = state.get("last_ran_at")
    if last_ran_at and min_interval_seconds > 0:
        elapsed = (parse_timestamp(timestamp) - parse_timestamp(str(last_ran_at))).total_seconds()
        if elapsed < min_interval_seconds:
            return {
                "status": "skipped",
                "reason": "min-interval",
                "phases": ["orient"],
                "policy": policy,
                "trigger_class": "transcript-backlog",
            }
    latest_input_timestamp = latest_episode_timestamp(episode_paths)
    last_seen_timestamp = state.get("last_episode_timestamp")
    if latest_input_timestamp and last_seen_timestamp and parse_timestamp(latest_input_timestamp) <= parse_timestamp(
        str(last_seen_timestamp)
    ):
        return {
            "status": "skipped",
            "reason": "no-backlog",
            "phases": ["orient"],
            "policy": policy,
            "trigger_class": "transcript-backlog",
            "latest_episode_timestamp": latest_input_timestamp,
        }
    result = dream_run(
        store,
        episode_paths=episode_paths,
        now=timestamp,
        max_recent_episodes=max_recent_episodes,
        min_episode_signals=min_episode_signals,
        trigger_class="transcript-backlog",
    )
    return result


def enqueue_dream_job(
    store: MemoryStore,
    *,
    episode_paths: list[Path],
    now: str | None = None,
    max_recent_episodes: int | None = None,
    min_episode_signals: int | None = None,
    trigger_class: str = "queued-manual",
) -> dict[str, Any]:
    timestamp = now or to_iso(utc_now())
    queue = store.load_dream_queue()
    job = {
        "job_id": stable_id("dream-job", store.store_id, timestamp, len(queue)),
        "enqueued_at": timestamp,
        "trigger_class": trigger_class,
        "episode_paths": [str(path.expanduser()) for path in episode_paths],
        "max_recent_episodes": max_recent_episodes,
        "min_episode_signals": min_episode_signals,
        "status": "queued",
        "attempts": 0,
        "last_polled_at": None,
        "last_started_at": None,
        "last_finished_at": None,
        "last_result": None,
        "run_id": None,
        "error": None,
    }
    validate_document("dream-job.schema.json", job)
    queue.append(job)
    store.save_dream_queue(queue)
    return {"status": "queued", "job": job, "queue_depth": len([item for item in queue if item["status"] == "queued"])}


def dream_worker(
    store: MemoryStore,
    *,
    now: str | None = None,
    interval_seconds: float = 0.0,
    max_polls: int = 1,
    max_jobs_per_poll: int | None = None,
    idle_exit: bool = True,
    process_backlog: bool = True,
) -> dict[str, Any]:
    worker_run_id = stable_id("dream-worker", store.store_id, now or to_iso(utc_now()))
    before_snapshot = store.snapshot_store_text()
    processed_jobs: list[dict[str, Any]] = []
    backlog_results: list[dict[str, Any]] = []
    try:
        with store.dream_worker_lock():
            for poll_index in range(max_polls):
                timestamp = now or to_iso(utc_now())
                queue = store.load_dream_queue()
                queued_jobs = [job for job in queue if job.get("status") == "queued"]
                jobs_this_poll = 0

                if queued_jobs:
                    limit = max_jobs_per_poll or len(queued_jobs)
                    for job in queued_jobs[:limit]:
                        processed = _process_job(store, job, queue, now=timestamp)
                        if processed is not None:
                            processed_jobs.append(processed)
                            jobs_this_poll += 1
                elif process_backlog:
                    backlog = dream_tick(
                        store,
                        episode_paths=sorted(store.transcripts_dir.glob("*.jsonl")),
                        now=timestamp,
                    )
                    backlog_results.append(backlog)

                pending_jobs = len([job for job in store.load_dream_queue() if job.get("status") == "queued"])
                last_result = processed_jobs[-1]["result"]["status"] if processed_jobs else (
                    backlog_results[-1]["status"] if backlog_results else "idle"
                )
                store.save_dream_worker_state(
                    {
                        "state": "idle" if pending_jobs == 0 else "queued",
                        "last_polled_at": timestamp,
                        "processed_jobs": len(processed_jobs),
                        "last_job_id": processed_jobs[-1]["job_id"] if processed_jobs else None,
                        "last_result": last_result,
                        "queue_depth": pending_jobs,
                    }
                )

                if idle_exit and jobs_this_poll == 0 and (
                    not backlog_results or backlog_results[-1]["status"] == "skipped"
                ):
                    break
                if poll_index + 1 < max_polls and interval_seconds > 0:
                    time.sleep(interval_seconds)
    except LockError:
        return {
            "run_id": worker_run_id,
            "status": "skipped",
            "reason": "worker-lock-held",
            "processed_jobs": [],
            "backlog_results": [],
        }

    summary = {
        "run_id": worker_run_id,
        "status": "completed",
        "polls": max_polls,
        "processed_jobs": processed_jobs,
        "backlog_results": backlog_results,
        "queue_depth": len([job for job in store.load_dream_queue() if job.get("status") == "queued"]),
    }
    summary["audit"] = store.write_worker_audit(worker_run_id, summary, before_snapshot)
    return summary


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


def _build_search_plan(
    *,
    episode_paths: list[Path],
    rows: list[dict[str, Any]],
    gathered: list[dict[str, Any]],
    orientation_tokens: set[str],
    limit: int,
) -> dict[str, Any]:
    gathered_counts: dict[str, int] = {}
    row_counts: dict[str, int] = {}
    for row in rows:
        source_path = str(row.get("source_path") or "")
        row_counts[source_path] = row_counts.get(source_path, 0) + 1
    for row in gathered:
        source_path = str(row.get("source_path") or "")
        gathered_counts[source_path] = gathered_counts.get(source_path, 0) + 1
    files_consulted = []
    for path in episode_paths:
        source_path = str(path.expanduser())
        files_consulted.append(
            {
                "path": source_path,
                "reason": "explicit-input",
                "tail_rows_scanned": row_counts.get(source_path, 0),
                "matched_rows": gathered_counts.get(source_path, 0),
            }
        )
    return {
        "strategy": "bounded-tail-search",
        "full_corpus_replay": False,
        "max_recent_episodes": limit,
        "orientation_token_sample": sorted(orientation_tokens)[:8],
        "files_consulted": files_consulted,
    }


def _process_job(
    store: MemoryStore,
    job: dict[str, Any],
    queue: list[dict[str, Any]],
    *,
    now: str,
) -> dict[str, Any] | None:
    job["status"] = "running"
    job["attempts"] = int(job.get("attempts", 0)) + 1
    job["last_polled_at"] = now
    job["last_started_at"] = now
    store.save_dream_queue(queue)

    episode_paths = [Path(path).expanduser() for path in job.get("episode_paths", [])]
    if not episode_paths:
        episode_paths = sorted(store.transcripts_dir.glob("*.jsonl"))

    result = dream_run(
        store,
        episode_paths=episode_paths,
        now=now,
        max_recent_episodes=job.get("max_recent_episodes"),
        min_episode_signals=job.get("min_episode_signals"),
        trigger_class=str(job.get("trigger_class") or "queued-manual"),
    )
    if result.get("reason") == "lock-held":
        job["status"] = "queued"
        job["last_result"] = "lock-held"
        job["last_finished_at"] = now
        store.save_dream_queue(queue)
        return None

    job["status"] = str(result.get("status", "completed"))
    job["last_result"] = str(result.get("status", "completed"))
    job["last_finished_at"] = now
    job["run_id"] = result.get("run_id")
    job["error"] = result.get("reason")
    validate_document("dream-job.schema.json", job)
    store.save_dream_queue(queue)
    return {"job_id": job["job_id"], "result": result}
