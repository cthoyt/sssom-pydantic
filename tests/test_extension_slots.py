"""Tests for extension slots."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from curies import Reference
from curies.vocabulary import xsd_float, xsd_integer

import sssom_pydantic
from sssom_pydantic import ExtensionDefinition, SemanticMapping
from sssom_pydantic.api import SSSOM_INVALID_CURIE_PREFIX
from sssom_pydantic.models import Slot


class TestExtensionSlots(unittest.TestCase):
    """Tests for extension slots."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.tmpdir.cleanup()

    def _get_path(self, *args: str) -> Path:
        return self.directory.joinpath(*args)

    def test_extension_slot_str(self) -> None:
        """Tests for extension slots."""
        start = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  xsd: http://www.w3.org/2001/XMLSchema#
            #mapping_set_id: https://example.org/test.tsv
            #extension_definitions:
            #- slot_name: test_slot
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	v1
        """)
        # add explicit type
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  xsd: http://www.w3.org/2001/XMLSchema#
            #mapping_set_id: https://example.org/test.tsv
            #extension_definitions:
            #- slot_name: test_slot
            #  type_hint: xsd:string
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	v1
        """)
        path = self._get_path("test.tsv")
        path.write_text(start, encoding="utf-8")
        mappings, converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [ExtensionDefinition.default("test_slot")],
            metadata.extension_definitions,
        )

        self.assertEqual(1, len(mappings))
        mapping = mappings[0]

        if mapping.extensions is None:
            raise self.fail()
        self.assertIn("test_slot", mapping.extensions)
        self.assertEqual(
            Slot(
                predicate=Reference(prefix=SSSOM_INVALID_CURIE_PREFIX, identifier="test_slot"),
                value="v1",
            ),
            mapping.extensions["test_slot"],
        )

        rr_path = self._get_path("test-2.tsv")
        sssom_pydantic.write(mappings, rr_path, converter=converter, metadata=metadata)
        self.assertEqual(expected, rr_path.read_text())

    def test_extension_slot_int(self) -> None:
        """Test an integer extension slot."""
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  xsd: http://www.w3.org/2001/XMLSchema#
            #mapping_set_id: https://example.org/test.tsv
            #extension_definitions:
            #- slot_name: test_slot_int
            #  type_hint: xsd:integer
            subject_id	predicate_id	object_id	mapping_justification	test_slot_int
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	15
        """)
        path = self._get_path("test.tsv")
        path.write_text(expected, encoding="utf-8")

        mappings, converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [ExtensionDefinition.default("test_slot_int", type_hint=xsd_integer)],
            metadata.extension_definitions,
        )
        self.assertEqual(1, len(mappings))
        mapping: SemanticMapping = mappings[0]
        if mapping.extensions is None:
            raise self.fail(msg="no extensions were set")
        self.assertIn("test_slot_int", mapping.extensions)
        self.assertEqual(
            Slot(
                predicate=Reference(prefix=SSSOM_INVALID_CURIE_PREFIX, identifier="test_slot_int"),
                value=15,
            ),
            mapping.extensions["test_slot_int"],
        )

        rr_path = self._get_path("test-2.tsv")
        sssom_pydantic.write(mappings, rr_path, converter=converter, metadata=metadata)
        self.assertEqual(expected, rr_path.read_text())

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
            #- slot_name: test_slot
            #  type_hint: xsd:float
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	0.11
        """)
        path = Path(self.tmpdir.name) / "test.tsv"
        path.write_text(expected, encoding="utf-8")

        mappings, converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [ExtensionDefinition.default("test_slot", type_hint=xsd_float)],
            metadata.extension_definitions,
        )
        self.assertEqual(1, len(mappings))
        mapping: SemanticMapping = mappings[0]
        if mapping.extensions is None:
            raise self.fail(msg="no extensions were set")
        self.assertIn("test_slot", mapping.extensions)
        self.assertEqual(
            Slot(
                predicate=Reference(prefix=SSSOM_INVALID_CURIE_PREFIX, identifier="test_slot"),
                value=0.11,
            ),
            mapping.extensions["test_slot"],
        )

        rr_path = self._get_path("test-2.tsv")
        sssom_pydantic.write(mappings, rr_path, converter=converter, metadata=metadata)
        self.assertEqual(expected, rr_path.read_text())

    def test_extension_slot_curie(self) -> None:
        """Tests for extension slots."""
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  ex: https://example.org/
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  sssom: https://w3id.org/sssom/
            #mapping_set_id: https://example.org/test.tsv
            #extension_definitions:
            #- slot_name: test_slot
            #  type_hint: sssom:curie
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	ex:1234567
        """)
        path = Path(self.tmpdir.name) / "test.tsv"
        path.write_text(expected, encoding="utf-8")

        mappings, converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [
                ExtensionDefinition.default(
                    slot_name="test_slot", type_hint=Reference.from_curie("sssom:curie")
                )
            ],
            metadata.extension_definitions,
        )
        self.assertEqual(1, len(mappings))
        mapping: SemanticMapping = mappings[0]
        if mapping.extensions is None:
            raise self.fail(msg="no extensions were set")
        self.assertIn("test_slot", mapping.extensions)
        self.assertEqual(
            Slot(
                predicate=Reference(prefix=SSSOM_INVALID_CURIE_PREFIX, identifier="test_slot"),
                value=Reference(prefix="ex", identifier="1234567"),
            ),
            mapping.extensions["test_slot"],
        )

        rr_path = self._get_path("test-2.tsv")
        sssom_pydantic.write(mappings, rr_path, converter=converter, metadata=metadata)
        self.assertEqual(expected, rr_path.read_text())

    @unittest.skip(reason="multivalued isn't in SSSOM yet")
    def test_extension_slot_str_multivalued(self) -> None:
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
            #   multivalued: true
            subject_id	predicate_id	object_id	mapping_justification	test_slot
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	v1
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	v1|v2
        """)
        path = Path(self.tmpdir.name) / "test.tsv"
        path.write_text(expected, encoding="utf-8")
        mappings, _converter, metadata = sssom_pydantic.read(path)
        self.assertEqual(
            [ExtensionDefinition.default("test_slot")],
            metadata.extension_definitions,
        )

        self.assertEqual(3, len(mappings))
        self.assertIsNone(mappings[0].extensions)

        if mappings[1].extensions is None:
            raise self.fail(msg="no extensions were set")
        self.assertIn("test_slot", mappings[1].extensions)
        self.assertEqual(["v1"], mappings[1].extensions["test_slot"])

        if mappings[2].extensions is None:
            raise self.fail(msg="no extensions were set")
        self.assertIn("test_slot", mappings[2].extensions)
        self.assertEqual(["v1", "v2"], mappings[2].extensions["test_slot"])
