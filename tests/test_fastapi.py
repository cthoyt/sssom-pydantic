"""Test mapping API."""

import tempfile
import unittest
from pathlib import Path

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

    def test_api(self) -> None:
        """Test the components of a mapping API."""
        expected = _m()

        with tempfile.TemporaryDirectory() as tmpdir:
            # this can't be memory because of weird thread-safe stuff
            path = Path(tmpdir).joinpath("test.db")

            database = SemanticMappingDatabase.from_connection(
                connection=f"sqlite:///{path}",
                semantic_mapping_hash=mapping_hash_v1,
            )
            database.add_mapping(expected)

            reference = database._hsh(expected)
            self.assertIsNotNone(database.get_mapping(reference))

            app = get_app(database=database)
            client = TestClient(app)

            response = client.get(f"/mapping/{reference.curie}")
            response.raise_for_status()
            response_json = response.json()
            actual = SemanticMapping.model_validate(response_json)
            self.assert_model_equal(_m(record=reference), actual)
