"""Test JSKOS export."""

import importlib.util
import unittest

from sssom_pydantic.examples import EXAMPLES
from tests.cases import TEST_CONVERTER, TEST_METADATA


@unittest.skipUnless(importlib.util.find_spec("jskos"), reason="requires JSKOS")
class TestJSKOSExport(unittest.TestCase):
    """Test JSKOS export."""

    def text_example_output(self) -> None:
        """Test that all SSSOM examples can be converted to JSKOS."""
        from sssom_pydantic.contrib.jskos_export import from_jskos, to_jskos

        for example in EXAMPLES:
            with self.subTest(desc=example.description):
                concept = to_jskos(
                    example.semantic_mapping, converter=TEST_CONVERTER, metadata=TEST_METADATA
                )
                mappings, _, _ = from_jskos(concept)
                self.assertEqual(1, len(mappings))
                self.assertEqual(
                    example.semantic_mapping,
                    mappings[0],
                    msg="reconstitution failed",
                )
