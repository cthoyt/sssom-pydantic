"""Test graph utilities."""

import unittest

import networkx as nx

from sssom_pydantic.contrib.graph import get_undirected_graph
from sssom_pydantic.examples import R1, R2, e1


class TestGraph(unittest.TestCase):
    """Test graph utilities."""

    def test_get_undirected_graph(self) -> None:
        """Test getting an undirected graph."""
        actual = get_undirected_graph([e1.semantic_mapping])
        expected = nx.DiGraph()
        expected.add_edge(R1, R2)
        self.assertEqual(list(expected.nodes()), list(actual.nodes()))
        self.assertEqual(list(expected.edges()), list(actual.edges()))
