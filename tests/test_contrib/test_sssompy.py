"""Test conversion to SSSOM-Py."""

from __future__ import annotations

import importlib.util
import unittest

from curies.vocabulary import charlie, manual_mapping_curation

from sssom_pydantic.contrib.sssom import to_df, to_sssompy
from tests.cases import P1, R1, R2, TEST_CONVERTER, TEST_METADATA, _m


@unittest.skipUnless(importlib.util.find_spec("sssom"), reason="SSSOM-Py must be installed")
class TestSSSOMPy(unittest.TestCase):
    """Test pandas contribution."""

    def test_to_pandas_1(self) -> None:
        """Test simplest reading."""
        from sssom import MappingSetDataFrame

        mappings = [_m()]
        df = to_df(mappings)

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

        def assert_msdf(msdf: MappingSetDataFrame) -> None:
            self.assertEqual(expected_rows, msdf.df.to_numpy().tolist())
            self.assertEqual(TEST_CONVERTER.bimap, msdf.converter.bimap)
            self.assertEqual(TEST_METADATA, msdf.metadata)

        msdf_no_validate = to_sssompy(
            mappings, converter=TEST_CONVERTER, metadata=TEST_METADATA, linkml_validate=False
        )
        assert_msdf(msdf_no_validate)

        msdf_validate = to_sssompy(
            mappings, converter=TEST_CONVERTER, metadata=TEST_METADATA, linkml_validate=True
        )
        assert_msdf(msdf_validate)

    def test_to_pandas_2(self) -> None:
        """Test simplest reading."""
        mappings = [_m(authors=[charlie, charlie])]
        df = to_df(mappings)

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
