"""Tools for working with datatypes.

.. todo:: move into :mod:`curies` with better docs and :class:`curies.Reference` support
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Literal, TypeAlias

import curies
from curies import Reference
from curies import vocabulary as v

__all__ = [
    "XSD_TYPE_TO_FUNC",
    "SemanticPrimitive",
    "TypeHint",
    "primitive_from_string",
    "primitive_to_string",
]

TypeHint: TypeAlias = Literal[
    "xsd:string",
    "xsd:float",
    "xsd:integer",
    "xsd:date",
    "xsd:datetime",
    "linkml:Uriorcurie",
    "xsd:boolean",
    "xsd:anyURI",
]

TypeHintToReference: dict[TypeHint, Reference] = {
    "xsd:string": v.xsd_string,
    "xsd:float": v.xsd_float,
    "xsd:integer": v.xsd_integer,
    "xsd:date": v.xsd_date,
    "xsd:datetime": v.xsd_datetime,
    "linkml:Uriorcurie": v.linkml_uri_or_curie,
    "xsd:boolean": v.xsd_boolean,
    "xsd:anyURI": v.xsd_uri,
}

SemanticPrimitive: TypeAlias = (
    str | int | float | bool | datetime.date | datetime.datetime | Reference
)


def _bool(v: str) -> bool:
    if v == "true":
        return True
    elif v == "false":
        return False
    else:
        raise ValueError


XSD_TYPE_TO_FUNC: dict[TypeHint, Callable[[str], SemanticPrimitive]] = {
    "xsd:string": str,
    "xsd:anyURI": str,
    "xsd:float": float,
    "xsd:double": float,
    "xsd:integer": int,
    "xsd:date": datetime.date.fromisoformat,
    "xsd:datetime": datetime.datetime.fromisoformat,
    "linkml:Uriorcurie": Reference.from_curie,
    "xsd:boolean": _bool,
}


def primitive_from_string(
    type_hint: TypeHint | None, value: str, converter: curies.Converter
) -> SemanticPrimitive:
    """Parse a value via a type hint."""
    if type_hint is None:
        return value
    if type_hint == "sssom:curie":
        return converter.parse_curie(value, strict=True).to_pydantic()
    if type_hint == "linkml:uriOrCurie":
        return converter.parse(value, strict=True).to_pydantic()
    # TODO arbitrary type parsing registration?
    return XSD_TYPE_TO_FUNC[type_hint](value)


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
