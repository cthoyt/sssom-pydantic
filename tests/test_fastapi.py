"""Test mapping API."""

import unittest

from curies import Reference
from starlette.testclient import TestClient

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import mapping_hash_v1
from sssom_pydantic.database import SemanticMappingDatabase
from sssom_pydantic.web import get_app
from tests.cases import _m


class TestFastAPI(unittest.TestCase):
    """Test API."""

    def test_api(self) -> None:
        """Test the components of a mapping API."""
        input_mapping = _m(record=Reference(prefix="sssom", identifier="123456"))
        database = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        database.add_mapping(input_mapping)
        app = get_app(database=database)
        client = TestClient(app)

        response = client.get("/mapping/sssom:123456")
        s = SemanticMapping.model_validate(response.json())
        self.assertEqual(input_mapping, s)
