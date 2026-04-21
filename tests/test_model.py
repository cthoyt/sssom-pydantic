"""Tests for the Pydantic model."""

import unittest

from curies import NamableReference, Reference
from curies.vocabulary import unspecified_matching_process

from sssom_pydantic import MappingSetRecord, SemanticMapping, hash_triple
from sssom_pydantic.api import NOT
from sssom_pydantic.examples import TEST_CONVERTER
from tests.cases import P1, R1, R2


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

    def test_negate(self) -> None:
        """Test negation."""
        m1 = SemanticMapping.exact(R1, R2)
        self.assertEqual(R1, m1.subject)
        self.assertEqual(P1, m1.predicate)
        self.assertEqual(R2, m1.object)
        self.assertEqual(unspecified_matching_process, m1.justification)
        self.assertIsNone(m1.predicate_modifier)
        self.assertFalse(m1.negated)
        self.assertFalse(hash_triple(m1, TEST_CONVERTER).endswith("~"))

        m2 = m1.negate()
        self.assertEqual(R1, m2.subject)
        self.assertEqual(P1, m2.predicate)
        self.assertEqual(R2, m2.object)
        self.assertEqual(unspecified_matching_process, m2.justification)
        self.assertEqual(NOT, m2.predicate_modifier)
        self.assertTrue(m2.negated)
        self.assertTrue(hash_triple(m2, TEST_CONVERTER).endswith("~"))

        # test round trip
        m3 = m2.negate()
        self.assertEqual(R1, m3.subject)
        self.assertEqual(P1, m3.predicate)
        self.assertEqual(R2, m3.object)
        self.assertEqual(unspecified_matching_process, m3.justification)
        self.assertIsNone(m3.predicate_modifier)
        self.assertFalse(m3.negated)
        self.assertFalse(hash_triple(m3, TEST_CONVERTER).endswith("~"))
