"""Test the database."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

from curies import Reference

import sssom_pydantic
from sssom_pydantic.api import MAPPING_HASH_V1_PREFIX, mapping_hash_v1
from sssom_pydantic.database import (
    QUERY_TO_CLAUSE,
    SemanticMappingDatabase,
    clauses_from_query,
)
from sssom_pydantic.examples import EXAMPLES
from sssom_pydantic.query import Query
from tests import cases
from tests.cases import TEST_CONVERTER, TEST_METADATA

if TYPE_CHECKING:
    from sssom_pydantic.database.neo4j_database import Neo4jSemanticMappingRepository

USER = Reference(prefix="orcid", identifier="1234")


class TestUtils(unittest.TestCase):
    """Test the utility functions."""

    def test_query_functionality(self) -> None:
        """Check that all query fields are implemented."""
        for name in Query.model_fields:
            self.assertIn(name, QUERY_TO_CLAUSE)

    def test_clause_generation(self) -> None:
        """Test clause generation."""
        query = Query(query="hello")
        clauses = clauses_from_query(query)
        self.assertEqual(1, len(clauses))


class TestSQL(cases.TestRepository):
    """Test for a SQL database."""

    def setUp(self) -> None:
        """Set up the test with a SQL database."""
        self.repository = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)


class TestNeo4j(cases.TestRepository):
    """Test for a SQL database."""

    repository: Neo4jSemanticMappingRepository

    def setUp(self) -> None:
        """Set up the test with a SQL database."""
        try:
            from sssom_pydantic.database.neo4j_database import Neo4jSemanticMappingRepository
        except ImportError:
            self.skipTest("can not import neo4j")
        self.repository = Neo4jSemanticMappingRepository(
            user="neo4j",
            password="neo4jneo4j",  # noqa:S106
            uri="neo4j://localhost:7687",
        )

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.repository.drop_all()
        self.repository.driver.close()


class TestIO(unittest.TestCase):
    """Test I/O operations."""

    def test_read(self) -> None:
        """Test reading mappings from a file."""
        # FIXME when excluding columns while writing, should also exclude
        #  them from building up the prefix list
        converter = TEST_CONVERTER.get_subconverter(
            TEST_CONVERTER.get_prefixes() - {MAPPING_HASH_V1_PREFIX}
        )

        for example in EXAMPLES:
            if example.description == "reference for the mapping itself in the `record` field":
                continue
            with self.subTest(desc=example.description), tempfile.TemporaryDirectory() as tmpdir:
                mappings = [example.semantic_mapping]
                path = Path(tmpdir).joinpath("test.sssom.tsv")
                sssom_pydantic.write(mappings, path, converter=converter, metadata=TEST_METADATA)
                db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
                db.read(path, converter=converter, metadata=TEST_METADATA)

                written_path = Path(tmpdir).joinpath("test2.sssom.tsv")
                db.write(
                    written_path,
                    converter=converter,
                    metadata=TEST_METADATA,
                    exclude_columns=["record_id"],
                )
                self.assertEqual(path.read_text(), written_path.read_text())
