"""Router for SSSOM Server."""

import datetime
from typing import Annotated, TypeAlias, cast

import fastapi
from curies import Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request

from sssom_pydantic import SemanticMapping
from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.examples import R1, R2
from sssom_pydantic.process import MARKS, Mark
from sssom_pydantic.query import Query

__all__ = ["router"]

router = APIRouter()


def get_repository(request: Request) -> SemanticMappingRepository:
    """Get the controller from the web app."""
    return cast(SemanticMappingRepository, request.app.state.repository)


#: A type alias for a controller that contains a dependency injection
#: annotation for FastAPI.
AnnotatedRepository: TypeAlias = Annotated[SemanticMappingRepository, Depends(get_repository)]

#: A type alias for a CURIE passed via the path
AnnotatedCURIE = Annotated[str, Path(description="The CURIE for mapping record")]


@router.get("/mapping/", response_model_exclude_unset=True, response_model_exclude_defaults=True)
def get_mappings(
    repository: AnnotatedRepository,
    query: Annotated[Query | None, fastapi.Path(examples=[Query(query="ammeline")])] = None,
    limit: Annotated[int | None, fastapi.Path()] = None,
    offset: Annotated[int | None, fastapi.Path()] = None,
    order_by: Annotated[str | None, fastapi.Path()] = None,
) -> list[SemanticMapping]:
    """Get mappings."""
    return list(repository.get_mappings(query, limit=limit, offset=offset, order_by=order_by))


@router.get(
    "/mapping/{curie}", response_model_exclude_unset=True, response_model_exclude_defaults=True
)
def get_mapping(repository: AnnotatedRepository, curie: AnnotatedCURIE) -> SemanticMapping:
    """Get a mapping by CURIE."""
    mapping = repository.get_mapping(Reference.from_curie(curie))
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping


@router.delete("/mapping/{curie}")
def delete_mapping(repository: AnnotatedRepository, curie: AnnotatedCURIE) -> str:
    """Get a mapping by CURIE."""
    repository.delete_mapping(Reference.from_curie(curie))
    return "ok"


@router.post("/mapping/")
def post_mapping(
    repository: AnnotatedRepository,
    mapping: Annotated[
        SemanticMapping,
        Body(
            examples=[
                SemanticMapping(
                    subject=R1,
                    predicate=exact_match,
                    object=R2,
                    justification=manual_mapping_curation,
                    authors=[charlie],
                    mapping_date=datetime.date(2025, 8, 1),
                ),
            ]
        ),
    ],
) -> Reference:
    """Add a mapping by CURIE."""
    return repository.add_mapping(mapping)


# TODO bulk posting mappings (test on scale up to 10k or 100k at a time)


@router.post("/action/publish/{curie}")
def publish_mapping(
    repository: AnnotatedRepository,
    curie: AnnotatedCURIE,
    date: Annotated[
        datetime.date | None,
        fastapi.Query(..., description="The date on which the mapping was published"),
    ] = None,
) -> Reference:
    """Publish a mapping with the given CURIE."""
    return repository.publish(Reference.from_curie(curie), date=date)


@router.post("/action/curate/{curie}")
def curate_mapping(
    repository: AnnotatedRepository,
    curie: AnnotatedCURIE,
    authors: Annotated[list[Reference], Body(..., examples=[charlie])],
    mark: Annotated[Mark, Body(..., examples=list(MARKS))],
) -> Reference:
    """Publish a mapping with the given CURIE."""
    return repository.curate(Reference.from_curie(curie), authors=authors, mark=mark)
