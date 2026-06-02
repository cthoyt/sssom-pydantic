"""Compare semantic mappings."""

from pathlib import Path

import click
from curies.triples import keep_prefixes_both

import sssom_pydantic
from curies.vocabulary import manual_mapping_curation
from sssom_pydantic import SemanticMapping
from sssom_pydantic.process import invert_by_prefix_pair
from collections import defaultdict

__all__ = ["compare"]


def compare(left_mappings: list[SemanticMapping], right_mappings: list[SemanticMapping],
            show_same: bool = False) -> None:
    """Compare two sets of mappings.

    :param left_mappings: left mappings
    :param right_mappings: right mappings

    Ideas:

    - comparison between manually curated ones
    - check mappings between each
    - which S-O pairs have different predicates / different predicate modifiers / different confidences?
    - (optional) show definitions looked up from PyOBO
    """
    left_mappings = [m for m in left_mappings if m.justification == manual_mapping_curation]
    right_mappings = [m for m in right_mappings if m.justification == manual_mapping_curation]

    left_dd = defaultdict(list)
    right_dd = defaultdict(list)
    for mapping in left_mappings:
        left_dd[mapping.subject, mapping.object].append(mapping)
    for k, values in left_dd.items():
        if len(values) > 1:
            print(f'comparison only works for single predicate between S-O: {k}')
    left_d = {so: values[0] for so, values in left_dd.items() if len(values) == 1}

    for mapping in right_mappings:
        right_dd[mapping.subject, mapping.object].append(mapping)
    for k, values in right_dd.items():
        if len(values) > 1:
            print(f'comparison only works for single predicate between S-O: {k}')
    right_d = {so: values[0] for so, values in right_dd.items() if len(values) == 1}

    left_only = set(left_d) - set(right_d)
    right_only = set(right_d) - set(left_d)
    both = set(right_d).intersection(left_d)

    print(f"{len(left_only)} subject-object pairs left only")
    print(f"{len(right_only)} subject-object pairs right only")
    print(f"{len(both)} subject-object pairs both")
    for k in both:
        left = left_d[k]
        right = right_d[k]
        x = k[0].curie, k[1].curie
        if left.predicate != right.predicate:
            print(f"different predicate for {x}: {left.predicate.curie} in left, {right.predicate.curie} in right")
        elif left.predicate_modifier != right.predicate_modifier:
            print(
                f"different predicate for {x}: {left.predicate_modifier} in left, {right.predicate_modifier} in right")
        elif show_same:
            print(f"same: {x} {left.predicate} ({left.predicate_modifier})")


@click.command()
def _demo() -> None:
    import pystow

    module = pystow.module("tmp")
    internal_url = "https://github.com/NFDI4Chem/rsc-cmo/raw/refs/heads/Add-tsv-files/src/mappings/fix-mappings.sssom.tsv"
    external_url = "https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv"

    target_prefix = "FIX"
    internal_cache_path = module.join(name=f"{target_prefix}-rsc.sssom.tsv")
    internal_mappings = _do_it(internal_url, internal_cache_path, target_prefix)
    external_cache_path = module.join(name=f"{target_prefix}-wg-onto.sssom.tsv")
    external_mappings = _do_it(external_url, external_cache_path, target_prefix)

    compare(internal_mappings, external_mappings)


def _do_it(o: str | Path, p: Path, target_prefix: str) -> list[SemanticMapping]:
    if p.is_file() and False:
        return sssom_pydantic.read(p).mappings
    mappings_l, converter, metadata = sssom_pydantic.read(o)
    mappings = sssom_pydantic.standardize_mappings(mappings_l)
    mappings = keep_prefixes_both(mappings, {"CHMO", target_prefix})
    mappings = list(
        invert_by_prefix_pair(
            mappings,
            target_prefix,
            "CHMO",
            converter=converter,
        )
    )
    click.echo(f"got {len(mappings)} mappings for {target_prefix} from {o}")
    sssom_pydantic.write(mappings, p, converter=converter, metadata=metadata)
    return mappings


if __name__ == "__main__":
    _demo()
