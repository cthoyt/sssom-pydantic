"""Test API."""

from __future__ import annotations

import tempfile
import types
import typing
import unittest
from pathlib import Path
from textwrap import dedent

import curies
from curies import Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from pydantic import BaseModel

import sssom_pydantic
import sssom_pydantic.io
from sssom_pydantic import MappingSet, MappingSetRecord, SemanticMapping
from sssom_pydantic.constants import MULTIVALUED
from sssom_pydantic.io import _chomp_frontmatter, append, append_unprocessed, write_unprocessed
from sssom_pydantic.models import Record
from tests.cases import (
    P1,
    R1,
    R2,
    TEST_MAPPING_SET_ID,
    TEST_METADATA_W_PREFIX_MAP,
    TEST_PREFIX_MAP,
    _m,
    _r,
)

ROUND_TRIP_TESTS = [
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        source=Reference.from_curie("w3id:biopragmatics/biomappings/sssom/biomappings.sssom.tsv"),
        justification=manual_mapping_curation.curie,
    ),
    SemanticMapping(  # test multiple random keys in `other`
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        other={"key1": "value1", "key2": "value2"},
    ),
    SemanticMapping(  # test a single key in `other`
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        other={"key": "value"},
    ),
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        cardinality="1:1",
    ),
    SemanticMapping(
        subject=R1,
        predicate=P1,
        object=R2,
        justification=manual_mapping_curation.curie,
        provider="https://github.com/biopragmatics/biomappings",
    ),
]


class TestIO(unittest.TestCase):
    """Test reading SSSOM."""

    def setUp(self) -> None:
        """Set up the test case."""
        self._tmp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp_directory.name)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self._tmp_directory.cleanup()

    def assert_model_equal(self, expected: BaseModel, actual: BaseModel) -> None:
        """Check two models are equal by serializing to dict."""
        self.assertEqual(
            expected.model_dump(exclude_none=True), actual.model_dump(exclude_none=True)
        )

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
        record = _r()
        path = self.directory.joinpath("test.tsv")
        write_unprocessed([record], path, metadata=TEST_METADATA_W_PREFIX_MAP)

        unprocessed, _converter, _mapping_set = sssom_pydantic.io.read_unprocessed(path)
        self.assertEqual(1, len(unprocessed))
        self.assert_model_equal(record, unprocessed[0])

        semantic_mapping = _m()
        processed, _converter, _mapping_set = sssom_pydantic.io.read(path)
        self.assertEqual(1, len(processed))
        self.assert_model_equal(semantic_mapping, processed[0])

    def test_read_2(self) -> None:
        """Test reading from a file."""
        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{charlie.curie}
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)

        with path.open() as file:
            columns, mapping_set_record = _chomp_frontmatter(file)
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
            MappingSetRecord.model_validate(
                {
                    "mapping_set_id": TEST_MAPPING_SET_ID,
                    "curie_map": {
                        "mesh": "http://id.nlm.nih.gov/mesh/",
                        "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
                    },
                }
            ),
            mapping_set_record,
            msg="metadata was read incorrectly",
        )

        unprocessed_records, _, _mapping_set = sssom_pydantic.io.read_unprocessed(path)
        self.assertEqual(1, len(unprocessed_records))
        self.assert_model_equal(
            _r(author_id=[charlie.curie]),
            unprocessed_records[0],
        )

        processed_records, _converter, _mapping_set = sssom_pydantic.io.read(path)

        self.assertEqual(1, len(processed_records))
        self.assert_model_equal(
            _m(authors=[charlie]),
            processed_records[0],
        )

    def test_round_trip(self) -> None:
        """Test that mappings can be written and read."""
        self.maxDiff = None
        mapping_set = MappingSet(id="https://example.org/test.sssom.tsv")
        converter = curies.Converter.from_prefix_map(
            {**TEST_PREFIX_MAP, "w3id": "https://w3id.org/"}
        )
        for expected_mapping in ROUND_TRIP_TESTS:
            with self.subTest():
                path = self.directory.joinpath("test.sssom.tsv")
                sssom_pydantic.write(
                    [expected_mapping], path, converter=converter, metadata=mapping_set
                )
                mappings, _, _ = sssom_pydantic.read(path)
                self.assertEqual(
                    1, len(mappings), msg=f"Failed, file contents:\n\n{path.read_text()}"
                )
                self.assertEqual(
                    expected_mapping.model_dump(exclude_none=True, exclude_unset=True),
                    mappings[0].model_dump(exclude_none=True, exclude_unset=True),
                )

    def test_read_metadata_empty_line(self) -> None:
        """Test reading from a file whose metadata has a blank line in it."""
        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{charlie.curie}
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)

        processed_records, _converter, _mapping_set = sssom_pydantic.io.read(path)

        self.assertEqual(1, len(processed_records))
        self.assert_model_equal(
            _m(authors=[charlie]),
            processed_records[0],
        )

    def test_append(self) -> None:
        """Test appending to the end of a file."""
        original = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration
        """)

        path = self.directory.joinpath("test.tsv")
        path.write_text(original)

        with self.assertRaises(NotImplementedError):
            # raises because it introduces a new column that's not already in the file
            append([_m(curation_rule_text=["something something"])], path)

        record = Record(
            subject_id="mesh:C000090",
            predicate_id="skos:exactMatch",
            object_id="chebi:28647",
            mapping_justification="semapv:ManualMappingCuration",
        )
        append_unprocessed([record], path)

        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration
            mesh:C000090	skos:exactMatch	chebi:28647	semapv:ManualMappingCuration
        """)
        self.assertEqual(expected.splitlines(), path.read_text().splitlines())

    def test_standardize_semantic_mapping(self) -> None:
        """Test standardizing a semantic mapping."""
        original = SemanticMapping(
            subject="chebi:10001",
            predicate=exact_match,
            object="mesh:C067604",
            justification=manual_mapping_curation,
            authors=[Reference.from_curie("ORCiD:0000-0003-4423-4370")],
        )
        expected = SemanticMapping(
            subject="CHEBI:10001",
            predicate=exact_match,
            object="mesh:C067604",
            justification=manual_mapping_curation,
            authors=[Reference.from_curie("orcid:0000-0003-4423-4370")],
        )
        converter = curies.Converter(
            [
                curies.Record(
                    prefix="CHEBI",
                    prefix_synonyms=["chebi"],
                    uri_prefix="http://purl.obolibrary.org/obo/CHEBI_",
                ),
                curies.Record(
                    prefix="mesh",
                    prefix_synonyms=["MeSH"],
                    uri_prefix="http://id.nlm.nih.gov/mesh/",
                ),
                curies.Record(
                    prefix="orcid",
                    prefix_synonyms=["ORCiD"],
                    uri_prefix="https://orcid.org/",
                ),
                curies.Record(prefix="skos", uri_prefix="http://www.w3.org/2004/02/skos/core#"),
                curies.Record(prefix="semapv", uri_prefix="https://w3id.org/semapv/vocab/"),
            ]
        )
        self.assert_model_equal(expected, original.standardize(converter))
