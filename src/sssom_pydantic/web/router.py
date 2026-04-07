"""Router for SSSOM Server."""

import datetime
from typing import Annotated, TypeAlias, cast

import fastapi
from curies import NamedReference, Reference
from curies.vocabulary import charlie, exact_match, manual_mapping_curation
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field

from sssom_pydantic import SemanticMapping
from sssom_pydantic.database import SemanticMappingRepository
from sssom_pydantic.process import MARKS, Mark, estimate_confidence
from sssom_pydantic.query import Query

__all__ = ["ReviewPayload", "router"]

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
                    subject=NamedReference(prefix="mesh", identifier="C000089", name="ammeline"),
                    predicate=exact_match,
                    object=NamedReference(prefix="chebi", identifier="28646", name="ammeline"),
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


class TripleResponse(BaseModel):
    """A response for triples."""

    triple_id: str
    confidence: float
    mappings: list[SemanticMapping]


@router.get("/triple/{triple_id}")
def get_triple(repository: AnnotatedRepository, triple_id: str) -> TripleResponse:
    """Get a triple by CURIE."""
    mappings = repository.get_mappings(Query(triple_id=triple_id))
    return TripleResponse(
        triple_id=triple_id,
        mappings=list(mappings),
        confidence=estimate_confidence(mappings),
    )


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


class ReviewPayload(BaseModel):
    """A review."""

    reviewers: list[Reference] = Field(..., examples=[[charlie]])
    score: float = Field(..., ge=-1.0, le=1.0)


@router.post("/action/review/{curie}")
def review_mapping(
    repository: AnnotatedRepository,
    curie: AnnotatedCURIE,
    review_payload: ReviewPayload,
) -> Reference:
    """Review a mapping with the given CURIE."""
    return repository.review(
        Reference.from_curie(curie), reviewers=review_payload.reviewers, score=review_payload.score
    )
