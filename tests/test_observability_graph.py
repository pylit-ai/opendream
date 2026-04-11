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
