"""Tests for constants in SSSOM."""

from __future__ import annotations

import datetime
import importlib.util
import tempfile
import typing
import unittest
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.request import urlretrieve

import pystow
from curies import Reference
from pydantic import AnyUrl

from sssom_pydantic import MappingSetRecord, Record, SemanticMapping
from sssom_pydantic.constants import (
    MAPPING_SET_SLOTS,
    MAPPING_SET_SLOTS_SKIP,
    MULTIVALUED,
    PROPAGATABLE,
)
from sssom_pydantic.examples import EXAMPLES
from sssom_pydantic.models import Cardinality

if TYPE_CHECKING:
    import linkml_runtime

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

        if CACHE_SSSOM_SCHEMA:
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
            PROPAGATABLE,
            msg="The sssom-pydantic PROPAGATABLE list is out of sync with the SSSOM schema.",
        )

        x = PROPAGATABLE - self.mapping_slots
        self.assertEqual(
            0,
            len(x),
            msg=f"\n\nthere are elements in propagatable that aren't in the mapping slots: {x}",
        )

    def test_completeness(self) -> None:
        """Test that the Record class fully covers."""
        self.assertEqual(
            self.mapping_slots,
            set(Record.model_fields),
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
            # get rid of the redundant suffix `_id`
            "record_id": "record",
            "subject_id": "subject",
            "predicate_id": "predicate",
            "object_id": "object",
            "reviewer_id": "reviewers",
            "author_id": "authors",
            "creator_id": "creators",
            # get rid of the redundant prefix `mapping_`
            "mapping_justification": "justification",
            "mapping_cardinality": "cardinality",
            "mapping_source": "source",
            "mapping_provider": "provider",
        }
        skips = {
            # skip these because they're mapped in a custom way
            "mapping_tool_id",
            "mapping_tool_version",
            "mapping_tool",
            "subject_label",
            "predicate_label",
            "object_label",
            "other",  # is a dict[str, str]
            "mapping_provider",  # is an AnyURL
            # skip these because they're not included
            "creator_label",
            "author_label",
            "reviewer_label",
        }
        for slot in self.mapping_slots:
            if slot in skips:
                continue
            with self.subTest(slot=slot):
                annotation = SemanticMapping.model_fields[maps.get(slot, slot)].annotation
                multivalued = slot in MULTIVALUED
                match self.view.get_slot(slot).range:
                    case "EntityReference":
                        if multivalued:
                            self.assertEqual(
                                list[Reference] | None,
                                annotation,
                                msg=f"{slot} should be annotated as a list of "
                                f"references, but got {annotation}",
                            )
                        else:
                            self.assertIn(
                                annotation,
                                {Reference, Reference | None},
                                msg=f"{slot} should be annotated as a reference",
                            )
                    case "string" | "NonRelativeURI":
                        if multivalued:
                            self.assertIn(
                                annotation,
                                {list[str], list[str] | None},
                                msg=f"{slot} should be annotated as a list[str]",
                            )
                        else:
                            self.assertIn(
                                annotation,
                                {str, str | None},
                                msg=f"{slot} should be annotated as a string",
                            )
                    case "double":
                        self.assertIn(
                            annotation,
                            {float, float | None},
                            msg=f"{slot} should be annotated as a float",
                        )
                    case "date":
                        self.assertIn(
                            annotation,
                            {datetime.date, datetime.date | None},
                            msg=f"{slot} should be annotated as a datetime",
                        )
                    case "mapping_cardinality_enum":
                        self.assertEqual(Cardinality | None, annotation)
                    case "predicate_modifier_enum":
                        self.assertEqual(typing.Literal["Not"] | None, annotation)
                    case "entity_type_enum":
                        self.assertEqual(
                            Reference | None,
                            annotation,
                            msg=f"{slot} with LinkML type 'entity_type_enum' should "
                            f"be annotated as a reference",
                        )
                    case _:
                        self.fail(
                            f"missing handling for {slot} with "
                            f"range {self.view.get_slot(slot).range}"
                        )

    def test_mapping_set(self) -> None:
        """Test the mapping set has all fields except propagated ones and explicit skips."""
        for slot in self.mapping_set_slots:
            if slot in {"curie_map", "mappings"}:
                continue
            with self.subTest(slot=slot):
                self.assertIn(slot, MappingSetRecord.model_fields)
                annotation = MappingSetRecord.model_fields[slot].annotation
                multivalued = self.view.get_slot(slot).multivalued
                match self.view.get_slot(slot).range:
                    case "EntityReference":
                        if annotation is Reference:
                            self.assertNotIn(slot, MULTIVALUED)
                        elif multivalued:
                            self.assertEqual(
                                list[str] | None,
                                annotation,
                                msg=f"{slot} should be annotated as a list of "
                                f"references, but got {annotation}",
                            )
                        else:
                            self.assertEqual(
                                str | None,
                                annotation,
                                msg=f"{slot} should be annotated as a reference",
                            )
                    case "string":
                        if multivalued:
                            self.assertIn(
                                annotation,
                                {list[str], list[str] | None},
                                msg=f"{slot} should be annotated as a list[str]",
                            )
                        else:
                            self.assertIn(
                                annotation,
                                {str, str | None},
                                msg=f"{slot} should be annotated as a string",
                            )
                    case "NonRelativeURI":
                        if multivalued:
                            self.assertIn(
                                annotation,
                                {list[AnyUrl], list[AnyUrl] | None},
                                msg=f"{slot} should be annotated as a list[str]",
                            )
                        else:
                            self.assertIn(
                                annotation,
                                {AnyUrl, AnyUrl | None},
                                msg=f"{slot} should be annotated as a string",
                            )
                    case "double":
                        self.assertIn(
                            annotation,
                            {float, float | None},
                            msg=f"{slot} should be annotated as a float",
                        )
                    case "date":
                        self.assertIn(
                            annotation,
                            {datetime.date, datetime.date | None},
                            msg=f"{slot} should be annotated as a datetime",
                        )
                    case "extension definition":
                        pass
                    case "sssom_version_enum" | "entity_type_enum":
                        self.assertIn(annotation, {str, str | None})
                    case _:
                        self.fail(
                            f"missing handling for slot {slot} with range "
                            f"{self.view.get_slot(slot).range}"
                        )


class TestExampleCompleteness(unittest.TestCase):
    """Test that the examples cover the full set of cases."""

    def test_completeness(self) -> None:
        """Test there's an example for all fields."""
        counter: Counter[str] = Counter()
        for example in EXAMPLES:
            for k, _v in example.semantic_mapping.model_dump(exclude_none=True).items():
                counter[k] += 1

        for field in SemanticMapping.model_fields:
            with self.subTest(field=field):
                self.assertIn(field, set(counter), msg=f"\n\nthere's no example that uses {field}")
