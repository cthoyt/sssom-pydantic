"""Test Wikidata conversion."""

import getpass
import unittest
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import requests.exceptions
from curies import Converter, Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from quickstatements_client import EntityQualifier, TextLine, TextQualifier

from sssom_pydantic import SemanticMapping
from sssom_pydantic.contrib.wikidata import get_quickstatements_lines
from sssom_pydantic.contrib.wikidata.query import (
    get_equivalent_properties_by_ids,
    get_equivalent_property_mappings,
    get_exact_matches_by_ids,
    get_mappings_by_property,
    get_property_matches_by_ids,
)
from tests.cases import TEST_MAPPING_SET, TEST_MAPPING_SET_ID, TEST_PREFIX_MAP

CHARLIE_WD = "Q47475003"
TEST_CONVERTER = Converter.from_prefix_map(TEST_PREFIX_MAP)
TEST_CONVERTER.add_prefix("ex", "https://example.org/")

if getpass.getuser() == "cthoyt":
    TIMEOUT = 60
else:
    TIMEOUT = 10

T = TypeVar("T")
P = ParamSpec("P")


def skip_on_wikidata_timeout(func: Callable[P, T]) -> Callable[P, T]:
    """Decorate a function to skip."""

    @wraps(func)
    def _wrapped_func(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except OSError:
            raise unittest.SkipTest("wikidata SPARQL timed out 🤷") from None

    return _wrapped_func


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

    @skip_on_wikidata_timeout
    def test_lookup_mapping_in_property(self) -> None:
        """Test looking up existing mappings."""
        res = get_property_matches_by_ids(
            wikidata_ids=["Q47512"],
            prefix_to_wikidata={
                "chebi": "P683",
                "pdb": "P638",  # exists, but not for this entry
                "bioregistry": None,  # does not exist
            },
        )
        self.assertEqual({"Q47512": {Reference(prefix="chebi", identifier="15366")}}, res)

    @skip_on_wikidata_timeout
    def test_lookup_mapping_in_exact_match(self) -> None:
        """Test looking up existing mappings."""
        # https://www.wikidata.org/wiki/Q128700
        # http://purl.obolibrary.org/obo/GO_0005618
        converter = Converter.from_prefix_map({"GO": "http://purl.obolibrary.org/obo/GO_"})
        res = get_exact_matches_by_ids(
            wikidata_ids=["Q128700"], converter=converter, timeout=TIMEOUT
        )
        self.assertEqual({"Q128700": {Reference(prefix="GO", identifier="0005618")}}, res)

    @skip_on_wikidata_timeout
    def test_lookup_mapping_in_equivalent_property(self) -> None:
        """Test looking up existing mappings."""
        converter = Converter.from_prefix_map({"owl": "http://www.w3.org/2002/07/owl#"})
        res = get_equivalent_properties_by_ids(
            wikidata_ids=["P1628"], converter=converter, timeout=TIMEOUT
        )
        self.assertEqual({"P1628": {Reference(prefix="owl", identifier="equivalentProperty")}}, res)

    @skip_on_wikidata_timeout
    def test_get_equivalent_property_mappings(self) -> None:
        """Test getting equivalent property mappings."""
        mappings = get_equivalent_property_mappings(timeout=TIMEOUT)
        self.assertLessEqual(500, len(mappings))

    @skip_on_wikidata_timeout
    def test_get_property(self) -> None:
        """Test looking up mappings by a property.

        P12357 (bindingDB identifier) was chosen because there are only a small number
        of mappings in Wikidata (<10) and therefore the query should be fast.
        """
        mappings = list(get_mappings_by_property("P12357", timeout=TIMEOUT))
        self.assertLessEqual(4, len(mappings))
