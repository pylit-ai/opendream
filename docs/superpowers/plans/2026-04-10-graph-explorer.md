# Graph Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the JSON-dump `/graph` page in `opendream/webapp.py` with a beautiful, interactive provenance explorer powered by Sigma.js v3 + Graphology, vendored under `opendream/static/`.

**Architecture:** Three layers. (1) Backend extends `observability.build_graph()` with `depth` + `layout` params and computes Python-side hierarchical positions. (2) `webapp.py` gains a `/static/<path>` route that serves vendored JS/CSS plus our own `graph.js`. (3) Frontend is a single IIFE-wrapped `graph.js` file with six logical units (state, theme, data, render, UI chrome, wiring) lazy-loaded only on `/graph`.

**Tech Stack:** Python stdlib `http.server`, Sigma.js v3.0.2, Graphology 0.25.4, graphology-layout-forceatlas2, pure vanilla JS, `unittest` for Python tests.

**Source spec:** `docs/superpowers/specs/2026-04-10-graph-explorer-design.md`

---

## File map

**Created:**
- `opendream/static/vendor/sigma.min.js` (vendored, ~110 KB)
- `opendream/static/vendor/graphology.umd.min.js` (vendored, ~80 KB)
- `opendream/static/vendor/graphology-layout-forceatlas2.min.js` (vendored, ~12 KB)
- `opendream/static/vendor/README.md` (refresh procedure)
- `opendream/static/graph.js` (~700 lines, IIFE)
- `opendream/static/graph.css` (~50 lines)
- `tests/test_observability_graph.py`
- `tests/test_webapp_static.py`
- `tests/test_webapp_graph_route.py`
- `tests/fixtures/graph_fixture.py` (fixture builders for unit tests)
- `docs/runbooks/graph-explorer-verify.md`

**Modified:**
- `opendream/observability.py` — extend `build_graph()` (~50 lines added near line 67)
- `opendream/webapp.py` — add `_serve_static`, extend `do_GET`, extend `_handle_api_get` graph branch, replace `renderGraph()` JS in `INDEX_HTML` (~30 lines net change)
- `THIRD_PARTY_NOTICES.md` — append sigma.js + graphology MIT notices

---

## Phase 1 — Backend foundation (TDD)

### Task 1: Create graph fixture builder

**Files:**
- Create: `tests/fixtures/graph_fixture.py`

- [ ] **Step 1: Write the fixture module**

```python
# tests/fixtures/graph_fixture.py
"""Fixture builders for graph-related tests.

Each builder returns a dict shaped like ``index['entities']['graph']``:
``{"nodes": [{"id": str, "type": str, "title": str, ...}], "edges": [...]}``.
"""
from __future__ import annotations


def chain_fixture() -> dict:
    """Linear supersession chain: A -> B -> C (B supersedes A, C supersedes B)."""
    return {
        "nodes": [
            {"id": "A", "type": "memory", "title": "memory A", "created_at": "2026-01-01"},
            {"id": "B", "type": "memory", "title": "memory B", "created_at": "2026-01-02"},
            {"id": "C", "type": "memory", "title": "memory C", "created_at": "2026-01-03"},
        ],
        "edges": [
            {"source": "B", "target": "A", "type": "supersedes"},
            {"source": "C", "target": "B", "type": "supersedes"},
        ],
    }


def cycle_fixture() -> dict:
    """A 2-cycle in derived_from: A derived_from B, B derived_from A."""
    return {
        "nodes": [
            {"id": "A", "type": "memory", "title": "A", "created_at": "2026-01-01"},
            {"id": "B", "type": "memory", "title": "B", "created_at": "2026-01-02"},
        ],
        "edges": [
            {"source": "A", "target": "B", "type": "derived_from"},
            {"source": "B", "target": "A", "type": "derived_from"},
        ],
    }


def hub_fixture() -> dict:
    """One hub node H with three leaves L1/L2/L3 derived from it."""
    return {
        "nodes": [
            {"id": "H", "type": "memory", "title": "hub", "created_at": "2026-01-01"},
            {"id": "L1", "type": "memory", "title": "leaf 1", "created_at": "2026-01-02"},
            {"id": "L2", "type": "memory", "title": "leaf 2", "created_at": "2026-01-03"},
            {"id": "L3", "type": "memory", "title": "leaf 3", "created_at": "2026-01-04"},
        ],
        "edges": [
            {"source": "L1", "target": "H", "type": "derived_from"},
            {"source": "L2", "target": "H", "type": "derived_from"},
            {"source": "L3", "target": "H", "type": "derived_from"},
        ],
    }


def isolated_fixture() -> dict:
    """One node, no edges."""
    return {
        "nodes": [{"id": "X", "type": "memory", "title": "isolated", "created_at": "2026-01-01"}],
        "edges": [],
    }


def index_with(graph: dict) -> dict:
    """Wrap a graph dict in an ``index`` shape that ``build_graph`` accepts."""
    return {"entities": {"graph": graph}}
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/graph_fixture.py
git commit -m "test(graph): add fixture builders for hierarchical layout tests"
```

---

### Task 2: `_layered_positions` — happy path

**Files:**
- Create: `tests/test_observability_graph.py`
- Modify: `opendream/observability.py` (add `_layered_positions` near `build_graph`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_observability_graph.py
from __future__ import annotations

import unittest

from opendream.observability import _layered_positions, build_graph
from tests.fixtures.graph_fixture import (
    chain_fixture,
    cycle_fixture,
    hub_fixture,
    index_with,
    isolated_fixture,
)


class LayeredPositionsTests(unittest.TestCase):
    def test_chain_assigns_strictly_increasing_y(self) -> None:
        graph = chain_fixture()
        positions = _layered_positions(graph["nodes"], graph["edges"])
        y_a = positions["A"][1]
        y_b = positions["B"][1]
        y_c = positions["C"][1]
        # B supersedes A so B is "deeper" (higher Y); same for C over B.
        self.assertLess(y_a, y_b)
        self.assertLess(y_b, y_c)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_observability_graph.py::LayeredPositionsTests::test_chain_assigns_strictly_increasing_y -v`
Expected: `ImportError: cannot import name '_layered_positions' from 'opendream.observability'`

- [ ] **Step 3: Implement `_layered_positions`**

Add to `opendream/observability.py` immediately above `build_graph` (around line 65):

```python
_LAYOUT_RANK_EDGE_KINDS = frozenset({"supersedes", "derived_from"})


def _layered_positions(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, tuple[float, float]]:
    """Topologically rank nodes by supersedes/derived_from edges.

    Y is the rank (top-down: rank 0 is the oldest ancestor). X orders siblings
    within a rank by ``created_at`` (or ``id`` as fallback). Cycles short-circuit
    to a stable fallback rank rather than raising.
    """
    node_ids = [node["id"] for node in nodes]
    id_set = set(node_ids)
    parents: dict[str, set[str]] = {nid: set() for nid in node_ids}
    children: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for edge in edges:
        if edge.get("type") not in _LAYOUT_RANK_EDGE_KINDS:
            continue
        src = edge["source"]
        tgt = edge["target"]
        if src not in id_set or tgt not in id_set:
            continue
        # ``B supersedes A`` means B is deeper than A => parent edge A -> B.
        parents[src].add(tgt)
        children[tgt].add(src)

    rank: dict[str, int] = {}
    queue = [nid for nid in node_ids if not children[nid]]
    while queue:
        next_queue: list[str] = []
        for nid in queue:
            parent_ranks = [rank[p] for p in children[nid] if p in rank]
            rank[nid] = max(parent_ranks) + 1 if parent_ranks else 0
            for child in parents[nid]:
                if all(p in rank for p in children[child]):
                    next_queue.append(child)
        queue = next_queue

    # Cycle break: any node not yet ranked goes to max_rank + 1.
    if any(nid not in rank for nid in node_ids):
        fallback = max(rank.values(), default=-1) + 1
        for nid in node_ids:
            rank.setdefault(nid, fallback)

    by_rank: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_rank.setdefault(rank[node["id"]], []).append(node)

    positions: dict[str, tuple[float, float]] = {}
    for r, group in by_rank.items():
        group.sort(key=lambda n: (str(n.get("created_at") or ""), n["id"]))
        for i, node in enumerate(group):
            x = float(i) - (len(group) - 1) / 2.0
            positions[node["id"]] = (x, float(r))
    return positions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_observability_graph.py::LayeredPositionsTests::test_chain_assigns_strictly_increasing_y -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add opendream/observability.py tests/test_observability_graph.py
git commit -m "feat(graph): add _layered_positions topological rank assignment"
```

---

### Task 3: `_layered_positions` — sibling ordering, cycles, isolated

**Files:**
- Modify: `tests/test_observability_graph.py`

- [ ] **Step 1: Add three more failing tests**

Append to `LayeredPositionsTests`:

```python
    def test_siblings_at_same_rank_ordered_by_created_at(self) -> None:
        graph = hub_fixture()
        positions = _layered_positions(graph["nodes"], graph["edges"])
        # H is the parent (rank 0); L1/L2/L3 are siblings at rank 1.
        self.assertEqual(positions["H"][1], 0.0)
        self.assertEqual(positions["L1"][1], 1.0)
        self.assertEqual(positions["L2"][1], 1.0)
        self.assertEqual(positions["L3"][1], 1.0)
        # Created in order L1 < L2 < L3 => x increasing.
        self.assertLess(positions["L1"][0], positions["L2"][0])
        self.assertLess(positions["L2"][0], positions["L3"][0])

    def test_cycle_does_not_raise_and_assigns_all_nodes(self) -> None:
        graph = cycle_fixture()
        positions = _layered_positions(graph["nodes"], graph["edges"])
        self.assertIn("A", positions)
        self.assertIn("B", positions)

    def test_isolated_node_gets_position(self) -> None:
        graph = isolated_fixture()
        positions = _layered_positions(graph["nodes"], graph["edges"])
        self.assertEqual(positions["X"], (0.0, 0.0))
```

- [ ] **Step 2: Run all three to confirm they pass**

Run: `python -m pytest tests/test_observability_graph.py::LayeredPositionsTests -v`
Expected: 4 PASS

(They should pass on the first try because the implementation in Task 2 already handles all three cases. If any fail, fix `_layered_positions` and re-run.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_observability_graph.py
git commit -m "test(graph): cover siblings, cycles, and isolated nodes in layered positions"
```

---

### Task 4: `_select_subgraph` BFS by depth

**Files:**
- Modify: `tests/test_observability_graph.py`
- Modify: `opendream/observability.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_observability_graph.py`:

```python
from opendream.observability import _select_subgraph


class SelectSubgraphTests(unittest.TestCase):
    def test_no_focus_returns_first_limit_nodes(self) -> None:
        graph = chain_fixture()
        nodes, edges = _select_subgraph(graph, focus=None, limit=2, depth=1)
        self.assertEqual(len(nodes), 2)
        # Edges trimmed to those between selected nodes.
        for edge in edges:
            self.assertIn(edge["source"], {n["id"] for n in nodes})
            self.assertIn(edge["target"], {n["id"] for n in nodes})

    def test_focus_depth_1_returns_focus_plus_one_hop(self) -> None:
        graph = hub_fixture()
        nodes, _edges = _select_subgraph(graph, focus="H", limit=24, depth=1)
        ids = {n["id"] for n in nodes}
        self.assertEqual(ids, {"H", "L1", "L2", "L3"})

    def test_focus_depth_0_returns_only_focus(self) -> None:
        graph = hub_fixture()
        nodes, _edges = _select_subgraph(graph, focus="H", limit=24, depth=0)
        self.assertEqual([n["id"] for n in nodes], ["H"])

    def test_focus_with_unknown_id_returns_empty(self) -> None:
        graph = hub_fixture()
        nodes, edges = _select_subgraph(graph, focus="ZZZ", limit=24, depth=1)
        self.assertEqual(nodes, [])
        self.assertEqual(edges, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_observability_graph.py::SelectSubgraphTests -v`
Expected: `ImportError: cannot import name '_select_subgraph'`

- [ ] **Step 3: Implement `_select_subgraph`**

Add to `opendream/observability.py` immediately above `_layered_positions`:

```python
def _select_subgraph(
    graph: dict[str, Any],
    *,
    focus: str | None,
    limit: int,
    depth: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """BFS up to ``depth`` hops from ``focus``, capped at ``limit`` nodes.

    If ``focus`` is None, returns the first ``limit`` nodes from the graph.
    If ``focus`` is unknown, returns ``([], [])``.
    """
    all_nodes = graph.get("nodes", [])
    all_edges = graph.get("edges", [])
    by_id = {n["id"]: n for n in all_nodes}

    if focus is None:
        selected = all_nodes[:limit]
        ids = {n["id"] for n in selected}
        edges = [e for e in all_edges if e["source"] in ids and e["target"] in ids]
        return list(selected), edges

    if focus not in by_id:
        return [], []

    adjacency: dict[str, set[str]] = {nid: set() for nid in by_id}
    for edge in all_edges:
        if edge["source"] in by_id and edge["target"] in by_id:
            adjacency[edge["source"]].add(edge["target"])
            adjacency[edge["target"]].add(edge["source"])

    visited = {focus}
    frontier = {focus}
    for _ in range(max(depth, 0)):
        next_frontier: set[str] = set()
        for nid in frontier:
            next_frontier.update(adjacency[nid] - visited)
        if not next_frontier:
            break
        visited.update(next_frontier)
        frontier = next_frontier
        if len(visited) >= limit:
            break

    selected_ids = list(visited)[:limit]
    selected_set = set(selected_ids)
    nodes = [by_id[nid] for nid in selected_ids]
    edges = [e for e in all_edges if e["source"] in selected_set and e["target"] in selected_set]
    return nodes, edges
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_observability_graph.py::SelectSubgraphTests -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add opendream/observability.py tests/test_observability_graph.py
git commit -m "feat(graph): add _select_subgraph BFS extraction by focus + depth"
```

---

### Task 5: Wire `_select_subgraph` + `_layered_positions` into `build_graph`

**Files:**
- Modify: `tests/test_observability_graph.py`
- Modify: `opendream/observability.py:67-84` (replace existing `build_graph`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_observability_graph.py`:

```python
class BuildGraphIntegrationTests(unittest.TestCase):
    def test_default_layout_is_hierarchical_with_positions(self) -> None:
        index = index_with(chain_fixture())
        result = build_graph(index)
        self.assertEqual(result["layout"], "hierarchical")
        self.assertEqual(result["depth"], 1)
        for node in result["nodes"]:
            self.assertIn("x", node)
            self.assertIn("y", node)

    def test_force_layout_omits_positions(self) -> None:
        index = index_with(chain_fixture())
        result = build_graph(index, layout="forceatlas2")
        for node in result["nodes"]:
            self.assertNotIn("x", node)
            self.assertNotIn("y", node)

    def test_unknown_layout_falls_back_to_hierarchical(self) -> None:
        index = index_with(chain_fixture())
        result = build_graph(index, layout="totally-fake")
        self.assertEqual(result["layout"], "hierarchical")
        for node in result["nodes"]:
            self.assertIn("x", node)

    def test_depth_param_passed_to_select_subgraph(self) -> None:
        index = index_with(hub_fixture())
        result = build_graph(index, focus="H", depth=0, limit=24)
        self.assertEqual([n["id"] for n in result["nodes"]], ["H"])

    def test_focus_with_no_neighbors_returns_just_focus(self) -> None:
        index = index_with(isolated_fixture())
        result = build_graph(index, focus="X", depth=2)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["edges"], [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_observability_graph.py::BuildGraphIntegrationTests -v`
Expected: 5 FAIL (`build_graph` doesn't accept `layout` or `depth` yet)

- [ ] **Step 3: Replace `build_graph`**

Replace the existing `build_graph` in `opendream/observability.py` (currently lines 67-84) with:

```python
_VALID_LAYOUTS = frozenset({"hierarchical", "forceatlas2"})


def build_graph(
    index: dict[str, Any],
    *,
    focus: str | None = None,
    limit: int = 24,
    depth: int = 1,
    layout: str = "hierarchical",
) -> dict[str, Any]:
    graph = index["entities"]["graph"]
    if layout not in _VALID_LAYOUTS:
        layout = "hierarchical"
    nodes, edges = _select_subgraph(graph, focus=focus, limit=limit, depth=depth)
    # Copy nodes so we don't mutate the underlying index when assigning x/y.
    nodes = [dict(node) for node in nodes]
    if layout == "hierarchical":
        positions = _layered_positions(nodes, edges)
        for node in nodes:
            x, y = positions[node["id"]]
            node["x"] = x
            node["y"] = y
    return {
        "nodes": nodes,
        "edges": edges,
        "focus": focus,
        "depth": depth,
        "layout": layout,
    }
```

- [ ] **Step 4: Run all graph tests**

Run: `python -m pytest tests/test_observability_graph.py -v`
Expected: All PASS (12+ tests)

- [ ] **Step 5: Run the existing observability suite to confirm no regression**

Run: `python -m pytest tests/test_observability.py -v`
Expected: All PASS (no test in there currently checks the old `build_graph` signature shape, but verify)

- [ ] **Step 6: Commit**

```bash
git add opendream/observability.py tests/test_observability_graph.py
git commit -m "feat(graph): extend build_graph with depth and layout params"
```

---

## Phase 2 — `/static/` HTTP handler

### Task 6: Create empty static dir + sentinel file

**Files:**
- Create: `opendream/static/.gitkeep` (will be replaced when graph.js lands)
- Create: `opendream/static/vendor/.gitkeep`

- [ ] **Step 1: Make the directories**

```bash
mkdir -p opendream/static/vendor
touch opendream/static/.gitkeep opendream/static/vendor/.gitkeep
```

- [ ] **Step 2: Verify pyproject includes static files in the package**

Read `pyproject.toml`. If it uses setuptools/hatchling auto-discovery and a `[tool.setuptools.package-data]` or `[tool.hatch.build]` section, add `"static/**"` to `package-data` for `opendream`. Example for setuptools:

```toml
[tool.setuptools.package-data]
opendream = ["static/**"]
```

If the project uses `pyproject.toml` with `[tool.setuptools]` or hatchling and the static dir is missing from the package data, the build won't ship it. Verify with:

```bash
python -m build --sdist 2>&1 | tail -20
tar -tzf dist/opendream-*.tar.gz | grep static
```

Expected: `opendream/static/.gitkeep` appears in the sdist manifest.

(If the project uses `MANIFEST.in` instead, add `recursive-include opendream/static *` there.)

- [ ] **Step 3: Commit**

```bash
git add opendream/static/ pyproject.toml
git commit -m "chore(graph): scaffold opendream/static/ directory and packaging"
```

---

### Task 7: `_serve_static` happy-path

**Files:**
- Create: `tests/test_webapp_static.py`
- Modify: `opendream/webapp.py`

- [ ] **Step 1: Add a test fixture file under static/**

```bash
mkdir -p opendream/static/vendor
printf "// test fixture\n" > opendream/static/vendor/_test.js
git add opendream/static/vendor/_test.js
```

(This file is committed and used by the tests. It stays in the repo permanently as a smoke marker.)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_webapp_static.py
from __future__ import annotations

import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from opendream.storage import MemoryStore
from opendream.webapp import build_server


class StaticHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(workspace)
        self.store.initialize(store_kind="project")
        self.server = build_server(self.store, host="127.0.0.1", port=0)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
        self.temp_dir.cleanup()

    def test_static_serves_committed_test_fixture(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/static/vendor/_test.js") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers["Content-Type"], "application/javascript")
            self.assertIn("test fixture", resp.read().decode("utf-8"))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_webapp_static.py::StaticHandlerTests::test_static_serves_committed_test_fixture -v`
Expected: 404 (the `/static/` route doesn't exist yet)

- [ ] **Step 4: Implement `_serve_static`**

Modify `opendream/webapp.py`. Add an import:

```python
from pathlib import Path
```

Add a module-level constant:

```python
_STATIC_ROOT = (Path(__file__).parent / "static").resolve()
_STATIC_MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".md": "text/markdown",
    ".html": "text/html; charset=utf-8",
}
```

Modify `ObservabilityHandler.do_GET` (currently around line 319) — insert the static branch before the `/api/` branch:

```python
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
```

Add the `_serve_static` method to `ObservabilityHandler`:

```python
    def _serve_static(self, request_path: str) -> None:
        relative = request_path[len("/static/"):]
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_webapp_static.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add opendream/webapp.py tests/test_webapp_static.py opendream/static/vendor/_test.js
git commit -m "feat(webapp): add /static/ handler for vendored assets"
```

---

### Task 8: `_serve_static` security and edge cases

**Files:**
- Modify: `tests/test_webapp_static.py`

- [ ] **Step 1: Add four more failing tests**

Append to `StaticHandlerTests`:

```python
    def _expect_404(self, path: str) -> None:
        try:
            urllib.request.urlopen(f"{self.base_url}{path}")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)
            return
        self.fail(f"expected 404 for {path}")

    def test_static_refuses_path_traversal_dotdot(self) -> None:
        self._expect_404("/static/../webapp.py")

    def test_static_refuses_encoded_traversal(self) -> None:
        self._expect_404("/static/%2e%2e/webapp.py")

    def test_static_refuses_unknown_file(self) -> None:
        self._expect_404("/static/vendor/does-not-exist.js")

    def test_static_sets_long_cache_header(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/static/vendor/_test.js") as resp:
            self.assertEqual(resp.headers["Cache-Control"], "public, max-age=86400")
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_webapp_static.py -v`
Expected: All PASS (the implementation in Task 7 already covers these cases — `..` is filtered, the `relative_to` check prevents escapes, and missing files return 404)

If `test_static_refuses_encoded_traversal` fails, that's because `urlparse` does *not* decode `%2e`. Add explicit URL decoding to `_serve_static`:

```python
from urllib.parse import unquote
# ...
relative = unquote(request_path[len("/static/"):])
if not relative or ".." in relative.split("/"):
    ...
```

Re-run until green.

- [ ] **Step 3: Commit**

```bash
git add opendream/webapp.py tests/test_webapp_static.py
git commit -m "test(webapp): cover static handler traversal and 404 cases"
```

---

### Task 9: Pass `depth` and `layout` query params to `build_graph`

**Files:**
- Create: `tests/test_webapp_graph_route.py`
- Modify: `opendream/webapp.py:436-437`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_webapp_graph_route.py
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from opendream.integration import emit_event, maintain
from opendream.observability import index_observability
from opendream.storage import MemoryStore
from opendream.webapp import INDEX_HTML, build_server

FIXED_NOW = "2026-04-10T12:00:00Z"


class GraphRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(self.temp_dir.name) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(workspace)
        self.store.initialize(store_kind="project")
        emit_event(
            self.store,
            kind="project_decision",
            content="seed memory for graph test",
            scope="project",
            channel="cli",
            message_ref="g-1",
            timestamp=FIXED_NOW,
        )
        maintain(self.store, now=FIXED_NOW)
        index_observability(self.store, now=FIXED_NOW)
        self.server = build_server(self.store, host="127.0.0.1", port=0)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
        self.temp_dir.cleanup()

    def get_json(self, path: str) -> dict[str, object]:
        with urllib.request.urlopen(f"{self.base_url}{path}") as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_default_layout_includes_positions(self) -> None:
        payload = self.get_json("/api/graph")
        self.assertEqual(payload["layout"], "hierarchical")
        if payload["nodes"]:
            self.assertIn("x", payload["nodes"][0])
            self.assertIn("y", payload["nodes"][0])

    def test_force_layout_omits_positions(self) -> None:
        payload = self.get_json("/api/graph?layout=forceatlas2")
        self.assertEqual(payload["layout"], "forceatlas2")
        for node in payload["nodes"]:
            self.assertNotIn("x", node)

    def test_depth_query_param_accepted(self) -> None:
        payload = self.get_json("/api/graph?depth=3")
        self.assertEqual(payload["depth"], 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_webapp_graph_route.py -v`
Expected: First test fails — current `/api/graph` doesn't return `layout` key.

- [ ] **Step 3: Modify `webapp.py:436-437`**

Replace:

```python
        if parsed.path == "/api/graph":
            self._write_json(build_graph(index, focus=query.get("focus"), limit=int(query.get("limit", "24"))))
            return
```

with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_webapp_graph_route.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add opendream/webapp.py tests/test_webapp_graph_route.py
git commit -m "feat(webapp): pass depth and layout query params to build_graph"
```

---

## Phase 3 — Vendor third-party JS

### Task 10: Vendor Sigma + Graphology + ForceAtlas2

**Files:**
- Create: `opendream/static/vendor/sigma.min.js`
- Create: `opendream/static/vendor/graphology.umd.min.js`
- Create: `opendream/static/vendor/graphology-layout-forceatlas2.min.js`
- Create: `opendream/static/vendor/README.md`

- [ ] **Step 1: Download the three vendor files**

```bash
cd opendream/static/vendor
curl -fsSL -o sigma.min.js \
  https://cdnjs.cloudflare.com/ajax/libs/sigma.js/3.0.2/sigma.min.js
curl -fsSL -o graphology.umd.min.js \
  https://cdnjs.cloudflare.com/ajax/libs/graphology/0.25.4/graphology.umd.min.js
curl -fsSL -o graphology-layout-forceatlas2.min.js \
  https://cdn.jsdelivr.net/npm/graphology-layout-forceatlas2@0.10.1/dist/graphology-layout-forceatlas2.min.js
cd -
```

If any of these 404, look up the current paths on cdnjs.com / jsdelivr.com and adjust the URLs. Both services serve every published version.

- [ ] **Step 2: Verify file sizes and that they parse**

```bash
wc -c opendream/static/vendor/sigma.min.js opendream/static/vendor/graphology.umd.min.js opendream/static/vendor/graphology-layout-forceatlas2.min.js
node -e "require('./opendream/static/vendor/graphology.umd.min.js'); console.log('graphology ok')" 2>&1 || true
```

Expected: each file is 10–200 KB; node smoke test prints "graphology ok" or a recognizable global-scope error (acceptable — UMD bundles often complain when loaded via require).

- [ ] **Step 3: Add provenance header comments**

For each of the three files, prepend a short header (use sed or open the file):

```js
/* vendored from <SOURCE_URL>
 * version: <VERSION>
 * license: MIT
 * fetched: 2026-04-10
 * sha256: <RUN: shasum -a 256 <FILE>>
 */
```

- [ ] **Step 4: Write `vendor/README.md`**

```markdown
# Vendored third-party JS

This directory holds pinned third-party JavaScript used by the `/graph`
explorer. Files are committed verbatim so the observability dashboard works
offline and behind air-gapped networks.

## Contents

| File | Version | License | Source |
|------|---------|---------|--------|
| `sigma.min.js` | 3.0.2 | MIT | https://cdnjs.cloudflare.com/ajax/libs/sigma.js/3.0.2/sigma.min.js |
| `graphology.umd.min.js` | 0.25.4 | MIT | https://cdnjs.cloudflare.com/ajax/libs/graphology/0.25.4/graphology.umd.min.js |
| `graphology-layout-forceatlas2.min.js` | 0.10.1 | MIT | https://cdn.jsdelivr.net/npm/graphology-layout-forceatlas2@0.10.1/dist/graphology-layout-forceatlas2.min.js |

## Refresh procedure

1. Look up the desired version on cdnjs.com / jsdelivr.com.
2. Re-run the `curl -fsSL -o ...` commands documented above with the new URLs.
3. Update the version cells in this README and the `version` line in each file's
   header comment.
4. Recompute the sha256 for each file: `shasum -a 256 *.js`.
5. Run the manual verification checklist at
   `docs/runbooks/graph-explorer-verify.md`.
6. Update `THIRD_PARTY_NOTICES.md` if any license text changed.

## License notes

All files are MIT-licensed. See `THIRD_PARTY_NOTICES.md` at the repo root for
the verbatim license texts.
```

- [ ] **Step 5: Update `THIRD_PARTY_NOTICES.md`**

Append two entries — one for sigma.js (Copyright 2013-2025 Alexis Jacomy, Guillaume Plique), one for graphology (Copyright 2017-2025 Guillaume Plique). Use the standard MIT license text.

- [ ] **Step 6: Commit**

```bash
git add opendream/static/vendor/ THIRD_PARTY_NOTICES.md
git commit -m "vendor(graph): add Sigma.js 3.0.2, Graphology 0.25.4, FA2 layout"
```

---

## Phase 4 — Frontend (`graph.js` + `graph.css`)

> The next several tasks build `opendream/static/graph.js` incrementally. Each task adds one logical unit and is verified by manual smoke against `/graph` in a browser. The full file is ~700 lines; each task adds 50–150 lines.

### Task 11: `graph.css` and the IIFE skeleton

**Files:**
- Create: `opendream/static/graph.css`
- Create: `opendream/static/graph.js`

- [ ] **Step 1: Write `graph.css`**

```css
/* opendream/static/graph.css */
#graph-root {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  height: calc(100vh - 140px);
  min-height: 480px;
}
#graph-sidepanel {
  background: rgba(18, 25, 53, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 16px;
  overflow-y: auto;
  font-size: 13px;
}
#graph-sidepanel h3 { margin: 16px 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #94a3b8; }
#graph-canvas-wrap {
  position: relative;
  background: rgba(18, 25, 53, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  overflow: hidden;
}
#graph-canvas { position: absolute; inset: 0; }
#graph-minimap {
  position: absolute;
  bottom: 12px;
  right: 12px;
  width: 160px;
  height: 100px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(11, 16, 32, 0.7);
  border-radius: 8px;
}
#graph-tooltip {
  position: absolute;
  pointer-events: none;
  background: #0f1630;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  display: none;
  z-index: 5;
  max-width: 260px;
}
.graph-chip {
  display: inline-block;
  padding: 3px 8px;
  margin: 3px 4px 3px 0;
  border-radius: 999px;
  font-size: 11px;
  cursor: pointer;
  border: 1px solid transparent;
  user-select: none;
}
.graph-chip.disabled { opacity: 0.35; }
.graph-empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #94a3b8; font-size: 14px; text-align: center; padding: 24px; }
.graph-error { background: rgba(248, 113, 113, 0.18); color: #f87171; padding: 10px; border-radius: 8px; margin-bottom: 12px; }
.graph-segmented { display: inline-flex; border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; overflow: hidden; }
.graph-segmented button { background: transparent; color: #e2e8f0; border: 0; padding: 6px 12px; cursor: pointer; }
.graph-segmented button.active { background: #67e8f9; color: #0b1020; }
@media (max-width: 900px) {
  #graph-root { grid-template-columns: 1fr; height: auto; }
  #graph-canvas-wrap { height: 60vh; }
}
```

- [ ] **Step 2: Write the `graph.js` skeleton**

```js
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
```

- [ ] **Step 3: Manual smoke**

Start the webapp: `python -m opendream serve --port 8765` (or whatever the project's serve command is — check `opendream/cli.py` for the exact form). Browse to `http://127.0.0.1:8765/static/graph.js` and `http://127.0.0.1:8765/static/graph.css` — both should return 200 with the file contents.

The `/graph` route still shows the JSON dump because we haven't wired the loader yet. That's fine — that comes in Task 19.

- [ ] **Step 4: Commit**

```bash
git add opendream/static/graph.css opendream/static/graph.js
git commit -m "feat(graph): scaffold graph.js IIFE, state, theme, and graph.css"
```

---

### Task 12: Data layer — fetch + filter

**Files:**
- Modify: `opendream/static/graph.js`

- [ ] **Step 1: Replace the `// (filled in Task 12)` block with the data layer**

```js
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
```

- [ ] **Step 2: Manual smoke**

In a browser console at `/graph` (after Task 19 lands you can verify in-app; for now just paste the file into a console):

```js
window.__opendreamGraph._state.raw = { nodes: [{id:'a',type:'memory'}], edges: [] };
// visibleNodes is internal; just verify no syntax errors loading the file:
fetch('/static/graph.js').then(r => r.text()).then(t => { eval(t); console.log('ok'); });
```

Expected: prints "ok" with no syntax error.

- [ ] **Step 3: Commit**

```bash
git add opendream/static/graph.js
git commit -m "feat(graph): add fetchGraph + visibleNodes/Edges filter helpers"
```

---

### Task 13: Render layer — Sigma init and hierarchical render

**Files:**
- Modify: `opendream/static/graph.js`

- [ ] **Step 1: Replace the `// (filled in Task 13)` block**

```js
  // ---- 4. Render layer ----------------------------------------------------
  function buildGraphology() {
    const Graph = window.graphology;
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
      } catch (_e) { /* duplicate key — ignore */ }
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
    const FA2 = window.graphologyLayoutForceatlas2;
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
```

Update `mount` to call `refresh` after rendering chrome:

```js
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
```

Add a stub `parseUrlState` and `renderSidePanel` (filled in later tasks):

```js
  function parseUrlState() { /* filled in Task 16 */ }
  function renderSidePanel() {
    state.sidepanelEl.innerHTML = '<div class="graph-empty">Side panel coming in Task 14.</div>';
  }
```

- [ ] **Step 2: Commit**

```bash
git add opendream/static/graph.js
git commit -m "feat(graph): wire Sigma render with hierarchical positions and FA2"
```

---

### Task 14: UI chrome — side panel, filters, toggles

**Files:**
- Modify: `opendream/static/graph.js`

- [ ] **Step 1: Replace the `// (filled in Task 14)` and the `renderSidePanel` stub**

```js
  // ---- 5. UI chrome -------------------------------------------------------
  const NODE_TYPES = ['memory', 'review', 'run', 'retrieval'];
  const EDGE_KINDS = ['supersedes', 'conflicts_with', 'supports', 'derived_from', 'verified_by', 'invalidated_by', 'reviewed'];

  function renderSidePanel() {
    const focusLabel = state.focus
      ? (state.raw?.nodes.find(n => n.id === state.focus)?.title || state.focus)
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
    });
  }

  function toggleSetMember(set, value) {
    // Filter sets are inclusive: empty = all visible, populated = only listed visible.
    // Click toggles "is this kind shown?" — implemented as: empty means all on,
    // first click moves to the inverse (everything except that kind), etc.
    // Simpler model: track explicitly disabled members in a hidden-set sibling.
    // For first-pass simplicity we use the explicit-allowlist semantics:
    if (set.has(value)) set.delete(value);
    else set.add(value);
  }
```

- [ ] **Step 2: Commit**

```bash
git add opendream/static/graph.js
git commit -m "feat(graph): side panel chrome with layout/depth/filter chips"
```

---

### Task 15: Wiring — hover, click, dblclick, shift-click, right-click

**Files:**
- Modify: `opendream/static/graph.js`

- [ ] **Step 1: Replace the `// (filled in Task 15)` block**

```js
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
      const original = event.original;
      const raw = state.raw.nodes.find(n => n.id === node);
      if (original && original.shiftKey) {
        const route = { memory: '/memories/', run: '/runs/', retrieval: '/retrievals/' }[raw.type];
        if (route) { window.location.href = route + encodeURIComponent(node); return; }
      }
      state.selected = raw;
      renderSidePanel();
    });

    sigma.on('doubleClickNode', ({ node, event }) => {
      event.preventSigmaDefault();
      state.focus = node;
      pushUrlState();
      refresh();
    });

    sigma.on('rightClickNode', ({ node, event }) => {
      event.preventSigmaDefault();
      showContextMenu(node, event.original.clientX, event.original.clientY);
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
          const raw = state.raw.nodes.find(n => n.id === nodeId);
          const route = { memory: '/memories/', run: '/runs/', retrieval: '/retrievals/' }[raw.type];
          if (route) window.location.href = route + encodeURIComponent(nodeId);
        }
      },
      { label: 'Expand neighborhood', action: () => { state.depth = Math.min(state.depth + 1, 3); pushUrlState(); refresh(); } },
      { label: 'Hide node', action: () => { state.hidden.add(nodeId); renderSidePanel(); initSigma(); } },
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
      ctx.fillStyle = a.color;
      ctx.fillRect(px - 1, py - 1, 2, 2);
    });
  }
```

Update `refresh` to call `wireSigmaEvents` after `initSigma`:

```js
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
```

- [ ] **Step 2: Commit**

```bash
git add opendream/static/graph.js
git commit -m "feat(graph): wire hover, click, dblclick, right-click, minimap"
```

---

### Task 16: URL state parse and push

**Files:**
- Modify: `opendream/static/graph.js`

- [ ] **Step 1: Replace `parseUrlState` stub and add `pushUrlState`**

```js
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
  }

  function pushUrlState() {
    const params = new URLSearchParams();
    if (state.focus) params.set('focus', state.focus);
    if (state.depth !== 1) params.set('depth', String(state.depth));
    if (state.layout !== 'hierarchical') params.set('layout', state.layout);
    if (state.filters.nodeTypes.size) params.set('types', Array.from(state.filters.nodeTypes).join(','));
    if (state.filters.edgeKinds.size) params.set('edges', Array.from(state.filters.edgeKinds).join(','));
    const qs = params.toString();
    const newUrl = '/graph' + (qs ? '?' + qs : '');
    window.history.replaceState({}, '', newUrl);
  }
```

- [ ] **Step 2: Commit**

```bash
git add opendream/static/graph.js
git commit -m "feat(graph): URL state parse and push for shareable views"
```

---

## Phase 5 — Loader integration

### Task 17: Replace `renderGraph()` in `INDEX_HTML` with the lazy loader

**Files:**
- Modify: `opendream/webapp.py:181-186`

- [ ] **Step 1: Modify `INDEX_HTML`**

Replace:

```js
    async function renderGraph() {
      const data = await fetchJson('/api/graph');
      app.innerHTML = [
        panel('Provenance Graph', `<div class="split"><div>${pretty(data.nodes)}</div><div>${pretty(data.edges)}</div></div>`, true),
      ].join('');
    }
```

with:

```js
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
        // Fallback: legacy JSON dump so /graph is never worse than today.
        const data = await fetchJson('/api/graph');
        app.innerHTML = [
          panel('Provenance Graph (fallback view — interactive renderer failed: ' + err.message + ')', `<div class="split"><div>${pretty(data.nodes)}</div><div>${pretty(data.edges)}</div></div>`, true),
        ].join('');
      }
    }
```

- [ ] **Step 2: Manual smoke**

Restart the webapp. Browse to `/graph`. Expected:
- The page shows the new explorer with a side panel and Sigma canvas.
- The browser dev tools network tab shows `/static/graph.css`, `/static/vendor/graphology.umd.min.js`, `/static/vendor/graphology-layout-forceatlas2.min.js`, `/static/vendor/sigma.min.js`, `/static/graph.js`, and `/api/graph?depth=1&layout=hierarchical` all returning 200.
- If you delete `opendream/static/vendor/sigma.min.js` and reload, the page falls back to the JSON dump with an error message in the panel title.

- [ ] **Step 3: Commit**

```bash
git add opendream/webapp.py
git commit -m "feat(graph): replace JSON-dump renderGraph with Sigma loader + fallback"
```

---

### Task 18: HTML loader smoke test

**Files:**
- Modify: `tests/test_webapp_graph_route.py`

- [ ] **Step 1: Add a test that confirms `INDEX_HTML` references the static asset paths**

```python
    def test_graph_html_links_static_assets(self) -> None:
        # Sanity check: the SPA HTML must reference the loader scripts so that
        # /graph actually triggers Sigma loading. If someone deletes the loader
        # this test catches it before manual verification.
        for path in [
            '/static/graph.js',
            '/static/vendor/sigma.min.js',
            '/static/vendor/graphology.umd.min.js',
        ]:
            self.assertIn(path, INDEX_HTML)
```

- [ ] **Step 2: Run all webapp tests**

Run:
```bash
python -m pytest tests/test_webapp_static.py tests/test_webapp_graph_route.py tests/test_observability.py -v
```

Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_webapp_graph_route.py
git commit -m "test(graph): assert INDEX_HTML references the loader script paths"
```

---

## Phase 6 — Documentation and verification

### Task 19: Manual verification runbook

**Files:**
- Create: `docs/runbooks/graph-explorer-verify.md`

- [ ] **Step 1: Write the runbook**

```markdown
# Graph Explorer — Manual Verification Runbook

This checklist verifies the `/graph` provenance explorer page after any change
to `opendream/webapp.py`, `opendream/observability.py:build_graph`, or anything
under `opendream/static/`. JavaScript correctness cannot be unit-tested in this
buildless setup, so this is the gate that catches UI regressions.

## Setup

1. From the repo root, start the local webapp against a workspace that has
   memories and relations:
   ```
   opendream serve --port 8765
   ```
2. Open `http://127.0.0.1:8765/graph` in a modern browser (Chrome 120+ or
   Firefox 122+).

## Checklist

- [ ] **Empty store** — point the webapp at a freshly initialized workspace.
      `/graph` shows the centered "No relations to display" hint, no console errors.
- [ ] **5-node fixture** — load a workspace with the small test fixture under
      `tests/fixtures/graph_fixture.py::chain_fixture`. Hierarchical layout
      renders top-to-bottom. Edges colored per kind.
- [ ] **200-node fixture** — load a workspace populated by the integration
      test seed. Smooth pan and zoom with no visible jank.
- [ ] **Hover** — hovering a node highlights it and its neighbors; everything
      else dims. Tooltip shows title and type. Leaving the node restores.
- [ ] **Single click** — clicking a node updates the side panel "Selected"
      card with the node's title, type badge, raw JSON, and detail link.
- [ ] **Double click** — double-clicking a node re-fetches and re-centers.
      URL updates to include `?focus=<id>`. Browser back-button does NOT
      unwind to the previous focus (we use `replaceState`).
- [ ] **Shift-click memory** — shift-clicking a node of type `memory`
      navigates to `/memories/<id>`.
- [ ] **Layout toggle** — clicking `Force` triggers ForceAtlas2 and the graph
      re-flows. Clicking `Hierarchical` snaps back to layered positions.
- [ ] **Depth slider** — clicking `0`, `1`, `2`, `3` re-fetches with the new
      depth. URL updates to include `?depth=N` (omitted for the default `1`).
- [ ] **Node type chips** — clicking a chip fades nodes of that type. Other
      chips remain unaffected.
- [ ] **Edge kind chips** — clicking a chip fades edges of that kind.
- [ ] **Search box** — typing into the search box hides nodes whose label
      doesn't contain the substring.
- [ ] **Right-click context menu** — right-click shows Focus / Open detail /
      Expand neighborhood / Hide. Each action works.
- [ ] **Hide and show** — clicking Hide on a node removes it and its edges.
      The "Show N hidden" button restores them.
- [ ] **URL share** — copy the address bar URL with non-default state, open
      it in a new tab. Identical view loads.
- [ ] **Offline** — disable network in dev tools, reload `/graph`. Vendored
      assets load from cache; the page renders. (`/api/graph` will fail —
      that's expected; the error banner appears but the page does not crash.)
- [ ] **Vendor failure fallback** — temporarily rename
      `opendream/static/vendor/sigma.min.js` and reload. The legacy JSON dump
      view appears with an error message in the panel title. Restore the file.

## Sign-off

All boxes ticked → safe to merge / release.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/graph-explorer-verify.md
git commit -m "docs(graph): add manual verification runbook for /graph explorer"
```

---

### Task 20: Final test sweep + lint + typecheck

**Files:**
- (verification only, no edits unless something fails)

- [ ] **Step 1: Run the full test suite**

Run: `make test`
Expected: All PASS.

- [ ] **Step 2: Run lint**

Run: `make lint`
Expected: clean. If `ruff` complains about the new files (unused imports, line length), fix inline.

- [ ] **Step 3: Run typecheck**

Run: `make typecheck`
Expected: clean. The new functions in `observability.py` use `dict[str, Any]` and `tuple[float, float]` annotations that should pass mypy.

- [ ] **Step 4: Run verify**

Run: `make verify`
Expected: clean.

- [ ] **Step 5: Run the manual verification runbook**

Open `docs/runbooks/graph-explorer-verify.md` and tick every box against a real browser session.

- [ ] **Step 6: Commit if any fixes were needed**

```bash
git add -A  # use only if Step 1-4 produced fixes
git commit -m "fix(graph): address lint/typecheck/test feedback from verify pass"
```

---

## Self-review (against `2026-04-10-graph-explorer-design.md`)

**Spec coverage check:**

| Spec section | Plan task(s) |
|---|---|
| §4.1 graph.js as separate file | Task 11 |
| §5.1 `_layered_positions` + `_select_subgraph` + extended `build_graph` | Tasks 2–5 |
| §5.2 `/static/` handler + query passthrough | Tasks 7–9 |
| §6.1 loader inside `INDEX_HTML` | Task 17 |
| §6.2 `graph.js` six-unit IIFE | Tasks 11–16 |
| §6.3 visual layout (DOM) | Task 11 (CSS) + Task 13 (mount) |
| §6.4 theme + edge styling implementation risk | Task 11 (THEME constant uses opacity per kind, dashed/dotted deferred per spec) |
| §6.5 hover/click/dblclick/shift-click/right-click/minimap | Task 15 |
| §6.6 URL state | Task 16 |
| §6.7 empty/error/fallback | Task 13 (empty), Task 13 (error in `refresh`), Task 17 (vendor fallback) |
| §7 vendored asset tree + README + notices | Task 10 |
| §8.1 `tests/test_observability_graph.py` | Tasks 2–5 |
| §8.2 `tests/test_webapp_static.py` | Tasks 7–8 |
| §8.3 `tests/test_webapp_graph_route.py` | Tasks 9, 18 |
| §8.4 manual runbook | Task 19 |

**Open items deferred to implementation discretion:**

1. **Test fixtures location** (spec §11.1) — resolved as `tests/fixtures/graph_fixture.py` (matches existing `tests/fixtures/` directory).
2. **`make verify` extension** (spec §11.2) — kept as docs-only runbook; promoting to a make target requires headless-browser tooling out of scope.
3. **Vendor refresh make target** (spec §11.3) — kept as docs-only `curl` commands in `vendor/README.md`.

**Placeholder scan:** No TBDs, TODOs, or "implement later" found. Every step has either complete code, a complete command, or a complete test assertion.

**Type consistency check:**

- `_layered_positions` signature `(nodes, edges) -> dict[str, tuple[float, float]]` — used identically in Task 5 `build_graph`.
- `_select_subgraph` signature `(graph, *, focus, limit, depth) -> tuple[list, list]` — used identically in Task 5.
- JS `state` keys defined in Task 11 are referenced consistently in Tasks 12–16. `state.raw`, `state.graph`, `state.sigma`, `state.filters.nodeTypes`, `state.filters.edgeKinds`, `state.hidden`, `state.focus`, `state.depth`, `state.layout`, `state.selected` all match.
- `THEME.nodeColors` / `THEME.edgeColors` / `THEME.edgeOpacity` defined in Task 11 are used in Tasks 13–14 with consistent key names matching `RELATION_KINDS` from `opendream/relation_graph.py:17`.
- `fetchGraph`, `visibleNodes`, `visibleEdges`, `buildGraphology`, `initSigma`, `refresh`, `runForceAtlas2`, `wireSigmaEvents`, `renderSidePanel`, `parseUrlState`, `pushUrlState` — all defined exactly once and called by name in later tasks.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-10-graph-explorer.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
