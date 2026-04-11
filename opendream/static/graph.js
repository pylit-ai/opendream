// opendream/static/graph.js
// Provenance graph explorer for OpenDream observability.
// Loaded lazily by INDEX_HTML on /graph navigation.
(function () {
  'use strict';

  // ---- 1. State -----------------------------------------------------------
  const state = {
    focus: null,
    depth: 1,
    layout: 'hierarchical',
    filters: { nodeTypes: new Set(), edgeKinds: new Set() },
    hidden: new Set(),
    selected: null,
    sigma: null,        // sigma instance
    graph: null,        // graphology Graph instance
    raw: null,          // last /api/graph payload
    rootEl: null,
    canvasEl: null,
    sidepanelEl: null,
    tooltipEl: null,
  };

  // ---- 2. Theme -----------------------------------------------------------
  const THEME = {
    nodeColors: {
      memory:    '#67e8f9',
      review:    '#fbbf24',
      run:       '#4ade80',
      retrieval: '#94a3b8',
    },
    edgeColors: {
      supersedes:     '#f87171',
      conflicts_with: '#fbbf24',
      supports:       '#4ade80',
      derived_from:   '#94a3b8',
      verified_by:    '#67e8f9',
      invalidated_by: '#f87171',
      reviewed:       '#94a3b8',
    },
    edgeOpacity: {
      supersedes:     1.0,
      conflicts_with: 0.85,
      supports:       0.85,
      derived_from:   0.70,
      verified_by:    0.85,
      invalidated_by: 0.85,
      reviewed:       0.40,
    },
    nodeSize:      8,
    focusNodeSize: 14,
    fadedNodeSize: 4,
  };

  // ---- 3. Data layer ------------------------------------------------------
  async function fetchGraph() {
    const params = new URLSearchParams();
    if (state.focus) params.set('focus', state.focus);
    params.set('depth', String(state.depth));
    params.set('layout', state.layout);
    const url = '/api/graph?' + params.toString();
    const resp = await fetch(url);
    if (!resp.ok) throw new Error('graph fetch failed: ' + resp.status);
    state.raw = await resp.json();
    return state.raw;
  }

  function visibleNodes() {
    if (!state.raw) return [];
    return state.raw.nodes.filter(n => {
      if (state.hidden.has(n.id)) return false;
      if (state.filters.nodeTypes.size && !state.filters.nodeTypes.has(n.type)) return false;
      return true;
    });
  }

  function visibleEdges() {
    if (!state.raw) return [];
    const visibleIds = new Set(visibleNodes().map(n => n.id));
    return state.raw.edges.filter(e => {
      if (!visibleIds.has(e.source) || !visibleIds.has(e.target)) return false;
      if (state.filters.edgeKinds.size && !state.filters.edgeKinds.has(e.type)) return false;
      return true;
    });
  }

  // ---- 4. Render layer ----------------------------------------------------
  function buildGraphology() {
    const Graph = window.graphology.Graph || window.graphology;
    const g = new Graph({ type: 'directed', multi: true });
    for (const node of visibleNodes()) {
      const attrs = {
        label: node.title || node.id,
        size: (node.id === state.focus) ? THEME.focusNodeSize : THEME.nodeSize,
        color: THEME.nodeColors[node.type] || '#67e8f9',
        nodeType: node.type,
      };
      if (typeof node.x === 'number' && typeof node.y === 'number') {
        attrs.x = node.x;
        // Sigma's Y axis grows downward visually when negated; we want
        // higher rank => lower on screen, so invert the Python rank.
        attrs.y = -node.y;
      } else {
        attrs.x = Math.random();
        attrs.y = Math.random();
      }
      g.addNode(node.id, attrs);
    }
    for (const edge of visibleEdges()) {
      const key = edge.source + '->' + edge.target + ':' + edge.type;
      try {
        g.addEdgeWithKey(key, edge.source, edge.target, {
          edgeType: edge.type,
          color: THEME.edgeColors[edge.type] || '#94a3b8',
          size: 1.5,
          opacity: THEME.edgeOpacity[edge.type] ?? 0.85,
          type: 'arrow',
        });
      } catch (_e) { /* duplicate key or missing endpoint — ignore */ }
    }
    return g;
  }

  function initSigma() {
    if (state.sigma) {
      state.sigma.kill();
      state.sigma = null;
    }
    state.graph = buildGraphology();
    if (state.graph.order === 0) {
      state.canvasEl.innerHTML = '<div class="graph-empty">No relations to display.<br>Run consolidation to generate provenance edges,<br>or adjust your filters.</div>';
      return;
    }
    state.canvasEl.innerHTML = '';
    state.sigma = new window.Sigma(state.graph, state.canvasEl, {
      renderEdgeLabels: false,
      defaultEdgeColor: '#94a3b8',
      labelColor: { color: '#e2e8f0' },
      labelSize: 11,
      labelWeight: '500',
    });
  }

  async function refresh() {
    try {
      await fetchGraph();
      if (state.layout === 'forceatlas2') {
        state.canvasEl.innerHTML = '<div class="graph-empty">Computing layout…</div>';
        initSigma();
        runForceAtlas2();
      } else {
        initSigma();
      }
      renderSidePanel();
    } catch (err) {
      state.canvasEl.innerHTML = '<div class="graph-empty graph-error">Failed to load graph: ' + escapeHtml(err.message) + '</div>';
    }
  }

  function runForceAtlas2() {
    if (!state.graph || state.graph.order === 0) return;
    // NOTE: global is capitalized — matches the locally-built esbuild UMD
    // (the npm package ships CJS only, no prebuilt CDN UMD was available).
    const FA2 = window.GraphologyLayoutForceAtlas2;
    if (!FA2) return;
    // Seed with random positions if missing.
    state.graph.forEachNode((id, attrs) => {
      if (typeof attrs.x !== 'number') state.graph.setNodeAttribute(id, 'x', Math.random());
      if (typeof attrs.y !== 'number') state.graph.setNodeAttribute(id, 'y', Math.random());
    });
    FA2.assign(state.graph, { iterations: 200, settings: { gravity: 1, scalingRatio: 10 } });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  // ---- 5. UI chrome -------------------------------------------------------
  // (filled in Task 14)

  // ---- 6. Wiring ----------------------------------------------------------
  // (filled in Task 15)

  function parseUrlState() { /* filled in Task 16 */ }
  function pushUrlState() { /* filled in Task 16 */ }
  function renderSidePanel() {
    if (!state.sidepanelEl) return;
    state.sidepanelEl.innerHTML = '<div class="graph-empty">Side panel coming in Task 14.</div>';
  }

  function mount(rootEl) {
    state.rootEl = rootEl;
    rootEl.innerHTML = `
      <link rel="stylesheet" href="/static/graph.css">
      <div id="graph-sidepanel"><div class="graph-empty">Loading…</div></div>
      <div id="graph-canvas-wrap">
        <div id="graph-canvas"></div>
        <div id="graph-tooltip"></div>
        <canvas id="graph-minimap" width="320" height="200"></canvas>
      </div>`;
    state.sidepanelEl = rootEl.querySelector('#graph-sidepanel');
    state.canvasEl = rootEl.querySelector('#graph-canvas');
    state.tooltipEl = rootEl.querySelector('#graph-tooltip');
    parseUrlState();
    refresh();
  }

  window.__opendreamGraph = { mount, _state: state, _theme: THEME };
})();
