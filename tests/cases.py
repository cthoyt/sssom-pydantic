"""Test constants."""

from __future__ import annotations

import datetime
import importlib.util
import unittest
from typing import TYPE_CHECKING, Any

import curies
from curies import NamableReference, NamedReference, Reference
from curies.vocabulary import (
    charlie,
    exact_match,
    lexical_matching_process,
    manual_mapping_curation,
)
from pydantic import BaseModel

from sssom_pydantic import MappingSetRecord
from sssom_pydantic.api import MAPPING_HASH_V1_PREFIX, SemanticMapping, mapping_hash_v1
from sssom_pydantic.database import (
    NEGATIVE_MAPPING_CLAUSE,
    POSITIVE_MAPPING_CLAUSE,
    UNCURATED_NOT_UNSURE_CLAUSE,
    UNCURATED_UNSURE_CLAUSE,
    SemanticMappingDatabase,
    SemanticMappingModel,
    SemanticMappingRepository,
)
from sssom_pydantic.examples import EXAMPLE_MAPPINGS
from sssom_pydantic.models import Record
from sssom_pydantic.process import UNSURE
from sssom_pydantic.query import Query

if TYPE_CHECKING:
    from starlette.testclient import TestClient


__all__ = [
    "P1",
    "R1",
    "R2",
    "TEST_CONVERTER",
    "TEST_MAPPING_SET",
    "TEST_MAPPING_SET_ID",
    "TEST_METADATA",
    "TEST_METADATA_W_PREFIX_MAP",
    "TEST_PREFIX_MAP",
    "TestRepository",
    "_m",
    "_r",
]


R1 = NamedReference(prefix="mesh", identifier="C000089", name="ammeline")
R2 = NamedReference(prefix="chebi", identifier="28646", name="ammeline")
P1 = NamableReference(prefix="skos", identifier="exactMatch")
AUTHOR = charlie.pair.to_pydantic()


def _m(
    predicate: Reference | None = None, justification: Reference | None = None, **kwargs: Any
) -> SemanticMapping:
    """Construct a base semantic mapping."""
    return SemanticMapping(
        subject=R1,
        predicate=P1 if predicate is None else predicate,
        object=R2,
        justification=manual_mapping_curation.curie
        if justification is None
        else justification.curie,
        **kwargs,
    )


def _r(**kwargs: Any) -> Record:
    """Construct a base record."""
    return Record(
        subject_id=R1.curie,
        subject_label=R1.name,
        predicate_id=exact_match.curie,
        object_id=R2.curie,
        object_label=R2.name,
        mapping_justification=manual_mapping_curation.curie,
        **kwargs,
    )


TEST_MAPPING_SET_ID = "https://example.org/sssom.mappingset/1.sssom.tsv"
TEST_PREFIX_MAP = {
    "mesh": "http://id.nlm.nih.gov/mesh/",
    "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
    # the following are the default ones
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "sssom": "https://w3id.org/sssom/",
    "spdx": "https://spdx.org/licenses/",
    "w3id": "https://w3id.org/",
    MAPPING_HASH_V1_PREFIX: f"https://w3id.org/sssom/{MAPPING_HASH_V1_PREFIX}/",
    "issue": "https://github.com/cthoyt/sssom-pydantic/issues/",
    "biolink": "https://w3id.org/biolink/vocab/",
    "rule": "https://example.org/disease-rule/",
    "bioregistry": "https://bioregistry.io/",
    "orcid": "https://orcid.org/",
}
TEST_CONVERTER = curies.Converter.from_prefix_map(TEST_PREFIX_MAP)
TEST_METADATA = MappingSetRecord(
    mapping_set_id=TEST_MAPPING_SET_ID,
    license="https://spdx.org/licenses/CC0-1.0",
)
TEST_MAPPING_SET = TEST_METADATA.process(TEST_CONVERTER)
TEST_METADATA_W_PREFIX_MAP = MappingSetRecord(
    curie_map=TEST_PREFIX_MAP,
    mapping_set_id=TEST_MAPPING_SET_ID,
    license="https://spdx.org/licenses/CC0-1.0",
)


class TestRepository(unittest.TestCase):
    """Test the database."""

    repository: SemanticMappingRepository

    def assert_model_equal(self, expected: SemanticMapping, actual: SemanticMapping) -> None:
        """Assert two models are equal."""
        return self.assertEqual(
            expected.model_dump(
                exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude={"record"}
            ),
            actual.model_dump(
                exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude={"record"}
            ),
        )

    def assert_models_equal(
        self, expected: list[SemanticMapping], actual: list[SemanticMapping]
    ) -> None:
        """Assert two models are equal."""
        return self.assertEqual(
            [
                e.model_dump(
                    exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude={"record"}
                )
                for e in sorted(expected)
            ],
            [
                a.model_dump(
                    exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude={"record"}
                )
                for a in sorted(actual)
            ],
        )

    def test_db(self) -> None:
        """Test the database."""
        mapping_1 = _m()
        mapping_2 = _m(justification=lexical_matching_process)
        mapping_3 = _m(predicate_modifier="Not")
        mapping_4 = _m(justification=lexical_matching_process, comment=UNSURE)

        db = self.repository

        self.assertEqual(0, db.count_mappings())
        self.assertEqual(0, db.count_entities())

        db.add_mapping(mapping_1)
        db.add_mappings([mapping_2, mapping_3, mapping_4])

        self.assertEqual(4, db.count_mappings())
        self.assertEqual(2, db.count_entities())

        if isinstance(db, SemanticMappingDatabase):
            # this test isn't relevant for all databases
            mappings = db.get_mappings(
                where_clauses=[SemanticMappingModel.justification == lexical_matching_process]
            )
            self.assertEqual(2, len(mappings))
            self.assertEqual(lexical_matching_process, mappings[0].justification)
            self.assertEqual(lexical_matching_process, mappings[1].justification)

        self.assertEqual(1, len(db.get_mappings(limit=1)))
        self.assertEqual(4, len(db.get_mappings()))
        self.assertEqual(4, len(db.get_mappings(limit=1000)))

        if isinstance(db, SemanticMappingDatabase):
            mappings = db.get_mappings(where_clauses=[POSITIVE_MAPPING_CLAUSE])
            self.assertEqual(1, len(mappings))
            self.assertEqual(manual_mapping_curation, mappings[0].justification)
            self.assertIsNone(mappings[0].predicate_modifier)
            self.assertIsNone(mappings[0].comment)

        if isinstance(db, SemanticMappingDatabase):
            mappings = db.get_mappings(where_clauses=[NEGATIVE_MAPPING_CLAUSE])
            self.assertEqual(1, len(mappings))
            self.assertEqual(manual_mapping_curation, mappings[0].justification)
            self.assertIsNotNone(mappings[0].predicate_modifier)
            self.assertIsNone(mappings[0].comment)

        self.assertIn("mesh", TEST_CONVERTER.get_prefixes())

        self.assertEqual(
            4,
            len(
                db.get_mappings(
                    where_clauses=Query(triple_id=TEST_CONVERTER.hash_triple(mapping_1)),
                )
            ),
        )
        self.assertEqual(
            0,
            len(db.get_mappings(where_clauses=Query(triple_id="xxxx"))),
        )

        # test no-op query
        query = Query()
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="mesh")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        query = Query(object_prefix="chebi")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="chebi")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(0, len(mappings))

        query = Query(object_prefix="mesh")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(0, len(mappings))

        query = Query(query="mesh")
        mappings = db.get_mappings(where_clauses=query)
        self.assertEqual(4, len(mappings))

        db.delete_mapping(mapping_1)

        # deleting a mapping that doesn't exist should cause nothing to happen
        db.delete_mapping(Reference.from_curie("nope:nope"))

        self.assertEqual(3, db.count_mappings())
        self.assertIsNone(db.get_mapping(mapping_hash_v1(mapping_1)))
        with self.assertRaises(ValueError):
            db.get_mapping(mapping_hash_v1(mapping_1), strict=True)
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_2)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_3)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_4)))

    def test_queries(self) -> None:
        """Generate and execute variety of queries."""
        db = self.repository
        db.add_mappings(EXAMPLE_MAPPINGS)
        for mapping in EXAMPLE_MAPPINGS:
            queries = [Query(query=mapping.subject.prefix)]
            for query in queries:
                results = db.get_mappings(query)
                self.assertNotEqual(0, len(results))

    def test_curate_correct(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = self.repository
        db.add_mapping(mapping)
        original_hash = db.hash_mapping(mapping)
        db.curate(original_hash, authors=charlie, mark="correct")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(expected)))

    def test_curate_incorrect(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = self.repository
        db.add_mapping(mapping)
        original_hash = db.hash_mapping(mapping)
        db.curate(original_hash, authors=charlie, mark="incorrect")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
            predicate_modifier="Not",
        )
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(expected)))

    def test_curate_broad(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = self.repository
        db.add_mapping(mapping)
        original_hash = db.hash_mapping(mapping)
        db.curate(original_hash, authors=charlie, mark="BROAD")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=R1,
            predicate="skos:broadMatch",
            object=R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(expected)))

    def test_curate_unsure(self) -> None:
        """Test curating a mapping as unsure in the database."""
        mapping = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = self.repository
        db.add_mapping(mapping)
        original_hash = db.hash_mapping(mapping)
        db.curate(original_hash, authors=charlie, mark="unsure")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
            comment=UNSURE,
        )
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(expected)))

    def test_mutate_key_error(self) -> None:
        """Test mutating on a missing reference."""
        with self.assertRaises(KeyError):
            self.repository.publish(Reference.from_curie("nope:nope"))

    def test_publish(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            publication_date=None,
        )

        db = self.repository
        db.add_mapping(mapping)
        original_hash = db.hash_mapping(mapping)
        db.publish(original_hash)
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            publication_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(expected)))

    def test_query_unsure(self) -> None:
        """Test querying for unsure curations."""
        m1 = SemanticMapping(
            subject="chebi:1",
            predicate="skos:exactMatch",
            object="mesh:1",
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m2 = SemanticMapping(
            subject="chebi:2",
            predicate="skos:exactMatch",
            object="mesh:2",
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m2_curated = SemanticMapping(
            subject="chebi:2",
            predicate="skos:exactMatch",
            object="mesh:2",
            justification=lexical_matching_process,
            confidence=0.95,
            comment=UNSURE,
        )

        db = self.repository
        db.add_mappings([m1, m2])
        m2_curated_reference = db.curate(mapping_hash_v1(m2), authors=charlie, mark="unsure")
        self.assertEqual(mapping_hash_v1(m2_curated), m2_curated_reference)
        self.assertEqual(2, db.count_mappings())

        self.assert_models_equal(
            [m1, m2_curated],
            sorted(
                db.get_mappings(),
                key=lambda m: m.subject.identifier,
            ),
        )

        if isinstance(db, SemanticMappingDatabase):
            uncurated_mappings = db.get_mappings([UNCURATED_NOT_UNSURE_CLAUSE])
            self.assert_models_equal(
                [m1],
                list(uncurated_mappings),
            )

            unsure_mappings = db.get_mappings([UNCURATED_UNSURE_CLAUSE])
            self.assert_models_equal(
                [m2_curated],
                list(unsure_mappings),
            )

    def test_order_by(self) -> None:
        """Test order by."""
        for order_by in [
            "confidence",
            "date",
            "date-published",
            "date-reviewed",
            "subject",
            "object",
        ]:
            with self.subTest(order_by=order_by):
                self.repository.get_mappings(order_by=order_by)
                # TODO add explicit values

    def test_query_same_text(self) -> None:
        """Test querying for same text."""
        self.maxDiff = None
        m1 = SemanticMapping(
            subject=R1,
            predicate="skos:exactMatch",
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m2 = SemanticMapping(
            subject=NamedReference.from_curie("chebi:2", name="Test-a"),
            predicate="skos:exactMatch",
            object=NamedReference.from_curie("mesh:2", name="test a"),
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m3 = SemanticMapping(
            subject="chebi:3",
            predicate="skos:exactMatch",
            object="mesh:3",
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = self.repository
        db.add_mappings([m1, m2, m3])

        self.assertIsNotNone(db.get_mapping(db.hash_mapping(m1), strict=True).subject_name)
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(m2), strict=True).subject_name)
        self.assertIsNone(db.get_mapping(db.hash_mapping(m3), strict=True).subject_name)

        self.assert_models_equal([m1, m2], list(db.get_mappings(Query(same_text=True))))
        self.assert_models_equal([m3], list(db.get_mappings(Query(same_text=False))))


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "fastapi not installed")
class TestFastAPI(unittest.TestCase):
    """Test API."""

    repository: SemanticMappingRepository
    client: TestClient

    def assert_model_equal(self, expected: BaseModel, actual: BaseModel) -> None:
        """Assert that two models are equal."""
        self.assertEqual(
            expected.model_dump(exclude_unset=True, exclude_none=True),
            actual.model_dump(exclude_unset=True, exclude_none=True),
        )

    def test_get_missing_mapping(self) -> None:
        """Test getting a missing mapping from the API."""
        response = self.client.get("/mapping/nope:nope")
        self.assertEqual(response.status_code, 404)

    def test_get_mapping(self) -> None:
        """Test getting a mapping from the API."""
        expected = _m()
        self.repository.add_mapping(expected)

        reference = self.repository.hash_mapping(expected)
        self.assertIsNotNone(self.repository.get_mapping(reference))

        response = self.client.get(f"/mapping/{reference.curie}")
        response.raise_for_status()
        response_json = response.json()
        actual = SemanticMapping.model_validate(response_json)
        self.assert_model_equal(_m(record=reference), actual)

        self.client.delete(f"/mapping/{reference.curie}")
        self.assertEqual(0, self.repository.count_mappings())

    def test_post_mapping(self) -> None:
        """Test posting a mapping to the API."""
        mapping = _m()

        reference = self.repository.hash_mapping(mapping)
        self.assertEqual(0, self.repository.count_mappings())

        response = self.client.post("/mapping", json=mapping.model_dump())
        response.raise_for_status()

        actual = Reference.model_validate(response.json())
        self.assertEqual(reference, actual)

        self.assertIsNotNone(self.repository.get_mapping(reference))

    def test_curate_mapping(self) -> None:
        """Test curating a mapping through the API."""
        mapping_predicted = _m(justification=lexical_matching_process, confidence=1)

        response = self.client.post("/mapping", json=mapping_predicted.model_dump())
        post_reference = Reference.model_validate(response.json())

        curation_response = self.client.post(
            f"/action/curate/{post_reference.curie}",
            json={"authors": [charlie.model_dump()], "mark": "correct"},
        )
        curation_response.raise_for_status()
        curation_reference = Reference.model_validate(curation_response.json())

        get_response = self.client.get(f"/mapping/{curation_reference.curie}")
        get_response.raise_for_status()
        actual = SemanticMapping.model_validate(get_response.json())

        expected = _m(
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        expected = expected.model_copy(update={"record": self.repository.hash_mapping(expected)})
        self.assert_model_equal(expected, actual)

        publish_response = self.client.post(f"/action/publish/{curation_reference.curie}")
        publish_response.raise_for_status()
        publish_reference = Reference.model_validate(publish_response.json())

        published_mapping_response = self.client.get(f"/mapping/{publish_reference.curie}")
        published_mapping_response.raise_for_status()
        published_mapping = SemanticMapping.model_validate(published_mapping_response.json())

        expected_2 = _m(
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
            publication_date=datetime.date.today(),
        )
        expected_2 = expected_2.model_copy(
            update={"record": self.repository.hash_mapping(expected_2)}
        )
        self.assert_model_equal(expected_2, published_mapping)
