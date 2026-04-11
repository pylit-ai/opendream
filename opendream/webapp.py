from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from . import workspace_catalog
from .observability import (
    build_graph,
    create_annotation,
    create_export,
    create_review_decision,
    index_observability,
    load_or_build_index,
    query_memories,
)
from .storage import MemoryStore


_STATIC_ROOT = (Path(__file__).parent / "static").resolve()
_STATIC_MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".md": "text/markdown",
    ".html": "text/html; charset=utf-8",
}


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenDream Observability</title>
  <style>
    :root { --bg:#0b1020; --panel:#121935; --muted:#94a3b8; --text:#e2e8f0; --accent:#67e8f9; --warn:#fbbf24; --bad:#f87171; --good:#4ade80; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background: radial-gradient(circle at top, #152042, #0b1020 58%); color:var(--text); }
    header { padding: 20px 24px; border-bottom: 1px solid rgba(255,255,255,0.08); position: sticky; top:0; backdrop-filter: blur(8px); background: rgba(11,16,32,0.9); }
    nav a { color: var(--muted); margin-right: 12px; text-decoration: none; }
    nav a.active, nav a:hover { color: var(--accent); }
    main { padding: 24px; display:grid; gap:16px; grid-template-columns: 1.2fr 1fr; }
    .full { grid-column: 1 / -1; }
    .panel { background: rgba(18,25,53,0.86); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:16px; box-shadow: 0 12px 40px rgba(0,0,0,0.25); }
    .metric { display:inline-block; min-width: 140px; margin: 0 16px 12px 0; }
    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .value { font-size: 28px; font-weight: 700; }
    input, select, button, textarea { background:#0f1630; border:1px solid rgba(255,255,255,0.12); color:var(--text); border-radius:10px; padding:10px 12px; }
    button { cursor:pointer; }
    table { width:100%; border-collapse: collapse; }
    th, td { text-align:left; padding:10px; border-bottom: 1px solid rgba(255,255,255,0.06); vertical-align: top; }
    tr:hover { background: rgba(255,255,255,0.03); }
    pre { white-space: pre-wrap; word-break: break-word; background:#0a1128; padding:12px; border-radius:10px; max-height: 420px; overflow:auto; }
    .badge { display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; margin-right: 6px; }
    .active-badge { background: rgba(74,222,128,0.18); color: var(--good); }
    .contested-badge, .warning-badge { background: rgba(251,191,36,0.18); color: var(--warn); }
    .superseded-badge, .error-badge { background: rgba(248,113,113,0.18); color: var(--bad); }
    .muted { color: var(--muted); }
    .row { display:flex; gap:12px; flex-wrap: wrap; align-items:center; }
    .split { display:grid; gap:16px; grid-template-columns: 1fr 1fr; }
    @media (max-width: 900px) { main { grid-template-columns: 1fr; } .split { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="row" style="justify-content:space-between">
      <div>
        <div class="label">Observe</div>
        <h1 style="margin:6px 0 0 0">OpenDream Observability</h1>
      </div>
      <nav>
        <a href="/overview">Overview</a>
        <a href="/workspaces">Workspaces</a>
        <a href="/memories">Memories</a>
        <a href="/runs">Runs</a>
        <a href="/retrievals">Retrievals</a>
        <a href="/reviews">Reviews</a>
        <a href="/graph">Graph</a>
        <a href="/evals">Evals</a>
        <a href="/exports">Exports</a>
        <a href="/settings">Settings</a>
      </nav>
    </div>
  </header>
  <main id="app"></main>
  <script>
    const app = document.getElementById('app');
    const route = location.pathname;
    document.querySelectorAll('nav a').forEach(a => { if (route === a.getAttribute('href')) a.classList.add('active'); });
    const qs = (obj) => new URLSearchParams(obj).toString();
    const fetchJson = async (path, options={}) => {
      const response = await fetch(path, options);
      if (!response.ok) throw new Error(await response.text());
      return await response.json();
    };
    const badge = (value) => `<span class="badge ${value === 'active' ? 'active-badge' : value === 'contested' ? 'contested-badge' : value === 'superseded' ? 'superseded-badge' : 'warning-badge'}">${value}</span>`;
    const panel = (title, body, full=false) => `<section class="panel ${full ? 'full' : ''}"><h2>${title}</h2>${body}</section>`;
    const pretty = (obj) => `<pre>${JSON.stringify(obj, null, 2)}</pre>`;

    async function renderOverview() {
      const data = await fetchJson('/api/overview');
      app.innerHTML = [
        panel('Store Health', `
          <div class="metric"><div class="label">State</div><div class="value">${data.store_health.lock.present ? 'Locked' : 'Ready'}</div></div>
          <div class="metric"><div class="label">Memory Root</div><div class="value" style="font-size:16px">${data.store_health.memory_root}</div></div>
          <div class="metric"><div class="label">Contested</div><div class="value">${data.contested_memories}</div></div>
        `),
        panel('Counts', `
          <div class="metric"><div class="label">Total Memories</div><div class="value">${data.memory_counts.total}</div></div>
          <div class="metric"><div class="label">Startup Entries</div><div class="value">${data.startup_index.entries}</div></div>
          <div class="metric"><div class="label">Retrieval Hit Rate</div><div class="value">${data.retrievals.total ? Math.round((data.retrievals.successful / data.retrievals.total) * 100) + '%' : '0%'}</div></div>
        `),
        panel('Recent Runs', `<table><thead><tr><th>ID</th><th>Status</th><th>Type</th></tr></thead><tbody>${data.recent_runs.map(run => `<tr><td><a href="/runs/${run.run_id}">${run.run_id}</a></td><td>${run.status || ''}</td><td>${run.type}</td></tr>`).join('')}</tbody></table>`, true),
        panel('Recent Sessions', `<table><thead><tr><th>Session</th><th>Events</th><th>Ended</th></tr></thead><tbody>${data.recent_sessions.map(session => `<tr><td><a href="/sessions/${session.session_id}">${session.session_id}</a></td><td>${session.event_count}</td><td>${session.ended_at || ''}</td></tr>`).join('')}</tbody></table>`, true),
        panel('Fidelity Diagnostics', `<div class="split"><div>${pretty(data.signal_coverage)}</div><div>${pretty(data.activation_diagnostics)}</div></div>`, true),
      ].join('');
    }

    async function renderMemories(memoryId=null) {
      const params = new URLSearchParams(location.search);
      const search = params.get('search') || '';
      const type = params.get('type') || '';
      const data = await fetchJson('/api/memories?' + qs({search, type}));
      let detailHtml = '<p class="muted">Select a memory record.</p>';
      if (memoryId) {
        const detail = await fetchJson('/api/memories/' + memoryId);
        detailHtml = `
          <div class="row"><strong>${detail.title}</strong>${badge(detail.status)}</div>
          <p>${detail.summary}</p>
          <p class="muted">Sources: ${detail.source_event_ids.join(', ') || 'none'}</p>
          <div class="split">
            <div>${pretty(detail.raw_json)}</div>
            <div>${pretty({lineage: detail.lineage, annotations: detail.annotations, manual_reviews: detail.manual_reviews})}</div>
          </div>`;
      }
      app.innerHTML = [
        panel('Memory Explorer', `
          <form class="row" onsubmit="event.preventDefault(); location.search = '?' + qs({search:this.search.value, type:this.type.value});">
            <input name="search" placeholder="search memory" value="${search}">
            <input name="type" placeholder="type filter" value="${type}">
            <button type="submit">Filter</button>
          </form>
          <table><thead><tr><th>Title</th><th>Status</th><th>Type</th><th>Scope</th><th>Updated</th></tr></thead><tbody>
            ${data.items.map(item => `<tr><td><a href="/memories/${item.memory_id}">${item.title}</a></td><td>${badge(item.status)}</td><td>${item.type}</td><td>${item.scope}</td><td>${item.updated_at}</td></tr>`).join('')}
          </tbody></table>
        `),
        panel('Memory Detail', detailHtml),
      ].join('');
    }

    async function renderRuns(runId=null) {
      const data = await fetchJson('/api/runs');
      let detailHtml = '<p class="muted">Select a run.</p>';
      if (runId) {
        const detail = await fetchJson('/api/runs/' + runId);
        detailHtml = `
          <div class="row"><strong>${detail.run_id}</strong><span>${detail.type}</span><span>${detail.status}</span></div>
          <h3>Phase Timeline</h3>${pretty(detail.phase_traces)}
          <h3>Op Log</h3>${pretty(detail.operations)}
          <h3>Diff</h3><pre>${detail.diff_text || 'No diff artifact.'}</pre>`;
      }
      app.innerHTML = [
        panel('Runs', `<table><thead><tr><th>ID</th><th>Type</th><th>Status</th></tr></thead><tbody>${data.items.map(run => `<tr><td><a href="/runs/${run.run_id}">${run.run_id}</a></td><td>${run.type}</td><td>${run.status}</td></tr>`).join('')}</tbody></table>`),
        panel('Consolidation Inspector', detailHtml),
      ].join('');
    }

    async function renderRetrievals(retrievalId=null) {
      const data = await fetchJson('/api/retrievals');
      let detailHtml = '<p class="muted">Select a retrieval.</p>';
      if (retrievalId) {
        const detail = await fetchJson('/api/retrievals/' + retrievalId);
        detailHtml = `<p><strong>${detail.query}</strong></p><div class="split"><div>${pretty(detail.explanations)}</div><div>${pretty({excluded:detail.excluded, order:detail.final_context_assembly_order})}</div></div>`;
      }
      app.innerHTML = [
        panel('Retrievals', `<table><thead><tr><th>ID</th><th>Query</th><th>Selected</th></tr></thead><tbody>${data.items.map(item => `<tr><td><a href="/retrievals/${item.id}">${item.id}</a></td><td>${item.query}</td><td>${item.selected_memory_ids.length}</td></tr>`).join('')}</tbody></table>`),
        panel('Retrieval Explainability', detailHtml),
      ].join('');
    }

    async function renderReviews() {
      const data = await fetchJson('/api/reviews');
      app.innerHTML = [
        panel('Review Queue', `<table><thead><tr><th>Type</th><th>Item</th><th>Reason</th></tr></thead><tbody>${data.items.map(item => `<tr><td>${item.queue_item_type}</td><td>${item.queue_item_id}</td><td>${item.reason}</td></tr>`).join('')}</tbody></table>`, true),
      ].join('');
    }

    function loadScript(src) {
      return new Promise((resolve, reject) => {
        if (document.querySelector('script[src="' + src + '"]')) return resolve();
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = () => reject(new Error('failed to load ' + src));
        document.head.appendChild(s);
      });
    }

    async function renderGraph() {
      app.innerHTML = '<section class="panel full" style="padding:0;"><div id="graph-root"></div></section>';
      try {
        if (!window.__opendreamGraph) {
          const scripts = [
            '/static/vendor/graphology.umd.min.js',
            '/static/vendor/graphology-layout-forceatlas2.min.js',
            '/static/vendor/sigma.min.js',
            '/static/graph.js',
          ];
          for (const src of scripts) await loadScript(src);
        }
        window.__opendreamGraph.mount(document.getElementById('graph-root'));
      } catch (err) {
        const data = await fetchJson('/api/graph');
        app.innerHTML = [
          panel('Provenance Graph (fallback view \u2014 interactive renderer failed: ' + err.message + ')', `<div class="split"><div>${pretty(data.nodes)}</div><div>${pretty(data.edges)}</div></div>`, true),
        ].join('');
      }
    }

    async function renderEvals() {
      const data = await fetchJson('/api/evals');
      app.innerHTML = [panel('Health / Evals', pretty(data), true)].join('');
    }

    async function renderExports() {
      const data = await fetchJson('/api/exports');
      app.innerHTML = [panel('Exports', pretty(data), true)].join('');
    }

    async function renderSettings() {
      const data = await fetchJson('/api/overview');
      app.innerHTML = [panel('Settings / Store Metadata', pretty({store_health:data.store_health, startup_index:data.startup_index, activation_diagnostics:data.activation_diagnostics}), true)].join('');
    }

    async function renderSessions(sessionId=null) {
      const data = await fetchJson('/api/sessions');
      let detailHtml = '<p class="muted">Select a session.</p>';
      if (sessionId) {
        const detail = await fetchJson('/api/sessions/' + sessionId + '/timeline');
        detailHtml = pretty(detail);
      }
      app.innerHTML = [
        panel('Sessions', `<table><thead><tr><th>ID</th><th>Events</th><th>Contexts</th></tr></thead><tbody>${data.items.map(item => `<tr><td><a href="/sessions/${item.session_id}">${item.session_id}</a></td><td>${item.event_count}</td><td>${item.context_count}</td></tr>`).join('')}</tbody></table>`),
        panel('Session Timeline', detailHtml),
      ].join('');
    }

    async function renderContext(contextId) {
      const data = await fetchJson('/api/context/' + contextId);
      app.innerHTML = [panel('Context Viewer', `<div class="split"><div>${pretty({selected:data.selected_memory_ids, omitted:data.omission_reasons, startup:data.startup_index_snapshot})}</div><div><pre>${data.assembled_text}</pre></div></div>`, true)].join('');
    }

    async function renderWorkspaces() {
      const data = await fetchJson('/api/workspaces');
      const summary = data.summary;
      const entries = data.entries;
      const searchParams = new URLSearchParams(location.search);
      const q = (searchParams.get('q') || '').toLowerCase();
      const statusFilter = searchParams.get('status') || '';
      const filtered = entries.filter(e => {
        if (statusFilter && e.status_kind !== statusFilter) return false;
        if (q) {
          const hay = (e.workspace_path + ' ' + (e.workspace_name || '')).toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
      const rows = filtered.map(e => {
        const statusCls = e.status_kind === 'ok' ? 'active-badge' : (e.status_kind === 'stale' ? 'warning-badge' : 'error-badge');
        return `<tr>
          <td><a href="/workspaces/${encodeURIComponent(e.workspace_path)}">${e.workspace_name}</a><div class="muted" style="font-size:11px">${e.workspace_path}</div></td>
          <td><span class="badge ${statusCls}">${e.status_kind}</span></td>
          <td>${e.activation_state_summary || '<span class="muted">—</span>'}</td>
          <td>${e.service_state_summary || '<span class="muted">—</span>'}</td>
          <td>${e.memory_dir || '<span class="muted">—</span>'}</td>
          <td>${e.semantic_state_summary || '<span class="muted">—</span>'}</td>
          <td class="muted">${e.last_seen_at || ''}</td>
        </tr>`;
      }).join('');
      app.innerHTML = [
        panel('Workspaces Overview', `
          <div class="metric"><div class="label">Total</div><div class="value">${summary.total}</div></div>
          <div class="metric"><div class="label">Healthy</div><div class="value">${summary.ok}</div></div>
          <div class="metric"><div class="label">With Service</div><div class="value">${summary.with_service}</div></div>
          <div class="metric"><div class="label">Stale/Missing/Broken</div><div class="value">${summary.stale + summary.missing + summary.broken}</div></div>
        `, true),
        panel('Workspace Catalog', `
          <form class="row" onsubmit="event.preventDefault(); location.search = '?' + qs({q:this.q.value, status:this.status.value});">
            <input name="q" placeholder="search path/name" value="${q}">
            <select name="status">
              <option value="">any status</option>
              <option value="ok" ${statusFilter==='ok'?'selected':''}>ok</option>
              <option value="stale" ${statusFilter==='stale'?'selected':''}>stale</option>
              <option value="missing" ${statusFilter==='missing'?'selected':''}>missing</option>
              <option value="broken" ${statusFilter==='broken'?'selected':''}>broken</option>
            </select>
            <button type="submit">Filter</button>
            <span class="muted">${filtered.length} of ${entries.length} entries</span>
          </form>
          <table>
            <thead><tr><th>Workspace</th><th>Status</th><th>Activation</th><th>Service</th><th>Memory Dir</th><th>Semantic</th><th>Last Seen</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="7" class="muted">No workspaces in the local catalog. Run <code>opendream workspace scan --root &lt;path&gt;</code> or initialize a workspace.</td></tr>'}</tbody>
          </table>
        `, true),
        panel('Privacy', `<p class="muted">This catalog is machine-local. Workspace <code>.opendream/</code> state remains canonical. Scans only run on explicitly configured roots.</p>`, true),
      ].join('');
    }

    async function renderWorkspaceDetail(rawPath) {
      const path = decodeURIComponent(rawPath);
      const data = await fetchJson('/api/workspaces/' + encodeURIComponent(path));
      if (data.status === 'missing') {
        app.innerHTML = [panel('Workspace Detail', `<p class="muted">No catalog entry for <code>${path}</code>.</p>`, true)].join('');
        return;
      }
      app.innerHTML = [
        panel('Workspace Detail', `
          <h3>${data.entry.workspace_name}</h3>
          <p class="muted">${data.entry.workspace_path}</p>
          ${pretty(data.entry)}
        `, true),
      ].join('');
    }

    if (route === '/' || route === '/overview') renderOverview();
    else if (route === '/workspaces') renderWorkspaces();
    else if (route.startsWith('/workspaces/')) renderWorkspaceDetail(route.split('/').pop());
    else if (route === '/memories') renderMemories();
    else if (route.startsWith('/memories/')) renderMemories(route.split('/').pop());
    else if (route === '/runs') renderRuns();
    else if (route.startsWith('/runs/')) renderRuns(route.split('/').pop());
    else if (route === '/retrievals') renderRetrievals();
    else if (route.startsWith('/retrievals/')) renderRetrievals(route.split('/').pop());
    else if (route === '/reviews') renderReviews();
    else if (route === '/graph') renderGraph();
    else if (route === '/evals') renderEvals();
    else if (route === '/exports') renderExports();
    else if (route === '/settings') renderSettings();
    else if (route === '/sessions') renderSessions();
    else if (route.startsWith('/sessions/')) renderSessions(route.split('/').pop());
    else if (route.startsWith('/context/')) renderContext(route.split('/').pop());
    else renderOverview();
  </script>
</body>
</html>"""


class ObservabilityHandler(BaseHTTPRequestHandler):
    store: MemoryStore

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/stream"):
            self._write_event_stream()
            return
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path)
            return
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed)
            return
        self._write_html(INDEX_HTML)

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
            result = query_memories(
                index,
                search=query.get("search", ""),
                filters={key: query.get(key, "") for key in ["type", "scope", "status"]},
                sort=query.get("sort", "updated_at"),
                offset=int(query.get("offset", "0")),
                limit=int(query.get("limit", "50")),
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
            self._write_json({"items": entities["runs"]})
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
            self._write_json({"items": entities["retrievals"]})
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
            self._write_json(
                build_graph(
                    index,
                    focus=query.get("focus"),
                    limit=int(query.get("limit", "24")),
                    depth=int(query.get("depth", "1")),
                    layout=query.get("layout", "hierarchical"),
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

    def _write_html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, request_path: str) -> None:
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
        self.wfile.write(body)

    def _write_event_stream(self) -> None:
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
