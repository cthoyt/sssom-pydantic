"""Test the database."""

import hashlib
import unittest

from curies import Reference
from curies.vocabulary import lexical_matching_process, manual_mapping_curation

from sssom_pydantic import SemanticMapping
from sssom_pydantic.database import (
    NEGATIVE_MAPPING_CLAUSE,
    POSITIVE_MAPPING_CLAUSE,
    QUERY_TO_CLAUSE,
    SemanticMappingDatabase,
    SemanticMappingModel,
    clauses_from_query,
)
from sssom_pydantic.query import Query
from tests import cases

USER = Reference(prefix="orcid", identifier="1234")

DEFAULT_HASH_PREFIX = "sssom-curator-hash-v2"
DEFAULT_HASH_EXCLUDE: set[str] = {"record", "cardinality", "cardinality_scope"}


def _default_hash(m: SemanticMapping) -> Reference:
    """Hash a mapping into a reference."""
    h = hashlib.md5(usedforsecurity=False)
    h.update(m.model_dump_json(exclude=DEFAULT_HASH_EXCLUDE).encode("utf8"))
    return Reference(prefix=DEFAULT_HASH_PREFIX, identifier=h.hexdigest())


class TestDatabase(unittest.TestCase):
    """Test the database."""

    def test_db(self) -> None:
        """Test the database."""
        mapping_1 = cases._m()
        mapping_2 = cases._m(justification=lexical_matching_process)
        mapping_3 = cases._m(predicate_modifier="Not")
        mapping_4 = cases._m(justification=lexical_matching_process, curation_rule_text=["unsure"])

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=_default_hash)

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
        mappings = db.get_mappings(where_clauses=clauses_from_query(query))
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="mesh")
        mappings = db.get_mappings(where_clauses=clauses_from_query(query))
        self.assertEqual(4, len(mappings))

        query = Query(object_prefix="chebi")
        mappings = db.get_mappings(where_clauses=clauses_from_query(query))
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="chebi")
        mappings = db.get_mappings(where_clauses=clauses_from_query(query))
        self.assertEqual(0, len(mappings))

        query = Query(object_prefix="mesh")
        mappings = db.get_mappings(where_clauses=clauses_from_query(query))
        self.assertEqual(0, len(mappings))

        db.delete_mapping(mapping_1)

        self.assertEqual(3, db.count_mappings())
        self.assertIsNone(db.get_mapping(_default_hash(mapping_1)))
        self.assertIsNotNone(db.get_mapping(_default_hash(mapping_2)))
        self.assertIsNotNone(db.get_mapping(_default_hash(mapping_3)))
        self.assertIsNotNone(db.get_mapping(_default_hash(mapping_4)))

    def test_query_functionality(self) -> None:
        """Check that all query fields are implemented."""
        for name, model_field in Query.model_fields.items():
            if model_field.annotation == str | None:
                self.assertIn(name, QUERY_TO_CLAUSE)
