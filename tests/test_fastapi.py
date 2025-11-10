"""Test mapping API."""

import unittest

from curies import Reference
from starlette.testclient import TestClient

from sssom_pydantic import SemanticMapping
from sssom_pydantic.web import get_app, DictController
from tests.cases import _m


class TestFastAPI(unittest.TestCase):
    """Test API."""

    def test_api(self) -> None:
        """Test the components of a mapping API."""
        input_mapping = _m(record=Reference(prefix="sssom", identifier="123456"))
        mappings = [input_mapping]
        controller = DictController(mappings)
        app = get_app(controller)
        client = TestClient(app)

        response = client.get("/mapping/sssom:123456")
        s = SemanticMapping.model_validate(response.json())
        self.assertEqual(input_mapping, s)
