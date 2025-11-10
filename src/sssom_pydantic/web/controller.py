"""Abstract implementation of a semantic mapping controller."""

import datetime
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Concatenate, Generic, Literal, ParamSpec

from curies import Reference
from curies.vocabulary import manual_mapping_curation
from pydantic import BaseModel
from typing_extensions import TypeVar

from sssom_pydantic import SemanticMapping
from sssom_pydantic.api import NOT

__all__ = [
    "Controller",
]

T = TypeVar("T", bound=SemanticMapping, default=SemanticMapping)
P = ParamSpec("P")


class Query(BaseModel):
    """A filter on mappings."""


class Controller(ABC, Generic[T]):
    """A controller."""

    @abstractmethod
    def get_mapping(self, record: Reference) -> T:
        """Get a semantic mapping by reference."""

    @abstractmethod
    def delete_mapping(self, record: Reference) -> None:
        """Delete a semantic mapping by reference."""

    @abstractmethod
    def add_mapping(self, mapping: T) -> None:
        """Add a mapping."""

    @abstractmethod
    def count_mappings(self) -> int:
        """Count the mappings."""

    @abstractmethod
    def hash_mapping(self, mapping: T) -> Reference:
        """Get the record ID for the semantic mapping."""

    def _update_hash(self, mapping: T) -> T:
        return mapping.model_copy(update={"record": self.hash_mapping(mapping)})

    def _modify(
        self,
        record: Reference,
        func: Callable[Concatenate[T, P], T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Publish a mapping."""
        mapping = self.get_mapping(record)
        new_mapping = func(mapping, *args, **kwargs)
        new_mapping = self._update_hash(new_mapping)
        self.add_mapping(new_mapping)
        self.delete_mapping(record)
        return new_mapping

    def publish(self, record: Reference, date: datetime.date | None = None) -> T:
        """Publish a mapping."""
        return self._modify(record, publish_mapping, date=date)

    def curate(
        self,
        record: Reference,
        agents: Reference | list[Reference],
        add_not: bool = False,
        confidence: float | None = None,
        **kwargs: Any,
    ) -> T:
        """Curate a predicted record."""
        return self._modify(
            record, curate, agents=agents, confidence=confidence, add_not=add_not, **kwargs
        )

    @abstractmethod
    def get_subject(self, subject: Reference) -> list[T]:
        """Get mappings with the given subject."""

    @abstractmethod
    def get_object(self, obj: Reference) -> list[T]:
        """Get mappings with the given object."""


def publish_mapping(
    mapping: T,
    /,
    *,
    exists_action: Literal["error", "overwrite", "keep"] | None = None,
    date: datetime.date | None = None,
) -> T:
    """Add a publication date to the mapping."""
    if mapping.publication_date is not None:
        if exists_action == "error" or exists_action is None:
            raise ValueError
        elif exists_action == "keep":
            return mapping
        elif exists_action == "overwrite":
            pass  # just use the implementation below to update the publication date
        else:
            raise ValueError(f"invalid exists_action: {exists_action}")
    rv = mapping.model_copy(
        update={"publication_date": date if date is not None else datetime.date.today()}
    )
    return rv


def curate(
    mapping: T,
    /,
    *,
    agents: Reference | list[Reference],
    confidence: float | None = None,
    add_not: bool = False,
    **kwargs: Any,
) -> T:
    """Curate a predicted record."""
    agents = [agents] if isinstance(agents, Reference) else agents
    if not agents:
        raise ValueError

    if mapping.justification == manual_mapping_curation:
        reviewers = set(mapping.reviewers or []).union(agents)
        new_mapping = mapping.model_copy(
            update={
                "reviewers": sorted(reviewers),
            }
        )
    else:
        # We're going down the manual curation process

        if mapping.authors:
            raise ValueError("")

        update = {
            "justification": manual_mapping_curation,
            "mapping_date": datetime.date.today(),
            "authors": agents,
            "confidence": confidence,
            # Zero out the following
            "mapping_tool": None,
            "similarity_measure": None,
            "similarity_score": None,
            **kwargs,
        }
        if add_not:
            update["predicate_modifier"] = NOT

        new_mapping = mapping.model_copy(update=update)
    return new_mapping
