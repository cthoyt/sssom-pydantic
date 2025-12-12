"""Test mapping API."""

import datetime
import tempfile
import unittest
from pathlib import Path

from curies import Reference
from curies.vocabulary import (
    charlie,
    lexical_matching_process,
    manual_mapping_curation,
)
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

        self.client.delete(f"/mapping/{reference.curie}")
        self.assertEqual(0, self.database.count_mappings())

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

    def test_curate_mapping(self) -> None:
        """Test curating a mapping through the API."""
        mapping_predicted = _m(justification=lexical_matching_process, confidence=1)

        response = self.client.post("/mapping", json=mapping_predicted.model_dump())
        post_reference = Reference.model_validate(response.json())

        curation_response = self.client.post(
            f"/action/curate/{post_reference.curie}",
            json={"authors": [charlie.model_dump()], "mark": "correct"},
        )
        curation_response.raise_for_status()
        curation_reference = Reference.model_validate(curation_response.json())

        get_response = self.client.get(f"/mapping/{curation_reference.curie}")
        get_response.raise_for_status()
        actual = SemanticMapping.model_validate(get_response.json())

        expected = _m(
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        expected = expected.model_copy(update={"record": self.database._hsh(expected)})
        self.assert_model_equal(expected, actual)
