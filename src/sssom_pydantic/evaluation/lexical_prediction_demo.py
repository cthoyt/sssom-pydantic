"""Automatically assess a lexical matching scenario."""

import itertools as itt
from collections import defaultdict
from collections.abc import Iterable

import biomappings
import bioregistry
import click
import pyobo
import pystow
from curies.triples import keep_prefixes_both
from curies.vocabulary import exact_match, lexical_matching_process
from ssslm import GildaGrounder, Grounder, LiteralMapping
from tabulate import tabulate
from tqdm import tqdm

import sssom_pydantic
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.evaluation.evaluation import evaluate_predictions
from sssom_pydantic.process import invert_by_prefix_pair


def _grounder_to_mappings(grounders: dict[str, Grounder]) -> Iterable[SemanticMapping]:
    terms: dict[str, dict[str, list[LiteralMapping]]] = {
        prefix: _get_text_to_literal_mappings(grounder)
        for prefix, grounder in tqdm(grounders.items(), desc="Indexing texts")
    }
    for (p1, g1), (p2, _g2) in tqdm(
        itt.combinations(grounders.items(), 2), unit_scale=True, desc="Generating mappings"
    ):
        text_to_terms = terms[p2]
        for text, literal_mappings in tqdm(
            text_to_terms.items(), unit_scale=True, desc=f"{p1}-{p2} lexical"
        ):
            scored_matches = g1.get_matches(text)
            # there are lots of ways to do this, now we do all-by-all
            for literal_mapping, scored_match in itt.product(literal_mappings, scored_matches):
                yield SemanticMapping(
                    subject=literal_mapping.reference,
                    predicate=exact_match,
                    object=scored_match.reference,
                    justification=lexical_matching_process,
                    confidence=scored_match.score,
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
    converter = bioregistry.get_preferred_converter()

    positive_biomappings_mappings = biomappings.load_positive_mappings()
    click.echo(f"Got {len(positive_biomappings_mappings):,} positive mappings from Biomappings")

    negative_biomappings_mappings = biomappings.load_false_mappings()
    click.echo(f"Got {len(negative_biomappings_mappings):,} negative mappings from Biomappings")

    rows = []
    mesh_grounder = pyobo.get_grounder("mesh")
    for prefix in sorted(["chebi", "maxo", "cl", "doid", "go", "uberon", "vo", "clo"]):
        path = pystow.join(
            "semra", "evaluation_prediction", name=f"evaluation_prediction_sample_{prefix}.tsv"
        )
        if path.is_file():
            predicted_mappings = sssom_pydantic.read(path).mappings
        else:
            grounders = {"mesh": mesh_grounder, prefix: pyobo.get_grounder(prefix)}
            predicted_mappings = list(_grounder_to_mappings(grounders))
            click.echo(f"Got {len(predicted_mappings):,} predicted mappings")
            sssom_pydantic.write(
                predicted_mappings,
                path,
                metadata=MappingSet(id=f"https://example.org/{prefix}.tsv"),
            )

        ontology_mappings = pyobo.get_semantic_mappings(prefix)
        click.echo(f"[{prefix}] got {len(ontology_mappings):,} mappings from the ontology")

        mappings: Iterable[SemanticMapping] = itt.chain(
            positive_biomappings_mappings,
            negative_biomappings_mappings,
            predicted_mappings,
            ontology_mappings,
        )
        mappings = keep_prefixes_both(mappings, [prefix, "mesh"])
        mappings = invert_by_prefix_pair(mappings, prefix, "mesh", converter=converter)

        evaluation_row = evaluate_predictions(mappings, tag=prefix, converter=converter)
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
