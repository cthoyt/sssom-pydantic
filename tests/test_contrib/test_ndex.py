"""Test NDEx integration."""

import importlib.util
import unittest

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

        mappings: list[SemanticMapping] = [_m()]
        metadata = MappingSet(mapping_set_id="https://example.org")
        cx = get_nice_cx(mappings, metadata)
        self.assertIsInstance(cx, ndex2.NiceCXNetwork)
