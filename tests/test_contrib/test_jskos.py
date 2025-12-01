"""Test JSKOS export."""

import unittest

from curies import Converter, Reference
from curies.vocabulary import exact_match, manual_mapping_curation
from jskos import Concept

from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.contrib.jskos_export import mapping_set_to_jskos


class TestJSKOSExport(unittest.TestCase):
    """Test JSKOS export."""

    def test_jskos(self) -> None:
        """Test JSKOS export."""
        converter = Converter.from_prefix_map(
            {
                "skos": "http://www.w3.org/2004/02/skos/core#",
                "x": "https://example.org/",
                "semapv": "https://w3id.org/semapv/vocab/",
            }
        )
        mapping_set_id = "https://example.org/mappings"
        license_uri = "https://creativecommons.org/licenses/by/4.0/"
        mapping_set = MappingSet(id=mapping_set_id)
        mapping = SemanticMapping(
            subject=Reference(prefix="x", identifier="1"),
            predicate=exact_match,
            object=Reference(prefix="x", identifier="1"),
            justification=manual_mapping_curation,
        )
        d = {
            "license": [{"uri": license_uri}],
            "uri": mapping_set_id,
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
        self.assertEqual(
            expected.model_dump(exclude_none=True, exclude_unset=True),
            mapping_set_to_jskos([mapping], converter, mapping_set).model_dump(
                exclude_unset=True, exclude_none=True
            ),
        )
