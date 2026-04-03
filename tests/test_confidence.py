"""Test confidence."""

import unittest

from curies.vocabulary import (
    lexical_matching_process as lexical,
)
from curies.vocabulary import (
    manual_mapping_curation as manual,
)

from sssom_pydantic.confidence import get_mapping_confidence
from tests.cases import _m


class TestConfidence(unittest.TestCase):
    """Test confidence."""

    def test_confidence(self) -> None:
        """Test confidence."""
        _m(justification=lexical, confidence=0.6)
        _m(justification=manual, confidence=0.8)
        _m(justification=manual, confidence=0.9, reviewer_agreement=0.9)
        _m(justification=manual, confidence=0.9, reviewer_agreement=0.5)

        for x in range(0, 100):
            i = x / 10
            v1 = _m(justification=manual, confidence=i, reviewer_agreement=0.4)
            v2 = _m(justification=manual, confidence=i, reviewer_agreement=0.5)
            v3 = _m(justification=manual, confidence=i, reviewer_agreement=0.6)
            self.assertLessEqual(get_mapping_confidence([v1]), get_mapping_confidence([v2]))
            self.assertAlmostEqual(i, get_mapping_confidence([v2]), places=4)
            self.assertLessEqual(get_mapping_confidence([v2]), get_mapping_confidence([v3]))
