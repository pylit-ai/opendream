# Graph Explorer — Manual Verification Runbook

This checklist verifies the `/graph` provenance explorer page after any change
to `opendream/webapp.py`, `opendream/observability.build_graph`, or anything
under `opendream/static/`. JavaScript correctness cannot be unit-tested in this
buildless setup, so this is the gate that catches UI regressions.

## Setup

1. From the repo root, start the local webapp against a workspace that has
   memories and relations:
   ```
   .venv/bin/python -m opendream.cli serve --workspace <path> --port 8765
   ```
   (Exact flag name may differ — check `opendream --help` for the current CLI.)
2. Open `http://127.0.0.1:8765/graph` in a modern browser (Chrome 120+ or
   Firefox 122+).
3. Open the browser dev tools → Network tab. Reload `/graph` and confirm that
   `/static/vendor/graphology.umd.min.js`,
   `/static/vendor/graphology-layout-forceatlas2.min.js`,
   `/static/vendor/sigma.min.js`, `/static/graph.js`, and `/static/graph.css`
   all return 200 with the right MIME types.

## Checklist

- [ ] **Empty store** — point the webapp at a freshly initialized workspace.
      `/graph` shows the centered "No relations to display" hint, no console
      errors.
- [ ] **Small fixture (5 nodes)** — load a workspace with the
      `tests/fixtures/graph_fixture.py::chain_fixture` shape. Hierarchical
      layout renders top-to-bottom (oldest ancestor at top). Edges colored per
      kind.
- [ ] **Medium fixture (~30 nodes, real memory store)** — seed a workspace via
      the integration test's `setUp` helper or a demo. Smooth pan/zoom, no
      visible jank.
- [ ] **Hover** — hovering a node highlights it and its 1-hop neighbors;
      non-neighbor nodes dim to dark grey with labels hidden. Tooltip shows
      title and type. Leaving the node restores original rendering.
- [ ] **Single click** — clicking a node updates the side panel "Selected"
      card with the node's title, type badge, raw JSON blob, and typed detail
      link (`Open detail →`).
- [ ] **Double click** — double-clicking a node refetches with that node as
      focus. URL updates to include `?focus=<id>`. Browser back-button does
      NOT unwind to the previous focus state (we use `replaceState`).
- [ ] **Shift-click memory** — shift-clicking a node of type `memory` navigates
      the browser to `/memories/<id>`. Similarly `run` → `/runs/<id>`,
      `retrieval` → `/retrievals/<id>`.
- [ ] **Layout toggle** — clicking `Force` in the side panel triggers
      ForceAtlas2 and the graph re-flows organically. Clicking `Hierarchical`
      snaps back to the Python-computed layered positions.
- [ ] **Depth slider** — clicking `0`, `1`, `2`, or `3` in the Depth segmented
      control re-fetches with the new depth. URL updates to `?depth=N`
      (the default `1` is omitted).
- [ ] **Node type chips** — clicking a node-type chip toggles a filter that
      hides/shows nodes of that type. The chip's `disabled` state reflects
      whether the type is currently active in the explicit allowlist.
- [ ] **Edge kind chips** — clicking an edge-kind chip toggles a filter that
      hides/shows edges of that kind. The chip doubles as a legend (its color
      matches the edge color in the canvas).
- [ ] **Search box** — typing into the search box hides nodes whose label
      does not contain the substring. Clearing the box restores all nodes.
- [ ] **Right-click context menu** — right-clicking a node shows a menu with
      `Focus here | Open detail | Expand neighborhood | Hide node`. Each
      action works. Clicking outside the menu dismisses it.
- [ ] **Hide and show** — clicking `Hide node` in the context menu removes the
      node and its incident edges from the rendered graph. A `Show N hidden`
      button appears in the side panel. Clicking it restores all hidden nodes.
- [ ] **URL share** — copy the address bar URL with non-default state set
      (e.g. `/graph?focus=<id>&depth=2&layout=force&types=memory,review`),
      open it in a new browser tab. The identical view loads.
- [ ] **Minimap** — the bottom-right minimap shows all nodes as small pixels
      and updates when the main camera pans or zooms.
- [ ] **Offline** — disable network in dev tools, reload `/graph`. Vendored
      assets come from the HTTP cache (they have `Cache-Control:
      public, max-age=86400`); the page still renders. If the `/api/graph`
      request fails, the error banner appears but the page does not crash.
- [ ] **Vendor failure fallback** — temporarily rename
      `opendream/static/vendor/sigma.min.js` (e.g. `mv sigma.min.js sigma.min.js.bak`)
      and reload `/graph`. The legacy JSON-dump view appears with a "fallback
      view — interactive renderer failed: ..." error message in the panel
      title. Restore the file when done.

## Sign-off

All boxes ticked → safe to merge / release. Attach the checklist (or a link
to it) to the PR description when the graph explorer code changes.
