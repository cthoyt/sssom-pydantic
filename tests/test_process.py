"""Test processing functions."""

import datetime
import unittest

from curies.vocabulary import (
    broad_match,
    charlie,
    exact_match,
    lexical_matching_process,
    manual_mapping_curation,
    narrow_match,
    semantic_mapping_scopes,
)
from curies.vocabulary import (
    lexical_matching_process as lexical,
)
from curies.vocabulary import (
    manual_mapping_curation as manual,
)
from pydantic import BaseModel

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import NOT
from sssom_pydantic.process import UNSURE, Mark, curate, estimate_confidence, publish
from tests.cases import R1, R2, _m

today = datetime.date.today()
author = charlie.pair.to_pydantic()


class TestProcess(unittest.TestCase):
    """Test processing."""

    def assert_model_equal(
        self, expected: BaseModel, actual: BaseModel, msg: str | None = None
    ) -> None:
        """Assert two models are equal."""
        self.assertEqual(
            expected.model_dump(exclude_none=True, exclude_unset=True),
            actual.model_dump(exclude_none=True, exclude_unset=True),
            msg=msg,
        )

    def test_curate(self) -> None:
        """Test curation."""
        for predicate in semantic_mapping_scopes.values():
            mapping = SemanticMapping(
                subject=R1, predicate=predicate, object=R2, justification=lexical_matching_process
            )
            with self.assertRaises(ValueError):
                curate(mapping, author, "NOPE")  # type:ignore[arg-type]

            cases: list[tuple[Mark, SemanticMapping]] = [
                (
                    "correct",
                    SemanticMapping(
                        subject=R1,
                        predicate=predicate,
                        object=R2,
                        justification=manual_mapping_curation,
                        authors=[author],
                        mapping_date=today,
                    ),
                ),
                (
                    "incorrect",
                    SemanticMapping(
                        subject=R1,
                        predicate=predicate,
                        object=R2,
                        justification=manual_mapping_curation,
                        predicate_modifier=NOT,
                        mapping_date=today,
                        authors=[author],
                    ),
                ),
                (
                    "unsure",
                    SemanticMapping(
                        subject=R1,
                        predicate=predicate,
                        object=R2,
                        justification=lexical_matching_process,
                        comment=UNSURE,
                    ),
                ),
                (
                    "EXACT",
                    SemanticMapping(
                        subject=R1,
                        predicate=exact_match,
                        object=R2,
                        justification=manual_mapping_curation,
                        authors=[author],
                        mapping_date=today,
                    ),
                ),
                (
                    "BROAD",
                    SemanticMapping(
                        subject=R1,
                        predicate=broad_match,
                        object=R2,
                        justification=manual_mapping_curation,
                        authors=[author],
                        mapping_date=today,
                    ),
                ),
                (
                    "NARROW",
                    SemanticMapping(
                        subject=R1,
                        predicate=narrow_match,
                        object=R2,
                        justification=manual_mapping_curation,
                        authors=[author],
                        mapping_date=today,
                    ),
                ),
            ]
            for i, (mark, expected) in enumerate(cases):
                self.assert_model_equal(
                    expected, curate(mapping, author, mark), msg=f"[{i}] failed for {mark}"
                )

    def test_curate_with_comment(self) -> None:
        """Test that comment makes it through without worry."""
        predicate = exact_match
        mapping = SemanticMapping(
            subject=R1,
            predicate=predicate,
            object=R2,
            justification=lexical_matching_process,
            comment="comment",
        )
        self.assert_model_equal(
            SemanticMapping(
                subject=R1,
                predicate=predicate,
                object=R2,
                justification=manual_mapping_curation,
                authors=[author],
                mapping_date=today,
                comment="comment",
            ),
            curate(mapping, author, "correct"),
        )

    def test_curate_unsure(self) -> None:
        """Test overriding an unsure annotation."""
        for predicate in semantic_mapping_scopes.values():
            self.assert_model_equal(
                SemanticMapping(
                    subject=R1,
                    predicate=predicate,
                    object=R2,
                    justification=manual_mapping_curation,
                    authors=[author],
                    mapping_date=today,
                ),
                curate(
                    SemanticMapping(
                        subject=R1,
                        predicate=predicate,
                        object=R2,
                        justification=lexical_matching_process,
                        comment=UNSURE,
                    ),
                    author,
                    "correct",
                ),
            )

    def test_curate_unsure_2(self) -> None:
        """Test overriding an unsure annotation."""
        for predicate in semantic_mapping_scopes.values():
            self.assert_model_equal(
                SemanticMapping(
                    subject=R1,
                    predicate=predicate,
                    object=R2,
                    justification=manual_mapping_curation,
                    authors=[author],
                    mapping_date=today,
                    comment="some text before.",
                ),
                curate(
                    SemanticMapping(
                        subject=R1,
                        predicate=predicate,
                        object=R2,
                        justification=lexical_matching_process,
                        comment=f"some text before. ({UNSURE})",
                    ),
                    author,
                    "correct",
                ),
            )

    def test_curate_unsure_3(self) -> None:
        """Test overriding an unsure annotation."""
        for predicate in semantic_mapping_scopes.values():
            with self.assertRaises(ValueError):
                curate(
                    SemanticMapping(
                        subject=R1,
                        predicate=predicate,
                        object=R2,
                        justification=lexical_matching_process,
                        comment=UNSURE,
                    ),
                    author,
                    "unsure",
                )

    def test_curate_unsure_4(self) -> None:
        """Test overriding an unsure annotation."""
        for predicate in semantic_mapping_scopes.values():
            self.assert_model_equal(
                SemanticMapping(
                    subject=R1,
                    predicate=predicate,
                    object=R2,
                    justification=lexical_matching_process,
                    comment=f"something ({UNSURE})",
                ),
                curate(
                    SemanticMapping(
                        subject=R1,
                        predicate=predicate,
                        object=R2,
                        justification=lexical_matching_process,
                        comment="something",
                    ),
                    author,
                    "unsure",
                ),
            )

    def test_publish(self) -> None:
        """Test the publication workflow."""
        yesterday = today - datetime.timedelta(days=1)
        # no worries
        self.assert_model_equal(
            SemanticMapping(
                subject=R1,
                predicate=exact_match,
                object=R2,
                justification=manual_mapping_curation,
                publication_date=today,
            ),
            publish(
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                ),
            ),
        )
        self.assert_model_equal(
            SemanticMapping(
                subject=R1,
                predicate=exact_match,
                object=R2,
                justification=manual_mapping_curation,
                publication_date=today,
            ),
            publish(
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                    publication_date=yesterday,
                ),
                exists_action="overwrite",
            ),
        )
        self.assert_model_equal(
            SemanticMapping(
                subject=R1,
                predicate=exact_match,
                object=R2,
                justification=manual_mapping_curation,
                publication_date=yesterday,
            ),
            publish(
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                    publication_date=yesterday,
                ),
                exists_action="keep",
            ),
        )
        with self.assertRaises(ValueError):
            publish(
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                    publication_date=yesterday,
                ),
                exists_action="error",
            )

        with self.assertRaises(ValueError):
            publish(
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                    publication_date=yesterday,
                ),
                exists_action="blahblah",  # type:ignore
            )

    def test_estimate_confidence(self) -> None:
        """Test estimating confidence."""
        self.assertEqual(1.0, estimate_confidence([]))

        # sanity checks for fully confident
        l1 = [_m(confidence=1.0)]
        l2 = [_m(confidence=1.0), _m(confidence=1.0)]
        self.assertEqual(1.0, estimate_confidence(l1, confidence_model="binomial"))
        self.assertEqual(1.0, estimate_confidence(l1, confidence_model="mean"))
        self.assertEqual(1.0, estimate_confidence(l2, confidence_model="binomial"))
        self.assertEqual(1.0, estimate_confidence(l2, confidence_model="mean"))

        # sanity checks for fully non-confident
        l3 = [_m(confidence=0.0)]
        l4 = [_m(confidence=0.0), _m(confidence=0.0)]
        self.assertEqual(0.0, estimate_confidence(l3, confidence_model="binomial"))
        self.assertEqual(0.0, estimate_confidence(l3, confidence_model="mean"))
        self.assertEqual(0.0, estimate_confidence(l4, confidence_model="binomial"))
        self.assertEqual(0.0, estimate_confidence(l4, confidence_model="mean"))

        l5 = [_m(confidence=1.0), _m(confidence=0.64)]
        self.assertAlmostEqual(0.82, estimate_confidence(l5, confidence_model="mean"))
        self.assertAlmostEqual(1.0, estimate_confidence(l5, confidence_model="binomial"))

        l6 = [_m(confidence=0.99), _m(confidence=0.64)]
        self.assertAlmostEqual(0.815, estimate_confidence(l6, confidence_model="mean"))
        self.assertAlmostEqual(0.9964, estimate_confidence(l6, confidence_model="binomial"))

    def test_confidence(self) -> None:
        """Test confidence."""
        _m(justification=lexical, confidence=0.6)
        _m(justification=manual, confidence=0.8)
        _m(justification=manual, confidence=0.9, reviewer_agreement=0.9)
        _m(justification=manual, confidence=0.9, reviewer_agreement=0.5)

        for x in range(100):
            i = x / 100
            v1 = _m(justification=manual, confidence=i, reviewer_agreement=0.4)
            v2 = _m(justification=manual, confidence=i, reviewer_agreement=0.5)
            v3 = _m(justification=manual, confidence=i, reviewer_agreement=0.6)
            self.assertLessEqual(estimate_confidence([v1]), estimate_confidence([v2]))
            self.assertAlmostEqual(i, estimate_confidence([v2]), places=4)
            self.assertLessEqual(estimate_confidence([v2]), estimate_confidence([v3]))
