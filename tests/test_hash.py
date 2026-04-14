"""Test hashing."""

import datetime
import unittest

from curies import Converter, Reference

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import _hash_mapping_to_str, mapping_to_sexpr_str
from sssom_pydantic.examples import EXAMPLES
from sssom_pydantic.models import Box, box_to_str
from tests.cases import TEST_CONVERTER

CONVERTER = Converter.from_prefix_map(
    {
        "FOODON": "http://purl.obolibrary.org/obo/FOODON_",
        "KF_FOOD": "https://kewl-foodie.ince/food/",
        "semapv": "https://w3id.org/semapv/vocab/",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "wikidata": "https://www.wikidata.org/wiki/",
        "FBbt": "http://purl.obolibrary.org/obo/FBbt_",
        "HP": "http://purl.obolibrary.org/obo/HP_",
        "MP": "http://purl.obolibrary.org/obo/MP_",
        "UBERON": "http://purl.obolibrary.org/obo/UBERON_",
        "example": "https://example.org/sets/record-id#",
    }
)
CASES = [
    (
        SemanticMapping(
            subject="KF_FOOD:F001",
            predicate="skos:exactMatch",
            object="FOODON:00002473",
            justification="semapv:ManualMappingCuration",
            confidence=0.95,
            mapping_date=datetime.date(2022, 5, 2),
            subject_source=Reference.from_curie("KF_FOOD:DB"),
            object_source=Reference.from_curie("wikidata:Q55118395"),
            object_source_version="http://purl.obolibrary.org/obo/foodon/releases/2022-02-01/foodon.owl",
        ),
        "(7:mapping((10:subject_id34:https://kewl-foodie.ince/food/F001)(12:predicate_id46:http://www.w3.org/2004/02/skos/core#exactMatch)(9:object_id46:http://purl.obolibrary.org/obo/FOODON_00002473)(21:mapping_justification51:https://w3id.org/semapv/vocab/ManualMappingCuration)(14:subject_source32:https://kewl-foodie.ince/food/DB)(13:object_source39:https://www.wikidata.org/wiki/Q55118395)(21:object_source_version68:http://purl.obolibrary.org/obo/foodon/releases/2022-02-01/foodon.owl)(12:mapping_date10:2022-05-02)(10:confidence4:0.95)))",
        "97170EB542E9AE8F",
    ),
    (
        SemanticMapping(
            record="example:0000001",
            subject="FBbt:0009124",
            predicate="skos:exactMatch",
            object="UBERON:0000003",
            justification="semapv:LexicalMatching",
        ),
        "(7:mapping((10:subject_id43:http://purl.obolibrary.org/obo/FBbt_0009124)(12:predicate_id46:http://www.w3.org/2004/02/skos/core#exactMatch)(9:object_id45:http://purl.obolibrary.org/obo/UBERON_0000003)(21:mapping_justification45:https://w3id.org/semapv/vocab/LexicalMatching)))",
        "18F3436E89AA1AA2",
    ),
    (
        SemanticMapping(
            subject="HP:0009124",
            predicate="skos:exactMatch",
            object="MP:0000003",
            justification="semapv:LexicalSimilarityThresholdMatching",
            similarity_score=0.8,
            provider="https://w3id.org/sssom/core_team",
        ),
        "(7:mapping((10:subject_id41:http://purl.obolibrary.org/obo/HP_0009124)(12:predicate_id46:http://www.w3.org/2004/02/skos/core#exactMatch)(9:object_id41:http://purl.obolibrary.org/obo/MP_0000003)(21:mapping_justification64:https://w3id.org/semapv/vocab/LexicalSimilarityThresholdMatching)(16:mapping_provider32:https://w3id.org/sssom/core_team)(16:similarity_score3:0.8)))",
        "0D45A2E8C64EBD65",
    ),
    # TODO add extension slot
]


class TestSexpr(unittest.TestCase):
    """Test hashing."""

    def test_it(self) -> None:
        """Test hashing."""
        subject_id = Box(label="subject_id", value="http://purl.obolibrary.org/obo/FBbt_00001234")
        self.assertEqual(
            "(10:subject_id44:http://purl.obolibrary.org/obo/FBbt_00001234)",
            box_to_str(subject_id),
        )

        mapping = Box(
            label="mapping",
            value=[
                Box(label="subject_id", value="http://purl.obolibrary.org/obo/FBbt_00001234"),
                Box(label="predicate_id", value="http://www.w3.org/2004/02/skos/core#exactMatch"),
            ],
        )
        self.assertEqual(
            """
        (7:mapping(
           (10:subject_id44:http://purl.obolibrary.org/obo/FBbt_00001234)
           (12:predicate_id46:http://www.w3.org/2004/02/skos/core#exactMatch)
        ))
        """.replace("\n", "").replace(" ", ""),
            box_to_str(mapping),
        )

    def test_smoke(self) -> None:
        """Test hashing works on all example mappings."""
        for example in EXAMPLES:
            with self.subTest(example=example.description):
                s = _hash_mapping_to_str(example.semantic_mapping, TEST_CONVERTER)
                self.assertIsInstance(s, str)

    def test_explicit(self) -> None:
        """Test hashing works on explicit examples."""
        for mapping, sexpr, digest in CASES:
            self.assertEqual(sexpr, mapping_to_sexpr_str(mapping, converter=CONVERTER))
            self.assertEqual(digest, _hash_mapping_to_str(mapping, converter=CONVERTER))
