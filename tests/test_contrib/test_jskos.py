"""Test JSKOS export."""

import importlib.util
import unittest

from sssom_pydantic.examples import EXAMPLES
from tests.cases import TEST_CONVERTER, TEST_METADATA

JSKOS_IMPLEMENTED = {
    "comment",
}


@unittest.skipUnless(importlib.util.find_spec("jskos"), reason="requires JSKOS")
class TestJSKOSExport(unittest.TestCase):
    """Test JSKOS export."""

    def test_examples(self) -> None:
        """Test that all SSSOM examples can be converted to JSKOS."""
        from sssom_pydantic.contrib.jskos_export import from_jskos, to_jskos

        for example in EXAMPLES:
            with self.subTest(desc=example.description):
                concept = to_jskos(
                    example.semantic_mapping, converter=TEST_CONVERTER, metadata=TEST_METADATA
                )
                if example.description not in JSKOS_IMPLEMENTED:
                    # some parts of SSSOM aren't represented in JSKOS
                    # yet, or don't get exported from sssom-js, so skip
                    # ones that aren't explicitly working already
                    continue
                mappings = from_jskos(concept, TEST_CONVERTER)
                self.assertEqual(1, len(mappings))
                self.assertEqual(
                    example.semantic_mapping.model_dump(exclude_none=True, exclude_unset=True),
                    mappings[0].model_dump(exclude_none=True, exclude_unset=True),
                    msg=f"reconstitution failed\n\n"
                    f"{concept.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)}",
                )
