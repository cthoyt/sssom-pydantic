"""Test linting."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from sssom_pydantic.io import lint


class TestLinting(unittest.TestCase):
    """Test linting."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name).joinpath("test.tsv")

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.directory.cleanup()

    def assert_linted(self, expected: str, original: str) -> None:
        """Test linting."""
        self.path.write_text(original)
        lint(self.path)
        self.assertEqual(expected.splitlines(), self.path.read_text().splitlines())

    def test_minimal(self) -> None:
        """Test minimal."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:ManualMappingCuration
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration
        """)
        self.assert_linted(expected, original)

    def test_minimal_no_propagation(self) -> None:
        """Test minimal where mapping justification isn't propagated."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:ManualMappingCuration
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:LexicalMatching
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:LexicalMatching
        """)
        self.assert_linted(expected, original)

    def test_single_author(self) -> None:
        """Test round trip for a single author."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification	author_id
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:ManualMappingCuration	orcid:0000-0003-4423-4370
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  orcid: https://orcid.org/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification	author_id
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	orcid:0000-0003-4423-4370
        """)
        self.assert_linted(expected, original)

    def test_multiple_author(self) -> None:
        """Test round trip for multiple authors."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification	author_id
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:ManualMappingCuration	orcid:0000-0003-4423-4370|orcid:0000-0003-1307-2508
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  orcid: https://orcid.org/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification	author_id
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	orcid:0000-0003-4423-4370|orcid:0000-0003-1307-2508
        """)
        self.assert_linted(expected, original)

    def test_no_condense_creator(self) -> None:
        """Test that creator shouldn't be condensed."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification	creator_id
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:ManualMappingCuration	orcid:0000-0003-4423-4370
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  orcid: https://orcid.org/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification	creator_id
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration	orcid:0000-0003-4423-4370
        """)
        self.assert_linted(expected, original)

    def test_condense_mapping_tool_id(self) -> None:
        """Test putting the mapping tool into the upper metadata."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #  biotools: https://bio.tools/
            object_id	subject_id	predicate_id	mapping_justification	mapping_tool_id
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:LexicalMatching	biotools:ssslm
        """)
        expected = dedent("""\
            #curie_map:
            #  biotools: https://bio.tools/
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            #mapping_tool_id: biotools:ssslm
            subject_id	predicate_id	object_id	mapping_justification
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:LexicalMatching
        """)
        self.assert_linted(expected, original)
