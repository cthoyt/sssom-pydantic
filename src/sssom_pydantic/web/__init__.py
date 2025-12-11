"""Implementation of a semantic mappings API."""

from .impl import get_app
from .router import router

__all__ = [
    "get_app",
    "router",
]
