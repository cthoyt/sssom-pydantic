"""Graph utilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import curies

from ..api import SemanticMapping

if TYPE_CHECKING:
    import networkx as nx

__all__ = [
    "get_undirected_graph",
]


def get_undirected_graph(mappings: Iterable[SemanticMapping]) -> nx.Graph[curies.Reference]:
    """Get an undirected graph based on the mappings."""
    import networkx as nx

    graph = nx.Graph()
    for mapping in mappings:
        graph.add_edge(mapping.subject, mapping.object)
    return graph
