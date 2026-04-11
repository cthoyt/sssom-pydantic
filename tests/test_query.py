"""Test queries."""

import unittest
from collections import Counter

from curies import NamedReference
from curies.vocabulary import exact_match, unspecified_matching_process

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import NOT
from sssom_pydantic.examples import R1, R2, R3, R4, R5
from sssom_pydantic.query import (
    QUERY_TO_FUNC,
    Query,
    count_entities,
    count_prefix_pairs,
    count_unique_entities,
    filter_mappings,
    paginate_mappings,
)


class TestQuery(unittest.TestCase):
    """Test queries."""

    def test_completeness(self) -> None:
        """Test completeness of implementations."""
        for name, field in Query.model_fields.items():
            if name == "triple_id":
                continue  # has custom implementation
            if field.annotation == str | None:
                self.assertIn(name, QUERY_TO_FUNC)

    def test_query(self) -> None:
        """Test querying."""
        m1 = SemanticMapping(
            subject="mesh:1234",
            predicate=exact_match,
            object="chebi:1234",
            justification=unspecified_matching_process,
        )
        m2 = SemanticMapping(
            subject="chebi:1234",
            predicate=exact_match,
            object="mesh:1234",
            justification=unspecified_matching_process,
        )
        m3 = SemanticMapping(
            subject=NamedReference.from_curie("chebi:1234", name="test"),
            predicate=exact_match,
            object=NamedReference.from_curie("mesh:1234", name="test"),
            justification=unspecified_matching_process,
        )

        mappings = [m1, m2, m3]
        cases: list[tuple[Query, list[SemanticMapping]]] = [
            (Query(), mappings),
            (Query(subject_prefix="chebi"), [m2, m3]),
            (Query(same_text=True), [m3]),
        ]
        for i, (query, expected) in enumerate(cases):
            with self.subTest(i=i):
                self.assertEqual(expected, list(filter_mappings(mappings, query)))

    def test_get_entity_counter(self) -> None:
        """Test getting an entity counter."""
        mappings = [
            SemanticMapping.exact(R1, R2),
            SemanticMapping.exact(R3, R4),
            SemanticMapping.exact(R5, R3, predicate_modifier=NOT),
        ]
        self.assertEqual(
            Counter({R1: 1, R2: 1, R3: 2, R4: 1, R5: 1}),
            count_entities(mappings),
        )

    def test_count_unique_entities(self) -> None:
        """Test getting a prefix pair counter."""
        mappings = [
            SemanticMapping.exact(R1, R2),
            SemanticMapping.exact(R3, R4),
            SemanticMapping.exact(R5, R3, predicate_modifier=NOT),
        ]
        self.assertEqual(5, count_unique_entities(mappings))

    def test_get_prefix_pair_counter(self) -> None:
        """Test getting a prefix pair counter."""
        mappings = [
            SemanticMapping.exact(R1, R2),
            SemanticMapping.exact(R3, R4),
            SemanticMapping.exact(R5, R3, predicate_modifier=NOT),
        ]
        self.assertEqual(
            Counter({("mesh", "chebi"): 2, ("mesh", "mesh"): 1}), count_prefix_pairs(mappings)
        )

    def test_pagination(self) -> None:
        """Test postprocessing."""
        paginate_mappings()
