"""Test mapping API."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from sssom_pydantic.api import mapping_hash_v1
from sssom_pydantic.database import FileSystemSemanticMappingRepository, SemanticMappingDatabase
from sssom_pydantic.web import get_app
from tests import cases


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "fastapi not installed")
class TestInstantiation(unittest.TestCase):
    """Test instantiation."""

    def test_instantiation(self) -> None:
        """Test instantiation without passing an explicit database."""
        from fastapi import FastAPI

        app = get_app()
        self.assertIsInstance(app, FastAPI)


class TestSQLRepository(cases.TestFastAPI):
    """Test the SQL repository."""

    def setUp(self) -> None:
        """Set up the test case with a database."""
        from starlette.testclient import TestClient

        self.td = tempfile.TemporaryDirectory()
        self.path = Path(self.td.name).joinpath("test.db")
        self.repository = SemanticMappingDatabase.from_connection(
            connection=f"sqlite:///{self.path}",
            semantic_mapping_hash=mapping_hash_v1,
        )
        self.app = get_app(repository=self.repository)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.td.cleanup()


class TestFileSystemRepository(cases.TestFastAPI):
    """Test the SQL repository."""

    def setUp(self) -> None:
        """Set up the test case with a database."""
        from starlette.testclient import TestClient

        self.td = tempfile.TemporaryDirectory()
        path = Path(self.td.name).joinpath("test.sssom.tsv")
        self.repository = FileSystemSemanticMappingRepository(path=path)
        self.app = get_app(repository=self.repository)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.td.cleanup()
