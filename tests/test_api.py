"""Test API."""

from __future__ import annotations

import datetime
import tempfile
import types
import typing
from pathlib import Path
from textwrap import dedent
from typing import Any

import curies
import yaml
from curies import Reference
from curies.vocabulary import exact_match, manual_mapping_curation

import sssom_pydantic
import sssom_pydantic.io
from sssom_pydantic import MappingSet, MappingSetRecord, SemanticMapping
from sssom_pydantic.constants import MULTIVALUED
from sssom_pydantic.examples import EXAMPLES
from sssom_pydantic.io import _chomp_frontmatter, append, append_unprocessed, write_unprocessed
from sssom_pydantic.models import Record
from tests import cases
from tests.cases import (
    AUTHOR,
    TEST_CONVERTER,
    TEST_MAPPING_SET_ID,
    TEST_METADATA,
    TEST_METADATA_W_PREFIX_MAP,
    TEST_PREFIX_MAP,
    _m,
    _r,
)


class TestIO(cases.MappingTestCaseMixin):
    """Test reading SSSOM."""

    def setUp(self) -> None:
        """Set up the test case."""
        self._tmp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp_directory.name)
        self.path = self.directory.joinpath("test.sssom.tsv")

    def tearDown(self) -> None:
        """Tear down the test case."""
        self._tmp_directory.cleanup()

    def assert_path(self, contents: str) -> None:
        """Check the path has the right contents after dedenting."""
        self.assertEqual(dedent(contents), self.path.read_text())

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
        self.assert_base_model_equal(record, unprocessed[0])

        semantic_mapping = _m()
        processed, _converter, _mapping_set = sssom_pydantic.io.read(path)
        self.assertEqual(1, len(processed))
        self.assert_base_model_equal(semantic_mapping, processed[0])

    def test_chomp_empty(self) -> None:
        """Test chomping a file with no header."""
        text = dedent(f"""\
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{AUTHOR.curie}
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)

        with path.open() as file:
            columns, mapping_set_record, frontmatter_length = _chomp_frontmatter(file)
        self.assertEqual(0, frontmatter_length)
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
        self.assertIsNone(mapping_set_record)

    def test_read_2(self) -> None:
        """Test reading from a file."""
        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{AUTHOR.curie}
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)

        with path.open() as file:
            columns, mapping_set_record, frontmatter_length = _chomp_frontmatter(file)
        self.assertEqual(4, frontmatter_length)
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
        self.assert_base_model_equal(_r(author_id=[AUTHOR.curie]), unprocessed_records[0])

        processed_records, _converter, _mapping_set = sssom_pydantic.io.read(path)

        self.assertEqual(1, len(processed_records))
        self.assert_model_equal(_m(authors=[AUTHOR]), processed_records[0])

    def test_round_trip(self) -> None:
        """Test that mappings can be written and read."""
        self.maxDiff = None
        converter = curies.Converter.from_prefix_map(TEST_PREFIX_MAP)
        for example in EXAMPLES:
            with self.subTest(desc=example.description):
                path = self.directory.joinpath("test.sssom.tsv")
                sssom_pydantic.write(
                    [example.semantic_mapping], path, converter=converter, metadata=TEST_METADATA
                )
                mappings, _, _ = sssom_pydantic.read(path)
                self.assertEqual(
                    1, len(mappings), msg=f"Failed, file contents:\n\n{path.read_text()}"
                )
                self.assert_model_equal(example.semantic_mapping, mappings[0])

    def test_read_metadata_empty_line(self) -> None:
        """Test reading from a file whose metadata has a blank line in it."""
        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{AUTHOR.curie}
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)

        processed_records, _converter, _mapping_set = sssom_pydantic.io.read(path)

        self.assertEqual(1, len(processed_records))
        self.assert_model_equal(_m(authors=[AUTHOR]), processed_records[0])

    def test_read_main_content_empty_line(self) -> None:
        """Test reading from a file whose main content a blank line in it."""
        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{AUTHOR.curie}

            mesh:C000090		skos:exactMatch	chebi:28647		{manual_mapping_curation.curie}	{AUTHOR.curie}
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)
        processed_records, _converter, _mapping_set = sssom_pydantic.io.read(path)
        self.assertEqual(2, len(processed_records))

    def test_read_with_external_metadata(self) -> None:
        """Test reading from a file whose main content a blank line in it."""
        text = dedent(f"""\
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{AUTHOR.curie}
        """)  # noqa:E501

        m1 = {
            "curie_map": {
                "mesh": "http://id.nlm.nih.gov/mesh/",
                "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
            },
            "mapping_set_id": TEST_MAPPING_SET_ID,
        }
        m2 = MappingSetRecord(
            curie_map={
                "mesh": "http://id.nlm.nih.gov/mesh/",
                "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
            },
            mapping_set_id=TEST_MAPPING_SET_ID,
        )
        metadatas: list[dict[str, Any] | MappingSetRecord] = [m1, m2]
        for i, metadata in enumerate(metadatas):
            path = self.directory.joinpath(f"test-{i}.tsv")
            path.write_text(text)
            processed_records, _converter, _mapping_set = sssom_pydantic.io.read(
                path, metadata=metadata
            )
            self.assertEqual(1, len(processed_records))
            self.assert_model_equal(_m(authors=[AUTHOR]), processed_records[0])

    def test_read_with_path_metadata(self) -> None:
        """Test reading from a file whose main content a blank line in it."""
        text = dedent(f"""\
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{AUTHOR.curie}
        """)  # noqa:E501

        m2 = MappingSetRecord(
            curie_map={
                "mesh": "http://id.nlm.nih.gov/mesh/",
                "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
            },
            mapping_set_id=TEST_MAPPING_SET_ID,
        )
        path_yaml = self.directory.joinpath("test.yaml")
        # json mode required to serialize AnyURL instances properly
        path_yaml.write_text(yaml.safe_dump(m2.model_dump(exclude_none=True, mode="json")))
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)
        processed_records, _converter, _mapping_set = sssom_pydantic.io.read(
            path, metadata_path=path_yaml
        )
        self.assertEqual(1, len(processed_records))
        self.assert_model_equal(_m(authors=[AUTHOR]), processed_records[0])

    def test_read_with_errors(self) -> None:
        """Test returning errors."""
        text = dedent(f"""\
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	{manual_mapping_curation.curie}	{AUTHOR.curie}
            mesh:C000090
        """)  # noqa:E501
        path = self.directory.joinpath("test.tsv")
        path.write_text(text)
        with self.assertLogs(level="DEBUG") as ctx:
            mappings, _converter, _mapping_set = sssom_pydantic.read(path)
            self.assertEqual(
                [
                    "DEBUG:sssom_pydantic.io:[line 7] failed to parse row: {'subject_id': 'mesh:C000090'}"  # noqa:E501
                ],
                ctx.output,
            )
        self.assertEqual(1, len(mappings))
        self.assert_model_equal(_m(authors=[AUTHOR]), mappings[0])

        # now, return the errors explicitly

        mappings, _converter, _mapping_set, errors = sssom_pydantic.read(path, return_errors=True)
        self.assertEqual(1, len(mappings))
        self.assert_model_equal(_m(authors=[AUTHOR]), mappings[0])
        self.assertEqual(1, len(errors))
        error = errors[0]
        self.assertEqual(7, error.line_number)
        # TODO add explicit error check?

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

    def test_write_with_exclude(self) -> None:
        """Test writing with exclude."""
        metadata = MappingSet(id=TEST_MAPPING_SET_ID)

        prefix = "ex"
        uri_prefix = "https://example.org/"
        m = _m(record=Reference(prefix=prefix, identifier="1"), authors=[AUTHOR])
        c2 = curies.Converter.from_prefix_map({**TEST_PREFIX_MAP, prefix: uri_prefix})
        path_no_record_id = self.directory.joinpath("test.tsv")
        sssom_pydantic.write([m], path_no_record_id, converter=c2, metadata=metadata)
        self.assertEqual(
            dedent(f"""\
                #curie_map:
                #  chebi: http://purl.obolibrary.org/obo/CHEBI_
                #  {prefix}: {uri_prefix}
                #  mesh: http://id.nlm.nih.gov/mesh/
                #  orcid: https://orcid.org/
                #  semapv: https://w3id.org/semapv/vocab/
                #  skos: http://www.w3.org/2004/02/skos/core#
                #mapping_set_id: {TEST_MAPPING_SET_ID}
                record_id	subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
                ex:1	mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration	{AUTHOR.curie}
            """),  # noqa:E501
            path_no_record_id.read_text(),
        )

        path = self.directory.joinpath("test2.tsv")
        sssom_pydantic.write(
            [m], path, exclude_columns=["record_id"], converter=TEST_CONVERTER, metadata=metadata
        )
        self.assertEqual(
            dedent(f"""\
                #curie_map:
                #  chebi: http://purl.obolibrary.org/obo/CHEBI_
                #  mesh: http://id.nlm.nih.gov/mesh/
                #  orcid: https://orcid.org/
                #  semapv: https://w3id.org/semapv/vocab/
                #  skos: http://www.w3.org/2004/02/skos/core#
                #mapping_set_id: {TEST_MAPPING_SET_ID}
                subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
                mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration	{AUTHOR.curie}
            """),  # noqa:E501
            path.read_text(),
        )

        # now, test appending with exclude
        a2 = curies.Reference(prefix="orcid", identifier="0000-0002-1216-4761")
        m2 = _m(record=Reference(prefix=prefix, identifier="2"), authors=[a2])
        sssom_pydantic.append([m2], path, converter=TEST_CONVERTER, exclude_columns=["record_id"])
        self.assertEqual(
            dedent(f"""\
                #curie_map:
                #  chebi: http://purl.obolibrary.org/obo/CHEBI_
                #  mesh: http://id.nlm.nih.gov/mesh/
                #  orcid: https://orcid.org/
                #  semapv: https://w3id.org/semapv/vocab/
                #  skos: http://www.w3.org/2004/02/skos/core#
                #mapping_set_id: {TEST_MAPPING_SET_ID}
                subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
                mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration	{AUTHOR.curie}
                mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration	{a2.curie}
            """),  # noqa:E501
            path.read_text(),
        )

    def test_write_explicit_columns(self) -> None:
        """Test writing with exclude."""
        sssom_pydantic.write(
            [_m(authors=[AUTHOR])],
            self.path,
            converter=TEST_CONVERTER,
            metadata=MappingSet(id=TEST_MAPPING_SET_ID),
            columns=["subject_id", "predicate_id", "object_id", "mapping_justification"],
        )
        self.assert_path(f"""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  orcid: https://orcid.org/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	predicate_id	object_id	mapping_justification
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration
        """)

    def test_toggle_condense(self) -> None:
        """Test toggling condense."""
        metadata = MappingSet(id=TEST_MAPPING_SET_ID)
        date = "2026-05-04"
        m1 = _m(authors=[AUTHOR], mapping_date=datetime.date.fromisoformat(date))
        m2 = _m(mapping_date=datetime.date.fromisoformat(date))

        path_condensed = self.directory.joinpath("test.sssom.tsv")
        sssom_pydantic.write(
            [m1, m2],
            path_condensed,
            converter=TEST_CONVERTER,
            metadata=metadata,
        )
        self.assertEqual(
            dedent(f"""\
                #curie_map:
                #  chebi: http://purl.obolibrary.org/obo/CHEBI_
                #  mesh: http://id.nlm.nih.gov/mesh/
                #  orcid: https://orcid.org/
                #  semapv: https://w3id.org/semapv/vocab/
                #  skos: http://www.w3.org/2004/02/skos/core#
                #mapping_date: '2026-05-04'
                #mapping_set_id: {TEST_MAPPING_SET_ID}
                subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id
                mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration	{AUTHOR.curie}
                mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration	
            """),  # noqa:E501,W291
            path_condensed.read_text(),
            msg="subject/object labels and authors should not be included, "
            "since they were not in the columns list",
        )

        path_uncondensed = self.directory.joinpath("test-uncondensed.sssom.tsv")
        sssom_pydantic.write(
            [m1, m2], path_uncondensed, converter=TEST_CONVERTER, metadata=metadata, condense=False
        )
        self.assertEqual(
            dedent(f"""\
                #curie_map:
                #  chebi: http://purl.obolibrary.org/obo/CHEBI_
                #  mesh: http://id.nlm.nih.gov/mesh/
                #  orcid: https://orcid.org/
                #  semapv: https://w3id.org/semapv/vocab/
                #  skos: http://www.w3.org/2004/02/skos/core#
                #mapping_set_id: {TEST_MAPPING_SET_ID}
                subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	author_id	mapping_date
                mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration	{AUTHOR.curie}	2026-05-04
                mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration		2026-05-04
            """),  # noqa:E501
            path_uncondensed.read_text(),
            msg="\nskipping condense failed",
        )

    def test_toggle_subset_converter(self) -> None:
        """Test toggling condense."""
        sssom_pydantic.write(
            [_m()],
            self.path,
            converter=TEST_CONVERTER,
            metadata=MappingSet(id=TEST_MAPPING_SET_ID),
            subset_converter=False,
        )
        self.assert_path(f"""\
            #curie_map:
            #  biolink: https://w3id.org/biolink/vocab/
            #  bioregistry: https://bioregistry.io/
            #  cas: https://commonchemistry.cas.org/detail?cas_rn=
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  issue: https://github.com/cthoyt/sssom-pydantic/issues/
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  orcid: https://orcid.org/
            #  owl: http://www.w3.org/2002/07/owl#
            #  rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#
            #  rdfs: http://www.w3.org/2000/01/rdf-schema#
            #  rule: https://example.org/disease-rule/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #  spdx: https://spdx.org/licenses/
            #  sssom: https://w3id.org/sssom/
            #  sssom.record: https://w3id.org/sssom/record/
            #  w3id: https://w3id.org/
            #mapping_set_id: {TEST_MAPPING_SET_ID}
            subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification
            mesh:C000089	ammeline	skos:exactMatch	chebi:28646	ammeline	semapv:ManualMappingCuration
        """)  # noqa:E501
