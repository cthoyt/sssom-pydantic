"""Tests for consuming OntoPortal mappings."""

import json
import unittest
from pathlib import Path

import curies
from curies import Reference
from curies.vocabulary import exact_match, lexical_matching_process, mapping_chaining

from sssom_pydantic import MappingTool, SemanticMapping
from sssom_pydantic.contrib.ontoportal import _process

HERE = Path(__file__).parent.resolve()
LOOM_EXAMPLE_PATH = HERE.joinpath("ontoportal_loom_example.json")
CUI_EXAMPLE_PATH = HERE.joinpath("ontoportal_cui_example.json")
SAME_URI_EXAMPLE_PATH = HERE.joinpath("ontoportal_same_uri_example.json")


class TestBioportal(unittest.TestCase):
    """Test processing OntoPortal mappings."""

    def test_process_loom(self) -> None:
        """Test processing OntoPortal mappings."""
        converter = curies.Converter.from_prefix_map(
            {
                "OMRE": "http://purl.obolibrary.org/obo/ogms/OMRE_",
                "SNOMEDCT": "http://purl.bioontology.org/ontology/SNOMEDCT/",
            }
        )
        data = json.loads(LOOM_EXAMPLE_PATH.read_text())
        mapping = _process(data, converter)
        self.assertIsNotNone(mapping)
        expected = SemanticMapping(
            subject=Reference(prefix="OMRE", identifier="0000023"),
            predicate=exact_match,
            object=Reference(prefix="SNOMEDCT", identifier="3415004"),
            justification=lexical_matching_process,
            mapping_tool=MappingTool(name="LOOM"),
        )
        self.assertEqual(expected, mapping)

    def test_process_cui(self) -> None:
        """Test processing OntoPortal mappings."""
        converter = curies.Converter.from_prefix_map(
            {
                "ATC": "http://purl.bioontology.org/ontology/ATC/",
                "SNOMEDCT": "http://purl.bioontology.org/ontology/SNOMEDCT/",
            }
        )
        data = json.loads(CUI_EXAMPLE_PATH.read_text())
        mapping = _process(data, converter)
        self.assertIsNotNone(mapping)
        expected = SemanticMapping(
            object=Reference(prefix="ATC", identifier="N05AX15"),
            predicate=exact_match,
            subject=Reference(prefix="SNOMEDCT", identifier="715295006"),
            justification=mapping_chaining,
            mapping_tool=None,
        )
        self.assertEqual(expected, mapping)

    def test_process_same_uri(self) -> None:
        """Test processing OntoPortal mappings."""
        converter = curies.Converter()
        data = json.loads(SAME_URI_EXAMPLE_PATH.read_text())
        mapping = _process(data, converter)
        self.assertIsNone(mapping)
