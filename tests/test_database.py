"""Test the database."""

import hashlib
import unittest

from curies import Reference
from curies.vocabulary import lexical_matching_process

from sssom_pydantic import SemanticMapping
from sssom_pydantic.database import SemanticMappingDatabase
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

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=_default_hash)

        self.assertEqual(0, db.count_mappings())

        db.add_mapping(mapping_1)
        db.add_mapping(mapping_2)

        self.assertEqual(2, db.count_mappings())

        db.delete_mapping(mapping_1)

        self.assertEqual(1, db.count_mappings())
        self.assertIsNone(db.get_mapping(_default_hash(mapping_1)))
        self.assertIsNotNone(db.get_mapping(_default_hash(mapping_2)))
