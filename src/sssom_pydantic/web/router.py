"""Mock an API."""

import datetime
from typing import Annotated, TypeAlias, cast

from curies import Reference
from fastapi import APIRouter, Depends, Query, Request

from sssom_pydantic import SemanticMapping

from .controller import Controller

__all__ = [
    "router",
]

router = APIRouter()


def get_controller(request: Request) -> Controller:
    """Get the controller from the web app."""
    return cast(Controller, request.app.state.controller)


#: A type alias for a controller that contains a dependency injection
#: annotation for FastAPI.
AnnotatedController: TypeAlias = Annotated[Controller, Depends(get_controller)]


@router.get("/mapping/{curie}")
def get_mapping(controller: AnnotatedController, curie: str) -> SemanticMapping:
    """Get a mapping by CURIE."""
    return controller.get_mapping(Reference.from_curie(curie))


@router.get("/get/subject/{curie}")
def get_subject(controller: AnnotatedController, curie: str) -> list[SemanticMapping]:
    """Get a mappings by subject."""
    return controller.get_subject(Reference.from_curie(curie))


@router.get("/get/object/{curie}")
def get_object(controller: AnnotatedController, curie: str) -> list[SemanticMapping]:
    """Get a mappings by object."""
    return controller.get_object(Reference.from_curie(curie))


@router.delete("/mapping/{curie}")
def delete_mapping(controller: AnnotatedController, curie: str) -> str:
    """Get a mapping by CURIE."""
    controller.delete_mapping(Reference.from_curie(curie))
    return "ok"


@router.post("/mapping/")
def post_mapping(controller: AnnotatedController, mapping: SemanticMapping) -> str:
    """Add a mapping by CURIE."""
    controller.add_mapping(mapping)
    return "ok"


@router.post("/action/publish/{curie}")
def publish_mapping(
    controller: AnnotatedController,
    curie: str,
    date: Annotated[datetime.date | None, Query(...)] = None,
) -> str:
    """Publish a mapping with the given CURIE."""
    controller.publish(Reference.from_curie(curie), date=date)
    return "ok"


@router.post("/action/publish/{curie}")
def curate_mapping(
    controller: AnnotatedController,
    curie: str,
    date: Annotated[datetime.date | None, Query(...)] = None,
) -> str:
    """Publish a mapping with the given CURIE."""
    controller.publish(Reference.from_curie(curie), date=date)
    return "ok"
