"""Mermaid utilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import curies

from sssom_pydantic.api import SemanticMapping, hash_mapping, hash_triple

if TYPE_CHECKING:
    import IPython.display

__all__ = [
    "make_mermaid",
    "make_mermaid_block",
    "make_mermaid_ipython",
]


def make_mermaid_ipython(
    mappings: Iterable[SemanticMapping], converter: curies.Converter
) -> IPython.display.Markdown:
    """Make a Mermaid IPython display."""
    from IPython.display import Markdown

    return Markdown(make_mermaid_block(mappings, converter))


def make_mermaid_block(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> str:
    """Make a Mermaid block for Markdown."""
    mermaid = make_mermaid(mappings, converter)
    block = f"```mermaid\n{mermaid}\n```"
    return block


def _n(r: curies.Reference) -> str:
    if name := getattr(r, "name", None):
        return f"{name}\n{r.curie}"
    return r.curie


def make_mermaid(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> str:
    """Make a mermaid flowchart string."""
    lines = []
    edges = []
    derives = []
    mapping_count = 0
    record_count = 0
    seen = set()
    for mapping in mappings:
        if mapping.subject.curie not in seen:
            lines.append(f"{mapping.subject.curie}[{_n(mapping.subject)}]")
            seen.add(mapping.subject.curie)
        if mapping.object.curie not in seen:
            lines.append(f"{mapping.object.curie}[{_n(mapping.object)}]")
            seen.add(mapping.object.curie)

        record_id = hash_mapping(mapping, converter)
        if record_id not in seen:
            seen.add(record_id)
            record_count += 1
            label = f"Record {record_count}\n{mapping.justification.identifier}"
            lines.append(f'{record_id}("{label}")')
            lines.append(f"style {record_id} fill:#bbf")

        for people, relationship in [
            (mapping.authors, "has author"),
            (mapping.reviewers, "has reviewer"),
            (mapping.creators, "has creator"),
        ]:
            for person in people or []:
                if person.curie not in seen:
                    seen.add(person.curie)
                    lines.append(f"{person.curie}[{_n(person)}]")
                    lines.append(f"style {person.curie} fill:#bef")
                edges.append((record_id, relationship, person.curie))

        if mapping.source:
            if mapping.source.curie not in seen:
                seen.add(mapping.source.curie)
                lines.append(f"{mapping.source.curie}[{_n(mapping.source)}]")
                lines.append(f"style {mapping.source.curie} fill:#feb")
            edges.append((record_id, "from", mapping.source.curie))

        mapping_id = hash_triple(mapping, converter).replace("~", "N")
        if mapping_id not in seen:
            mapping_count += 1
            seen.add(mapping_id)
            if mapping_id.endswith("N"):
                label = f'"not {mapping.predicate.curie}\nMapping {mapping_count}"'
            else:
                label = f'"{mapping.predicate.curie}\nMapping {mapping_count}"'
            lines.append(f"{mapping_id}[[{label}]]")
            lines.append(f"style {mapping_id} fill:#f9f")

        edges.append((mapping.subject.curie, "subject of", record_id))
        edges.append((mapping.object.curie, "object of", record_id))
        edges.append((mapping_id, "has evidence", record_id))

        for derived_mapping_reference in mapping.derived_from or []:
            derives.append((record_id, derived_mapping_reference.identifier.replace("~", "N")))

    for s, p, o in edges:
        lines.append(f"{s}-->|{p}|{o}")

    for record_id, mapping_id in derives:
        if mapping_id in seen:
            lines.append(f"{record_id}-->|derived from|{mapping_id}")

    # TODO prune mappings with no incoming relationships

    return "flowchart LR\n" + "\n".join("  " + line for line in lines)
