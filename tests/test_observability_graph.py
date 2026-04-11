from __future__ import annotations

import unittest

from opendream.observability import _layered_positions, _select_subgraph, build_graph
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
