"""Automatically assess a lexical matching scenario."""

import itertools as itt
import time
from collections import defaultdict
from collections.abc import Collection, Iterable
from typing import Any, TypeVar

import biomappings
import bioregistry
import click
import pyobo
import pystow
from curies.triples import keep_object_prefixes, keep_prefixes_both
from curies.vocabulary import exact_match, lexical_matching_process
from humanize import naturaldelta
from ssslm import GildaGrounder, Grounder, LiteralMapping
from tabulate import tabulate
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

import sssom_pydantic
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.evaluation.evaluation import evaluate_predictions
from sssom_pydantic.process import invert_by_prefix_pair

X = TypeVar("X")


def _tqdm_combinations(x: Collection[X], n: int, **kwargs: Any) -> Iterable[tuple[X, X]]:
    yield from tqdm(itt.combinations(x, n), total=len(x) * (len(x) - 1) // 2, **kwargs)


def _grounder_to_mappings(grounders: dict[str, Grounder]) -> Iterable[SemanticMapping]:
    terms: dict[str, dict[str, list[LiteralMapping]]] = {
        prefix: _get_text_to_literal_mappings(grounder)
        for prefix, grounder in tqdm(grounders.items(), desc="Indexing texts", leave=False)
    }
    for (p1, g1), (p2, _g2) in _tqdm_combinations(
        grounders.items(),
        2,
        unit_scale=True,
        desc="Generating mappings",
        leave=False,
    ):
        text_to_terms = terms[p2]
        for text, literal_mappings in tqdm(
            text_to_terms.items(), unit_scale=True, desc=f"{p1}-{p2} lexical", leave=False
        ):
            scored_matches = g1.get_matches(text)
            # there are lots of ways to do this, now we do all-by-all
            for literal_mapping, scored_match in itt.product(literal_mappings, scored_matches):
                yield SemanticMapping(
                    subject=literal_mapping.reference,
                    predicate=exact_match,
                    object=scored_match.reference,
                    justification=lexical_matching_process,
                    confidence=round(scored_match.score, 4),
                )


def _get_text_to_literal_mappings(grounder: Grounder) -> dict[str, list[LiteralMapping]]:
    if not isinstance(grounder, GildaGrounder):
        raise NotImplementedError
    dd = defaultdict(list)
    for terms in grounder._grounder.entries.values():
        for term in terms:
            dd[term.text].append(LiteralMapping.from_gilda(term))
    return dict(dd)


@click.command()
def main() -> None:
    """Run the workflow for evaluating predicted mappings."""
    converter = bioregistry.get_converter()

    start = time.time()
    positive_biomappings_mappings = biomappings.load_positive_mappings()
    click.echo(
        f"Got {len(positive_biomappings_mappings):,} positive mappings from Biomappings"
        f" in {naturaldelta(time.time() - start)}"
    )

    prefixes = set()
    for m in positive_biomappings_mappings:
        if m.subject.prefix == "mesh":
            prefixes.add(m.object.prefix)
        elif m.object.prefix == "mesh":
            prefixes.add(m.subject.prefix)

    # skip a few
    prefixes -= {"pubchem.compound", "kegg.pathway", "umls", "ncit", "snomedct"}

    start = time.time()
    negative_biomappings_mappings = biomappings.load_false_mappings()
    click.echo(
        f"Got {len(negative_biomappings_mappings):,} negative mappings from Biomappings"
        f" in {naturaldelta(time.time() - start)}"
    )

    start = time.time()
    click.echo("getting MeSH grounder")
    mesh_grounder = pyobo.get_grounder("mesh")
    click.echo(f"Got MeSH grounder in {naturaldelta(time.time() - start)}")

    rows = []
    module = pystow.module("sssom", "evaluation_prediction")

    it = tqdm(sorted(prefixes))
    for prefix in it:
        prefix = converter.standardize_prefix(prefix, strict=True)
        it.set_description(f"Evaluating {prefix}")
        path = module.join(name=f"{prefix}-predicted.sssom.tsv")
        if path.is_file() and False:
            predicted_mappings, _, _ = sssom_pydantic.read(path)
            tqdm.write(
                f"[{prefix}] loaded {len(predicted_mappings):,} predicted mappings from {path}"
            )
        else:
            try:
                with logging_redirect_tqdm():
                    external_grounder = pyobo.get_grounder(prefix, force=False)
            except Exception as e:  # noqa:BLE001
                tqdm.write(click.style(f"[{prefix}] failed to get grounder: {e}"))
                continue
            grounders = {"mesh": mesh_grounder, prefix: external_grounder}
            predicted_mappings = list(_grounder_to_mappings(grounders))
            # TODO deduplicate predicted mappings
            if not predicted_mappings:
                tqdm.write(click.style(f"[{prefix}] retrieved no mappings to MeSH"))
                continue
            tqdm.write(f"[{prefix}] Got {len(predicted_mappings):,} predicted mappings")
            sssom_pydantic.write(
                predicted_mappings,
                path,
                # TODO there's a better way to get metadata for a given prefix
                metadata=MappingSet(id=f"https://example.org/{prefix}-predicted.tsv"),
                converter=converter,
            )

        path = module.join(name=f"{prefix}-from-ontology.sssom.tsv")
        if path.is_file():
            ontology_mappings, _, _ = sssom_pydantic.read(path)
            tqdm.write(
                f"[{prefix}] got {len(ontology_mappings):,} cached mappings from "
                f"the ontology from {path}"
            )
        else:
            ontology_mappings = list(pyobo.get_semantic_mappings(prefix))
            ontology_mappings = list(keep_object_prefixes(ontology_mappings, "mesh"))
            tqdm.write(f"[{prefix}] got {len(ontology_mappings):,} mappings from the ontology")
            sssom_pydantic.write(
                ontology_mappings,
                path,
                # TODO there's a better way to get metadata for a given prefix
                metadata=MappingSet(id=f"https://example.org/{prefix}-from-ontology.tsv"),
                converter=converter,
            )

        mappings: list[SemanticMapping] = list(
            itt.chain(
                positive_biomappings_mappings,
                negative_biomappings_mappings,
                predicted_mappings,
                ontology_mappings,
            )
        )
        tqdm.write(f"[{prefix}] got {len(mappings):,} merged mappings")
        mappings = list(keep_prefixes_both(mappings, [prefix, "mesh"]))
        tqdm.write(f"[{prefix}] got {len(mappings):,} merged mappings filtered to MeSH")
        mappings = list(invert_by_prefix_pair(mappings, prefix, "mesh", converter=converter))
        sssom_pydantic.write(
            mappings,
            module.join(name=f"{prefix}-merged.tsv"),
            metadata=MappingSet(id=f"https://example.org/{prefix}-merged.tsv"),
            converter=converter,
        )

        evaluation_results = evaluate_predictions(mappings, tag=prefix)
        evaluation_row = next(iter(evaluation_results.values()))

        rows.append((f"[{prefix}](https://bioregistry.io/{prefix})", *evaluation_row))

    click.echo(
        tabulate(
            rows,
            headers=["prefix", "completion", "accuracy", "precision", "recall", "f1"],
            floatfmt=".1%",
            tablefmt="github",
        )
    )


if __name__ == "__main__":
    main()
