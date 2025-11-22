"""Tests for consuming OntoPortal mappings."""

import json
import unittest
from pathlib import Path

import curies
from curies import Reference
from curies.vocabulary import exact_match, lexical_matching_process

from sssom_pydantic import MappingTool, SemanticMapping
from sssom_pydantic.contrib.ontoportal import _process

HERE = Path(__file__).parent.resolve()
PATH = HERE.joinpath("ontoportal_example.json")


class TestBioportal(unittest.TestCase):
    """Test processing OntoPortal mappings."""

    def test_process(self) -> None:
        """Test processing OntoPortal mappings."""
        converter = curies.Converter.from_prefix_map(
            {
                "OMRE": "http://purl.obolibrary.org/obo/ogms/OMRE_",
                "SNOMEDCT": "http://purl.bioontology.org/ontology/SNOMEDCT/",
            }
        )
        data = json.loads(PATH.read_text())
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
