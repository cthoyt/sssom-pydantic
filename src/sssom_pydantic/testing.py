"""Utilities for testing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import curies

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import mapping_to_sexpr_str

if TYPE_CHECKING:
    import unittest

__all__ = [
    "assert_semantic_model_equal",
]


def assert_semantic_model_equal(
    test_case: unittest.TestCase,
    expected: SemanticMapping,
    actual: SemanticMapping | None,
    *,
    converter: curies.Converter | None = None,
    msg: str | None = None,
) -> None:
    """Assert two models are equal."""
    if actual is None:
        raise test_case.fail()

    if converter is not None:
        test_case.assertEqual(
            mapping_to_sexpr_str(expected, converter, _debug=True),
            mapping_to_sexpr_str(actual, converter, _debug=True),
        )

    parameters: dict[str, Any] = {
        "exclude_none": True,
        "exclude_unset": True,
        "exclude_defaults": True,
    }
    test_case.assertEqual(
        expected.model_dump(**parameters), actual.model_dump(**parameters), msg=msg
    )
    test_case.assertEqual(expected.subject_name, actual.subject_name)
    test_case.assertEqual(expected.predicate_name, actual.predicate_name)
    test_case.assertEqual(expected.object_name, actual.object_name)
