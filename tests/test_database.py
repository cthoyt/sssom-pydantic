"""Test the database."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pystow
from curies import Reference
from curies.vocabulary import manual_mapping_curation

import sssom_pydantic
from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import MAPPING_HASH_V1_PREFIX, mapping_hash_v1
from sssom_pydantic.database import (
    QUERY_TO_CLAUSE,
    FileSystemSemanticMappingRepository,
    Neo4jSemanticMappingRepository,
    SemanticMappingDatabase,
    SemanticMappingModel,
    clauses_from_query,
)
from sssom_pydantic.examples import EXAMPLES
from sssom_pydantic.query import Query
from tests import cases
from tests.cases import P1, R1, R2, TEST_CONVERTER, TEST_METADATA

USER = Reference(prefix="orcid", identifier="1234")


class TestUtils(unittest.TestCase):
    """Test the utility functions."""

    def test_query_functionality(self) -> None:
        """Check that all query fields are implemented."""
        for name in Query.model_fields:
            self.assertIn(name, QUERY_TO_CLAUSE)

    def test_clause_generation(self) -> None:
        """Test clause generation."""
        # test empty queries
        self.assertEqual([], clauses_from_query(None))
        self.assertEqual([], clauses_from_query(Query()))

        query = Query(query="hello")
        clauses = clauses_from_query(query)
        self.assertEqual(1, len(clauses))


class TestSQL(cases.TestRepository):
    """Test for a SQL database."""

    def setUp(self) -> None:
        """Set up the test with a SQL database."""
        self.repository = SemanticMappingDatabase.memory(
            semantic_mapping_hash=mapping_hash_v1, converter=TEST_CONVERTER
        )


class TestFilesystem(cases.TestRepository):
    """Test for a file-based database."""

    def setUp(self) -> None:
        """Set up the test with a SQL database."""
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name).joinpath("test.sssom.tsv")
        self.repository = FileSystemSemanticMappingRepository(self.path)
        for record in TEST_CONVERTER:
            self.repository.converter.add_record(record, merge=True)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.directory.cleanup()


@unittest.skipUnless(importlib.util.find_spec("neo4j"), "Neo4j is not installed")
class TestNeo4j(cases.TestRepository):
    """Test for a SQL database."""

    repository: Neo4jSemanticMappingRepository

    def setUp(self) -> None:
        """Set up the test with a SQL database."""
        import neo4j

        self.repository = Neo4jSemanticMappingRepository(
            user=pystow.get_config("sssom", "neo4j_username"),
            password=pystow.get_config("sssom", "neo4j_password"),
            uri="neo4j://localhost:7687",
            converter=TEST_CONVERTER,
        )
        try:
            self.repository.driver.verify_connectivity()
        except neo4j.exceptions.AuthError:
            self.skipTest("neo4j credentials are not properly configured")

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.repository.drop_all()
        self.repository.driver.close()


@unittest.skipUnless(importlib.util.find_spec("sqlmodel"), "SQLModel is required for database test")
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
                db = SemanticMappingDatabase.memory(
                    semantic_mapping_hash=mapping_hash_v1, converter=converter
                )
                db.read(path, metadata=TEST_METADATA)

                written_path = Path(tmpdir).joinpath("test2.sssom.tsv")
                db.write(
                    written_path,
                    converter=converter,
                    metadata=TEST_METADATA,
                    exclude_columns=["record_id"],
                )
                self.assertEqual(path.read_text(), written_path.read_text())


@unittest.skipUnless(importlib.util.find_spec("sqlmodel"), "SQLModel is required for database test")
class TestDatabase(unittest.TestCase):
    """Tests for the database."""

    def test_name_io(self) -> None:
        """Test that names make it to and from database models."""
        mapping = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=manual_mapping_curation,
        )
        database_mapping = SemanticMappingModel.from_semantic_mapping(
            mapping, converter=TEST_CONVERTER
        )
        self.assertEqual(R1.name, database_mapping.subject_name)
        self.assertEqual(R2.name, database_mapping.object_name)

    def test_round_trip_database(self) -> None:
        """Test database roundtrip."""
        from sqlmodel import Session, SQLModel, create_engine, select

        for example in EXAMPLES:
            with self.subTest(desc=example.description):
                orm_model = SemanticMappingModel.from_semantic_mapping(
                    example.semantic_mapping, converter=TEST_CONVERTER
                )
                engine = create_engine("sqlite:///:memory:")
                SQLModel.metadata.create_all(engine)

                with Session(engine) as session:
                    session.add(orm_model)
                    session.commit()

                with Session(engine) as session:
                    statement = select(SemanticMappingModel)
                    orm_models = session.exec(statement).all()
                    self.assertEqual(1, len(orm_models))
                    self.assertEqual(example.semantic_mapping, orm_models[0].to_semantic_mapping())
