"""Test JSKOS export."""

import importlib.util
import unittest
from typing import TYPE_CHECKING

from curies import Converter, Reference
from curies.vocabulary import exact_match, manual_mapping_curation
from pydantic import BaseModel

from sssom_pydantic import SemanticMapping
from sssom_pydantic.examples import EXAMPLES
from tests.cases import TEST_CONVERTER, TEST_METADATA

if TYPE_CHECKING:
    pass


@unittest.skipUnless(importlib.util.find_spec("jskos"), reason="requires JSKOS")
class TestJSKOSExport(unittest.TestCase):
    """Test JSKOS export."""

    def assert_model_equal(self, expected: BaseModel, actual: BaseModel) -> None:
        """Assert two models are equal."""
        self.assertEqual(
            expected.model_dump(exclude_none=True, exclude_unset=True),
            actual.model_dump(exclude_unset=True, exclude_none=True),
        )

    def test_jskos(self) -> None:
        """Test JSKOS export."""
        from jskos import Concept

        from sssom_pydantic.contrib.jskos_export import mapping_set_to_jskos

        converter = Converter.from_prefix_map(
            {
                "skos": "http://www.w3.org/2004/02/skos/core#",
                "x": "https://example.org/",
                "semapv": "https://w3id.org/semapv/vocab/",
            }
        )
        license_uri = "https://creativecommons.org/licenses/by/4.0/"
        mapping = SemanticMapping(
            subject=Reference(prefix="x", identifier="1"),
            predicate=exact_match,
            object=Reference(prefix="x", identifier="1"),
            justification=manual_mapping_curation,
        )
        expected_jskos_record = {
            "license": [{"uri": license_uri}],
            "uri": TEST_METADATA.mapping_set_id,
            "mappings": [
                {
                    "type": ["http://www.w3.org/2004/02/skos/core#exactMatch"],
                    "from": {"memberSet": [{"uri": "http://example.org/1"}]},
                    "to": {"memberSet": [{"uri": "http://example.org/2"}]},
                    "justification": "https://w3id.org/semapv/vocab/ManualMappingCuration",
                }
            ],
        }
        expected = Concept.model_validate(expected_jskos_record)
        self.assert_model_equal(
            expected, mapping_set_to_jskos([mapping], converter, TEST_METADATA.process(converter))
        )

    def test_all_jskos(self) -> None:
        """Test converting examples to JSKOS then back."""
        from sssom_pydantic.contrib.jskos_export import mapping_to_jskos_oracle

        for example in EXAMPLES:
            with self.subTest(desc=example.description):
                mapping_to_jskos_oracle(
                    example.semantic_mapping, metadata=TEST_METADATA, converter=TEST_CONVERTER
                )
