from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from . import workspace_catalog
from .dream import dream_worker
from .integration import emit_event
from .observability import (
    build_graph,
    create_annotation,
    create_export,
    create_review_decision,
    index_observability,
    load_or_build_index,
    query_memories,
    query_retrievals,
    query_runs,
)
from .semantic_dreamer import dream_status_semantic
from .service import disable_background_runtime, enable_background_runtime, restart_service, service_status, start_service, stop_service
from .storage import MemoryStore
from .util import CLI_JSON_VERSION, to_iso, utc_now
from .validation import SchemaValidationError, validate_document

_STATIC_ROOT = (Path(__file__).parent / "static").resolve()


def _observe_static_asset_version() -> str:
    """Cache-bust string for observe UI assets (changes when observe-ui.js mtime changes)."""
    try:
        return str(int((_STATIC_ROOT / "observe-ui.js").stat().st_mtime))
    except OSError:
        return "1"


def _index_html() -> str:
    """INDEX_HTML with versioned /static/* URLs so browsers pick up updated JS/CSS."""
    v = _observe_static_asset_version()
    return (
        INDEX_HTML.replace(
            'href="/static/observe-ui.css"',
            f'href="/static/observe-ui.css?v={v}"',
        )
        .replace(
            'href="/static/graph.css"',
            f'href="/static/graph.css?v={v}"',
        )
        .replace(
            'src="/static/observe-ui.js"',
            f'src="/static/observe-ui.js?v={v}"',
        )
    )


_STATIC_MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".md": "text/markdown",
    ".html": "text/html; charset=utf-8",
}

_MEMORY_LIST_LIMIT_CAP = 500
_RETRIEVAL_LIST_LIMIT_CAP = 500
_RUN_LIST_LIMIT_CAP = 500


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


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <script>
(function(){
  try {
    var k='opendream-ui-theme';
    var s=localStorage.getItem(k);
    var pref=(s==='light'||s==='dark'||s==='system')?s:'system';
    var resolved;
    if(pref==='light') resolved='light';
    else if(pref==='dark') resolved='dark';
    else resolved=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';
    document.documentElement.setAttribute('data-theme-pref', pref);
    document.documentElement.setAttribute('data-theme', resolved);
  } catch(e) {
    document.documentElement.setAttribute('data-theme-pref', 'system');
    document.documentElement.setAttribute('data-theme','dark');
  }
  try {
    var pk='opendream-ui-palette';
    var pv=localStorage.getItem(pk);
    var ok=['default','violet','teal','rose','emerald'];
    document.documentElement.setAttribute('data-palette', ok.indexOf(pv)>=0 ? pv : 'default');
  } catch(e4) { document.documentElement.setAttribute('data-palette','default'); }
  try {
    var sk='opendream-sidebar';
    var sv=localStorage.getItem(sk);
    if(sv==='wide'||sv==='narrow') document.documentElement.setAttribute('data-sidebar',sv);
    else document.documentElement.setAttribute('data-sidebar','wide');
  } catch(e2) { document.documentElement.setAttribute('data-sidebar','wide'); }
  try {
    var dk='opendream-ui-density';
    var dv=localStorage.getItem(dk);
    if(dv==='compact'||dv==='comfortable') document.documentElement.setAttribute('data-density',dv);
    else document.documentElement.setAttribute('data-density','comfortable');
  } catch(e3) { document.documentElement.setAttribute('data-density','comfortable'); }
})();
  </script>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenDream Observability</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/observe-ui.css">
  <link rel="stylesheet" href="/static/graph.css">
</head>
<body>
  <a class="od-skip-link" href="#app">Skip to main content</a>
  <div class="app-shell">
    <button type="button" class="icon-btn sidebar-toggle sidebar-toggle--mobile" id="sidebar-mobile-open" aria-controls="sidebar-nav" aria-expanded="false" title="Open menu">
      <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <div class="sidebar-backdrop" id="sidebar-backdrop" aria-hidden="true"></div>
    <aside class="sidebar" id="sidebar-aside" aria-label="App">
      <button type="button" class="icon-btn sidebar-toggle" id="sidebar-toggle" aria-controls="sidebar-nav" title="Narrow sidebar">
        <span class="when-wide" aria-hidden="true"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg></span>
        <span class="when-narrow" aria-hidden="true"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg></span>
      </button>
      <div class="sidebar-brand">
        <div class="sidebar-logo" aria-hidden="true">OD</div>
        <div class="sidebar-brand-text">
          <div class="sidebar-brand-kicker">Observe</div>
          <div class="sidebar-brand-title">OpenDream</div>
        </div>
      </div>
      <nav class="sidebar-nav" id="sidebar-nav" aria-label="Primary">
        <p class="sidebar-nav-section" id="sidebar-sec-catalog">Catalog</p>
        <ul class="sidebar-nav-list" aria-labelledby="sidebar-sec-catalog">
          <li><a href="/workspaces" data-short="Ws" title="Workspaces"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg><span class="nav-label">Workspaces</span></a></li>
        </ul>
        <p class="sidebar-nav-section" id="sidebar-sec-this-ws">This workspace</p>
        <ul class="sidebar-nav-list" aria-labelledby="sidebar-sec-this-ws">
          <li><a href="/overview" data-short="Ov" title="Overview"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg><span class="nav-label">Overview</span></a></li>
          <li><a href="/memories" data-short="Mem" title="Memories"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg><span class="nav-label">Memories</span></a></li>
        </ul>
        <p class="sidebar-nav-section" id="sidebar-sec-trace">Trace</p>
        <ul class="sidebar-nav-list" aria-labelledby="sidebar-sec-trace">
          <li><a href="/runs" data-short="Rn" title="Runs"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span class="nav-label">Runs</span></a></li>
          <li><a href="/retrievals" data-short="Ret" title="Retrievals"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span class="nav-label">Retrievals</span></a></li>
          <li><a href="/sessions" data-short="Ses" title="Sessions"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg><span class="nav-label">Sessions</span></a></li>
          <li><a href="/context" data-short="Ctx" title="Context"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg><span class="nav-label">Context</span></a></li>
        </ul>
        <p class="sidebar-nav-section" id="sidebar-sec-audit">Audit and tools</p>
        <ul class="sidebar-nav-list" aria-labelledby="sidebar-sec-audit">
          <li><a href="/reviews" data-short="Rev" title="Reviews"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="m9 12 2 2 4-4"/></svg><span class="nav-label">Reviews</span></a></li>
          <li><a href="/graph" data-short="Gr" title="Graph"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg><span class="nav-label">Graph</span></a></li>
          <li><a href="/evals" data-short="Ev" title="Evals"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg><span class="nav-label">Evals</span></a></li>
          <li><a href="/exports" data-short="Ex" title="Exports"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span class="nav-label">Exports</span></a></li>
          <li><a href="/settings" data-short="St" title="Settings"><svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg><span class="nav-label">Settings</span></a></li>
        </ul>
      </nav>
      <div class="sidebar-footer">
        <div class="theme-toggle" role="group" aria-label="Appearance">
          <button type="button" data-theme-pref="light" id="theme-btn-light" class="icon-btn" aria-label="Light theme" title="Light theme">
            <svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
          </button>
          <button type="button" data-theme-pref="dark" id="theme-btn-dark" class="icon-btn" aria-label="Dark theme" title="Dark theme">
            <svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          </button>
          <button type="button" data-theme-pref="system" id="theme-btn-system" class="icon-btn" aria-label="Match system theme" title="Match system">
            <svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
          </button>
        </div>
      </div>
    </aside>
    <div class="main-wrap">
      <div id="od-scope-bar" class="od-scope-bar" role="region" aria-label="Observability scope">
        <div class="od-scope-bar-inner">
          <div class="od-scope-main">
            <p class="od-scope-title">Observability scope</p>
            <div class="od-scope-path-row">
            <p id="od-scope-path" class="od-scope-path" title="">Loading workspace…</p>
            <a id="od-scope-health-pill" class="od-scope-health-pill od-scope-health-pill--loading" aria-live="polite" title="" href="/overview">…</a>
            </div>
            <div class="od-dream-mode-row" id="od-dream-mode-row">
              <div class="od-dream-mode-control">
                <span id="od-dream-mode-sparkle" class="od-dream-mode-sparkle-wrap" aria-hidden="true" hidden></span>
                <label for="od-dream-mode-select" class="od-dream-mode-label">Advanced semantic mode</label>
                <select id="od-dream-mode-select" class="od-dream-mode-select" disabled aria-describedby="od-dream-mode-help">
                  <option value="deterministic" title='Same as opendream semantic config JSON "mode": "deterministic" — consolidation only; semantic synthesis stays off until providers are configured.'>Deterministic only — consolidation only (matches CLI mode deterministic)</option>
                  <option value="hybrid" title='Same as "mode": "hybrid" — run deterministic consolidation, then learned-context / semantic phases.'>Hybrid — consolidation then learned-context (matches CLI mode hybrid)</option>
                  <option value="semantic" title='Same as "mode": "semantic" — learned-context phases without a deterministic consolidation pass first.'>Semantic only — learned-context without consolidation first (matches CLI mode semantic)</option>
                </select>
                <span id="od-dream-mode-status" class="od-dream-mode-status muted" aria-live="polite"></span>
              </div>
              <p id="od-dream-mode-help" class="od-dream-mode-help muted">This is an advanced control for the raw <code>mode</code> field in <code>memory/state/semantic_config.json</code>. It does not by itself prove semantic readiness. Use <a href="/overview">Overview</a> and <a href="/settings">Settings</a> for readiness, state reason, next action, memory-quality warnings, and pruning evidence. Each <code>opendream dream run --mode …</code> can still override for a single run.</p>
            </div>
            <p id="od-scope-origin" class="od-scope-origin muted"></p>
            <details class="od-scope-about">
              <summary class="od-scope-about-summary muted">About this dashboard</summary>
              <p class="od-scope-hint muted">The Workspaces page lists every catalog entry on this machine. Overview, Memories, Trace, and Audit tabs show data for the workspace bound to this <code>observe serve</code> process only. Overview and Settings lead with semantic readiness, degraded fallback, memory-quality warnings, and pruning evidence; the raw mode selector remains available as an advanced control.</p>
            </details>
          </div>
          <div class="od-scope-actions">
            <details class="od-scope-bookmarks" aria-label="Other saved observe serve dashboards">
              <summary class="od-scope-summary">Other dashboards</summary>
              <div class="od-scope-bookmarks-body">
                <p class="muted" style="font-size:11px;margin:0 0 6px;line-height:1.45">Bookmark each running server (different port = different workspace). Open jumps to that origin.</p>
                <button type="button" class="od-scope-add-btn" id="od-scope-add-bookmark">Bookmark this</button>
                <ul id="od-scope-bookmark-list" class="od-scope-bookmark-list" aria-label="Saved dashboard URLs"></ul>
              </div>
            </details>
          </div>
        </div>
      </div>
      <div id="od-data-freshness" class="od-data-freshness muted" aria-live="polite"></div>
      <div id="od-route-announce" class="sr-only" aria-live="polite" aria-atomic="true"></div>
      <main id="app" class="main-content" tabindex="-1" aria-busy="false" aria-label="Main content"></main>
    </div>
  </div>
  <dialog id="od-fs-dialog" class="od-fs-dialog" aria-labelledby="od-fs-title" aria-modal="true">
    <div class="od-fs-chrome">
      <h2 id="od-fs-title" class="od-fs-title"></h2>
      <button type="button" class="icon-btn" id="od-fs-close" aria-label="Close fullscreen" title="Close">
        <svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
    <div class="od-fs-scroll" id="od-fs-host"></div>
  </dialog>
  <dialog id="od-command-palette" class="od-command-palette" aria-labelledby="od-palette-title">
    <div class="od-palette-head">
      <h2 id="od-palette-title" class="od-palette-title">Command palette</h2>
      <button type="button" class="icon-btn" id="od-palette-close" aria-label="Close command palette" title="Close">
        <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
    <input type="search" id="od-palette-input" class="od-palette-input" autocomplete="off" placeholder="Filter pages and actions…" />
    <ul id="od-palette-list" class="od-palette-list"></ul>
    <p class="muted od-palette-hint">⌘K / Ctrl+K · ↑↓ · Enter · Esc · Empty filter shows recent routes · Actions (copy path, latest run) match search keywords</p>
  </dialog>
  <script src="/static/observe-ui.js" defer></script>
</body>
</html>"""


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
        self._write_html(_index_html(), head_only=head_only)

    def do_POST(self) -> None:  # noqa: N802
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
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        index_observability(self.store)
        self._write_json(response)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _handle_api_get(self, parsed: Any) -> None:
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        if parsed.path == "/api/ui-context":
            self._write_json(_ui_context_payload(self.store))
            return
        if parsed.path == "/api/ui-meta":
            self._write_json(_ui_meta_payload())
            return
        if parsed.path == "/api/health":
            self._write_json(_health_payload(self.store))
            return
        index = load_or_build_index(self.store)
        entities = index["entities"]
        if parsed.path == "/api/overview":
            self._write_json(index["overview"])
            return
        if parsed.path == "/api/workspaces":
            self._write_json(_workspace_dashboard_payload())
            return
        if parsed.path.startswith("/api/workspaces/"):
            from urllib.parse import unquote

            workspace_arg = unquote(parsed.path[len("/api/workspaces/") :])
            entry = workspace_catalog.inspect_entry(workspace_arg)
            if entry is None:
                self._write_json({"status": "missing", "workspace": workspace_arg})
            else:
                self._write_json({"status": "ok", "entry": entry})
            return
        if parsed.path == "/api/memories":
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
                index,
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
        if parsed.path == "/api/sessions":
            self._write_json({"items": entities["sessions"]})
            return
        if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/timeline"):
            session_id = parsed.path.split("/")[-2]
            session = _find_by_id(entities["sessions"], "session_id", session_id)
            self._write_json(session or {})
            return
        if parsed.path == "/api/runs":
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_RUN_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            result = query_runs(
                index,
                search=query.get("search", ""),
                sort=query.get("sort", "ended_at"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                ended_after=(query.get("ended_after") or "").strip() or None,
                ended_before=(query.get("ended_before") or "").strip() or None,
            )
            self._write_json(result)
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
        if parsed.path == "/api/retrievals":
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_RETRIEVAL_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            result = query_retrievals(
                index,
                search=query.get("search", ""),
                filters={key: query.get(key, "") for key in ["agent_id"]},
                sort=query.get("sort", "timestamp"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                timestamp_after=(query.get("timestamp_after") or "").strip() or None,
                timestamp_before=(query.get("timestamp_before") or "").strip() or None,
                min_selected=_parse_query_int(query.get("min_selected"), 0, minimum=0, maximum=1_000_000)
                if (query.get("min_selected") or "").strip()
                else None,
                max_selected=_parse_query_int(query.get("max_selected"), 0, minimum=0, maximum=1_000_000)
                if (query.get("max_selected") or "").strip()
                else None,
            )
            self._write_json(result)
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
            self._write_json(
                build_graph(
                    index,
                    focus=focus,
                    limit=int(query.get("limit", "24")),
                    depth=depth,
                    layout=layout,
                )
            )
            return
        if parsed.path == "/api/reviews":
            self._write_json({"items": entities["reviews"], "decisions": self.store.load_review_decisions()})
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
    product_posture = str(overview.get("product_posture") or "deterministic-by-choice")
    semantic_capability_state = str(overview.get("semantic_capability_state") or "unknown")
    semantic_unavailability_reason = overview.get("semantic_unavailability_reason")
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
        "observe_ui": {"static_assets": ["observe-ui.css", "observe-ui.js"]},
    }


def _workspace_dashboard_payload() -> dict[str, Any]:
    """Build the read-model payload used by the /workspaces dashboard route.

    Uses the machine-local catalog for fast initial render; the dashboard
    can trigger re-probes via the CLI (``opendream workspace doctor``) rather
    than performing synchronous disk work inside the HTTP handler.
    """
    entries = workspace_catalog.list_entries()
    summary = {
        "total": len(entries),
        "ok": sum(1 for e in entries if e.get("status_kind") == "ok"),
        "stale": sum(1 for e in entries if e.get("status_kind") == "stale"),
        "missing": sum(1 for e in entries if e.get("status_kind") == "missing"),
        "broken": sum(1 for e in entries if e.get("status_kind") == "broken"),
        "with_service": sum(1 for e in entries if e.get("service_state_summary")),
        "with_semantic": sum(1 for e in entries if e.get("semantic_state_summary")),
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
