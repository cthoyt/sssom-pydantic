"""Test API."""

import tempfile
import unittest
from pathlib import Path

from curies import Reference
from curies.vocabulary import exact_match, manual_mapping_curation

from sssom_pydantic import Record, read, write

S1 = Reference(prefix="p1", identifier="i1")
O1 = Reference(prefix="p2", identifier="ia")


class TestIO(unittest.TestCase):
    """Test reading SSSOM."""

    def setUp(self) -> None:
        """Set up the test case."""
        self._tmp_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp_directory.name)

    def tearDown(self) -> None:
        """Tear down the test case."""
        self._tmp_directory.cleanup()

    def test_read_1(self) -> None:
        """Test simplest reading."""
        r = Record(
            subject_id=S1.curie,
            predicate_id=exact_match.curie,
            object_id=O1.curie,
            mapping_justification=manual_mapping_curation.curie,
            mapping_set_id="test",
        )
        path = self.directory.joinpath("test.tsv")
        write([r], path)

        self.assertEqual([r], read(path))
