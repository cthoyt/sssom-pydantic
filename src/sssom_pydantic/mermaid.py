from typing import Iterable

import curies
from sssom_pydantic.api import SemanticMapping, hash_mapping, hash_triple

__all__ = ["make_mermaid", "make_mermaid_block"]


def make_mermaid_block(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> str:
    mermaid = make_mermaid(mappings, converter)
    block = f"```mermaid\n{mermaid}\n```"
    return block


def _n(r: curies.NamableReference) -> str:
    if not r.name:
        return r.curie
    return f"{r.name}\n{r.curie}"

def make_mermaid(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> str:
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
            label = f"Record {record_count}"
            lines.append(f"{record_id}({label})")
            lines.append(f"style {record_id} fill:#bbf")

        mapping_id = hash_triple(mapping, converter).replace("~", "N")
        if mapping_id not in seen:
            mapping_count += 1
            seen.add(mapping_id)
            if mapping_id.endswith("N"):
                label = f"\"not {mapping.predicate.curie}\nMapping {mapping_count}\""
            else:
                label = f"\"{mapping.predicate.curie}\nMapping {mapping_count}\""
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

    return "flowchart LR\n" + "\n".join("  " + line for line in lines)


if __name__ == '__main__':
    from sssom_pydantic.examples import EXAMPLE_MAPPINGS, TEST_CONVERTER

    print(make_mermaid(EXAMPLE_MAPPINGS, TEST_CONVERTER))
