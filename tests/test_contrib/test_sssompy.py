"""Test conversion to SSSOM-Py."""

from __future__ import annotations

import unittest

from curies.vocabulary import charlie, manual_mapping_curation

import sssom_pydantic.io
from tests.cases import P1, R1, R2, _m


class TestSSSOMPy(unittest.TestCase):
    """Test pandas contribution."""

    def test_to_pandas_1(self) -> None:
        """Test simplest reading."""
        mappings = [_m()]
        df = sssom_pydantic.io._to_df(mappings)

        expected_columns = [
            "subject_id",
            "subject_label",
            "predicate_id",
            "object_id",
            "object_label",
            "mapping_justification",
        ]
        self.assertEqual(expected_columns, df.columns.tolist())

        expected_rows = [
            [R1.curie, R1.name, P1.curie, R2.curie, R2.name, manual_mapping_curation.curie],
        ]
        self.assertEqual(expected_rows, df.to_numpy().tolist())

    def test_to_pandas_2(self) -> None:
        """Test simplest reading."""
        mappings = [_m(authors=[charlie, charlie])]
        df = sssom_pydantic._to_df(mappings)

        expected_columns = [
            "subject_id",
            "subject_label",
            "predicate_id",
            "object_id",
            "object_label",
            "mapping_justification",
            "author_id",
        ]
        self.assertEqual(expected_columns, df.columns.tolist())

        expected_rows = [
            [
                R1.curie,
                R1.name,
                P1.curie,
                R2.curie,
                R2.name,
                manual_mapping_curation.curie,
                "|".join((charlie.curie, charlie.curie)),
            ],
        ]
        self.assertEqual(expected_rows, df.to_numpy().tolist())
