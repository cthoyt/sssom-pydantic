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
from sssom_pydantic.process import UNSURE, Mark, curate
from tests.cases import R1, R2

today = datetime.date.today()


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
        author = charlie.pair.to_pydantic()

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
                        curation_rule_text=[UNSURE],
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

    def test_curate_unsure(self) -> None:
        """Test overriding an unsure annotation."""
        author = charlie.pair.to_pydantic()

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
                        curation_rule_text=[UNSURE],
                    ),
                    author,
                    "correct",
                ),
            )
