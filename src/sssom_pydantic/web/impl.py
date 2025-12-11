"""Construct a FastAPI app."""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from sssom_pydantic.api import SemanticMappingHash, mapping_hash_v1

from .router import router
from ..database import SemanticMappingDatabase

__all__ = [
    "get_app",
]


def get_app(
    *,
    database: SemanticMappingDatabase | None = None,
    semantic_mapping_hash: SemanticMappingHash | None = None,
) -> FastAPI:
    """Get a FastAPI app."""
    if database is None:
        if semantic_mapping_hash is None:
            semantic_mapping_hash = mapping_hash_v1
        database = SemanticMappingDatabase.memory(semantic_mapping_hash=semantic_mapping_hash)
    app = FastAPI()
    app.state.database = database
    app.include_router(router)
    return app


def get_openapi_schema() -> dict[str, Any]:
    """Get the OpenAPI schema."""
    return get_app().openapi()


def write_openapi_schema(path: Path) -> None:
    """Write the OpenAPI schema."""
    path.write_text(json.dumps(get_openapi_schema(), indent=2))
