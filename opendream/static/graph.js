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
      wireSigmaEvents();
      updateMinimap();
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
  const NODE_TYPES = ['memory', 'review', 'run', 'retrieval'];
  const EDGE_KINDS = ['supersedes', 'conflicts_with', 'supports', 'derived_from', 'verified_by', 'invalidated_by', 'reviewed'];

  function renderSidePanel() {
    const focusLabel = state.focus
      ? ((state.raw && state.raw.nodes.find(n => n.id === state.focus)?.title) || state.focus)
      : 'all memories';
    const nodeTypeChips = NODE_TYPES.map(t => {
      const enabled = state.filters.nodeTypes.size === 0 || state.filters.nodeTypes.has(t);
      const color = THEME.nodeColors[t];
      return `<span class="graph-chip ${enabled ? '' : 'disabled'}" data-node-type="${t}" style="background:${color};color:#0b1020;">${t}</span>`;
    }).join('');
    const edgeKindChips = EDGE_KINDS.map(k => {
      const enabled = state.filters.edgeKinds.size === 0 || state.filters.edgeKinds.has(k);
      const color = THEME.edgeColors[k];
      return `<span class="graph-chip ${enabled ? '' : 'disabled'}" data-edge-kind="${k}" style="background:${color};color:#0b1020;">${k}</span>`;
    }).join('');
    const selectedHtml = state.selected ? renderSelectedCard(state.selected) : '';
    const hiddenCount = state.hidden.size;
    state.sidepanelEl.innerHTML = `
      <h3>Focus</h3>
      <div>${escapeHtml(focusLabel)}</div>
      <input id="graph-search" placeholder="search visible nodes" style="width:100%;margin-top:8px;background:#0f1630;border:1px solid rgba(255,255,255,0.12);color:#e2e8f0;border-radius:8px;padding:6px 10px;">

      <h3>Layout</h3>
      <div class="graph-segmented">
        <button data-layout="hierarchical" class="${state.layout==='hierarchical'?'active':''}">Hierarchical</button>
        <button data-layout="forceatlas2" class="${state.layout==='forceatlas2'?'active':''}">Force</button>
      </div>

      <h3>Depth</h3>
      <div class="graph-segmented">
        ${[0,1,2,3].map(d => `<button data-depth="${d}" class="${state.depth===d?'active':''}">${d}</button>`).join('')}
      </div>

      <h3>Node types</h3>
      <div>${nodeTypeChips}</div>

      <h3>Edge kinds (legend)</h3>
      <div>${edgeKindChips}</div>

      ${hiddenCount ? `<h3>Hidden</h3><button id="graph-show-hidden">Show ${hiddenCount} hidden</button>` : ''}

      ${selectedHtml}
    `;
    wireSidePanelEvents();
  }

  function renderSelectedCard(node) {
    return `
      <h3>Selected</h3>
      <div><strong>${escapeHtml(node.title || node.id)}</strong>
        <span class="graph-chip" style="background:${THEME.nodeColors[node.type]};color:#0b1020;">${node.type}</span>
      </div>
      <pre style="background:#0a1128;padding:8px;border-radius:8px;max-height:200px;overflow:auto;font-size:11px;margin-top:8px;">${escapeHtml(JSON.stringify(node, null, 2))}</pre>
      ${detailLinkFor(node)}
    `;
  }

  function detailLinkFor(node) {
    const detailRoutes = { memory: '/memories/', run: '/runs/', retrieval: '/retrievals/' };
    const base = detailRoutes[node.type];
    if (!base) return '';
    return `<a href="${base}${encodeURIComponent(node.id)}" style="color:#67e8f9;">Open detail →</a>`;
  }

  function wireSidePanelEvents() {
    // Layout toggle
    state.sidepanelEl.querySelectorAll('[data-layout]').forEach(btn => {
      btn.addEventListener('click', () => {
        state.layout = btn.dataset.layout;
        pushUrlState();
        refresh();
      });
    });
    // Depth toggle
    state.sidepanelEl.querySelectorAll('[data-depth]').forEach(btn => {
      btn.addEventListener('click', () => {
        state.depth = Number(btn.dataset.depth);
        pushUrlState();
        refresh();
      });
    });
    // Node type chips
    state.sidepanelEl.querySelectorAll('[data-node-type]').forEach(chip => {
      chip.addEventListener('click', () => {
        const t = chip.dataset.nodeType;
        toggleSetMember(state.filters.nodeTypes, t);
        pushUrlState();
        renderSidePanel();
        initSigma();
        wireSigmaEvents();
      });
    });
    // Edge kind chips
    state.sidepanelEl.querySelectorAll('[data-edge-kind]').forEach(chip => {
      chip.addEventListener('click', () => {
        const k = chip.dataset.edgeKind;
        toggleSetMember(state.filters.edgeKinds, k);
        pushUrlState();
        renderSidePanel();
        initSigma();
        wireSigmaEvents();
      });
    });
    // Search box
    const search = state.sidepanelEl.querySelector('#graph-search');
    if (search) search.addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      if (!state.sigma) return;
      state.sigma.setSetting('nodeReducer', (id, attrs) => {
        const visible = !q || (attrs.label || '').toLowerCase().includes(q);
        return visible ? attrs : { ...attrs, hidden: true };
      });
      state.sigma.refresh();
    });
    // Show hidden
    const showHidden = state.sidepanelEl.querySelector('#graph-show-hidden');
    if (showHidden) showHidden.addEventListener('click', () => {
      state.hidden.clear();
      renderSidePanel();
      initSigma();
      wireSigmaEvents();
    });
  }

  function toggleSetMember(set, value) {
    // Explicit-allowlist filter semantics: empty set = all visible;
    // clicking a chip toggles its presence in the set. First click on any chip
    // switches from "all visible" to "only this one visible"; clicking again
    // removes it (back to empty = all visible).
    if (set.has(value)) set.delete(value);
    else set.add(value);
  }

  // ---- 6. Wiring ----------------------------------------------------------
  function wireSigmaEvents() {
    if (!state.sigma) return;
    const sigma = state.sigma;

    sigma.on('enterNode', ({ node }) => {
      const attrs = state.graph.getNodeAttributes(node);
      const { x, y } = sigma.graphToViewport({ x: attrs.x, y: attrs.y });
      state.tooltipEl.innerHTML = `<strong>${escapeHtml(attrs.label)}</strong><br><span style="color:#94a3b8;">${attrs.nodeType}</span>`;
      state.tooltipEl.style.left = (x + 12) + 'px';
      state.tooltipEl.style.top = (y + 12) + 'px';
      state.tooltipEl.style.display = 'block';
      // Highlight neighbors
      const neighbors = new Set([node, ...state.graph.neighbors(node)]);
      sigma.setSetting('nodeReducer', (id, a) => neighbors.has(id) ? a : { ...a, color: '#3a4570', label: '' });
      sigma.setSetting('edgeReducer', (id, a) => {
        const [s, t] = state.graph.extremities(id);
        return neighbors.has(s) && neighbors.has(t) ? a : { ...a, hidden: true };
      });
      sigma.refresh();
    });

    sigma.on('leaveNode', () => {
      state.tooltipEl.style.display = 'none';
      sigma.setSetting('nodeReducer', null);
      sigma.setSetting('edgeReducer', null);
      sigma.refresh();
    });

    sigma.on('clickNode', ({ node, event }) => {
      const original = event && event.original;
      const raw = state.raw && state.raw.nodes.find(n => n.id === node);
      if (!raw) return;
      if (original && original.shiftKey) {
        const route = { memory: '/memories/', run: '/runs/', retrieval: '/retrievals/' }[raw.type];
        if (route) { window.location.href = route + encodeURIComponent(node); return; }
      }
      state.selected = raw;
      renderSidePanel();
    });

    sigma.on('doubleClickNode', ({ node, event }) => {
      if (event && typeof event.preventSigmaDefault === 'function') event.preventSigmaDefault();
      state.focus = node;
      pushUrlState();
      refresh();
    });

    sigma.on('rightClickNode', ({ node, event }) => {
      if (event && typeof event.preventSigmaDefault === 'function') event.preventSigmaDefault();
      const original = event && event.original;
      const cx = original ? original.clientX : 100;
      const cy = original ? original.clientY : 100;
      showContextMenu(node, cx, cy);
    });

    sigma.getCamera().on('updated', updateMinimap);
  }

  function showContextMenu(nodeId, clientX, clientY) {
    const existing = document.getElementById('graph-ctx-menu');
    if (existing) existing.remove();
    const menu = document.createElement('div');
    menu.id = 'graph-ctx-menu';
    menu.style.cssText = `position:fixed;left:${clientX}px;top:${clientY}px;background:#0f1630;border:1px solid rgba(255,255,255,0.18);border-radius:8px;padding:4px 0;z-index:1000;font-size:12px;`;
    const items = [
      { label: 'Focus here', action: () => { state.focus = nodeId; pushUrlState(); refresh(); } },
      { label: 'Open detail', action: () => {
          const raw = state.raw && state.raw.nodes.find(n => n.id === nodeId);
          if (!raw) return;
          const route = { memory: '/memories/', run: '/runs/', retrieval: '/retrievals/' }[raw.type];
          if (route) window.location.href = route + encodeURIComponent(nodeId);
        }
      },
      { label: 'Expand neighborhood', action: () => { state.depth = Math.min(state.depth + 1, 3); pushUrlState(); refresh(); } },
      { label: 'Hide node', action: () => { state.hidden.add(nodeId); renderSidePanel(); initSigma(); wireSigmaEvents(); } },
    ];
    for (const item of items) {
      const btn = document.createElement('div');
      btn.textContent = item.label;
      btn.style.cssText = 'padding:6px 14px;cursor:pointer;color:#e2e8f0;';
      btn.addEventListener('mouseenter', () => btn.style.background = 'rgba(103,232,249,0.12)');
      btn.addEventListener('mouseleave', () => btn.style.background = '');
      btn.addEventListener('click', () => { item.action(); menu.remove(); });
      menu.appendChild(btn);
    }
    document.body.appendChild(menu);
    setTimeout(() => {
      const dismiss = (e) => { if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('click', dismiss); } };
      document.addEventListener('click', dismiss);
    }, 0);
  }

  function updateMinimap() {
    const canvas = document.getElementById('graph-minimap');
    if (!canvas || !state.sigma || !state.graph) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'rgba(11,16,32,0.7)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    state.graph.forEachNode((_id, a) => {
      if (a.x < minX) minX = a.x; if (a.x > maxX) maxX = a.x;
      if (a.y < minY) minY = a.y; if (a.y > maxY) maxY = a.y;
    });
    const w = (maxX - minX) || 1;
    const h = (maxY - minY) || 1;
    state.graph.forEachNode((_id, a) => {
      const px = ((a.x - minX) / w) * (canvas.width - 8) + 4;
      const py = ((a.y - minY) / h) * (canvas.height - 8) + 4;
      ctx.fillStyle = a.color || '#67e8f9';
      ctx.fillRect(px - 1, py - 1, 2, 2);
    });
  }

  function parseUrlState() { /* filled in Task 16 */ }
  function pushUrlState() { /* filled in Task 16 */ }

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
