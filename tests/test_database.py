"""Test the database."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pystow
from curies import Reference
from curies.vocabulary import manual_mapping_curation

from sssom_pydantic import SemanticMapping
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
from tests.cases import P1, R1, R2, TEST_CONVERTER

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

    repository: SemanticMappingDatabase

    def setUp(self) -> None:
        """Set up the test with a SQL database."""
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name).joinpath("test.db")
        self.repository = SemanticMappingDatabase.from_connection(
            connection=f"sqlite:///{path}",
            converter=TEST_CONVERTER,
        )

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.directory.cleanup()

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
                    self.assert_model_equal(
                        example.semantic_mapping, orm_models[0].to_semantic_mapping()
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

    def test_queries(self) -> None:
        """Skip query tests."""
        raise self.skipTest("queries test is implemented for neo4j")
