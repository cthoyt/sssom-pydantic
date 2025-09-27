"""Test API."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from curies import Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation

import sssom_pydantic
from sssom_pydantic import Record, write
from sssom_pydantic.api import _chomp_frontmatter

S1 = Reference(prefix="p1", identifier="i1")
O1 = Reference(prefix="p2", identifier="ia")


class TestIO(unittest.TestCase):
    """Test reading SSSOM."""

    def setUp(self) -> None:
        """Set up the test case."""
        self._tmp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp_directory.name)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self._tmp_directory.cleanup()

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
        write([r], path)

        records, _converter = sssom_pydantic.read(path)
        self.assertEqual([r], records)

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

        records, _converter = sssom_pydantic.read(path)
        self.assertEqual(
            [
                Record(
                    subject_id="mesh:C000089",
                    subject_label="ammeline",
                    predicate_id=exact_match.curie,
                    object_id="chebi:28646",
                    object_label="ammeline",
                    mapping_justification=manual_mapping_curation.curie,
                    author_id=charlie.curie,
                    mapping_set_id=mapping_set_id,
                )
            ],
            records,
        )
