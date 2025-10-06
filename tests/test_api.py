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
from urllib.request import urlretrieve

from curies import NamedReference, Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from pydantic import BaseModel

import sssom_pydantic
import sssom_pydantic.io
from sssom_pydantic import Record, write_unprocessed
from sssom_pydantic.api import MappingSet, SemanticMapping
from sssom_pydantic.constants import (
    MAPPING_SET_SLOTS,
    MAPPING_SET_SLOTS_SKIP,
    MULTIVALUED,
    PROPAGATABLE_EXTRAS,
    PROPAGATABLE_SPEC,
)
from sssom_pydantic.io import _chomp_frontmatter

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
    mapping_set_slots: typing.ClassVar[set[str]]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the class with a schema view."""
        from linkml_runtime import SchemaView

        if CACHE_SSSOM_SCHEMA and importlib.util.find_spec("pystow"):
            import pystow

            # get path remotely, since :mod:`sssom_schema` is
            # not usually kept up-to-date
            path = pystow.ensure("sssom", url=SSSOM_SCHEMA_URL)
            cls.view = SchemaView(path)
        else:
            with tempfile.TemporaryDirectory() as d:
                path = Path(d).joinpath("schema.yml")
                urlretrieve(SSSOM_SCHEMA_URL, path)  # noqa:S310
                cls.view = SchemaView(path)

        cls.mapping_slots = set(cls.view.get_class("mapping").slots)
        cls.mapping_set_slots = set(cls.view.get_class("mapping set").slots)

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

    def test_propagatable(self) -> None:
        """Test that the propagatable list is fileld out."""
        expected_propagatable = set()
        for slot in self.mapping_set_slots:
            slot_annotations = self.view.annotation_dict(slot)
            if slot_annotations is not None and "propagated" in slot_annotations:
                expected_propagatable.add(slot)

        self.assertEqual(
            expected_propagatable,
            PROPAGATABLE_SPEC,
            msg="The sssom-pydantic PROPAGATABLE list is out of sync with the SSSOM schema.",
        )

        x = PROPAGATABLE_SPEC - self.mapping_slots
        self.assertEqual(
            0,
            len(x),
            msg=f"\n\nthere are elements in propagatable that aren't in the mapping slots: {x}",
        )

    def test_completeness(self) -> None:
        """Test that the Record class fully covers."""
        self.assertEqual(
            self.mapping_slots,
            set(Record.model_fields) - PROPAGATABLE_EXTRAS,
        )

    def test_mapping_set_keys(self) -> None:
        """Test mapping set slots are properly coded."""
        self.assertEqual(
            self.mapping_set_slots - MAPPING_SET_SLOTS_SKIP,
            MAPPING_SET_SLOTS,
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
        mapping_set_id = "https://example.org/test.tsv"
        r = Record(
            subject_id=S1.curie,
            predicate_id=exact_match.curie,
            object_id=O1.curie,
            mapping_justification=manual_mapping_curation.curie,
            mapping_set_id=mapping_set_id,
        )
        path = self.directory.joinpath("test.tsv")
        write_unprocessed([r], path, metadata={"curie_map": PM})

        unprocessed, _converter = sssom_pydantic.io.read_unprocessed(path)
        self.assertEqual(1, len(unprocessed))
        self.assert_model_equal(r, unprocessed[0])

        rp = SemanticMapping(
            subject=S1,
            predicate=exact_match,
            object=O1,
            justification=manual_mapping_curation,
            mapping_set=MappingSet(id=mapping_set_id),
        )
        processed, _converter = sssom_pydantic.io.read(path)
        self.assertEqual(1, len(processed))
        self.assert_model_equal(rp, processed[0])

    def test_read_2(self) -> None:
        """Test reading from a file."""
        mapping_set_id = "https://example.org/sssom.mappingset/1"

        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #mapping_set_id: {mapping_set_id}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{charlie.curie}
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)

        with path.open() as file:
            columns, metadata = _chomp_frontmatter(file)
        self.assertEqual(
            [
                "subject_id",
                "subject_label",
                "predicate_id",
                "object_id",
                "object_label",
                "mapping_justification",
                "author_id",
            ],
            columns,
            msg="columns were parsed incorrectly",
        )
        self.assertEqual(
            {
                "curie_map": {
                    "mesh": "http://id.nlm.nih.gov/mesh/",
                    "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
                },
                "mapping_set_id": mapping_set_id,
            },
            metadata,
            msg="metadata was read incorrectly",
        )

        unprocessed_records, _ = sssom_pydantic.io.read_unprocessed(path)
        self.assertEqual(1, len(unprocessed_records))
        self.assert_model_equal(
            Record(
                subject_id="mesh:C000089",
                subject_label="ammeline",
                predicate_id=exact_match.curie,
                object_id="chebi:28646",
                object_label="ammeline",
                mapping_justification=manual_mapping_curation.curie,
                author_id=[charlie.curie],
                mapping_set_id=mapping_set_id,
            ),
            unprocessed_records[0],
        )

        processed_records, _converter = sssom_pydantic.io.read(path)

        self.assertEqual(1, len(processed_records))
        self.assert_model_equal(
            SemanticMapping(
                subject=NamedReference(prefix="mesh", identifier="C000089", name="ammeline"),
                predicate=Reference(prefix="skos", identifier="exactMatch"),
                object=NamedReference(prefix="chebi", identifier="28646", name="ammeline"),
                justification=manual_mapping_curation,
                authors=[charlie],
                mapping_set=MappingSet(id=mapping_set_id),
            ),
            processed_records[0],
        )

    def assert_model_equal(self, expected: BaseModel, actual: BaseModel) -> None:
        """Check two models are equal by serializing to dict."""
        self.assertEqual(
            expected.model_dump(exclude_none=True), actual.model_dump(exclude_none=True)
        )
