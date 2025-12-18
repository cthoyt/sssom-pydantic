"""Test the database."""

import datetime
import tempfile
import unittest
from pathlib import Path

from curies import Reference
from curies.vocabulary import (
    charlie,
    lexical_matching_process,
    manual_mapping_curation,
)

import sssom_pydantic
from sssom_pydantic.api import SemanticMapping, mapping_hash_v1
from sssom_pydantic.database import (
    NEGATIVE_MAPPING_CLAUSE,
    POSITIVE_MAPPING_CLAUSE,
    QUERY_TO_CLAUSE,
    UNCURATED_NOT_UNSURE_CLAUSE,
    UNCURATED_UNSURE_CLAUSE,
    SemanticMappingDatabase,
    SemanticMappingModel,
    clauses_from_query,
)
from sssom_pydantic.examples import EXAMPLE_MAPPINGS
from sssom_pydantic.process import UNSURE
from sssom_pydantic.query import Query
from tests import cases
from tests.cases import TEST_CONVERTER, TEST_METADATA

USER = Reference(prefix="orcid", identifier="1234")


class TestDatabase(unittest.TestCase):
    """Test the database."""

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
        mapping_1 = cases._m()
        mapping_2 = cases._m(justification=lexical_matching_process)
        mapping_3 = cases._m(predicate_modifier="Not")
        mapping_4 = cases._m(justification=lexical_matching_process, comment=UNSURE)

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)

        self.assertEqual(0, db.count_mappings())

        db.add_mapping(mapping_1)
        db.add_mappings([mapping_2, mapping_3, mapping_4])

        self.assertEqual(4, db.count_mappings())

        mappings = db.get_mappings(
            where_clauses=[SemanticMappingModel.justification == lexical_matching_process]
        )
        self.assertEqual(2, len(mappings))
        self.assertEqual(lexical_matching_process, mappings[0].justification)
        self.assertEqual(lexical_matching_process, mappings[1].justification)

        self.assertEqual(1, len(db.get_mappings(limit=1)))
        self.assertEqual(4, len(db.get_mappings()))
        self.assertEqual(4, len(db.get_mappings(limit=1000)))

        mappings = db.get_mappings(where_clauses=[POSITIVE_MAPPING_CLAUSE])
        self.assertEqual(1, len(mappings))
        self.assertEqual(manual_mapping_curation, mappings[0].justification)
        self.assertIsNone(mappings[0].predicate_modifier)
        self.assertIsNone(mappings[0].comment)

        mappings = db.get_mappings(where_clauses=[NEGATIVE_MAPPING_CLAUSE])
        self.assertEqual(1, len(mappings))
        self.assertEqual(manual_mapping_curation, mappings[0].justification)
        self.assertIsNotNone(mappings[0].predicate_modifier)
        self.assertIsNone(mappings[0].comment)

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

        self.assertEqual(3, db.count_mappings())
        self.assertIsNone(db.get_mapping(mapping_hash_v1(mapping_1)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_2)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_3)))
        self.assertIsNotNone(db.get_mapping(mapping_hash_v1(mapping_4)))

    def test_query_functionality(self) -> None:
        """Check that all query fields are implemented."""
        for name in Query.model_fields:
            self.assertIn(name, QUERY_TO_CLAUSE)

    def test_clause_generation(self) -> None:
        """Test clause generation."""
        query = Query(query="hello")
        clauses = clauses_from_query(query)
        self.assertEqual(1, len(clauses))

    def test_queries(self) -> None:
        """Generate and execute variety of queries."""
        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mappings(EXAMPLE_MAPPINGS)
        for mapping in EXAMPLE_MAPPINGS:
            queries = [Query(query=mapping.subject.prefix)]
            for query in queries:
                results = db.get_mappings(query)
                self.assertNotEqual(0, len(results))

    def test_curate_correct(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mapping(mapping)
        original_hash = db._hsh(mapping)
        db.curate(original_hash, authors=charlie, mark="correct")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db._hsh(expected)))

    def test_curate_incorrect(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mapping(mapping)
        original_hash = db._hsh(mapping)
        db.curate(original_hash, authors=charlie, mark="incorrect")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
            predicate_modifier="Not",
        )
        self.assertIsNotNone(db.get_mapping(db._hsh(expected)))

    def test_curate_broad(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mapping(mapping)
        original_hash = db._hsh(mapping)
        db.curate(original_hash, authors=charlie, mark="BROAD")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=cases.R1,
            predicate="skos:broadMatch",
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            mapping_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db._hsh(expected)))

    def test_curate_unsure(self) -> None:
        """Test curating a mapping as unsure in the database."""
        mapping = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=lexical_matching_process,
            confidence=0.95,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mapping(mapping)
        original_hash = db._hsh(mapping)
        db.curate(original_hash, authors=charlie, mark="unsure")
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=lexical_matching_process,
            confidence=0.95,
            comment=UNSURE,
        )
        self.assertIsNotNone(db.get_mapping(db._hsh(expected)))

    def test_publish(self) -> None:
        """Test curation in the database."""
        mapping = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            publication_date=None,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mapping(mapping)
        original_hash = db._hsh(mapping)
        db.publish(original_hash)
        self.assertIsNone(db.get_mapping(original_hash))

        expected = SemanticMapping(
            subject=cases.R1,
            predicate=cases.P1,
            object=cases.R2,
            justification=manual_mapping_curation,
            authors=[charlie],
            publication_date=datetime.date.today(),
        )
        self.assertIsNotNone(db.get_mapping(db._hsh(expected)))

    def test_read(self) -> None:
        """Test reading mappings from a file."""
        # TODO why are `other` and `source` not making the round trip?
        mappings = [m for m in EXAMPLE_MAPPINGS if not m.other and not m.source]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir).joinpath("test.sssom.tsv")
            sssom_pydantic.write(mappings, path, converter=TEST_CONVERTER, metadata=TEST_METADATA)
            db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
            db.read(path, converter=TEST_CONVERTER, metadata=TEST_METADATA)

            written_path = Path(tmpdir).joinpath("test2.sssom.tsv")
            db.write(
                written_path,
                converter=TEST_CONVERTER,
                metadata=TEST_METADATA,
                exclude_columns=["record_id"],
            )
            self.assertEqual(path.read_text(), written_path.read_text())

    def test_query_unsure(self) -> None:
        """Test querying for unsure curations."""
        m1 = SemanticMapping(
            subject="a:1",
            predicate="skos:exactMatch",
            object="b:1",
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m2 = SemanticMapping(
            subject="a:2",
            predicate="skos:exactMatch",
            object="b:2",
            justification=lexical_matching_process,
            confidence=0.95,
        )
        m2_curated = SemanticMapping(
            subject="a:2",
            predicate="skos:exactMatch",
            object="b:2",
            justification=lexical_matching_process,
            confidence=0.95,
            comment=UNSURE,
        )

        db = SemanticMappingDatabase.memory(semantic_mapping_hash=mapping_hash_v1)
        db.add_mappings([m1, m2])
        m2_curated_reference = db.curate(mapping_hash_v1(m2), authors=charlie, mark="unsure")
        self.assertEqual(mapping_hash_v1(m2_curated), m2_curated_reference)
        self.assertEqual(2, db.count_mappings())

        self.assert_models_equal(
            [m1, m2_curated],
            sorted(
                [m.to_semantic_mapping() for m in db.get_mappings()],
                key=lambda m: m.subject.identifier,
            ),
        )

        uncurated_mappings = db.get_mappings([UNCURATED_NOT_UNSURE_CLAUSE])
        self.assert_models_equal(
            [m1],
            [m.to_semantic_mapping() for m in uncurated_mappings],
        )

        unsure_mappings = db.get_mappings([UNCURATED_UNSURE_CLAUSE])
        self.assert_models_equal(
            [m2_curated],
            [m.to_semantic_mapping() for m in unsure_mappings],
        )
