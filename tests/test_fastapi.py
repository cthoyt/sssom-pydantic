"""Test mapping API."""

import tempfile
import unittest
from pathlib import Path

from curies import Reference
from pydantic import BaseModel
from starlette.testclient import TestClient

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import mapping_hash_v1
from sssom_pydantic.database import SemanticMappingDatabase
from sssom_pydantic.web import get_app
from tests.cases import _m


class TestFastAPI(unittest.TestCase):
    """Test API."""

    def assert_model_equal(self, expected: BaseModel, actual: BaseModel) -> None:
        """Assert that two models are equal."""
        self.assertEqual(
            expected.model_dump(exclude_unset=True, exclude_none=True),
            actual.model_dump(exclude_unset=True, exclude_none=True),
        )

    def setUp(self) -> None:
        """Set up the test case with a database."""
        self.td = tempfile.TemporaryDirectory()
        self.path = Path(self.td.name).joinpath("test.db")
        self.database = SemanticMappingDatabase.from_connection(
            connection=f"sqlite:///{self.path}",
            semantic_mapping_hash=mapping_hash_v1,
        )
        self.app = get_app(database=self.database)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.td.cleanup()

    def test_get_mapping(self) -> None:
        """Test getting a mapping from the API."""
        expected = _m()
        self.database.add_mapping(expected)

        reference = self.database._hsh(expected)
        self.assertIsNotNone(self.database.get_mapping(reference))

        response = self.client.get(f"/mapping/{reference.curie}")
        response.raise_for_status()
        response_json = response.json()
        actual = SemanticMapping.model_validate(response_json)
        self.assert_model_equal(_m(record=reference), actual)

    def test_post_mapping(self) -> None:
        """Test posting a mapping to the API."""
        mapping = _m()

        reference = self.database._hsh(mapping)
        self.assertEqual(0, self.database.count_mappings())

        response = self.client.post("/mapping", json=mapping.model_dump())
        response.raise_for_status()

        actual = Reference.model_validate(response.json())
        self.assertEqual(reference, actual)

        self.assertIsNotNone(self.database.get_mapping(reference))
