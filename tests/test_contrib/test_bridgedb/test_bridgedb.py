"""Test importing BridgeDB."""

import unittest
from pathlib import Path

from curies import NamableReference

from sssom_pydantic import SemanticMapping
from sssom_pydantic.contrib.bridgedb_duckdb import from_bridgedb

HERE = Path(__file__).parent.resolve()
V4_PATH = HERE.joinpath("aminoacids_duckdb_db4.bridge")


class TestImportBridgeDb(unittest.TestCase):
    """Test importing BridgeDB."""

    def test_from_bridgedb(self) -> None:
        """Test importing from BridgeDB v4."""
        mappings = from_bridgedb(V4_PATH)
        self.assertIn(
            SemanticMapping(
                subject=NamableReference.from_curie("wikidata:Q100980887", name="ornaline"),
                predicate=NamableReference.from_curie("oboInOwl:hasDbXref"),
                object=NamableReference.from_curie("CHEBI:133921"),
                justification="semapv:UnspecifiedMatching",
            ),
            mappings,
        )
        self.assertNotIn(
            SemanticMapping(
                subject=NamableReference.from_curie("wikidata:Q100980887", name="ornaline"),
                predicate=NamableReference.from_curie("oboInOwl:hasDbXref"),
                object=NamableReference.from_curie("CHEBI:CHEBI:133921"),
                justification="semapv:UnspecifiedMatching",
            ),
            mappings,
            msg="self mapping shouldn't be there",
        )
        self.assertNotIn(
            SemanticMapping(
                subject=NamableReference.from_curie("wikidata:Q100980887", name="ornaline"),
                predicate=NamableReference.from_curie("oboInOwl:hasDbXref"),
                object=NamableReference.from_curie("wikidata:Q100980887", name="ornaline"),
                justification="semapv:UnspecifiedMatching",
            ),
            mappings,
            msg="self mapping shouldn't be there",
        )
