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
  // (filled in Task 12)

  // ---- 4. Render layer ----------------------------------------------------
  // (filled in Task 13)

  // ---- 5. UI chrome -------------------------------------------------------
  // (filled in Task 14)

  // ---- 6. Wiring ----------------------------------------------------------
  // (filled in Task 15)

  function mount(rootEl) {
    state.rootEl = rootEl;
    rootEl.innerHTML = `
      <link rel="stylesheet" href="/static/graph.css">
      <div id="graph-sidepanel">
        <div class="graph-empty">Loading…</div>
      </div>
      <div id="graph-canvas-wrap">
        <div id="graph-canvas"></div>
        <div id="graph-tooltip"></div>
        <canvas id="graph-minimap" width="320" height="200"></canvas>
      </div>`;
    state.sidepanelEl = rootEl.querySelector('#graph-sidepanel');
    state.canvasEl = rootEl.querySelector('#graph-canvas');
    state.tooltipEl = rootEl.querySelector('#graph-tooltip');
  }

  window.__opendreamGraph = { mount, _state: state, _theme: THEME };
})();
