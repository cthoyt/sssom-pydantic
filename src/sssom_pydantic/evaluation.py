"""A workflow for evaluating predicted mappings."""

import itertools as itt
import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import NamedTuple, TypeAlias, TypeVar

import click
import curies
from curies.vocabulary import exact_match, lexical_matching_process, manual_mapping_curation
from ssslm import GildaGrounder, Grounder, LiteralMapping
from tqdm import tqdm

import sssom_pydantic
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.process import invert_by_prefix_pair

logger = logging.getLogger(__name__)

X = TypeVar("X")


def _get_v1(
    positive_set: set[X], negative_set: set[X], predicted_set: set[X]
) -> tuple[int, int, int, int]:
    tp = len(positive_set.intersection(predicted_set))  # true positives
    fp = len(negative_set.intersection(predicted_set))  # false positives
    fn = len(positive_set - predicted_set)  # false negatives
    tn = len(negative_set - predicted_set)  # true negatives
    return tp, fp, fn, tn


DD: TypeAlias = dict[str, set[SemanticMapping]]


def stratify(mappings: Iterable[SemanticMapping], converter: curies.Converter) -> tuple[DD, DD, DD]:
    """Stratify a set of mappings."""
    positive, negative, predicted = defaultdict(set), defaultdict(set), defaultdict(set)
    for mapping in mappings:
        hsh = converter.hash_triple(mapping)
        if mapping.justification == lexical_matching_process:
            predicted[hsh].add(mapping)
        elif (
            mapping.justification == manual_mapping_curation and mapping.predicate_modifier is None
        ):
            positive[hsh].add(mapping)
        elif (
            mapping.justification == lexical_matching_process
            and mapping.predicate_modifier is not None
        ):
            negative[hsh].add(mapping)
        else:
            pass  # TODO what to do with others?
    return dict(positive), dict(negative), dict(predicted)


class Evaluation(NamedTuple):
    """An evaluation tuple."""

    completion: float
    accuracy: float
    precision: float
    recall: float
    f1: float


def evaluate_predictions(
    mappings: Iterable[SemanticMapping],
    converter: curies.Converter,
    *,
    tag: str | None = None,
) -> Evaluation:
    """Evaluate predicted mappings using ground truth positive and negative mappings."""
    positive_set, negative_set, predicted_set = map(set, stratify(mappings, converter))

    tp, fp, fn, tn = _get_v1(positive_set, negative_set, predicted_set)

    predicted_only = len(predicted_set - positive_set - negative_set)
    union_len = len(positive_set.union(predicted_set).union(negative_set))

    msg = f"union={union_len:,}, intersection={tp:,}, curated={fn:,}, predicted={predicted_only:,}"
    if tag is not None:
        msg = f"[{tag}] {msg}"
    logger.info(msg)

    accuracy = (tp + tn) / (tp + tn + fp + fn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * tp / (2 * tp + fp + fn)
    completion = 1 - predicted_only / len(predicted_set)

    # what is the percentage of curated examples that are positive?
    _positive_percentage = len(positive_set) / (len(positive_set) + len(negative_set))

    return Evaluation(completion, accuracy, precision, recall, f1)


def _get_text_to_literal_mappings(grounder: Grounder) -> dict[str, list[LiteralMapping]]:
    if not isinstance(grounder, GildaGrounder):
        raise NotImplementedError
    dd = defaultdict(list)
    for terms in grounder._grounder.entries.values():
        for term in terms:
            dd[term.text].append(LiteralMapping.from_gilda(term))
    return dict(dd)


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


@click.command()
def main() -> None:
    """Run the workflow for evaluating predicted mappings."""
    import biomappings
    import bioregistry
    import pyobo
    import pystow
    from curies.triples import keep_prefixes_both
    from tabulate import tabulate

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
