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
