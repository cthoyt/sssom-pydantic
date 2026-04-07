"""Test JSKOS export."""

import importlib.util
import unittest

from sssom_pydantic.examples import EXAMPLES
from tests import cases
from tests.cases import TEST_CONVERTER, TEST_METADATA

JSKOS_IMPLEMENTED = {
    "comment",
}


@unittest.skipUnless(importlib.util.find_spec("jskos"), reason="requires JSKOS")
class TestJSKOSExport(cases.MappingTestCaseMixin):
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
                self.assert_model_equal(
                    example.semantic_mapping,
                    mappings[0],
                    msg=f"reconstitution failed\n\n"
                    f"{concept.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)}",
                    skip_name_check=True,
                )
