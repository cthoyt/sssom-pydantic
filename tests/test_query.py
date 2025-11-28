"""Test queries."""

import unittest

from sssom_pydantic.query import QUERY_TO_FUNC, Query


class TestQuery(unittest.TestCase):
    """Test queries."""

    def test_completeness(self) -> None:
        """Test completeness of implementations."""
        for name, field in Query.model_fields.items():
            if field.annotation == str | None:
                self.assertIn(name, QUERY_TO_FUNC)
