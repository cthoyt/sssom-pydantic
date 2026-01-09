"""Test Wikidata conversion."""

import unittest

import requests.exceptions
from curies import Converter, Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from quickstatements_client import EntityQualifier, TextLine, TextQualifier

from sssom_pydantic import SemanticMapping
from sssom_pydantic.contrib.wikidata import (
    _get_wikidata_to_exact_matches,
    _get_wikidata_to_property_matches,
    get_quickstatements_lines,
)
from tests.cases import TEST_MAPPING_SET, TEST_MAPPING_SET_ID, TEST_PREFIX_MAP

CHARLIE_WD = "Q47475003"
TEST_CONVERTER = Converter.from_prefix_map(TEST_PREFIX_MAP)
TEST_CONVERTER.add_prefix("ex", "https://example.org/")


class TestWikidata(unittest.TestCase):
    """Test Wikidata conversion."""

    def test_get_lines(self) -> None:
        """Test getting lines."""
        for mapping, line in [
            (
                SemanticMapping(
                    subject=Reference(prefix="wikidata", identifier="Q47512"),
                    predicate=exact_match,
                    object=Reference(prefix="chebi", identifier="15366"),
                    justification=manual_mapping_curation,
                ),
                TextLine(
                    subject="Q47512",
                    predicate="P683",
                    target="15366",
                    qualifiers=[
                        EntityQualifier(predicate="S4390", target="Q39893449"),
                        TextQualifier(predicate="S854", target=TEST_MAPPING_SET_ID),
                    ],
                ),
            ),
            (
                SemanticMapping(
                    subject=Reference(prefix="wikidata", identifier="Q47512"),
                    predicate=exact_match,
                    object=Reference(prefix="chebi", identifier="15366"),
                    justification=manual_mapping_curation,
                    authors=[charlie],
                    license="CC-BY-4.0",
                ),
                TextLine(
                    subject="Q47512",
                    predicate="P683",
                    target="15366",
                    qualifiers=[
                        EntityQualifier(predicate="S275", target="Q20007257"),
                        EntityQualifier(predicate="S4390", target="Q39893449"),
                        EntityQualifier(predicate="S50", target=CHARLIE_WD),
                        TextQualifier(predicate="S854", target=TEST_MAPPING_SET_ID),
                    ],
                ),
            ),
            (
                SemanticMapping(
                    subject=Reference(prefix="wikidata", identifier="Q902623"),
                    predicate=exact_match,
                    object=Reference(prefix="ex", identifier="chebi"),
                    justification=manual_mapping_curation,
                ),
                TextLine(
                    subject="Q902623",
                    predicate="P2888",
                    target="https://example.org/chebi",
                    qualifiers=[
                        EntityQualifier(predicate="S4390", target="Q39893449"),
                        TextQualifier(predicate="S854", target=TEST_MAPPING_SET_ID),
                    ],
                ),
            ),
        ]:
            with self.subTest():
                try:
                    lines = get_quickstatements_lines(
                        [mapping],
                        converter=TEST_CONVERTER,
                        metadata=TEST_MAPPING_SET,
                        wikidata_id_to_exact={},
                        wikidata_id_to_references={},
                        orcid_to_wikidata={charlie.identifier: CHARLIE_WD},
                    )
                except requests.exceptions.ReadTimeout:
                    continue
                else:
                    self.assertEqual(1, len(lines))
                    self.assertEqual(line, lines[0])

    def test_lookup_mapping_in_property(self) -> None:
        """Test looking up existing mappings."""
        try:
            res = _get_wikidata_to_property_matches(
                wikidata_ids=["Q47512"],
                prefix_to_wikidata={
                    "chebi": "P683",
                    "pdb": "P638",  # exists, but not for this entry
                    "bioregistry": None,  # does not exist
                },
            )
        except requests.exceptions.ReadTimeout:
            raise unittest.skip("wikidata SPARQL is not available") from None
        else:
            self.assertEqual({"Q47512": {Reference(prefix="chebi", identifier="15366")}}, res)

    def test_lookup_mapping_in_exact_match(self) -> None:
        """Test looking up existing mappings."""
        # https://www.wikidata.org/wiki/Q128700
        # http://purl.obolibrary.org/obo/GO_0005618
        converter = Converter.from_prefix_map({"GO": "http://purl.obolibrary.org/obo/GO_"})
        try:
            res = _get_wikidata_to_exact_matches(wikidata_ids=["Q128700"], converter=converter)
        except requests.exceptions.ReadTimeout:
            raise unittest.skip("wikidata SPARQL is not available") from None
        else:
            self.assertEqual({"Q128700": {Reference(prefix="GO", identifier="0005618")}}, res)
