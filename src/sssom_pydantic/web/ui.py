"""A flask-based UI for SSSOM."""

from typing import cast

import flask
from curies import Reference
from flask import Blueprint, current_app
from werkzeug.local import LocalProxy

from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.process import estimate_confidence
from sssom_pydantic.query import Query

__all__ = [
    "ui_blueprint",
]

ui_blueprint = Blueprint("ui", __name__)

repository = cast(SemanticMappingRepository, LocalProxy(lambda: current_app.config["repository"]))


@ui_blueprint.get("/")
def show_home() -> str:
    """Show the homepage."""
    query = Query.model_validate(flask.request.args)
    n_mappings = repository.count_mappings(query)
    n_entities = repository.count_entities(query)
    mappings = repository.get_mappings(
        query,
        limit=10,
        order_by=flask.request.args.get("order_by"),
    )
    return flask.render_template(
        "home.html",
        repository=repository,
        converter=repository.converter,
        mappings=mappings,
        query=query,
        n_mappings=n_mappings,
        n_entities=n_entities,
    )


@ui_blueprint.get("/show/triple/<triple_id>")
def show_triple(triple_id: str) -> str:
    """Show a page for a triple."""
    mappings = repository.get_mappings(Query(triple_id=triple_id))
    confidence = estimate_confidence(mappings)
    return flask.render_template(
        "triple.html",
        repository=repository,
        converter=repository.converter,
        triple_id=triple_id,
        mappings=mappings,
        confidence=confidence,
    )


@ui_blueprint.get("/show/mapping/<curie>")
def show_mapping(curie: str) -> str:
    """Show a page for a mapping."""
    reference = Reference.from_curie(curie)
    mapping = repository.get_mapping(reference)
    if mapping is None:
        raise flask.abort(404)
    return flask.render_template(
        "mapping.html",
        repository=repository,
        converter=repository.converter,
        mapping=mapping,
    )
