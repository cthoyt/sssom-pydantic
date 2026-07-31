"""Tools for working with datatypes.

.. todo:: move into :mod:`curies` with better docs and :class:`curies.Reference` support
"""

from __future__ import annotations

import datetime
from typing import Literal, TypeAlias

import curies
from curies import Reference
from curies import vocabulary as v

__all__ = [
    "SemanticPrimitive",
    "primitive_from_string",
    "primitive_to_string",
]

SemanticPrimitive: TypeAlias = v.XSDPrimitive | curies.Reference


def primitive_from_string(
    type_hint: Reference | None, value: str, converter: curies.Converter
) -> SemanticPrimitive:
    """Parse a value via a type hint."""
    if type_hint is None:
        return value
    elif type_hint == v.linkml_uri_or_curie:
        return converter.parse(value, strict=True).to_pydantic()
    else:
        parser = v.XSD_TO_PARSER[type_hint]
        return parser(value)


def primitive_to_string(primitive: SemanticPrimitive) -> str:
    """Convert a primitive to string."""
    match primitive:
        case datetime.datetime() | datetime.date():
            return primitive.isoformat()
        case bool():
            return "true" if primitive else "false"
        case str():
            return primitive
        case float() | int():
            return str(primitive)
        case Reference():
            return primitive.curie
        case _:
            raise TypeError(f"unhandled type {type(primitive)} - {primitive}")
