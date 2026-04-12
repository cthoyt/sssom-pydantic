"""Tests for extension slots."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

import sssom_pydantic
from sssom_pydantic.api import ExtensionDefinition


class TestExtensionSlots(unittest.TestCase):
    """Tests for extension slots."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.tmpdir.cleanup()

    def test_extension_slot(self) -> None:
        """Tests for extension slots."""
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            #extension_definitions:
            # - slot_name: test_slot
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	v1
            mesh:C000090	skos:exactMatch	chebi:28647	semapv:ManualMappingCuration	v2
        """)
        path = Path(self.tmpdir.name) / "test.tsv"
        path.write_text(expected, encoding="utf-8")

        _mappings, _converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [
                ExtensionDefinition(
                    slot_name="test_slot",
                )
            ],
            metadata.extension_definitions,
        )
