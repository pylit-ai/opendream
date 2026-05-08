from __future__ import annotations

import json
import os
import sys
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from . import workspace_catalog
from .dream import dream_worker
from .integration import emit_event
from .observability import (
    _build_overview_lite,
    _session_diagnostics,
    build_dream_coverage,
    build_dream_funnel,
    build_graph,
    build_semantic_change_unavailable,
    build_semantic_change_review,
    create_annotation,
    create_export,
    create_review_decision,
    get_dream_cycle,
    index_observability,
    load_or_build_list_index,
    load_or_build_index,
    project_retrieval_list_row,
    project_run_list_row,
    project_session_list_row,
    query_dream_cycles,
    query_memories,
    query_retrievals,
    query_runs,
)
from .semantic_verifier import restore_record as restore_learned_context_record
from .semantic_dreamer import dream_status_semantic
from .service import disable_background_runtime, enable_background_runtime, restart_service, service_status, start_service, stop_service
from .showcase import load_showcase_report
from .storage import MemoryStore
from .util import CLI_JSON_VERSION, to_iso, utc_now
from . import auto_reviewer as _auto_reviewer
from .validation import SchemaValidationError, validate_document

# 446-observability-perf Phase 3: request timing ring buffer.
# Holds up to 200 entries: {path, query_keys, ms, status}.
# /api/_perf is excluded from self-recording to avoid noise.
_PERF_TIMINGS: deque[dict[str, Any]] = deque(maxlen=200)
_OPENDREAM_DEV = os.environ.get("OPENDREAM_DEV") == "1"

_STATIC_ROOT = (Path(__file__).parent / "static").resolve()


_SPA_DIST_DIR = (Path(__file__).parent / "static" / "dist").resolve()
_SPA_INDEX_PATH = _SPA_DIST_DIR / "index.html"


def _spa_index_html() -> bytes:
    try:
        return _SPA_INDEX_PATH.read_bytes()
    except OSError:
        return (
            b"<!doctype html><html><body>"
            b"<h1>OpenDream UI build missing</h1>"
            b"<p>Run <code>pnpm --dir frontend build</code></p>"
            b"</body></html>"
        )


_STATIC_MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".md": "text/markdown",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

_MEMORY_LIST_LIMIT_CAP = 500
_RETRIEVAL_LIST_LIMIT_CAP = 500
_RUN_LIST_LIMIT_CAP = 500
_SESSION_LIST_LIMIT_CAP = 500


def _auto_reviewer_stats_payload(
    store: MemoryStore,
    cfg: Any,
) -> dict[str, Any]:
    """Build the stats payload for GET /api/auto-reviewer/stats."""
    last_run = _auto_reviewer.load_last_run(store)
    rules_status = []
    for rule in _auto_reviewer.DEFAULT_RULES:
        rc = cfg.rule(rule.rule_id)
        rules_status.append({
            "rule_id": rule.rule_id,
            "description": rule.description,
            "enabled": rc.enabled if rc else True,
            "thresholds": rc.thresholds if rc else {},
        })
    cooldown_count = last_run.get("applied_count", 0) if last_run else 0
    return {
        "enabled": cfg.enabled,
        "run_in_dream_cycle": cfg.run_in_dream_cycle,
        "rules": rules_status,
        "last_run": last_run,
        "cooldown_count": cooldown_count,
    }


def _graph_default_focus(index: dict[str, Any]) -> str | None:
    memories = list(index.get("entities", {}).get("memories", []))
    if not memories:
        return None
    memories.sort(
        key=lambda item: (
            str(item.get("updated_at") or item.get("created_at") or ""),
            str(item.get("memory_id") or ""),
        ),
        reverse=True,
    )
    focus = memories[0].get("memory_id")
    return str(focus) if focus else None


def _resolve_graph_request(index: dict[str, Any], query: dict[str, str]) -> tuple[str | None, int, str]:
    explicit_focus = (query.get("focus") or "").strip() or None
    explicit_depth = (query.get("depth") or "").strip() or None
    explicit_limit = (query.get("limit") or "").strip() or None
    # If the caller provided a generous limit (>= 50), assume overview-mode
    # and DO NOT auto-pin a focus — return the first `limit` nodes.
    # Auto-focus only kicks in for the legacy default tiny window.
    try:
        wants_overview = explicit_limit is not None and int(explicit_limit) >= 50
    except ValueError:
        wants_overview = False
    if explicit_focus is None and wants_overview:
        focus = None
    else:
        focus = explicit_focus or _graph_default_focus(index)
    if explicit_depth is not None:
        depth = _parse_query_int(explicit_depth, 1, minimum=0, maximum=3)
    else:
        depth = 2 if explicit_focus is None and focus else 1
    layout = (query.get("layout") or "").strip() or "hierarchical"
    return focus, depth, layout


def _default_graph_location(index: dict[str, Any], query: dict[str, str]) -> str | None:
    if (query.get("focus") or "").strip():
        return None
    focus, depth, _layout = _resolve_graph_request(index, query)
    if not focus:
        return None
    params = dict(query)
    params["focus"] = focus
    if not (query.get("depth") or "").strip():
        params["depth"] = str(depth)
    return "/graph?" + urlencode(params)


def _parse_query_float(raw: str | None) -> float | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_query_int(raw: str | None, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw) if raw is not None and str(raw).strip() else default
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _health_section(status: str, checked_at: str, reasons: list[str]) -> dict[str, Any]:
    return {"status": status, "checked_at": checked_at, "reasons": reasons}


def _latest_live_check_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        source = event.get("source", {})
        if (
            isinstance(source, dict)
            and source.get("message_ref") == "observe-live-check"
            and event.get("sensitivity") == "do_not_store"
        ):
            return event
    return None


def _health_payload(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    checked_at = now or to_iso(utc_now())
    index = load_or_build_index(store, now=checked_at)
    overview = index["overview"]
    freshness = overview.get("freshness", {})
    snapshot = store.status_snapshot(now=checked_at)
    service = service_status(store, now=checked_at)
    events = store.load_events()
    latest_probe = _latest_live_check_event(events)

    startup = _health_section(
        "ok",
        checked_at,
        [
            f"observe server bound to workspace {store.workspace}",
            f"memory root {store.memory_root}",
        ],
    )

    readiness_reasons: list[str] = []
    if not snapshot.get("initialized"):
        readiness_status = "not_ready"
        readiness_reasons.append("memory store is not initialized")
    else:
        readiness_status = "ready"
        readiness_reasons.append("observability index is readable")
        lock = (overview.get("store_health") or {}).get("lock") or {}
        if lock.get("present") and not lock.get("stale"):
            readiness_reasons.append("consolidator lock is present; reads are available while writes may be in flight")
    readiness = _health_section(readiness_status, checked_at, readiness_reasons)

    liveness_reasons: list[str] = []
    if not snapshot.get("initialized"):
        liveness_status = "unknown"
        liveness_reasons.append("workspace has not been initialized yet")
    elif service.get("installed"):
        service_health = str(service.get("health", "unknown"))
        if service_health == "healthy":
            liveness_status = "live"
        elif service_health in {"idle", "draining"}:
            liveness_status = "idle"
        elif service_health in {"degraded", "stuck", "crash_loop"}:
            liveness_status = "stale"
        else:
            liveness_status = "unknown"
        liveness_reasons.append(f"background service health is {service_health}")
    elif freshness.get("last_event_at") or freshness.get("last_run_at") or freshness.get("index_generated_at"):
        liveness_status = "live"
        liveness_reasons.append("recent artifacts are readable through the observability index")
    else:
        liveness_status = "idle"
        liveness_reasons.append("no recent event or run evidence is available yet")
    if snapshot.get("pending_events"):
        liveness_reasons.append(f"{snapshot['pending_events']} pending event(s) are waiting for maintenance")
    liveness = _health_section(liveness_status, checked_at, liveness_reasons)

    return {
        "checked_at": checked_at,
        "startup": startup,
        "readiness": readiness,
        "liveness": liveness,
        "evidence": {
            "index_generated_at": freshness.get("index_generated_at"),
            "last_event_at": freshness.get("last_event_at"),
            "last_run_at": freshness.get("last_run_at"),
            "last_session_activity_at": freshness.get("last_session_activity_at"),
            "last_retrieval_at": freshness.get("last_retrieval_at"),
            "pending_events": snapshot.get("pending_events", 0),
            "pending_candidates": snapshot.get("pending_candidates", 0),
            "memory_total": overview.get("memory_counts", {}).get("total", 0),
            "contested_memories": overview.get("contested_memories", 0),
            "service_health": service.get("health"),
            "service_running": service.get("running"),
        },
        "live_check": {
            "supported": True,
            "last_probe_at": latest_probe.get("timestamp") if latest_probe else None,
            "last_probe_event_id": latest_probe.get("event_id") if latest_probe else None,
            "last_probe_session_id": latest_probe.get("session_id") if latest_probe else None,
        },
    }


def _run_live_check(store: MemoryStore, *, now: str | None = None) -> dict[str, Any]:
    checked_at = now or to_iso(utc_now())
    session_id = "session-observe-live-check"
    result = emit_event(
        store,
        kind="task_outcome",
        content=f"Observe live check at {checked_at}",
        scope="workspace",
        channel="system",
        message_ref="observe-live-check",
        session_id=session_id,
        timestamp=checked_at,
        tags=["probe:live-check", "key:observe-live-check"],
        sensitivity="do_not_store",
        reporting_agent={
            "agent_id": "opendream",
            "agent_label": "OpenDream",
            "runtime": "observe-serve",
        },
    )
    store.mark_events_processed([str(result["event_id"])])
    health = _health_payload(store, now=checked_at)
    probe = {
        "event_id": str(result["event_id"]),
        "session_id": session_id,
        "timestamp": checked_at,
        "observed_in_index": health["live_check"]["last_probe_event_id"] == str(result["event_id"]),
    }
    return {
        "status": "ok",
        "checked_at": checked_at,
        "probe": probe,
        "evidence": health["evidence"],
    }


class ObservabilityHandler(BaseHTTPRequestHandler):
    store: MemoryStore

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch_request(head_only=False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch_request(head_only=True)

    def _dispatch_request(self, *, head_only: bool) -> None:
        parsed = urlparse(self.path)
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        if parsed.path == "/favicon.ico":
            self._write_empty(HTTPStatus.NO_CONTENT)
            return
        if parsed.path.startswith("/api/stream"):
            self._write_event_stream(head_only=head_only)
            return
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path, head_only=head_only)
            return
        if parsed.path.startswith("/api/"):
            if head_only:
                self._write_empty(HTTPStatus.OK, content_type="application/json; charset=utf-8")
                return
            self._handle_api_get(parsed)
            return
        if parsed.path == "/graph":
            index = load_or_build_index(self.store)
            location = _default_graph_location(index, query)
            if location:
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", location)
                self.end_headers()
                return
        self._serve_spa_html(head_only=head_only)

    def do_POST(self) -> None:  # noqa: N802
        _t0 = time.monotonic()
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        try:
            if parsed.path == "/api/annotations":
                response = create_annotation(self.store, **payload)
            elif parsed.path == "/api/exports":
                response = create_export(self.store, **payload)
            elif parsed.path == "/api/health/live-check":
                response = _run_live_check(self.store, now=payload.get("now"))
            elif parsed.path == "/api/reviews/recommendations/apply":
                rule_ids = payload.get("rule_ids") if isinstance(payload, dict) else None
                if rule_ids is not None and not isinstance(rule_ids, list):
                    rule_ids = None
                self._write_json(
                    _auto_reviewer.apply_recommendations(self.store, rule_ids=rule_ids)
                )
                return
            elif parsed.path.startswith("/api/reviews/"):
                review_id = parsed.path.split("/")[3]
                action = parsed.path.split("/")[-1]
                response = create_review_decision(
                    self.store,
                    queue_item_type=str(payload.get("queue_item_type", "review")),
                    queue_item_id=review_id,
                    action=action,
                    rationale=str(payload.get("rationale", "")),
                    actor=str(payload.get("actor", "operator")),
                    now=payload.get("now"),
                )
            elif parsed.path == "/api/semantic-dream-mode":
                mode = str(payload.get("mode", "")).strip()
                try:
                    _apply_semantic_dream_mode(self.store, mode)
                except (ValueError, SchemaValidationError) as exc:
                    self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                index_observability(self.store)
                out = _ui_context_payload(self.store)
                out["status"] = "ok"
                self._write_json(out)
                return
            elif parsed.path == "/api/learned-context/restore":
                record_id = str(payload.get("record_id", "")).strip()
                if not record_id:
                    self._write_json({"error": "record_id is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                response = restore_learned_context_record(
                    self.store,
                    record_id,
                    now=payload.get("now"),
                )
                if response.get("status") in {"not_found", "not_restorable", "restore_window_missing", "restore_window_expired"}:
                    self._write_json({"error": response.get("reason") or response.get("status"), "result": response}, status=HTTPStatus.BAD_REQUEST)
                    return
                index_observability(self.store)
                self._write_json(
                    {
                        "status": "ok",
                        "result": response,
                        "overview": load_or_build_index(self.store)["overview"],
                        "semantic_changes_latest": build_semantic_change_review(self.store),
                    }
                )
                return
            elif parsed.path == "/api/service/control":
                action = str(payload.get("action", "")).strip()
                if action == "enable":
                    response = enable_background_runtime(self.store)
                elif action == "disable":
                    response = disable_background_runtime(self.store)
                elif action == "start":
                    response = start_service(self.store)
                elif action == "stop":
                    response = stop_service(self.store)
                elif action == "restart":
                    response = restart_service(self.store)
                elif action == "poll":
                    response = dream_worker(
                        self.store,
                        now=payload.get("now"),
                        max_polls=1,
                        idle_exit=True,
                        process_backlog=True,
                        mode="auto",
                    )
                else:
                    self._write_json({"error": f"unsupported service action: {action}"}, status=HTTPStatus.BAD_REQUEST)
                    return
                index_observability(self.store)
                self._write_json(
                    {
                        "status": "ok",
                        "action": action,
                        "service": service_status(self.store),
                        "overview": load_or_build_index(self.store)["overview"],
                        "ui_context": _ui_context_payload(self.store),
                        "result": response,
                    }
                )
                return
            elif parsed.path == "/api/reviews/recommendations/apply":
                rule_ids = payload.get("rule_ids") if isinstance(payload, dict) else None
                if rule_ids is not None and not isinstance(rule_ids, list):
                    rule_ids = None
                result = _auto_reviewer.apply_recommendations(
                    self.store, rule_ids=rule_ids
                )
                self._write_json(result)
                return
            elif parsed.path == "/api/auto-reviewer/run-dry":
                cfg = _auto_reviewer.load_config(self.store)
                result = _auto_reviewer.run_auto_reviewer(self.store, config=cfg, dry_run=True, now=payload.get("now"))
                self._write_json({
                    "proposed_count": result.get("proposed_count", 0),
                    "by_rule": result.get("by_rule", {}),
                    "dry_run": True,
                })
                return
            elif parsed.path == "/api/auto-reviewer/config":
                cfg = _auto_reviewer.apply_config_update(self.store, payload)
                self._write_json(_auto_reviewer_stats_payload(self.store, cfg))
                return
            elif parsed.path == "/api/dream/run":
                from .dream import dream_run
                mode = str(payload.get("mode") or "").strip().lower() or None
                episode_paths = sorted(self.store.transcripts_dir.glob("*.jsonl"))
                if mode in ("semantic", "hybrid"):
                    from .semantic_dreamer import semantic_dream_run
                    result = semantic_dream_run(
                        self.store,
                        episode_paths=episode_paths,
                        mode=mode,
                        now=payload.get("now"),
                    )
                else:
                    result = dream_run(
                        self.store,
                        episode_paths=episode_paths,
                        now=payload.get("now"),
                    )
                # Force a fresh build so subsequent /api/overview reflects the run
                from .observability import invalidate_index_cache
                invalidate_index_cache(self.store)
                self._write_json({
                    "status": result.get("status"),
                    "reason": result.get("reason"),
                    "phases": result.get("phases", []),
                    "narrative": result.get("narrative"),
                    "duration_ms": result.get("duration_ms"),
                    "appended_events": result.get("appended_events", 0),
                    "gathered_rows": result.get("gathered_rows", 0),
                    "run_id": result.get("run_id"),
                    "trigger_class": result.get("trigger_class"),
                    "mode": mode or "full",
                })
                return
            elif parsed.path == "/api/transcripts/ingest":
                from . import transcripts as _transcripts
                explicit = payload.get("from_dir")
                overwrite = bool(payload.get("overwrite"))
                if explicit:
                    result = _transcripts.ingest_claude_sessions(
                        self.store, explicit, overwrite=overwrite
                    )
                else:
                    result = _transcripts.ingest_claude_for_workspace(
                        self.store, overwrite=overwrite
                    )
                self._write_json(result)
                return
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        index_observability(self.store)
        self._write_json(response)
        _ms = (time.monotonic() - _t0) * 1000
        _PERF_TIMINGS.append({"path": parsed.path, "query_keys": [], "ms": round(_ms, 2), "status": 200})
        if _OPENDREAM_DEV and _ms > 250:
            print(f"[opendream perf] slow POST: {parsed.path} {_ms:.1f}ms", file=sys.stderr)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _handle_api_get(self, parsed: Any) -> None:
        _t0 = time.monotonic()
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        _record_timing = parsed.path != "/api/_perf"

        def _finish(status: int = 200) -> None:
            if not _record_timing:
                return
            ms = (time.monotonic() - _t0) * 1000
            _PERF_TIMINGS.append({
                "path": parsed.path,
                "query_keys": sorted(query.keys()),
                "ms": round(ms, 2),
                "status": status,
            })
            if _OPENDREAM_DEV and ms > 250:
                print(f"[opendream perf] slow request: {parsed.path} {ms:.1f}ms", file=sys.stderr)

        if parsed.path == "/api/_perf":
            self._write_json({"timings": list(_PERF_TIMINGS)})
            return
        if parsed.path == "/api/ui-context":
            self._write_json(_ui_context_payload(self.store))
            _finish()
            return
        if parsed.path == "/api/ui-meta":
            self._write_json(_ui_meta_payload())
            _finish()
            return
        if parsed.path == "/api/health":
            self._write_json(_health_payload(self.store))
            _finish()
            return
        if parsed.path == "/api/overview/lite":
            self._write_json(_build_overview_lite(self.store))
            _finish()
            return
        if parsed.path == "/api/overview":
            list_index = load_or_build_list_index(self.store)
            self._write_json(list_index["overview"])
            _finish()
            return
        if parsed.path == "/api/dream/cycles":
            list_index = load_or_build_list_index(self.store)
            limit = _parse_query_int(query.get("limit"), 50, minimum=1, maximum=_RUN_LIST_LIMIT_CAP)
            self._write_json(
                query_dream_cycles(
                    list_index,
                    limit=limit,
                    since=(query.get("since") or "").strip() or None,
                )
            )
            _finish()
            return
        if parsed.path == "/api/dream/coverage":
            self._write_json(build_dream_coverage(self.store, window=query.get("window", "7d")))
            _finish()
            return
        if parsed.path == "/api/dream/funnel":
            list_index = load_or_build_list_index(self.store)
            self._write_json(build_dream_funnel(list_index, window=query.get("window", "7d")))
            _finish()
            return
        if parsed.path == "/api/semantic-changes/latest":
            list_index = load_or_build_list_index(self.store)
            payload = build_semantic_change_review(
                self.store,
                now=str(list_index.get("generated_at") or ""),
            )
            if payload is None:
                self._write_json(
                    build_semantic_change_unavailable(
                        self.store,
                        now=str(list_index.get("generated_at") or ""),
                    )
                )
                _finish()
                return
            self._write_json(payload)
            _finish()
            return
        if parsed.path == "/api/workspaces":
            include_tempdir = str(query.get("include_tempdir", "")).lower() in ("1", "true", "yes")
            self._write_json(_workspace_dashboard_payload(include_tempdir=include_tempdir))
            _finish()
            return
        if parsed.path.startswith("/api/workspaces/"):
            from urllib.parse import unquote

            workspace_arg = unquote(parsed.path[len("/api/workspaces/") :])
            entry = workspace_catalog.inspect_entry(workspace_arg)
            if entry is None:
                self._write_json({"status": "missing", "workspace": workspace_arg})
            else:
                self._write_json({"status": "ok", "entry": entry})
            _finish()
            return
        if parsed.path == "/api/showcase":
            self._write_json(load_showcase_report(self.store))
            _finish()
            return
        if parsed.path == "/api/sessions/diagnostics":
            self._write_json(_session_diagnostics(self.store))
            _finish()
            return
        if parsed.path == "/api/memories":
            list_index = load_or_build_list_index(self.store)
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_MEMORY_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            result = query_memories(
                list_index,
                search=query.get("search", ""),
                filters={key: query.get(key, "") for key in ["type", "scope", "status", "agent_id"]},
                sort=query.get("sort", "updated_at"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                salience_min=_parse_query_float(query.get("salience_min")),
                salience_max=_parse_query_float(query.get("salience_max")),
                confidence_min=_parse_query_float(query.get("confidence_min")),
                confidence_max=_parse_query_float(query.get("confidence_max")),
                updated_after=(query.get("updated_after") or "").strip() or None,
                updated_before=(query.get("updated_before") or "").strip() or None,
                created_after=(query.get("created_after") or "").strip() or None,
                created_before=(query.get("created_before") or "").strip() or None,
            )
            self._write_json(result)
            _finish()
            return
        if parsed.path == "/api/sessions":
            list_index = load_or_build_list_index(self.store)
            entities = list_index["entities"]
            sessions = list(entities["sessions"])
            since = (query.get("since") or "").strip() or None
            if since:
                sessions = [s for s in sessions if str(s.get("started_at") or "") >= since]
            limit = _parse_query_int(query.get("limit"), 50, minimum=1, maximum=_SESSION_LIST_LIMIT_CAP)
            sessions = [project_session_list_row(s) for s in sessions[:limit]]
            self._write_json({"items": sessions})
            _finish()
            return
        if parsed.path == "/api/runs":
            list_index = load_or_build_list_index(self.store)
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_RUN_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            since = (query.get("since") or "").strip() or None
            result = query_runs(
                list_index,
                search=query.get("search", ""),
                sort=query.get("sort", "ended_at"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                ended_after=(query.get("ended_after") or "").strip() or since or None,
                ended_before=(query.get("ended_before") or "").strip() or None,
            )
            result["items"] = [project_run_list_row(row) for row in result.get("items", [])]
            self._write_json(result)
            _finish()
            return
        if parsed.path == "/api/retrievals":
            list_index = load_or_build_list_index(self.store)
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_RETRIEVAL_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            since = (query.get("since") or "").strip() or None
            result = query_retrievals(
                list_index,
                search=query.get("search", ""),
                filters={key: query.get(key, "") for key in ["agent_id"]},
                sort=query.get("sort", "timestamp"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                timestamp_after=(query.get("timestamp_after") or "").strip() or since or None,
                timestamp_before=(query.get("timestamp_before") or "").strip() or None,
                min_selected=_parse_query_int(query.get("min_selected"), 0, minimum=0, maximum=1_000_000)
                if (query.get("min_selected") or "").strip()
                else None,
                max_selected=_parse_query_int(query.get("max_selected"), 0, minimum=0, maximum=1_000_000)
                if (query.get("max_selected") or "").strip()
                else None,
            )
            result["items"] = [project_retrieval_list_row(row) for row in result.get("items", [])]
            self._write_json(result)
            _finish()
            return
        index = load_or_build_index(self.store)
        entities = index["entities"]
        if parsed.path.startswith("/api/dream/cycles/"):
            run_id = parsed.path.split("/")[-1]
            cycle = get_dream_cycle(index, run_id)
            if cycle is None:
                self._write_json({"error": f"dream cycle not found: {run_id}"}, status=HTTPStatus.NOT_FOUND)
                _finish(404)
                return
            self._write_json(cycle)
            _finish()
            return
        if parsed.path.startswith("/api/semantic-changes/"):
            source_id = parsed.path.split("/")[-1]
            payload = build_semantic_change_review(
                self.store,
                source_id=source_id,
                now=str(index.get("generated_at") or ""),
            )
            if payload is None:
                self._write_json({"error": f"semantic change review not found: {source_id}"}, status=HTTPStatus.NOT_FOUND)
                return
            self._write_json(payload)
            return
        if parsed.path.startswith("/api/memories/") and parsed.path.endswith("/lineage"):
            memory_id = parsed.path.split("/")[-2]
            memory = _find_by_id(entities["memories"], "memory_id", memory_id)
            self._write_json(memory.get("lineage", {}) if memory else {})
            return
        if parsed.path.startswith("/api/memories/"):
            memory_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["memories"], "memory_id", memory_id) or {})
            return
        if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/timeline"):
            session_id = parsed.path.split("/")[-2]
            session = _find_by_id(entities["sessions"], "session_id", session_id)
            self._write_json(session or {})
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/diff"):
            run_id = parsed.path.split("/")[-2]
            run = _find_by_id(entities["runs"], "run_id", run_id)
            self._write_json({"run_id": run_id, "diff_text": run.get("diff_text", "") if run else ""})
            return
        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["runs"], "run_id", run_id) or {})
            return
        if parsed.path.startswith("/api/retrievals/"):
            retrieval_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["retrievals"], "id", retrieval_id) or {})
            return
        if parsed.path.startswith("/api/context/"):
            context_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["contexts"], "context_id", context_id) or {})
            return
        if parsed.path == "/api/graph":
            index = load_or_build_index(self.store)
            focus, depth, layout = _resolve_graph_request(index, query)
            try:
                limit = max(1, min(int(query.get("limit", "100")), 2000))
            except ValueError:
                limit = 100
            self._write_json(
                build_graph(
                    index,
                    focus=focus,
                    limit=limit,
                    depth=depth,
                    layout=layout,
                )
            )
            return
        if parsed.path == "/api/auto-reviewer/stats":
            cfg = _auto_reviewer.load_config(self.store)
            self._write_json(_auto_reviewer_stats_payload(self.store, cfg))
            return
        if parsed.path == "/api/reviews/recommendations":
            self._write_json(_auto_reviewer.preview_recommendations(self.store))
            return
        if parsed.path == "/api/reviews":
            # 446-observability-perf: cap decisions at 50 (most recent by created_at desc).
            # decisions_total added so clients can detect truncation without a separate call.
            all_decisions = self.store.load_review_decisions()
            decisions_total = len(all_decisions)
            decisions_sorted = sorted(all_decisions, key=lambda d: str(d.get("created_at") or ""), reverse=True)[:50]
            self._write_json({"items": entities["reviews"], "decisions": decisions_sorted, "decisions_total": decisions_total})
            return
        if parsed.path == "/api/evals":
            self._write_json({"health": entities["health"], "evals": entities["evals"]})
            return
        if parsed.path == "/api/exports":
            self._write_json({"items": entities["exports"]})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _write_json(self, payload: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_empty(self, status: HTTPStatus, *, content_type: str | None = None) -> None:
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _write_html(self, body: str, *, head_only: bool = False) -> None:
        payload = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)

    def _serve_spa_html(self, *, head_only: bool = False) -> None:
        body = _spa_index_html()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _serve_static(self, request_path: str, *, head_only: bool = False) -> None:
        relative = unquote(request_path[len("/static/"):])
        if not relative or ".." in relative.split("/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        candidate = (_STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(_STATIC_ROOT)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime = _STATIC_MIME_TYPES.get(candidate.suffix, "application/octet-stream")
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _write_event_stream(self, *, head_only: bool = False) -> None:
        snapshot = {
            "status": self.store.status_snapshot(),
            "overview": load_or_build_index(self.store)["overview"],
        }
        body = (
            "event: status\n"
            f"data: {json.dumps(snapshot['status'])}\n\n"
            "event: overview\n"
            f"data: {json.dumps(snapshot['overview'])}\n\n"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)


def build_server(store: MemoryStore, *, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    handler = type("BoundObservabilityHandler", (ObservabilityHandler,), {"store": store})
    return ThreadingHTTPServer((host, port), handler)


def serve_observability(store: MemoryStore, *, host: str = "127.0.0.1", port: int = 8000) -> dict[str, Any]:
    server = build_server(store, host=host, port=port)
    try:
        actual_host, actual_port = server.server_address
        return {"status": "serving", "host": actual_host, "port": actual_port, "url": f"http://{actual_host}:{actual_port}"}
    finally:
        server.server_close()


def _dream_mode_from_semantic_summary(summary: str | None) -> str:
    """Map catalog/probe ``semantic_state_summary`` to a ``dream run`` mode string."""
    if not summary or not str(summary).strip():
        return "deterministic"
    text = str(summary).strip()
    if not text.startswith("semantic:"):
        return "deterministic"
    sub = text[len("semantic:") :].strip()
    if sub in ("hybrid", "semantic", "deterministic"):
        return sub
    if sub in ("on", ""):
        return "semantic"
    return "semantic"


def _apply_semantic_dream_mode(store: MemoryStore, mode: str) -> None:
    """Persist dream pipeline mode to ``semantic_config.json`` (validated)."""
    if mode not in ("deterministic", "semantic", "hybrid"):
        raise ValueError("mode must be deterministic, semantic, or hybrid")
    config = dict(store.load_semantic_config())
    if "providers" not in config or not isinstance(config.get("providers"), list):
        config["providers"] = []
    config["mode"] = mode
    validate_document("semantic-dream-config.schema.json", config)
    store.save_semantic_config(config)


def _ui_context_payload(store: MemoryStore) -> dict[str, Any]:
    """Minimal JSON for UI scope chrome (active workspace for this server)."""
    workspace_path = str(store.workspace.resolve())
    payload: dict[str, Any] = {
        "kind": "observe_serve",
        "workspace_path": workspace_path,
    }
    entry = workspace_catalog.inspect_entry(workspace_path)
    if entry:
        name = entry.get("workspace_name")
        if isinstance(name, str) and name.strip():
            payload["workspace_name"] = name.strip()

    probe = workspace_catalog.probe_workspace(workspace_path)
    payload["workspace_probe_status"] = probe.status_kind
    if probe.status_kind == "ok":
        payload["semantic_state_summary"] = probe.semantic_summary
    else:
        payload["semantic_state_summary"] = None
    payload["dream_mode"] = _dream_mode_from_semantic_summary(payload.get("semantic_state_summary"))

    index = load_or_build_index(store)
    overview = index["overview"]
    semantic_status = dream_status_semantic(store)
    sh = overview["store_health"]
    initialized = bool(sh.get("initialized"))
    lock = sh.get("lock") or {}
    lock_present = bool(lock.get("present"))
    lock_stale = bool(lock.get("stale"))
    mem_total = int(overview.get("memory_counts", {}).get("total", 0))
    contested = int(overview.get("contested_memories") or 0)
    pending_events = store.pending_event_count() if initialized else 0
    freshness = overview.get("freshness", {})
    semantic_mode = str(semantic_status.get("mode") or "")
    product_posture = (
        "deterministic-by-choice"
        if semantic_mode in {"", "deterministic"}
        else "semantic-first"
    )
    semantic_capability_state = str(
        semantic_status.get("semantic_capability_state")
        or overview.get("semantic_capability_state")
        or "unknown"
    )
    semantic_unavailability_reason = (
        semantic_status.get("availability_reason")
        or overview.get("semantic_unavailability_reason")
    )
    next_action = overview.get("next_action")
    memory_quality = overview.get("memory_quality") or {"state": "unknown", "warnings": [], "metrics": {}}
    context_pruning = overview.get("context_pruning") or {}
    execution_ownership = overview.get("execution_ownership") or {}
    service = service_status(store)

    payload["product_posture"] = product_posture
    payload["semantic_capability_state"] = semantic_capability_state
    payload["semantic_unavailability_reason"] = semantic_unavailability_reason
    payload["next_action"] = next_action
    payload["memory_quality"] = memory_quality
    payload["context_pruning"] = context_pruning
    payload["execution_ownership"] = execution_ownership
    payload["service_management"] = {
        "policy_mode": service.get("policy", {}).get("management_mode", "unknown"),
        "installed": service.get("installed", False),
        "running": service.get("running", False),
        "health": service.get("health", "unknown"),
        "backlog": service.get("backlog", 0),
        "active_phase": service.get("active_phase"),
        "last_success_at": service.get("last_success_at"),
    }
    payload["last_semantic_run"] = {
        "mode": semantic_status.get("last_semantic_run"),
        "execution_strategy": semantic_status.get("execution_strategy"),
        "trust_boundary": semantic_status.get("trust_boundary"),
        "auth_source": semantic_status.get("auth_source"),
        "learned_context": semantic_status.get("learned_context"),
    }

    if product_posture == "semantic-first" and semantic_capability_state == "setup_required":
        kind = "semantic_setup_required"
        level = "attention"
        label = "Semantic setup required"
    elif product_posture == "semantic-first" and semantic_capability_state == "degraded":
        kind = "semantic_degraded"
        level = "warning"
        label = "Semantic degraded"
    elif product_posture == "semantic-first" and semantic_capability_state == "ready":
        kind = "semantic_ready"
        level = "ok"
        label = "Semantic ready"
    elif semantic_capability_state == "disabled_by_choice":
        kind = "deterministic_choice"
        level = "neutral"
        label = "Deterministic by choice"
    elif not initialized:
        kind = "uninitialized"
        level = "attention"
        label = "Not initialized"
    elif lock_present and not lock_stale:
        kind = "locked"
        level = "warning"
        label = "Locked"
    elif contested > 0:
        kind = "contested"
        level = "warning"
        label = "Contested"
    elif pending_events > 0:
        kind = "pending_events"
        level = "warning"
        label = "Pending events"
    elif mem_total == 0:
        kind = "empty"
        level = "neutral"
        label = "No memories"
    else:
        kind = "ok"
        level = "ok"
        label = "Ready"

    link_by_kind: dict[str, str] = {
        "semantic_setup_required": "/settings",
        "semantic_degraded": "/settings",
        "semantic_ready": "/overview",
        "deterministic_choice": "/settings",
        "uninitialized": "/settings",
        "locked": "/settings",
        "contested": "/memories?status=contested",
        "pending_events": "/overview",
        "empty": "/memories",
        "ok": "/overview",
    }
    payload["scope_health"] = {
        "kind": kind,
        "level": level,
        "label": label,
        "link": link_by_kind.get(kind, "/overview"),
        "memory_total": mem_total,
        "contested": contested,
        "pending_events": pending_events,
        "lock_present": lock_present,
        "product_posture": product_posture,
        "semantic_capability_state": semantic_capability_state,
        "semantic_unavailability_reason": semantic_unavailability_reason,
        "next_action": next_action,
        "index_generated_at": freshness.get("index_generated_at"),
        "last_event_at": freshness.get("last_event_at"),
        "last_run_at": freshness.get("last_run_at"),
    }
    return payload


def _ui_meta_payload() -> dict[str, Any]:
    """Build metadata for Settings / diagnostics (no index load)."""
    return {
        "cli_json_version": CLI_JSON_VERSION,
    }


def _workspace_dashboard_payload(*, include_tempdir: bool = False) -> dict[str, Any]:
    """Build the read-model payload used by the /workspaces dashboard route.

    Uses the machine-local catalog for fast initial render; the dashboard
    can trigger re-probes via the CLI (``opendream workspace doctor``) rather
    than performing synchronous disk work inside the HTTP handler.

    Tempdir catalog entries (test fixture leftovers under /tmp,
    /private/var/folders, ...) are filtered out unless ``include_tempdir`` is
    set; callers can pass ``?include_tempdir=1`` to surface them.
    """
    all_entries = workspace_catalog.list_entries()
    if include_tempdir:
        entries = list(all_entries)
        hidden = 0
    else:
        entries = []
        hidden = 0
        for entry in all_entries:
            path = entry.get("workspace_path")
            if isinstance(path, str) and workspace_catalog._workspace_is_under_tempdir(path):
                hidden += 1
                continue
            entries.append(entry)
    summary = {
        "total": len(entries),
        "ok": sum(1 for e in entries if e.get("status_kind") == "ok"),
        "stale": sum(1 for e in entries if e.get("status_kind") == "stale"),
        "missing": sum(1 for e in entries if e.get("status_kind") == "missing"),
        "broken": sum(1 for e in entries if e.get("status_kind") == "broken"),
        "with_service": sum(1 for e in entries if e.get("service_state_summary")),
        "with_semantic": sum(1 for e in entries if e.get("semantic_state_summary")),
        "tempdir_hidden": hidden,
        "tempdir_total": len(all_entries) - len(entries) if not include_tempdir else 0,
    }
    return {
        "summary": summary,
        "entries": entries,
        "roots": workspace_catalog.list_roots(),
    }


def _find_by_id(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get(key, "")) == value:
            return row
    return None
