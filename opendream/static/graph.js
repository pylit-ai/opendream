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
    viewMode: 'canvas', // 'canvas' | 'data' — data = keyboard-friendly tables
    tableSearch: '', // substring filter for Graph data view (id/title)
    filters: { nodeTypes: new Set(), edgeKinds: new Set() },
    hidden: new Set(),
    selected: null,
    sigma: null,        // sigma instance
    graph: null,        // graphology Graph instance
    raw: null,          // last /api/graph payload
    rootEl: null,
    canvasWrapEl: null,
    canvasEl: null,
    dataPanelEl: null,
    dataTablesHostEl: null,
    sidepanelEl: null,
    tooltipEl: null,
  };

  function cssColor(prop, fallback) {
    try {
      const v = getComputedStyle(document.documentElement).getPropertyValue(prop).trim();
      return v || fallback;
    } catch (_e) {
      return fallback;
    }
  }

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
      defaultEdgeColor: cssColor('--muted', '#94a3b8'),
      labelColor: { color: cssColor('--text', '#eaeaea') },
      labelSize: 11,
      labelWeight: '500',
    });
  }

  function applyViewModeVisibility() {
    const wrap = state.canvasWrapEl;
    const panel = state.dataPanelEl;
    if (!wrap || !panel) return;
    if (state.viewMode === 'data') {
      wrap.setAttribute('aria-hidden', 'true');
      wrap.classList.add('graph-stage-hidden');
      panel.hidden = false;
      panel.removeAttribute('aria-hidden');
    } else {
      wrap.removeAttribute('aria-hidden');
      wrap.classList.remove('graph-stage-hidden');
      panel.hidden = true;
      panel.setAttribute('aria-hidden', 'true');
    }
  }

  function nodeDetailHref(node) {
    const detailRoutes = { memory: '/memories/', run: '/runs/', retrieval: '/retrievals/' };
    const base = detailRoutes[node.type];
    return base ? base + encodeURIComponent(node.id) : null;
  }

  function visibleNodesForDataView() {
    const base = visibleNodes();
    const q = (state.tableSearch || '').trim().toLowerCase();
    if (!q) return base;
    return base.filter((n) => {
      const id = String(n.id || '').toLowerCase();
      const title = String(n.title || '').toLowerCase();
      return id.includes(q) || title.includes(q);
    });
  }

  function visibleEdgesForDataView() {
    const ids = new Set(visibleNodesForDataView().map((n) => n.id));
    return visibleEdges().filter((e) => ids.has(e.source) && ids.has(e.target));
  }

  function renderDataTables() {
    const host = state.dataTablesHostEl;
    if (!host) return;
    const nodes = visibleNodesForDataView();
    const edges = visibleEdgesForDataView();
    if (!nodes.length && !edges.length) {
      host.innerHTML = '<p class="graph-empty" style="min-height:120px">No relations to display for the current filters. Adjust filters or run consolidation.</p>';
      return;
    }
    const nodeRows = nodes
      .slice()
      .sort((a, b) => String(a.id).localeCompare(String(b.id)))
      .map((n) => {
        const href = nodeDetailHref(n);
        const titleCell = href
          ? `<a href="${href}">${escapeHtml(n.title || n.id)}</a>`
          : escapeHtml(n.title || n.id);
        return `<tr><td><code>${escapeHtml(String(n.id))}</code></td><td>${escapeHtml(String(n.type || ''))}</td><td>${titleCell}</td></tr>`;
      })
      .join('');
    const nodeTable =
      '<table class="graph-data-table"><caption class="sr-only">Visible graph nodes</caption><thead><tr><th scope="col">ID</th><th scope="col">Type</th><th scope="col">Title</th></tr></thead><tbody>' +
      nodeRows +
      '</tbody></table>';
    const edgeRows = edges
      .map((e) => {
        const src = state.raw.nodes.find((n) => n.id === e.source);
        const tgt = state.raw.nodes.find((n) => n.id === e.target);
        const srcLink = src && nodeDetailHref(src) ? `<a href="${nodeDetailHref(src)}"><code>${escapeHtml(String(e.source))}</code></a>` : `<code>${escapeHtml(String(e.source))}</code>`;
        const tgtLink = tgt && nodeDetailHref(tgt) ? `<a href="${nodeDetailHref(tgt)}"><code>${escapeHtml(String(e.target))}</code></a>` : `<code>${escapeHtml(String(e.target))}</code>`;
        return `<tr><td>${srcLink}</td><td>${tgtLink}</td><td>${escapeHtml(String(e.type || ''))}</td></tr>`;
      })
      .join('');
    const edgeTable =
      '<h4 class="graph-data-heading">Edges</h4><table class="graph-data-table"><caption class="sr-only">Visible graph edges</caption><thead><tr><th scope="col">Source</th><th scope="col">Target</th><th scope="col">Kind</th></tr></thead><tbody>' +
      (edgeRows || '<tr><td colspan="3" class="muted">No edges</td></tr>') +
      '</tbody></table>';
    host.innerHTML = '<h4 class="graph-data-heading">Nodes</h4>' + nodeTable + edgeTable;
  }

  async function refresh() {
    try {
      await fetchGraph();
      if (state.viewMode === 'data') {
        if (state.sigma) {
          state.sigma.kill();
          state.sigma = null;
        }
        state.graph = null;
        applyViewModeVisibility();
        renderDataTables();
        renderSidePanel();
        return;
      }
      applyViewModeVisibility();
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
      const msg = escapeHtml(err.message);
      state.canvasEl.innerHTML = '<div class="graph-empty graph-error">Failed to load graph: ' + msg + '</div>';
      if (state.dataTablesHostEl) {
        state.dataTablesHostEl.innerHTML = '<p class="graph-empty graph-error">Failed to load graph: ' + msg + '</p>';
      }
      if (state.viewMode === 'data') applyViewModeVisibility();
      renderSidePanel();
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
    const searchPlaceholder =
      state.viewMode === 'data' ? 'Filter nodes by id or title' : 'Search visible nodes (canvas)';
    state.sidepanelEl.innerHTML = `
      <h3>View</h3>
      <div class="graph-segmented graph-view-toggle" role="group" aria-label="Graph view mode">
        <button type="button" data-view-mode="canvas" class="${state.viewMode === 'canvas' ? 'active' : ''}">Canvas</button>
        <button type="button" data-view-mode="data" class="${state.viewMode === 'data' ? 'active' : ''}">Graph data</button>
      </div>
      <details class="graph-shortcuts-help">
        <summary>Canvas shortcuts</summary>
        <ul class="graph-shortcuts-list">
          <li><strong>Graph data</strong> mode: use the tables for keyboard navigation and screen readers.</li>
          <li><strong>Double-click</strong> a node: set focus to that node (narrow the neighborhood).</li>
          <li><strong>Shift+click</strong> a node: open its detail page (memory, run, or retrieval).</li>
          <li><strong>Right-click</strong> a node: context menu (focus, open detail, expand neighborhood, hide node).</li>
        </ul>
      </details>

      <h3>Focus</h3>
      <div>${escapeHtml(focusLabel)}</div>
      <input id="graph-search" class="graph-search" value="${escapeHtml(state.tableSearch)}" placeholder="${escapeHtml(searchPlaceholder)}">

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
      <pre class="graph-json-pre">${escapeHtml(JSON.stringify(node, null, 2))}</pre>
      ${detailLinkFor(node)}
    `;
  }

  function detailLinkFor(node) {
    const detailRoutes = { memory: '/memories/', run: '/runs/', retrieval: '/retrievals/' };
    const base = detailRoutes[node.type];
    if (!base) return '';
    return `<a class="graph-detail-link" href="${base}${encodeURIComponent(node.id)}">Open detail →</a>`;
  }

  function wireSidePanelEvents() {
    state.sidepanelEl.querySelectorAll('[data-view-mode]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const v = btn.getAttribute('data-view-mode');
        if (v !== 'canvas' && v !== 'data') return;
        if (v === state.viewMode) return;
        state.viewMode = v;
        if (v === 'canvas') state.tableSearch = '';
        pushUrlState();
        void refresh();
      });
    });
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
        if (state.viewMode === 'data') {
          renderDataTables();
        } else {
          initSigma();
          wireSigmaEvents();
        }
      });
    });
    // Edge kind chips
    state.sidepanelEl.querySelectorAll('[data-edge-kind]').forEach(chip => {
      chip.addEventListener('click', () => {
        const k = chip.dataset.edgeKind;
        toggleSetMember(state.filters.edgeKinds, k);
        pushUrlState();
        renderSidePanel();
        if (state.viewMode === 'data') {
          renderDataTables();
        } else {
          initSigma();
          wireSigmaEvents();
        }
      });
    });
    // Search box
    const search = state.sidepanelEl.querySelector('#graph-search');
    if (search) search.addEventListener('input', e => {
      const q = e.target.value;
      if (state.viewMode === 'data') {
        state.tableSearch = q;
        renderDataTables();
        return;
      }
      const ql = q.toLowerCase();
      if (!state.sigma) return;
      state.sigma.setSetting('nodeReducer', (id, attrs) => {
        const visible = !ql || (attrs.label || '').toLowerCase().includes(ql);
        return visible ? attrs : { ...attrs, hidden: true };
      });
      state.sigma.refresh();
    });
    // Show hidden
    const showHidden = state.sidepanelEl.querySelector('#graph-show-hidden');
    if (showHidden) showHidden.addEventListener('click', () => {
      state.hidden.clear();
      renderSidePanel();
      if (state.viewMode === 'data') {
        renderDataTables();
      } else {
        initSigma();
        wireSigmaEvents();
      }
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
    menu.className = 'graph-ctx-menu';
    menu.style.left = clientX + 'px';
    menu.style.top = clientY + 'px';
    // Unified close path — item clicks AND outside clicks both route through
    // here so the document-level dismiss listener is always removed exactly
    // once (previously an item click removed the menu but leaked the listener
    // until the next stray outside click).
    let dismiss;
    const closeMenu = () => {
      menu.remove();
      if (dismiss) document.removeEventListener('click', dismiss);
    };
    dismiss = (e) => { if (!menu.contains(e.target)) closeMenu(); };
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
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = item.label;
      btn.addEventListener('click', () => { item.action(); closeMenu(); });
      menu.appendChild(btn);
    }
    document.body.appendChild(menu);
    setTimeout(() => document.addEventListener('click', dismiss), 0);
  }

  function updateMinimap() {
    const canvas = document.getElementById('graph-minimap');
    if (!canvas || !state.sigma || !state.graph) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = cssColor('--rail-bg', 'rgba(15,17,20,0.85)');
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

  function parseUrlState() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('focus')) state.focus = params.get('focus');
    if (params.has('depth')) state.depth = Math.max(0, Math.min(3, Number(params.get('depth')) || 1));
    if (params.has('layout')) state.layout = params.get('layout');
    if (params.has('types')) {
      state.filters.nodeTypes = new Set(params.get('types').split(',').filter(Boolean));
    }
    if (params.has('edges')) {
      state.filters.edgeKinds = new Set(params.get('edges').split(',').filter(Boolean));
    }
    const view = (params.get('view') || '').toLowerCase();
    if (view === 'data') state.viewMode = 'data';
    else state.viewMode = 'canvas';
  }

  function pushUrlState() {
    const params = new URLSearchParams();
    if (state.focus) params.set('focus', state.focus);
    if (state.depth !== 1) params.set('depth', String(state.depth));
    if (state.layout !== 'hierarchical') params.set('layout', state.layout);
    if (state.filters.nodeTypes.size) params.set('types', Array.from(state.filters.nodeTypes).join(','));
    if (state.filters.edgeKinds.size) params.set('edges', Array.from(state.filters.edgeKinds).join(','));
    if (state.viewMode === 'data') params.set('view', 'data');
    const qs = params.toString();
    const newUrl = '/graph' + (qs ? '?' + qs : '');
    window.history.replaceState({}, '', newUrl);
  }

  function mount(rootEl) {
    state.rootEl = rootEl;
    rootEl.innerHTML = `
      <link rel="stylesheet" href="/static/graph.css">
      <div class="od-graph-a11y-banner" role="region" aria-label="Graph view accessibility">
        <p class="od-graph-a11y-banner__p">
          The canvas is a <strong>visual</strong> view. For keyboard navigation and screen readers, use
          <strong>Graph data</strong> in the side panel, or
          <a href="#" id="od-graph-open-data">switch to tables now</a>
          (same as <code>?view=data</code> in the URL).
        </p>
      </div>
      <div id="graph-sidepanel"><div class="graph-empty">Loading…</div></div>
      <div id="graph-main-stage" class="graph-main-stage">
        <div id="graph-canvas-wrap">
          <div id="graph-canvas"></div>
          <div id="graph-tooltip"></div>
          <canvas id="graph-minimap" width="320" height="200" aria-hidden="true"></canvas>
        </div>
        <div id="graph-data-panel" class="graph-data-panel" hidden aria-hidden="true">
          <div id="graph-data-tables-host" class="graph-data-tables-host"></div>
        </div>
      </div>`;
    state.sidepanelEl = rootEl.querySelector('#graph-sidepanel');
    state.canvasWrapEl = rootEl.querySelector('#graph-canvas-wrap');
    state.canvasEl = rootEl.querySelector('#graph-canvas');
    state.dataPanelEl = rootEl.querySelector('#graph-data-panel');
    state.dataTablesHostEl = rootEl.querySelector('#graph-data-tables-host');
    state.tooltipEl = rootEl.querySelector('#graph-tooltip');
    var openData = rootEl.querySelector('#od-graph-open-data');
    if (openData) {
      openData.addEventListener('click', function (ev) {
        ev.preventDefault();
        var p = new URLSearchParams(window.location.search);
        p.set('view', 'data');
        window.history.replaceState({}, '', '/graph?' + p.toString());
        parseUrlState();
        void refresh();
      });
    }
    parseUrlState();
    void refresh();
  }

  window.__opendreamGraph = { mount, _state: state, _theme: THEME };
})();
