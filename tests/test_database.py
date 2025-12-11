"""Test the database."""

import datetime
import unittest

from curies import Reference
from curies.vocabulary import charlie, lexical_matching_process, manual_mapping_curation

from sssom_pydantic.api import SemanticMapping, mapping_hash_v1
from sssom_pydantic.database import (
    NEGATIVE_MAPPING_CLAUSE,
    POSITIVE_MAPPING_CLAUSE,
    QUERY_TO_CLAUSE,
    SemanticMappingDatabase,
    SemanticMappingModel,
    clauses_from_query,
)
from sssom_pydantic.examples import EXAMPLE_MAPPINGS
from sssom_pydantic.query import Query
from tests import cases

USER = Reference(prefix="orcid", identifier="1234")


class TestDatabase(unittest.TestCase):
    """Test the database."""

    def test_db(self) -> None:
        """Test the database."""
        mapping_1 = cases._m()
        mapping_2 = cases._m(justification=lexical_matching_process)
        mapping_3 = cases._m(predicate_modifier="Not")
        mapping_4 = cases._m(justification=lexical_matching_process, curation_rule_text=["unsure"])

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)

        self.assertEqual(0, db.count_mappings())

        db.add_mapping(mapping_1)
        db.add_mappings([mapping_2, mapping_3, mapping_4])

        self.assertEqual(4, db.count_mappings())

        mappings = db.get_mappings(
            where_clauses=[SemanticMappingModel.justification == lexical_matching_process]
        )
        self.assertEqual(2, len(mappings))
        self.assertEqual(lexical_matching_process, mappings[0].justification)
        self.assertEqual(lexical_matching_process, mappings[1].justification)

        self.assertEqual(1, len(db.get_mappings(limit=1)))
        self.assertEqual(4, len(db.get_mappings()))
        self.assertEqual(4, len(db.get_mappings(limit=1000)))

        mappings = db.get_mappings(where_clauses=[POSITIVE_MAPPING_CLAUSE])
        self.assertEqual(1, len(mappings))
        self.assertEqual(manual_mapping_curation, mappings[0].justification)
        self.assertIsNone(mappings[0].predicate_modifier)
        self.assertIsNone(mappings[0].curation_rule_text)

        mappings = db.get_mappings(where_clauses=[NEGATIVE_MAPPING_CLAUSE])
        self.assertEqual(1, len(mappings))
        self.assertEqual(manual_mapping_curation, mappings[0].justification)
        self.assertIsNotNone(mappings[0].predicate_modifier)
        self.assertIsNone(mappings[0].curation_rule_text)

        # test no-op query
        query = Query()
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="mesh")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        query = Query(object_prefix="chebi")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="chebi")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(0, len(mappings))

        query = Query(object_prefix="mesh")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(0, len(mappings))

        query = Query(query="mesh")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        db.delete_mapping(mapping_1)

        self.assertEqual(3, db.count_mappings())
        self.assertIsNone(db.get_mapping(mapping_hash_v1(mapping_1)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_2)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_3)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_4)))

    def test_query_functionality(self) -> None:
        """Check that all query fields are implemented."""
        for name, model_field in Query.model_fields.items():
            if model_field.annotation == str | None:
                self.assertIn(name, QUERY_TO_CLAUSE)

    def test_clause_generation(self) -> None:
        """Test clause generation."""
        query = Query(query="hello")
        clauses = clauses_from_query(query)
        self.assertEqual(1, len(clauses))

    def test_queries(self) -> None:
        """Generate and execute variety of queries."""
        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mappings(EXAMPLE_MAPPINGS)
        for mapping in EXAMPLE_MAPPINGS:
            queries = [Query(query=mapping.subject.prefix)]
            for query in queries:
                results = db.get_mappings(clauses_from_query(query))
                self.assertNotEqual(0, len(results))

    def test_curate(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mapping(mapping)
        original_hash = db._hsh(mapping)
        db.curate(original_hash, authors=charlie, mark="correct")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db._hsh(expected)))

    def test_publish(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            publication_date=None,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mapping(mapping)
        original_hash = db._hsh(mapping)
        db.publish(original_hash)
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            publication_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db._hsh(expected)))
