"""Tests for the Pydantic model."""

import unittest

from curies import NamableReference, Reference
from curies.vocabulary import unspecified_matching_process

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import MappingSetRecord


class TestModel(unittest.TestCase):
    """Tests for the Pydantic model."""

    def test_creator_id(self) -> None:
        """Test a non-list creator gets properly upgraded."""
        x = {
            "mapping_set_id": "https://example.org/test.tsv",
            "creator_id": "orcid:1111-1111-1111-1111",
        }
        model = MappingSetRecord.model_validate(x)
        self.assertIsInstance(model.creator_id, list)

        x2 = {
            "mapping_set_id": "https://example.org/test.tsv",
            "creator_id": ["orcid:1111-1111-1111-1111"],
        }
        model = MappingSetRecord.model_validate(x2)
        self.assertIsInstance(model.creator_id, list)

    def test_upgrade(self) -> None:
        """Test before-validation rule on subject, predicate, and object."""
        mapping = SemanticMapping(
            subject="a:1",
            predicate="a:2",
            object="a:3",
            justification=unspecified_matching_process,
        )
        self.assertIsInstance(mapping.subject, NamableReference)
        self.assertIsInstance(mapping.predicate, NamableReference)
        self.assertIsInstance(mapping.object, NamableReference)

        mapping2 = SemanticMapping(
            subject=Reference.from_curie("a:1"),
            predicate=Reference.from_curie("a:2"),
            object=Reference.from_curie("a:3"),
            justification=unspecified_matching_process,
        )
        self.assertIsInstance(mapping2.subject, NamableReference)
        self.assertIsInstance(mapping2.predicate, NamableReference)
        self.assertIsInstance(mapping2.object, NamableReference)

        mapping3 = SemanticMapping(
            subject=NamableReference.from_curie("a:1"),
            predicate=NamableReference.from_curie("a:2"),
            object=NamableReference.from_curie("a:3"),
            justification=unspecified_matching_process,
        )
        self.assertIsInstance(mapping3.subject, NamableReference)
        self.assertIsInstance(mapping3.predicate, NamableReference)
        self.assertIsInstance(mapping3.object, NamableReference)
