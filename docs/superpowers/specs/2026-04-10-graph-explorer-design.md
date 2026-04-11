# Graph Explorer — Design

**Date:** 2026-04-10
**Status:** approved for implementation planning
**Author:** brainstorming session (Claude + reynard)
**Topic:** replace the JSON-dump `/graph` page in `opendream/webapp.py` with a beautiful, interactive provenance explorer powered by Sigma.js v3 + Graphology

---

## 1. Problem

`opendream/webapp.py:181-186` currently renders the `/graph` route by calling `pretty(data.nodes)` and `pretty(data.edges)` — two side-by-side `<pre>` blocks of raw JSON. The backend already produces a rich provenance graph (`opendream/observability.py:67`, `opendream/relation_graph.py:17`) with four node types (`memory`, `review`, `run`, `retrieval`) and seven directed relation kinds (`supersedes`, `conflicts_with`, `supports`, `derived_from`, `verified_by`, `invalidated_by`, `reviewed`). None of that structure is legible to a human looking at the page.

The goal is to make this graph **beautiful and interactive** without breaking the single-Python-file webapp ethos and without introducing a build step (no npm, no bundler, no React).

## 2. Constraints (from current architecture)

- **No build pipeline.** `opendream/webapp.py` is a 527-line `http.server` handler that serves one inline `INDEX_HTML` string with vanilla JS. Any new dependency must load via `<script src="...">` tags.
- **Dark theme already established** (`--bg:#0b1020`, `--accent:#67e8f9`, etc.) — the explorer should inherit it.
- **Local-first.** This dashboard runs against a local memory store and is the kind of tool people fire up on a plane or behind a corporate proxy. It must work offline.
- **Existing API surface** is `/api/graph?focus=<id>&limit=<n>` returning `{nodes, edges, focus}`. We can extend it but should avoid breaking it.

## 3. Decisions made during brainstorming

| # | Question | Choice | Rationale |
|---|----------|--------|-----------|
| Q1 | Library | **Sigma.js v3 + Graphology** | WebGL ceiling, modern look, scales past 2k nodes if needed |
| Q2 | Interaction depth | **Full provenance explorer** | Beyond pretty rendering: focus-on-click, filters, URL state, click-through to detail pages |
| Q3 | Layout strategy | **Both, toggleable; default hierarchical** | Provenance reads naturally as a layered DAG; ForceAtlas2 toggle reveals cluster structure on demand |
| Q4 | Library delivery | **Vendored under `opendream/static/vendor/`** | Offline-first, no CDN dependency, deterministic, FA2 worker is trivially same-origin |

## 4. Architecture

Three changes, scoped tightly:

1. **`opendream/observability.py`** — extend `build_graph()` with a `depth` parameter and a `layout` parameter. When `layout="hierarchical"`, compute `{x, y}` positions per node using a topological rank over `supersedes` + `derived_from` edges. When `layout="forceatlas2"`, return nodes without positions and let Sigma compute them client-side.

2. **`opendream/webapp.py`** — add a `/static/<path>` GET handler. Replace the inline `renderGraph()` JS with a small loader that lazy-loads four `<script>` tags from `/static/`. Pass `depth` and `layout` query params through `/api/graph` to `build_graph()`.

3. **`opendream/static/`** — new directory shipped in-repo. Holds vendored third-party JS plus our own `graph.js` and `graph.css`.

The rest of the dashboard pages stay exactly as they are. The new `/static/` route is a foundation other pages can adopt later.

### 4.1 Why `graph.js` lives in its own file (not `INDEX_HTML`)

The graph code is ~700 lines. Embedding ~700 lines of JS inside a Python triple-quoted string is unreviewable, breaks editor tooling, and makes diffs noisy. Once we are vendoring static assets we should use the same mechanism for our own JS. The rest of the dashboard remains inline because each existing page is small (<100 lines of JS each).

## 5. Backend changes

### 5.1 `observability.py` — `build_graph()` extension

Approximately 50 lines added.

```python
def build_graph(
    index: dict[str, Any],
    *,
    focus: str | None = None,
    limit: int = 24,
    depth: int = 1,
    layout: str = "hierarchical",
) -> dict[str, Any]:
    graph = index["entities"]["graph"]
    nodes, edges = _select_subgraph(graph, focus=focus, limit=limit, depth=depth)
    if layout == "hierarchical":
        positions = _layered_positions(nodes, edges)
        for node in nodes:
            node["x"], node["y"] = positions[node["id"]]
    return {
        "nodes": nodes,
        "edges": edges,
        "focus": focus,
        "depth": depth,
        "layout": layout,
    }


def _select_subgraph(graph, *, focus, limit, depth):
    """BFS up to `depth` hops from `focus`, capped at `limit` nodes.
    If `focus` is None, returns the first `limit` nodes from `graph['nodes']`."""

def _layered_positions(nodes, edges):
    """Topological sort over (supersedes ∪ derived_from) → assigns Y-rank.
    Within each rank, orders nodes by created_at (or id) → assigns X.
    Cycles short-circuit to a stable fallback rank to prevent infinite loops.
    Returns {node_id: (x, y)}."""
```

**Cycle handling.** Provenance graphs *should* be acyclic but bugs happen. `_layered_positions()` uses Kahn's algorithm with an explicit cycle-break: if any nodes remain unassigned after the toposort settles, they get rank `max_rank + 1` in arbitrary order. The function never raises.

**Pure stdlib.** No `networkx` dependency.

### 5.2 `webapp.py` — `/static/` handler + query passthrough

Approximately 25 lines added.

- `do_GET` checks `parsed.path.startswith("/static/")` *before* `_handle_api_get`.
- `_serve_static(parsed.path)`:
  - Strips the `/static/` prefix, normalizes the result with `pathlib.Path`, and rejects any path containing `..` or resolving outside `opendream/static/` (defense-in-depth even though `Path.resolve()` already handles it).
  - Resolves MIME type from a small static dict (`{".js": "application/javascript", ".css": "text/css", ".md": "text/markdown"}`).
  - Sends `Cache-Control: public, max-age=86400` so vendor JS doesn't re-download every page navigation.
  - Returns `404` for unknown files; never falls through to the SPA HTML.
- `/api/graph` query parsing extends to read `depth` (default `1`) and `layout` (default `"hierarchical"`) and passes them through to `build_graph()`.

The existing `INDEX_HTML` route is unchanged except for a one-line `renderGraph()` rewrite (see §6.1).

## 6. Frontend

### 6.1 Loader inside `INDEX_HTML`

The current 5-line `renderGraph()` becomes:

```js
async function renderGraph() {
  app.innerHTML = '<div id="graph-root"></div>';
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
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement('script');
    s.src = src; s.onload = resolve; s.onerror = () => reject(new Error(src));
    document.head.appendChild(s);
  });
}
```

Scripts load **sequentially** (not `Promise.all`) because Sigma depends on Graphology being defined first. After the first load, `window.__opendreamGraph` is cached so subsequent navigations to `/graph` skip the network entirely.

### 6.2 `graph.js` module shape

One file, six logical units, all wrapped in a single IIFE to avoid leaking globals. Exposes exactly one global: `window.__opendreamGraph = { mount }`.

```js
(function () {
  // 1. State — single source of truth
  const state = {
    focus: null,
    depth: 1,
    layout: 'hierarchical',
    filters: { nodeTypes: new Set(), edgeKinds: new Set() },
    selected: null,
    sigma: null,
    graph: null,
  };

  // 2. Theme — node colors per type, edge colors per kind, sizes
  const THEME = { nodeColors: {...}, edgeColors: {...}, edgeStyles: {...} };

  // 3. Data layer — fetchGraph(), applyFilters()
  // 4. Render layer — initSigma(), swapLayout(kind), refresh()
  // 5. UI chrome — renderLegend(), renderFilterChips(), renderSidePanel(),
  //                renderSearchBox(), renderBreadcrumbs(), renderMinimap()
  // 6. Wiring — events: click=focus, dblclick=navigate, hover=tooltip,
  //             URL state sync via history.replaceState

  function mount(rootEl) {
    parseUrlState();
    renderChrome(rootEl);
    fetchGraph().then(initSigma).then(wireEvents);
  }

  window.__opendreamGraph = { mount };
})();
```

Each unit communicates only through `state`. No unit reaches into another unit's internals.

### 6.3 Visual layout (DOM)

Inside `#graph-root`:

```
┌─────────────────────────────────────────────────────────────┐
│ #graph-sidepanel (25%)        │ #graph-canvas-wrap (75%)    │
│  ┌─────────────────────────┐  │  ┌────────────────────────┐ │
│  │ Breadcrumbs             │  │  │                        │ │
│  │ Search box              │  │  │                        │ │
│  │ Layout toggle           │  │  │   Sigma canvas         │ │
│  │ Depth slider (1/2/3)    │  │  │                        │ │
│  │ Node-type filter chips  │  │  │                        │ │
│  │ Edge-kind filter chips  │  │  │                        │ │
│  │ ─── Selected node ───   │  │  │                ┌─────┐ │ │
│  │ Title + type badge      │  │  │                │mini-│ │ │
│  │ Raw data <pre>          │  │  │                │ map │ │ │
│  │ Open detail →           │  │  │                └─────┘ │ │
│  └─────────────────────────┘  │  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

The side panel collapses to a `▸` rail under 900px viewport width (matches the existing media query in `INDEX_HTML`).

### 6.4 Theme — node and edge styling

Driven entirely by the `THEME` constant in `graph.js`, sourced from the existing CSS variables in `INDEX_HTML` so the dark palette stays in sync.

**Node colors (by type):**
- `memory` → cyan `#67e8f9`
- `review` → amber `#fbbf24`
- `run` → green `#4ade80`
- `retrieval` → muted `#94a3b8`

**Node sizes:** uniform 8px by default; the focused node renders at 14px; nodes selected via filter chips render at 4px and 40% opacity to fade them out without removing them.

**Edge styling (by kind):**

| Kind | Color | Pattern | Arrowhead |
|---|---|---|---|
| `supersedes` | red `#f87171` | solid | yes |
| `conflicts_with` | amber `#fbbf24` | dashed | no (symmetric) |
| `supports` | green `#4ade80` | solid | yes |
| `derived_from` | gray `#94a3b8` | solid | yes |
| `verified_by` | cyan `#67e8f9` | solid | yes |
| `invalidated_by` | red `#f87171` | dashed | yes |
| `reviewed` | gray `#94a3b8` | dotted | yes |

**Implementation risk on edge patterns.** Sigma v3's bundled edge programs cover solid lines and arrows; *dashed* and *dotted* require either a custom WebGL shader, a separate `@sigma/edge-*` plugin (each adds another vendored file), or a Canvas overlay. For the first iteration, the safe fallback is **solid edges with reduced opacity for "weak" kinds** (e.g. `reviewed` at 40% opacity, `derived_from` at 70%) and rely on color + arrow direction to disambiguate. Dashed/dotted patterns can land as a follow-up once we know which edge-program plugins are stable in Sigma 3.0.x. The plan should treat dashed/dotted as a stretch goal, not a release blocker.

### 6.5 Interactions

- **Hover node** → Sigma highlights the node + 1-hop neighbors via the `nodeReducer`/`edgeReducer` pattern; everything else dims to 20% opacity. Tooltip (HTML overlay, positioned by `sigma.viewportToGraph` math) shows `title` and `type` badge.
- **Single click node** → selects it. Side panel updates with the selected-node card. Camera animates to center it (`sigma.getCamera().animate({ x, y, ratio: 0.7 })`).
- **Double click node** → fetches `/api/graph?focus=<id>&depth=<state.depth>&layout=<state.layout>`, replaces the loaded graph, animates camera to the new center, and updates URL via `history.replaceState`.
- **Shift-click node** → navigates the browser to the typed detail page: `/memories/<id>`, `/runs/<id>`, `/retrievals/<id>`. Uses the existing detail routes already in `INDEX_HTML`.
- **Right-click node** → context menu (small custom HTML overlay) with: `Focus | Open detail | Expand neighborhood | Hide`. **Hide** is local-only: it adds the node ID to a `state.hidden` set so the node and its incident edges are excluded from rendering until the user clicks "Show all hidden" in the side panel or reloads the page. Hidden state is *not* persisted to the URL, server, or localStorage.
- **Scroll wheel** → zoom (Sigma default).
- **Drag empty space** → pan (Sigma default).
- **Mini-map** in bottom-right corner of the canvas. Implemented as a small second canvas (~150×100px) that listens to `cameraStateChanged` and re-paints a desaturated version of the graph with a viewport rectangle. ~30 lines of code.

### 6.6 URL state

Fully shareable URLs. Example:

```
/graph?focus=mem_abc&depth=2&layout=force&types=memory,review&edges=supersedes,conflicts_with
```

- `parseUrlState()` runs once at `mount()` time, before the first fetch.
- `pushUrlState()` runs after every state change that affects the rendered view, using `history.replaceState` (not `pushState` — we don't want a back-button entry per click).
- Unknown query params are ignored, not rejected.
- Empty filter sets are omitted from the URL to keep it short.

### 6.7 Empty and error states

- **Empty graph** (`/api/graph` returns `{nodes: []}`) → centered hint: *"No relations yet. Run consolidation to generate provenance edges."*
- **Network error** → red banner at the top of the side panel: *"Failed to load graph. Retry."* with a retry button.
- **Vendor script load failure** → fallback to the old JSON dump (`renderGraph()` catches the rejected promise from `loadScript` and re-renders the original `pretty(data.nodes)` view). This guarantees `/graph` is never *worse* than today even if `/static/` breaks.

## 7. Vendored asset tree

```
opendream/static/
├── graph.js                                  # our app code, ~700 lines
├── graph.css                                 # graph-specific overrides, ~50 lines
└── vendor/
    ├── README.md                             # source URLs, versions, refresh command
    ├── graphology.umd.min.js                 # 0.25.4, ~80 KB
    ├── graphology-layout-forceatlas2.min.js  # ~12 KB
    ├── sigma.min.js                          # 3.0.2, ~110 KB
    └── fa2-worker.js                         # FA2 webworker shim, same-origin
```

**Total vendored payload:** approximately 210 KB. All files are MIT-licensed.

Each vendored file gets a header comment of the form:

```js
// vendored from https://cdnjs.cloudflare.com/ajax/libs/sigma.js/3.0.2/sigma.min.js
// sha256: <hash>
// license: MIT
// last refreshed: 2026-04-10
```

`opendream/static/vendor/README.md` documents the source URL, version, license, and exact `curl` command used to fetch each file, so future updates are auditable and reproducible.

`THIRD_PARTY_NOTICES.md` at the repo root gets entries appended for `sigma.js` and `graphology` with their MIT license texts.

## 8. Testing

Existing test layout per `tests/AGENTS.md`. Three new test files:

### 8.1 `tests/test_observability_graph.py` (unit)

- `test_build_graph_with_depth_parameter` — depth=2 returns the 2-hop subgraph from the focus node.
- `test_layered_positions_assigns_topological_y_ranks` — a `supersedes` chain of 3 nodes produces strictly increasing Y values.
- `test_layered_positions_orders_within_rank_by_created_at` — two siblings at the same rank are ordered left-to-right by `created_at`.
- `test_layered_positions_handles_cycles_gracefully` — a 2-cycle in `derived_from` does not raise and assigns both nodes a rank.
- `test_build_graph_force_layout_omits_positions` — `layout="forceatlas2"` returns nodes without `x`/`y` keys.
- `test_build_graph_focus_with_no_neighbors` — an isolated focus node returns just itself, edges empty.
- `test_build_graph_unknown_layout_falls_back_to_hierarchical` — `layout="totally-fake"` doesn't crash.

### 8.2 `tests/test_webapp_static.py` (integration against `build_server`)

- `test_static_serves_vendored_sigma` — GET `/static/vendor/sigma.min.js` returns 200 with `Content-Type: application/javascript`.
- `test_static_refuses_path_traversal` — GET `/static/../webapp.py` returns 404 (and does not leak the file).
- `test_static_refuses_absolute_paths` — GET `/static//etc/passwd` returns 404.
- `test_static_sets_long_cache_header` — response includes `Cache-Control: public, max-age=86400`.
- `test_static_unknown_file_returns_404` — GET `/static/does-not-exist.js` returns 404.
- `test_static_serves_graph_js` — GET `/static/graph.js` returns 200 with the IIFE source.

### 8.3 `tests/test_webapp_graph_route.py` (end-to-end on `/api/graph`)

- `test_api_graph_accepts_depth_query_param` — `?depth=3` reaches `build_graph` with `depth=3`.
- `test_api_graph_accepts_layout_query_param` — `?layout=forceatlas2` produces nodes without positions.
- `test_api_graph_default_layout_includes_positions` — the default response has `x` and `y` per node.
- `test_graph_html_links_static_assets` — the `INDEX_HTML` substring contains the expected loader script tags.

### 8.4 Manual verification gate

UI correctness can't be unit-tested without a headless browser, which is out of scope. Instead, a documented checklist at `docs/runbooks/graph-explorer-verify.md` covering:

1. Load `/graph` with an empty memory store → see the empty-state hint.
2. Load `/graph` with a 5-node fixture → see hierarchical layout with edges colored per kind.
3. Load `/graph` with a 200-node fixture → smooth zoom/pan, no visible jank.
4. Hover a node → highlights neighbors, dims rest, tooltip shows.
5. Click a node → selects it in the side panel.
6. Double-click a node → URL updates, view re-centers, browser back-button does *not* unwind (using `replaceState`).
7. Shift-click a memory node → navigates to `/memories/<id>`.
8. Toggle layout: `Hierarchical ↔ Force` → animates between layouts.
9. Toggle a filter chip → matching nodes/edges fade.
10. Use the depth slider → graph re-fetches with new depth.
11. Copy the URL, open in a new tab → identical view loads.
12. Disable network → reload `/graph` → still works (vendored assets, cached `/api/graph` data — or empty state if cache is cold).
13. Break `/static/` (e.g., rename a vendor file) → fallback JSON dump renders.

The checklist is run before declaring the feature done and again before any release that touches `webapp.py` or `static/`.

**No JS unit tests.** That is the cost of staying buildless. The interesting logic (hierarchical layout) lives in Python, where it *is* tested.

## 9. Out of scope (YAGNI)

Called out so we don't drift later:

- ❌ No edge bundling — overkill at 200-node scale, expensive at 2000.
- ❌ No graph-wide search across the entire memory store — the search box filters only the loaded subgraph. Use `/memories?search=` for store-wide search.
- ❌ No graph editing (creating/deleting edges from the UI) — that lives in the CLI (`opendream relation add`, etc.).
- ❌ No saved views or bookmarks — URL sharing covers it.
- ❌ No collaborative cursors / multi-user — this is a local single-user dashboard.
- ❌ No mobile layout — not a mobile tool. Side panel collapses under 900px but the canvas remains desktop-first.
- ❌ No 3D rendering — the `3d-force-graph` library is cool but pulls ~600 KB of ThreeJS for ~zero analytical value at this scale.
- ❌ No JS unit tests — would require a build pipeline (jest/vitest) and a DOM shim. Manual checklist + Python-side unit tests of the layout algorithm cover the high-value logic.
- ❌ No WebGL fallback to Canvas if WebGL is unavailable — Sigma v3 is WebGL-only by design, and any browser shipped after 2018 supports WebGL. If a user lacks WebGL, the loader catches the Sigma init error and falls back to the legacy JSON dump (same path as the vendor-load failure handler).

## 10. References

**Library research (April 2026):**

- [Sigma.js GitHub](https://github.com/jacomyal/sigma.js) — v3.0.2, MIT, ~12k stars
- [Graphology](https://github.com/graphology/graphology) — v0.25.4, MIT, ~830 stars
- [Sigma.js official demo](https://www.sigmajs.org/) — dark theme, WebGL, scales smoothly
- [johnymontana/sigma-graph-examples](https://github.com/johnymontana/sigma-graph-examples) — Neo4j-style knowledge graph, observability simulations (the closest visual reference for our use case)
- [DEV.to: Graphology + Sigma.js exploration](https://dev.to/gabetronic/exploring-network-graph-visualization-graphology-and-sigmajs-5fcg)
- [Cytoscape.js](https://github.com/cytoscape/cytoscape.js) — v3.33.2, MIT, considered as the runner-up for its single-tag CDN story and built-in dagre layout, but rejected in favor of Sigma's WebGL ceiling and more modern look.

**Internal references:**

- `opendream/webapp.py:181-186` — current `renderGraph()` (the JSON dump being replaced)
- `opendream/webapp.py:436-437` — current `/api/graph` route
- `opendream/observability.py:67-84` — current `build_graph()` to be extended
- `opendream/relation_graph.py:17-24` — `RELATION_KINDS` frozen set (the seven edge kinds)
- `tests/AGENTS.md` — verification and fixture conventions

## 11. Open questions for the implementation plan

These are intentionally not resolved here — they belong in the writing-plans pass:

1. **Where do test fixtures (5-node and 200-node graphs) live?** — `tests/fixtures/graph/`? Generated programmatically? Need to match existing fixture conventions in `tests/`.
2. **Does the manual verification checklist run as part of `make verify`** (which would require a headless-browser harness, currently out of scope), or stay as a docs-only runbook?
3. **Refresh procedure for vendored JS** — manual `curl` commands documented in `vendor/README.md`, or a `make vendor-refresh` target? Probably docs-only for the first iteration; promote to a Make target only if the refresh proves recurring.
