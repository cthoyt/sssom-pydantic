"""Test JSKOS export."""

import unittest

from curies import Converter, Reference
from curies.vocabulary import exact_match, manual_mapping_curation
from jskos import Concept

from sssom_pydantic import SemanticMapping
from sssom_pydantic.contrib.jskos_export import mapping_to_jskos


class TestJSKOSExport(unittest.TestCase):
    """Test JSKOS export."""

    def test_jskos(self) -> None:
        """Test JSKOS export."""
        converter = Converter()
        mapping = SemanticMapping(
            subject=Reference(prefix="x", identifier="1"),
            predicate=exact_match,
            object=Reference(prefix="x", identifier="1"),
            justification=manual_mapping_curation,
        )
        d = {
            "license": [{"uri": "https://creativecommons.org/licenses/by/4.0/"}],
            "uri": "https://example.org/mappings",
            "mappings": [
                {
                    "type": ["http://www.w3.org/2004/02/skos/core#exactMatch"],
                    "from": {"memberSet": [{"uri": "http://example.org/1"}]},
                    "to": {"memberSet": [{"uri": "http://example.org/2"}]},
                    "justification": "https://w3id.org/semapv/vocab/ManualMappingCuration",
                }
            ],
        }
        expected = Concept.model_validate(d)
        self.assertEqual(expected, mapping_to_jskos(mapping, converter))
