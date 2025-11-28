"""Test queries."""

import unittest

from curies import NamedReference
from curies.vocabulary import exact_match, unspecified_matching_process

from sssom_pydantic import SemanticMapping
from sssom_pydantic.query import QUERY_TO_FUNC, Query, filter_mappings


class TestQuery(unittest.TestCase):
    """Test queries."""

    def test_completeness(self) -> None:
        """Test completeness of implementations."""
        for name, field in Query.model_fields.items():
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
