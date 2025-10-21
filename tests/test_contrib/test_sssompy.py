"""Test conversion to SSSOM-Py."""

from __future__ import annotations

import importlib.util
import unittest
from typing import TYPE_CHECKING

from curies.vocabulary import charlie, manual_mapping_curation

from sssom_pydantic.contrib.sssom import _mappings_to_df, mappings_to_msdf
from tests.cases import P1, R1, R2, TEST_CONVERTER, TEST_METADATA, _m

if TYPE_CHECKING:
    import sssom


@unittest.skipUnless(importlib.util.find_spec("sssom"), reason="SSSOM-Py must be installed")
class TestSSSOMPy(unittest.TestCase):
    """Test pandas contribution."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.mappings = [_m()]
        self.expected_columns = [
            "subject_id",
            "subject_label",
            "predicate_id",
            "object_id",
            "object_label",
            "mapping_justification",
        ]
        self.expected_rows = [
            [R1.curie, R1.name, P1.curie, R2.curie, R2.name, manual_mapping_curation.curie],
        ]

    def assert_msdf(self, msdf: sssom.MappingSetDataFrame) -> None:
        """Assert the MSDF is correct."""
        self.assertEqual(self.expected_rows, msdf.df.to_numpy().tolist())
        self.assertEqual(TEST_CONVERTER.bimap, msdf.converter.bimap)
        self.assertNotIn("curie_map", msdf.metadata)
        self.assertEqual(TEST_METADATA, msdf.metadata)

    def test_to_pandas_1(self) -> None:
        """Test simplest reading."""
        df = _mappings_to_df(self.mappings)
        self.assertEqual(self.expected_columns, df.columns.tolist())
        self.assertEqual(self.expected_rows, df.to_numpy().tolist())

    def test_to_msdf_no_validate(self) -> None:
        """Test converting to a mapping set dataframe without¬ LinkML validation."""
        msdf = mappings_to_msdf(
            self.mappings, converter=TEST_CONVERTER, metadata=TEST_METADATA, linkml_validate=False
        )
        self.assert_msdf(msdf)

    def test_to_msdf_validate(self) -> None:
        """Test converting to a mapping set dataframe with LinkML validation."""
        msdf = mappings_to_msdf(
            self.mappings, converter=TEST_CONVERTER, metadata=TEST_METADATA, linkml_validate=True
        )
        self.assert_msdf(msdf)

    def test_to_pandas_2(self) -> None:
        """Test simplest reading."""
        mappings = [_m(authors=[charlie, charlie])]
        df = _mappings_to_df(mappings)

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
