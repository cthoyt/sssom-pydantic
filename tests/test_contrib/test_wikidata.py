"""Test Wikidata conversion."""

import unittest

from curies import Reference
from curies.vocabulary import exact_match, manual_mapping_curation
from quickstatements_client import EntityQualifier, TextLine, TextQualifier

from sssom_pydantic import SemanticMapping
from sssom_pydantic.contrib.wikidata import get_quickstatements_lines
from tests.cases import TEST_CONVERTER, TEST_MAPPING_SET, TEST_MAPPING_SET_ID


class TestWikidata(unittest.TestCase):
    """Test Wikidata conversion."""

    def test_get_lines(self) -> None:
        """Test getting lines."""
        mapping = SemanticMapping(
            subject=Reference(prefix="wikidata", identifier="Q47512"),
            predicate=exact_match,
            object=Reference(prefix="chebi", identifier="15366"),
            justification=manual_mapping_curation,
        )
        lines = get_quickstatements_lines(
            [mapping],
            TEST_CONVERTER,
            TEST_MAPPING_SET,
            wikidata_id_to_exact={},
            wikidata_id_to_references={},
            orcid_to_wikidata={},
        )
        self.assertEqual(1, len(lines))
        expected = TextLine(
            subject="Q47512",
            predicate="P683",
            target="15366",
            qualifiers=[
                TextQualifier(predicate="S854", target=TEST_MAPPING_SET_ID),
                EntityQualifier(predicate="S4390", target="Q39893449"),
            ],
        )
        self.assertEqual(expected, lines[0])
