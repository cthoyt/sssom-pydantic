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
from pydantic import BaseModel

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import NOT
from sssom_pydantic.process import UNSURE, Mark, curate, publish
from tests.cases import R1, R2

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
