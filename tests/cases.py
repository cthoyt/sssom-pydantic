"""Test constants."""

from __future__ import annotations

import datetime
import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, Any

from curies import NamedReference, Reference
from curies.vocabulary import (
    charlie,
    exact_match,
    lexical_matching_process,
    manual_mapping_curation,
)
from pydantic import BaseModel

import sssom_pydantic
from sssom_pydantic import MappingSetRecord
from sssom_pydantic.api import MAPPING_HASH_V1_PREFIX, SemanticMapping
from sssom_pydantic.database import (
    NEGATIVE_MAPPING_CLAUSE,
    POSITIVE_MAPPING_CLAUSE,
    UNCURATED_NOT_UNSURE_CLAUSE,
    UNCURATED_UNSURE_CLAUSE,
    SemanticMappingDatabase,
    SemanticMappingModel,
    SemanticMappingRepository,
)
from sssom_pydantic.examples import (
    EXAMPLE_MAPPINGS,
    EXAMPLES,
    P1,
    P2,
    P3,
    R1,
    R2,
    TEST_CONVERTER,
    TEST_PREFIX_MAP,
)
from sssom_pydantic.models import Record
from sssom_pydantic.query import Query, Sort
from sssom_pydantic.web.router import ReviewPayload

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


AUTHOR = charlie.without_name()


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


class MappingTestCaseMixin(unittest.TestCase):
    """A mixin for model testing."""

    def assert_model_equal(
        self,
        expected: SemanticMapping,
        actual: SemanticMapping | None,
        msg: str | None = None,
        *,
        skip_name_check: bool | None = None,
    ) -> None:
        """Assert two models are equal."""
        if actual is None:
            raise self.fail()
        parameters: dict[str, Any] = {
            "exclude_none": True,
            "exclude_unset": True,
            "exclude_defaults": True,
        }
        self.assertEqual(
            expected.model_dump(**parameters), actual.model_dump(**parameters), msg=msg
        )
        if not skip_name_check:
            # FIXME this shouldn't be optional
            self.assertEqual(expected.subject_name, actual.subject_name)
            self.assertEqual(expected.predicate_name, actual.predicate_name)
            self.assertEqual(expected.object_name, actual.object_name)

    def assert_base_model_equal(self, expected: BaseModel, actual: BaseModel) -> None:
        """Check two models are equal by serializing to dict."""
        self.assertEqual(
            expected.model_dump(exclude_none=True), actual.model_dump(exclude_none=True)
        )


class TestRepository(MappingTestCaseMixin):
    """Test the database."""

    repository: SemanticMappingRepository

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
        mapping_4 = _m(justification=lexical_matching_process, reviewer_agreement=0.0)

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
                query=[SemanticMappingModel.justification == lexical_matching_process]
            )
            self.assertEqual(2, len(mappings))
            self.assertEqual(lexical_matching_process, mappings[0].justification)
            self.assertEqual(lexical_matching_process, mappings[1].justification)

        self.assertEqual(1, len(db.get_mappings(limit=1)))
        self.assertEqual(4, len(db.get_mappings()))
        self.assertEqual(4, len(db.get_mappings(limit=1000)))

        if isinstance(db, SemanticMappingDatabase):
            mappings = db.get_mappings(query=[POSITIVE_MAPPING_CLAUSE])
            self.assertEqual(1, len(mappings))
            self.assertEqual(manual_mapping_curation, mappings[0].justification)
            self.assertIsNone(mappings[0].predicate_modifier)
            self.assertIsNone(mappings[0].comment)

        if isinstance(db, SemanticMappingDatabase):
            mappings = db.get_mappings(query=[NEGATIVE_MAPPING_CLAUSE])
            self.assertEqual(1, len(mappings))
            self.assertEqual(manual_mapping_curation, mappings[0].justification)
            self.assertIsNotNone(mappings[0].predicate_modifier)
            self.assertIsNone(mappings[0].comment)

        self.assertIn("mesh", db.converter.get_prefixes())

        self.assertEqual(
            4,
            len(
                db.get_mappings(
                    query=Query(triple_id=db.converter.hash_triple(mapping_1)),
                )
            ),
        )
        self.assertEqual(
            0,
            len(db.get_mappings(query=Query(triple_id="xxxx"))),
        )

        # test no-op query
        query = Query()
        mappings = db.get_mappings(query=query)
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="mesh")
        mappings = db.get_mappings(query=query)
        self.assertEqual(4, len(mappings))

        query = Query(object_prefix="chebi")
        mappings = db.get_mappings(query=query)
        self.assertEqual(4, len(mappings))

        query = Query(subject_prefix="chebi")
        mappings = db.get_mappings(query=query)
        self.assertEqual(0, len(mappings))

        query = Query(object_prefix="mesh")
        mappings = db.get_mappings(query=query)
        self.assertEqual(0, len(mappings))

        query = Query(query="mesh")
        mappings = db.get_mappings(query=query)
        self.assertEqual(4, len(mappings))

        db.delete_mapping(mapping_1)

        # deleting a mapping that doesn't exist should cause nothing to happen
        db.delete_mapping(Reference.from_curie("nope:nope"))

        self.assertEqual(3, db.count_mappings())
        self.assertIsNone(db.get_mapping(db.hash_mapping(mapping_1)))
        with self.assertRaises(ValueError):
            db.get_mapping(db.hash_mapping(mapping_1), strict=True)
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(mapping_2)))
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(mapping_3)))
        self.assertIsNotNone(db.get_mapping(db.hash_mapping(mapping_4)))

    def test_queries(self) -> None:
        """Generate and execute variety of queries."""
        db = self.repository
        db.add_mappings(EXAMPLE_MAPPINGS)
        for mapping in EXAMPLE_MAPPINGS:
            queries = [Query(query=mapping.subject.prefix)]
            for query in queries:
                results = db.get_mappings(query)
                self.assertNotEqual(0, len(results))

                self.assertNotEqual(0, db.count_entities(query))

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
        actual_reference = db.curate(original_hash, authors=charlie, mark="BROAD")
        self.assertIsNone(db.get_mapping(original_hash), msg="old mapping shouldn't still be in db")
        actual_mapping = db.get_mapping(actual_reference)
        self.assertIsNotNone(actual_mapping, msg="new mapping isn't added properly")

        expected_mapping = SemanticMapping(
            subject=R1,
            predicate=P2,
            object=R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        expected_mapping = expected_mapping.model_copy(
            update={
                "record": db.hash_mapping(expected_mapping),
            }
        )
        self.assertEqual("ammeline", expected_mapping.subject_name)
        self.assertEqual("ammeline", actual_mapping.subject_name)
        self.assert_model_equal(expected_mapping, actual_mapping)
        self.assertEqual(
            db.hash_mapping(expected_mapping),
            actual_reference,
            msg="hashing isn't working right",
        )

    def test_curate_narrow(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=R1,
            predicate=P3,
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = self.repository
        db.add_mapping(mapping)
        original_hash = db.hash_mapping(mapping)
        actual_reference = db.curate(original_hash, authors=charlie, mark="NARROW")
        self.assertIsNone(db.get_mapping(original_hash), msg="old mapping shouldn't still be in db")
        actual_mapping = db.get_mapping(actual_reference)
        self.assertIsNotNone(actual_mapping, msg="new mapping isn't added properly")

        expected_mapping = SemanticMapping(
            subject=R1,
            predicate=Reference.from_curie("skos:narrowMatch"),
            object=R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        expected_mapping = expected_mapping.model_copy(
            update={
                "record": db.hash_mapping(expected_mapping),
            }
        )
        self.assert_model_equal(expected_mapping, actual_mapping)
        self.assertEqual(
            db.hash_mapping(expected_mapping),
            actual_reference,
            msg="hashing isn't working right",
        )

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
            reviewers=[charlie],
            review_date=datetime.date.today(),
            reviewer_agreement=0.0,
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
            reviewers=[charlie],
            review_date=datetime.date.today(),
            reviewer_agreement=0.0,
        )

        db = self.repository
        db.add_mappings([m1, m2])
        m2_curated_reference = db.curate(db.hash_mapping(m2), authors=charlie, mark="unsure")
        self.assertEqual(db.hash_mapping(m2_curated), m2_curated_reference)
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
        sorts: list[Sort] = [
            "confidence",
            "date",
            "date-published",
            "date-reviewed",
            "subject",
            "object",
        ]
        for order_by in sorts:
            with self.subTest(order_by=order_by):
                self.repository.get_mappings(order_by=order_by)
                # TODO add explicit values

    def test_query_same_text(self) -> None:
        """Test querying for same text."""
        m1 = SemanticMapping(
            subject=R1,
            predicate=P1,
            object=R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m2 = SemanticMapping(
            subject=NamedReference.from_curie("chebi:2", name="Test-a"),
            predicate=P1,
            object=NamedReference.from_curie("mesh:2", name="test a"),
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m3 = SemanticMapping(
            subject="chebi:3",
            predicate=P1,
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

    def test_read(self) -> None:
        """Test reading mappings from a file."""
        db = self.repository

        for example in EXAMPLES:
            if example.description == "reference for the mapping itself in the `record` field":
                continue
            with self.subTest(desc=example.description), tempfile.TemporaryDirectory() as tmpdir:
                self.assertEqual(0, db.count_mappings())

                mappings = [example.semantic_mapping]
                path = Path(tmpdir).joinpath("test.sssom.tsv")
                sssom_pydantic.write(mappings, path, converter=db.converter, metadata=TEST_METADATA)

                db.read(path)
                self.assertEqual(1, db.count_mappings())

                written_path = Path(tmpdir).joinpath("test2.sssom.tsv")
                db.write(
                    written_path,
                    metadata=TEST_METADATA,
                    exclude_columns=["record_id"],
                    exclude_prefixes=[MAPPING_HASH_V1_PREFIX],
                )
                # clean up before actual test
                db.delete_mapping(example.semantic_mapping)
                self.assertEqual(0, db.count_mappings())

                self.assertEqual(path.read_text(), written_path.read_text())


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "fastapi not installed")
class TestFastAPI(MappingTestCaseMixin):
    """Test API."""

    repository: SemanticMappingRepository
    client: TestClient

    def post_mapping(self, mapping: SemanticMapping) -> Reference:
        """Post a mapping and parse the response."""
        response = self.client.post(
            "/mapping", json=mapping.model_dump(exclude_none=True, exclude_unset=True)
        )
        return Reference.model_validate(response.json())

    def get_mapping(self, reference: Reference) -> SemanticMapping:
        """Get a mapping."""
        response = self.client.get(f"/mapping/{reference.curie}")
        response.raise_for_status()
        return SemanticMapping.model_validate(response.json())

    def assert_missing(self, post_reference: Reference) -> None:
        """Assert a mapping is not in the database."""
        self.assertEqual(
            404,
            self.client.get(f"/mapping/{post_reference.curie}").status_code,
            msg="the old mapping should be deleted",
        )

    def test_converter(self) -> None:
        """Test the converter is ready."""
        self.assertIn("chebi", self.repository.converter.get_prefixes())

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

        actual = self.get_mapping(reference)
        self.assert_model_equal(_m(record=reference), actual)

        self.client.delete(f"/mapping/{reference.curie}")
        self.assertEqual(0, self.repository.count_mappings())

    def test_post_mapping(self) -> None:
        """Test posting a mapping to the API."""
        mapping = _m()

        reference = self.repository.hash_mapping(mapping)
        self.assertEqual(0, self.repository.count_mappings())

        actual = self.post_mapping(mapping)
        self.assertEqual(reference, actual)

        self.assertIsNotNone(self.repository.get_mapping(reference))

    def test_curate_mapping(self) -> None:
        """Test curating a mapping through the API."""
        mapping_predicted = _m(justification=lexical_matching_process, confidence=1)

        post_reference = self.post_mapping(mapping_predicted)

        curation_response = self.client.post(
            f"/action/curate/{post_reference.curie}",
            json={"authors": [charlie.model_dump()], "mark": "correct"},
        )
        curation_response.raise_for_status()
        curation_reference = Reference.model_validate(curation_response.json())

        self.assert_missing(post_reference)

        actual = self.get_mapping(curation_reference)

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

    def test_review_mapping(self) -> None:
        """Test reviewing a mapping."""
        mapping_predicted = _m(justification=lexical_matching_process)

        post_reference = self.post_mapping(mapping_predicted)

        score = 0.99

        payload = ReviewPayload(
            reviewers=[charlie],
            score=score,
        )
        review_response = self.client.post(
            f"/action/review/{post_reference.curie}",
            json=payload.model_dump(),
        )
        review_response.raise_for_status()
        review_reference = Reference.model_validate(review_response.json())

        self.assert_missing(post_reference)

        actual = self.get_mapping(review_reference)

        expected = _m(
            justification=lexical_matching_process,
            reviewers=[charlie],
            review_date=datetime.date.today(),
            reviewer_agreement=score,
        )
        expected = expected.model_copy(update={"record": self.repository.hash_mapping(expected)})
        self.assert_model_equal(expected, actual)
