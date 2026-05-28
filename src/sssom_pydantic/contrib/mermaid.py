"""Mermaid utilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import curies

from sssom_pydantic.api import NOT, SemanticMapping, hash_mapping, hash_triple

if TYPE_CHECKING:
    import IPython.display

__all__ = [
    "copy_mermaid_markdown",
    "to_mermaid",
    "to_mermaid_ipython",
    "to_mermaid_markdown",
]


def to_mermaid_ipython(
    mappings: Iterable[SemanticMapping], converter: curies.Converter
) -> IPython.display.Markdown:
    """Make a Mermaid IPython display."""
    from IPython.display import Markdown

    return Markdown(to_mermaid_markdown(mappings, converter))


def copy_mermaid_markdown(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> None:
    """Copy a Mermaid block for Markdown to the clipboard with :mod:`pyperclip`."""
    import pyperclip

    pyperclip.copy(to_mermaid_markdown(mappings, converter))


def to_mermaid_markdown(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> str:
    """Make a Mermaid block for Markdown."""
    mermaid = to_mermaid(mappings, converter)
    block = f"```mermaid\n{mermaid}\n```"
    return block


def _n(r: curies.Reference) -> str:
    if name := getattr(r, "name", None):
        return f"{name}\n{r.curie}"
    return r.curie


def to_mermaid(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> str:
    """Make a mermaid flowchart string."""
    lines = []
    edges = []
    derives = []
    mapping_count = 0
    record_count = 0
    seen = set()
    for m in mappings:
        if m.subject.curie not in seen:
            lines.append(f"{m.subject.curie}[{_n(m.subject)}]")
            seen.add(m.subject.curie)
        if m.object.curie not in seen:
            lines.append(f"{m.object.curie}[{_n(m.object)}]")
            seen.add(m.object.curie)

        record_id = hash_mapping(m, converter)
        if record_id not in seen:
            seen.add(record_id)
            record_count += 1
            label = f"{m.predicate.curie}\n{m.justification.identifier}"
            if m.predicate_modifier == NOT:
                label = "not " + label
            lines.append(f'{record_id}("{label}")')
            lines.append(f"style {record_id} fill:#bbf")

        for people, relationship in [
            (m.authors, "has author"),
            (m.reviewers, "has reviewer"),
            (m.creators, "has creator"),
        ]:
            for person in people or []:
                if person.curie not in seen:
                    seen.add(person.curie)
                    lines.append(f"{person.curie}[{_n(person)}]")
                    lines.append(f"style {person.curie} fill:#bef")
                edges.append((record_id, relationship, person.curie))

        if m.source:
            if m.source.curie not in seen:
                seen.add(m.source.curie)
                lines.append(f"{m.source.curie}[{_n(m.source)}]")
                lines.append(f"style {m.source.curie} fill:#feb")
            edges.append((record_id, "from", m.source.curie))

        mapping_id = _clean_msi(hash_triple(m, converter))
        if mapping_id not in seen:
            mapping_count += 1
            seen.add(mapping_id)
            if mapping_id.endswith("N"):
                label = f'"{m.subject.curie}\nnot {m.predicate.curie}\n{m.object.curie}"'
            else:
                label = f'"{m.subject.curie}\n{m.predicate.curie}\n{m.object.curie}"'
            lines.append(f"{mapping_id}[[{label}]]")
            lines.append(f"style {mapping_id} fill:#f9f")

        edges.append((m.subject.curie, "subject of", record_id))
        edges.append((m.object.curie, "object of", record_id))
        edges.append((mapping_id, "has evidence", record_id))

        for derived_mapping_reference in m.derived_from or []:
            derives.append((record_id, _clean_msi(derived_mapping_reference.identifier)))

    for s, p, o in edges:
        lines.append(f"{s}-->|{p}|{o}")

    for record_id, mapping_id in derives:
        if mapping_id in seen:
            lines.append(f"{record_id}-->|derived from|{mapping_id}")

    # TODO prune mappings with no incoming relationships

    return "flowchart LR\n" + "\n".join("  " + line for line in lines)


def _clean_msi(s: str) -> str:
    return s.replace("~", "N")
