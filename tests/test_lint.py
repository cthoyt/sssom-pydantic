"""Test linting."""

import tempfile
import unittest
from collections.abc import Iterable
from pathlib import Path
from textwrap import dedent

from curies import Reference
from curies.vocabulary import exact_match, manual_mapping_curation

from sssom_pydantic import SemanticMapping
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

    def assert_linted(
        self,
        expected: str,
        original: str,
        exclude_mappings: Iterable[SemanticMapping] | None = None,
        drop_duplicates: bool = False,
    ) -> None:
        """Test linting."""
        self.path.write_text(original)
        lint(self.path, exclude_mappings=exclude_mappings, drop_duplicates=drop_duplicates)
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

    def test_unspecified_matching(self) -> None:
        """Test minimal with an unspecified matching."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:UnspecifiedMatching
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:UnspecifiedMatching
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
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:LexicalMatching
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:ManualMappingCuration
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

    def test_confidence(self) -> None:
        """Test round trip with mapping confidence."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification	confidence
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:LexicalMatching	0.95
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification	confidence
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:LexicalMatching	0.95
        """)
        self.assert_linted(expected, original)

    def test_remove_specified(self) -> None:
        """Test round trip with mapping confidence."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            object_id	subject_id	predicate_id	mapping_justification	confidence
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:LexicalMatching	0.95
            chebi:1	mesh:C000001	skos:exactMatch	semapv:LexicalMatching	0.95
            chebi:2	mesh:C000002	skos:exactMatch	semapv:LexicalMatching	0.95
        """)
        expected = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification	confidence
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:LexicalMatching	0.95
        """)
        exclude_mappings = [
            SemanticMapping(
                subject=Reference(prefix="mesh", identifier="C000001"),
                predicate=exact_match,
                object=Reference(prefix="chebi", identifier="1"),
                justification=manual_mapping_curation,
            ),
            SemanticMapping(
                subject=Reference(prefix="mesh", identifier="C000002"),
                predicate=exact_match,
                object=Reference(prefix="chebi", identifier="2"),
                justification=manual_mapping_curation,
            ),
            # last one is a no-op
            SemanticMapping(
                subject=Reference(prefix="mesh", identifier="C000003"),
                predicate=exact_match,
                object=Reference(prefix="chebi", identifier="3"),
                justification=manual_mapping_curation,
            ),
        ]
        self.assert_linted(expected, original, exclude_mappings=exclude_mappings)

    def test_drop_duplicates(self) -> None:
        """Test round trip with mapping confidence."""
        original = dedent("""\
            #mapping_set_id: https://example.org/test.tsv
            #curie_map:
            #  mesh: "http://id.nlm.nih.gov/mesh/"
            #  chebi: "http://purl.obolibrary.org/obo/CHEBI_"
            #  oboInOwl: "http://www.geneontology.org/formats/oboInOwl#"
            object_id	subject_id	predicate_id	mapping_justification	confidence
            chebi:28646	mesh:C000089	skos:exactMatch	semapv:LexicalMatching	0.95
            chebi:28646	mesh:C000089	oboInOwl:hasDbXref	semapv:LexicalMatching	0.95
        """)
        expected_deduplicated = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification	confidence
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:LexicalMatching	0.95
        """)
        self.assert_linted(expected_deduplicated, original, drop_duplicates=True)

        expected_vanilla = dedent("""\
            #curie_map:
            #  chebi: http://purl.obolibrary.org/obo/CHEBI_
            #  mesh: http://id.nlm.nih.gov/mesh/
            #  oboInOwl: http://www.geneontology.org/formats/oboInOwl#
            #  semapv: https://w3id.org/semapv/vocab/
            #  skos: http://www.w3.org/2004/02/skos/core#
            #mapping_set_id: https://example.org/test.tsv
            subject_id	predicate_id	object_id	mapping_justification	confidence
            mesh:C000089	oboInOwl:hasDbXref	chebi:28646	semapv:LexicalMatching	0.95
            mesh:C000089	skos:exactMatch	chebi:28646	semapv:LexicalMatching	0.95
        """)
        self.assert_linted(expected_vanilla, original, drop_duplicates=False)
