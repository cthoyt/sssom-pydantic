"""Test NDEx integration."""

import importlib.util
import unittest

import curies

from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.contrib.ndex import get_nice_cx
from tests.cases import _m


@unittest.skipUnless(
    importlib.util.find_spec("ndex2"), reason="NDEx Python package (ndex2) is not installed"
)
class TestNDEx(unittest.TestCase):
    """Test NDEx integration."""

    def test_cx(self) -> None:
        """Test generating CX from mappings."""
        import ndex2

        pm = {
            "mesh": "https://example.org/mesh:",
            "semapv": "https://example.org/semapv:",
            "orcid": "https://orcid.org/",
            "skos": "https://example.org/skos:",
            "chebi": "https://example.org/chebi:",
        }
        mappings: list[SemanticMapping] = [_m()]
        metadata = MappingSet(mapping_set_id="https://example.org")
        converter = curies.Converter.from_prefix_map(pm)
        cx = get_nice_cx(mappings, metadata, converter=converter)
        self.assertIsInstance(cx, ndex2.NiceCXNetwork)
        self.assertEqual(pm, cx.get_context())
        self.assertEqual(1, len(cx.edges))
