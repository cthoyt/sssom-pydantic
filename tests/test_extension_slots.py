"""Tests for extension slots."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from curies.vocabulary import xsd_float

import sssom_pydantic
from sssom_pydantic import ExtensionDefinition, SemanticMapping


class TestExtensionSlots(unittest.TestCase):
    """Tests for extension slots."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.tmpdir.cleanup()

    def test_extension_slot_str(self) -> None:
        """Tests for extension slots."""
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  xsd: http://www.w3.org/2001/XMLSchema#
            #mapping_set_id: https://example.org/test.tsv
            #extension_definitions:
            # - slot_name: test_slot
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	v1
        """)
        path = Path(self.tmpdir.name) / "test.tsv"
        path.write_text(expected, encoding="utf-8")
        mappings, _converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [ExtensionDefinition(slot_name="test_slot")],
            metadata.extension_definitions,
        )

        self.assertEqual(1, len(mappings))
        mapping: SemanticMapping = mappings[0]
        if mapping.extensions is None:
            raise self.fail(msg="no extensions were set")
        self.assertIn("test_slot", mapping.extensions)
        self.assertEqual("v1", mapping.extensions["test_slot"])

    def test_extension_slot_float(self) -> None:
        """Tests for extension slots."""
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  xsd: http://www.w3.org/2001/XMLSchema#
            #mapping_set_id: https://example.org/test.tsv
            #extension_definitions:
            # - slot_name: test_slot
            #   type_hint: xsd:float
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	0.11
        """)
        path = Path(self.tmpdir.name) / "test.tsv"
        path.write_text(expected, encoding="utf-8")

        mappings, _converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [ExtensionDefinition(slot_name="test_slot", type_hint=xsd_float)],
            metadata.extension_definitions,
        )
        self.assertEqual(1, len(mappings))
        mapping: SemanticMapping = mappings[0]
        if mapping.extensions is None:
            raise self.fail(msg="no extensions were set")
        self.assertIn("test_slot", mapping.extensions)
        self.assertEqual(0.11, mapping.extensions["test_slot"])
