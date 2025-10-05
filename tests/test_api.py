"""Test API."""

from __future__ import annotations

import importlib.util
import tempfile
import types
import typing
import unittest
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pystow
from curies import NamedReference, Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from pystow.utils import download

import sssom_pydantic
import sssom_pydantic.io
from sssom_pydantic import Record, write_unprocessed
from sssom_pydantic.api import MappingSet, SemanticMapping
from sssom_pydantic.constants import MULTIVALUED
from sssom_pydantic.io import _chomp_frontmatter, lint

if TYPE_CHECKING:
    import linkml_runtime

S1 = Reference(prefix="p1", identifier="i1")
O1 = Reference(prefix="p2", identifier="ia")

PM = {
    "p1": "https://example.com/p1#",
    "p2": "https://example.com/p2#",
}
SSSOM_SCHEMA_URL = "https://github.com/mapping-commons/sssom/raw/refs/heads/master/src/sssom_schema/schema/sssom_schema.yaml"
CACHE_SSSOM_SCHEMA = False


@unittest.skipUnless(
    importlib.util.find_spec("linkml_runtime"),
    reason="This test requires both the LinkML runtime for accessing the SSSOM schema",
)
class TestSchema(unittest.TestCase):
    """Tests against the SSSOM schema."""

    view: typing.ClassVar[linkml_runtime.SchemaView]
    mapping_slots: typing.ClassVar[set[str]]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the class with a schema view."""
        from linkml_runtime import SchemaView

        if CACHE_SSSOM_SCHEMA:
            # get path remotely, since :mod:`sssom_schema` is
            # not usually kept up-to-date
            path = pystow.ensure("sssom", url=SSSOM_SCHEMA_URL)
            cls.view = SchemaView(path)
        else:
            with tempfile.TemporaryDirectory() as d:
                path = Path(d).joinpath("schema.yml")
                download(path=path, url=SSSOM_SCHEMA_URL)
                cls.view = SchemaView(path)

        cls.mapping_slots = set(cls.view.get_class("mapping").slots)

    def test_multivalued(self) -> None:
        """Test that the multivalued list is filled out."""
        expected_multivalued = {
            slot
            for slot in self.view.get_class("mapping").slots
            if self.view.get_slot(slot).multivalued
        }
        self.assertNotIn("mapping_set_source", expected_multivalued)
        self.assertEqual(
            expected_multivalued,
            MULTIVALUED,
            msg="The sssom-pydantic MULTIVALUED list is out of sync with the SSSOM schema.",
        )

    def test_completeness(self) -> None:
        """Test that the Record class fully covers."""
        # TODO get from view
        mapping_set_propagatable_slots: set[str] = {
            "mapping_set_id",
            "mapping_set_confidence",
            "mapping_set_description",
            "mapping_set_source",
            "mapping_set_title",
            "mapping_set_version",
        }

        self.assertEqual(
            self.mapping_slots | mapping_set_propagatable_slots,
            set(Record.model_fields),
        )

    def test_value_types(self) -> None:
        """Test that values with entity references are type annotated as references."""
        maps = {
            "record_id": "record",
            "subject_id": "subject",
            "predicate_id": "predicate",
            "object_id": "object",
            "mapping_justification": "justification",
            "reviewer_id": "reviewers",
            "author_id": "authors",
            "creator_id": "creators",
        }
        skips = {
            "mapping_tool_id",
        }
        for slot in self.mapping_slots:
            if slot in skips:
                continue
            if self.view.get_slot(slot).range != "EntityReference":
                continue
            with self.subTest(slot=slot):
                annotation = SemanticMapping.model_fields[maps.get(slot, slot)].annotation
                if annotation is Reference:
                    self.assertNotIn(slot, MULTIVALUED)
                elif slot in MULTIVALUED:
                    self.assertEqual(
                        list[Reference] | None,
                        annotation,
                        msg=f"{slot} should be annotated as a list of "
                        f"references, but got {annotation}",
                    )
                else:
                    self.assertEqual(
                        Reference | None,
                        annotation,
                        msg=f"{slot} should be annotated as a reference, but got {annotation}",
                    )


class TestIO(unittest.TestCase):
    """Test reading SSSOM."""

    def setUp(self) -> None:
        """Set up the test case."""
        self._tmp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp_directory.name)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self._tmp_directory.cleanup()

    def test_multivalued_record(self) -> None:
        """Test the Record class is properly type-annotated."""
        for name, field_info in Record.model_fields.items():
            with self.subTest(name=name):
                origin = typing.get_origin(field_info.annotation)
                if origin is types.UnionType:
                    origin = typing.get_origin(typing.get_args(field_info.annotation)[0])

                if name in MULTIVALUED:
                    self.assertEqual(
                        list,
                        origin,
                        msg=f"\nfield {name} is multivalued and therefore should "
                        f"have list as its origin, but got {origin}",
                    )
                else:
                    self.assertNotEqual(
                        list,
                        origin,
                        msg=f"\nfield {name} is not multivalued and therefore "
                        f"not should have list as its origin",
                    )

    def test_read_1(self) -> None:
        """Test simplest reading."""
        r = Record(
            subject_id=S1.curie,
            predicate_id=exact_match.curie,
            object_id=O1.curie,
            mapping_justification=manual_mapping_curation.curie,
            mapping_set_id="test",
        )
        path = self.directory.joinpath("test.tsv")
        write_unprocessed([r], path, metadata={"curie_map": PM})

        unprocessed, _converter = sssom_pydantic.io.read_unprocessed(path)
        self.assertEqual([r], unprocessed)

        rp = SemanticMapping(
            subject=S1,
            predicate=exact_match,
            object=O1,
            justification=manual_mapping_curation,
            mapping_set=MappingSet(id="test"),
        )
        processed, _converter = sssom_pydantic.io.read(path)
        self.assertEqual([rp], processed)

    def test_read_2(self) -> None:
        """Test reading from a file."""
        mapping_set_id = "https://example.org/sssom.mappingset/1"

        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #mapping_justification: {manual_mapping_curation.curie}
            #author_id: {charlie.curie}
            #mapping_set_id: {mapping_set_id}
            subject_id	subject_label	predicate_id	object_id	object_label
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline
        """)
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)

        with path.open() as file:
            columns, metadata = _chomp_frontmatter(file)
        self.assertEqual(
            ["subject_id", "subject_label", "predicate_id", "object_id", "object_label"],
            columns,
            msg="columns were parsed incorrectly",
        )
        self.assertEqual(
            {
                "curie_map": {
                    "mesh": "http://id.nlm.nih.gov/mesh/",
                    "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
                },
                "mapping_justification": manual_mapping_curation.curie,
                "author_id": charlie.curie,
                "mapping_set_id": mapping_set_id,
            },
            metadata,
            msg="metadata was read incorrectly",
        )

        unprocessed_records, _ = sssom_pydantic.io.read_unprocessed(path)
        self.assertEqual(
            [
                Record(
                    subject_id="mesh:C000089",
                    subject_label="ammeline",
                    predicate_id=exact_match.curie,
                    object_id="chebi:28646",
                    object_label="ammeline",
                    mapping_justification=manual_mapping_curation.curie,
                    author_id=[charlie.curie],
                    mapping_set_id=mapping_set_id,
                )
            ],
            unprocessed_records,
        )

        processed_records, _converter = sssom_pydantic.io.read(path)

        self.assertEqual(1, len(processed_records))
        self.assertEqual(
            SemanticMapping(
                subject=NamedReference(prefix="mesh", identifier="C000089", name="ammeline"),
                predicate=Reference(prefix="skos", identifier="exactMatch"),
                object=NamedReference(prefix="chebi", identifier="28646", name="ammeline"),
                justification=manual_mapping_curation,
                authors=[charlie],
                mapping_set=MappingSet(id=mapping_set_id),
            ).model_dump(exclude_none=True),
            processed_records[0].model_dump(exclude_none=True),
        )

    def test_lint(self) -> None:
        """Test linting."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:ManualMappingCuration
        """)
        fixed = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  orcid: https://orcid.org/
            #  owl: http://www.w3.org/2002/07/owl#
            #  rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#
            #  rdfs: http://www.w3.org/2000/01/rdf-schema#
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  sssom: https://w3id.org/sssom/
            #mapping_justification: semapv:ManualMappingCuration
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id
            mesh:C000089	skos:exactMatch	chebi:28646
        """)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).joinpath("test.tsv")
            path.write_text(original)

            lint(path)

            self.assertEqual(fixed.splitlines(), path.read_text().splitlines())
