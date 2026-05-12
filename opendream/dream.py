from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .boundaries import boundary_enforcement_report, default_allowed_write_roots, verify_no_code_writes
from .dream_narrative import synthesize_dream_narrative
from .episodes import latest_episode_timestamp, load_episode_rows, looks_memory_worthy, row_text, row_to_event
from .integration import maintain
from .storage import LockError, MemoryStore
from .util import CLI_JSON_VERSION, parse_timestamp, prune_recent_failures, semantic_tokens, stable_id, to_iso, utc_now
from .validation import validate_document

_UNSET = object()


def _dream_worker_agent_summary(
    processed_jobs: list[dict[str, Any]],
    backlog_results: list[dict[str, Any]],
) -> str:
    if processed_jobs:
        return f"Processed {len(processed_jobs)} queued dream job(s)."
    if backlog_results:
        last = backlog_results[-1]
        work_mode = str(last.get("mode") or "")
        if last.get("status") == "completed":
            if work_mode in {"semantic", "hybrid"}:
                return "Semantic backlog processed; learned-context materialization attempted."
            return "Transcript backlog processed; dream run completed."
        reason = str(last.get("reason") or "")
        if reason == "no-signal":
            return "No transcript or explicit-event signal is available for semantic backlog yet."
        if reason == "no-episodes":
            return (
                "No transcript episode files; dream skipped. "
                "Event-driven memory (emit-event + maintain) is unaffected."
            )
        if reason == "no-backlog":
            return "Transcript backlog already up to date."
        if reason == "insufficient-signal":
            return "Recent transcript rows did not yield enough memory-worthy signal for a dream run."
        if reason == "min-interval":
            return "Dream tick skipped: minimum interval between runs not elapsed."
        if reason == "lock-held":
            return "Dream run skipped: consolidator or dream lock held."
        return f"Dream backlog step skipped ({reason or 'unknown'})."
    return "Idle: no queued jobs and no backlog work this poll."


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
                summary["narrative"] = synthesize_dream_narrative(summary)
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
                summary["narrative"] = synthesize_dream_narrative(summary)
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

            # Runtime boundary verification: check no code writes occurred.
            after_snapshot = store.snapshot_store_text()
            boundary_report = verify_no_code_writes(before_snapshot, after_snapshot, memory_root=store.memory_root)
            allowed_roots = default_allowed_write_roots(store.memory_root)
            enforcement = boundary_enforcement_report(
                worker_type="dream",
                allowed_roots=allowed_roots,
                violations=boundary_report.get("violations", []),
            )
            store.write_boundary_audit(enforcement["report_id"], enforcement)

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
                "boundary_enforcement": enforcement,
            }
            summary["narrative"] = synthesize_dream_narrative(summary)
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
        summary = {
            "run_id": run_id,
            "status": "skipped",
            "reason": "lock-held",
            "phases": ["orient"],
            "policy": policy,
            "trigger_class": trigger_class,
        }
        summary["narrative"] = synthesize_dream_narrative(summary)
        return summary


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
    mode: str = "auto",
) -> dict[str, Any]:
    worker_run_id = stable_id("dream-worker", store.store_id, now or to_iso(utc_now()))
    before_snapshot = store.snapshot_store_text()
    processed_jobs: list[dict[str, Any]] = []
    backlog_results: list[dict[str, Any]] = []
    started_at = now or to_iso(utc_now())
    lock_failures = 0
    _write_worker_health(
        store,
        timestamp=started_at,
        state="starting",
        queue_backlog=len([job for job in store.load_dream_queue() if job.get("status") == "queued"]),
    )
    poll_count = 0
    try:
        while max_polls <= 0 or poll_count < max_polls:
            poll_count += 1
            timestamp = now or to_iso(utc_now())
            queue = store.load_dream_queue()
            queued_jobs = [job for job in queue if job.get("status") == "queued"]
            resolved_mode = _resolve_worker_mode(store, requested_mode=mode)
            jobs_this_poll = 0
            try:
                with store.dream_worker_lock():
                    _write_worker_health(
                        store,
                        timestamp=timestamp,
                        state="draining" if queued_jobs else "idle",
                        queue_backlog=len(queued_jobs),
                        active_phase="poll",
                    )

                    if queued_jobs:
                        limit = max_jobs_per_poll or len(queued_jobs)
                        for job in queued_jobs[:limit]:
                            _write_worker_health(
                                store,
                                timestamp=timestamp,
                                state="draining",
                                queue_backlog=len([item for item in queue if item.get("status") == "queued"]),
                                active_job_id=str(job.get("job_id")),
                                active_phase="job",
                            )
                            processed = _process_job(store, job, queue, now=timestamp, mode=resolved_mode)
                            if processed is not None:
                                processed_jobs.append(processed)
                                jobs_this_poll += 1
                                if processed["result"].get("status") == "completed":
                                    _write_worker_health(
                                        store,
                                        timestamp=timestamp,
                                        state="draining",
                                        queue_backlog=len([
                                            item
                                            for item in store.load_dream_queue()
                                            if item.get("status") == "queued"
                                        ]),
                                        last_success_at=timestamp,
                                    )
                    elif process_backlog:
                        if resolved_mode in {"semantic", "hybrid"}:
                            from .semantic_dreamer import semantic_dream_tick

                            backlog = semantic_dream_tick(
                                store,
                                episode_paths=sorted(store.transcripts_dir.glob("*.jsonl")),
                                now=timestamp,
                                mode=resolved_mode,
                            )
                        else:
                            backlog = dream_tick(
                                store,
                                episode_paths=sorted(store.transcripts_dir.glob("*.jsonl")),
                                now=timestamp,
                            )
                        backlog_results.append(backlog)
                        if backlog.get("status") == "completed":
                            _write_worker_health(
                                store,
                                timestamp=timestamp,
                                state="draining",
                                queue_backlog=0,
                                last_success_at=timestamp,
                            )
            except LockError:
                lock_failures += 1
                _record_worker_failure(store, reason="worker-lock-held", timestamp=timestamp)
                pending_jobs = len([job for job in store.load_dream_queue() if job.get("status") == "queued"])
                store.save_dream_worker_state(
                    {
                        "state": "idle" if pending_jobs == 0 else "queued",
                        "last_polled_at": timestamp,
                        "processed_jobs": len(processed_jobs),
                        "last_job_id": processed_jobs[-1]["job_id"] if processed_jobs else None,
                        "last_result": "worker-lock-held",
                        "queue_depth": pending_jobs,
                        "work_mode": resolved_mode,
                    }
                )
                if max_polls == 1:
                    return {
                        "run_id": worker_run_id,
                        "status": "skipped",
                        "reason": "worker-lock-held",
                        "processed_jobs": [],
                        "backlog_results": [],
                        "agent_summary": "Dream worker lock held by another process; try again shortly.",
                        "cli_output_version": CLI_JSON_VERSION,
                    }
                if (max_polls <= 0 or poll_count < max_polls) and interval_seconds > 0:
                    time.sleep(interval_seconds)
                continue

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
                    "work_mode": resolved_mode,
                }
            )
            _write_worker_health(
                store,
                timestamp=timestamp,
                state="idle" if pending_jobs == 0 else "draining",
                queue_backlog=pending_jobs,
                active_job_id=None,
                active_phase=None,
            )

            if idle_exit and jobs_this_poll == 0 and (
                not backlog_results or backlog_results[-1]["status"] == "skipped"
            ):
                break
            if (max_polls <= 0 or poll_count < max_polls) and interval_seconds > 0:
                time.sleep(interval_seconds)
    finally:
        _write_worker_health(
            store,
            timestamp=now or to_iso(utc_now()),
            state="stopped",
            queue_backlog=len([job for job in store.load_dream_queue() if job.get("status") == "queued"]),
            active_job_id=None,
            active_phase=None,
        )

    summary = {
        "run_id": worker_run_id,
        "status": "completed",
        "polls": poll_count,
        "processed_jobs": processed_jobs,
        "backlog_results": backlog_results,
        "queue_depth": len([job for job in store.load_dream_queue() if job.get("status") == "queued"]),
        "lock_failures": lock_failures,
        "work_mode": _resolve_worker_mode(store, requested_mode=mode),
        "agent_summary": _dream_worker_agent_summary(processed_jobs, backlog_results),
        "cli_output_version": CLI_JSON_VERSION,
    }
    summary["audit"] = store.write_worker_audit(worker_run_id, summary, before_snapshot)

    # Post-dream auto-reviewer hook — gated by config; never crashes the cycle.
    try:
        from . import auto_reviewer as _auto_reviewer
        _ar_cfg = _auto_reviewer.load_config(store)
        if _ar_cfg.enabled and _ar_cfg.run_in_dream_cycle:
            _auto_reviewer.run_auto_reviewer(store, config=_ar_cfg)
    except Exception:
        pass

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
            row_text(row),
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
    mode: str,
) -> dict[str, Any] | None:
    job["status"] = "running"
    job["attempts"] = int(job.get("attempts", 0)) + 1
    job["last_polled_at"] = now
    job["last_started_at"] = now
    store.save_dream_queue(queue)

    episode_paths = [Path(path).expanduser() for path in job.get("episode_paths", [])]
    if not episode_paths:
        episode_paths = sorted(store.transcripts_dir.glob("*.jsonl"))

    if mode in {"semantic", "hybrid"}:
        from .semantic_dreamer import semantic_dream_run

        result = semantic_dream_run(
            store,
            episode_paths=episode_paths,
            mode=mode,
            now=now,
            max_recent_episodes=job.get("max_recent_episodes"),
            min_episode_signals=job.get("min_episode_signals"),
            trigger_class=str(job.get("trigger_class") or "queued-manual"),
        )
    else:
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
        _record_worker_failure(store, reason="dream-lock-held", timestamp=now)
        return None

    job["status"] = str(result.get("status", "completed"))
    job["last_result"] = str(result.get("status", "completed"))
    job["last_finished_at"] = now
    job["run_id"] = result.get("run_id")
    job["error"] = result.get("reason")
    validate_document("dream-job.schema.json", job)
    store.save_dream_queue(queue)
    if result.get("status") != "completed":
        _record_worker_failure(
            store,
            reason=str(result.get("reason") or result.get("status") or "unknown"),
            timestamp=now,
        )
    return {"job_id": job["job_id"], "result": result}


def _resolve_worker_mode(store: MemoryStore, *, requested_mode: str) -> str:
    if requested_mode in {"deterministic", "semantic", "hybrid"}:
        return requested_mode
    configured = str(store.load_semantic_config().get("mode", "deterministic") or "deterministic")
    return configured if configured in {"deterministic", "semantic", "hybrid"} else "deterministic"


def _write_worker_health(
    store: MemoryStore,
    *,
    timestamp: str,
    state: str,
    queue_backlog: int,
    active_job_id: str | None | object = _UNSET,
    active_phase: str | None | object = _UNSET,
    last_success_at: str | None = None,
) -> None:
    existing = store.load_worker_health()
    payload = {
        "pid": os.getpid(),
        "started_at": existing.get("started_at") or timestamp,
        "last_loop_at": timestamp,
        "last_success_at": last_success_at if last_success_at is not None else existing.get("last_success_at"),
        "queue_backlog": max(0, int(queue_backlog)),
        "active_job_id": existing.get("active_job_id") if active_job_id is _UNSET else active_job_id,
        "active_phase": existing.get("active_phase") if active_phase is _UNSET else active_phase,
        "restart_count": int(existing.get("restart_count", 0)) + (1 if existing.get("pid") != os.getpid() else 0),
        "recent_failures": prune_recent_failures(
            existing.get("recent_failures", []),
            now=timestamp,
            last_success_at=last_success_at if last_success_at is not None else existing.get("last_success_at"),
        ),
        "state": state,
        "service_name": store.load_service_manifest().get("service_name"),
        "supervisor_kind": store.load_service_manifest().get("supervisor_kind"),
    }
    validate_document("worker-health.schema.json", payload)
    store.save_worker_health(payload)


def _record_worker_failure(store: MemoryStore, *, reason: str, timestamp: str) -> None:
    health = store.load_worker_health()
    failures = list(health.get("recent_failures", []))
    failures.append({"at": timestamp, "reason": reason})
    health["recent_failures"] = prune_recent_failures(
        failures,
        now=timestamp,
        last_success_at=health.get("last_success_at"),
    )
    health["state"] = "degraded"
    health["last_loop_at"] = timestamp
    health["pid"] = os.getpid()
    health.setdefault("started_at", timestamp)
    health.setdefault("last_success_at", None)
    health.setdefault("queue_backlog", len([job for job in store.load_dream_queue() if job.get("status") == "queued"]))
    health.setdefault("active_job_id", None)
    health.setdefault("active_phase", None)
    health["restart_count"] = int(health.get("restart_count", 0))
    validate_document("worker-health.schema.json", health)
    store.save_worker_health(health)
