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
)

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import NOT
from sssom_pydantic.process import Mark, curate
from tests.cases import R1, R2


class TestProcess(unittest.TestCase):
    """Test processing."""

    def test_curate(self) -> None:
        """Test curation."""
        today = datetime.date.today()
        author = charlie.pair.to_pydantic()
        mapping = SemanticMapping(
            subject=R1, predicate=exact_match, object=R2, justification=lexical_matching_process
        )

        with self.assertRaises(ValueError):
            curate(mapping, author, "NOPE")  # type:ignore[arg-type]

        cases: list[tuple[Mark, SemanticMapping]] = [
            (
                "correct",
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
                "incorrect",
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                    predicate_modifier=NOT,
                    mapping_date=today,
                    authors=[author],
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
            (
                "unsure",
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=lexical_matching_process,
                    curation_rule_text=["sssom-curator-unsure"],
                ),
            ),
        ]
        for i, (mark, expected) in enumerate(cases):
            with self.subTest(line=i, mark=mark):
                self.assertEqual(
                    expected.model_dump(exclude_none=True, exclude_unset=True),
                    curate(mapping, author, mark).model_dump(exclude_none=True, exclude_unset=True),
                    msg=f"[{i}] failed for {mark}",
                )
