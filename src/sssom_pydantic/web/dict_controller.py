"""A dictionary-based implementation of a controller."""

from curies import Reference

from sssom_pydantic import SemanticMapping

from .controller import Controller

__all__ = [
    "DictController",
]


class DictController(Controller):
    """A demo controller."""

    mappings: dict[Reference, SemanticMapping]

    def __init__(self, mappings: list[SemanticMapping] | None = None) -> None:
        """Initialize the demo controller."""
        self.mappings = {}
        if mappings:
            for mapping in mappings:
                if not mapping.record:
                    raise ValueError
                self.mappings[mapping.record] = mapping

    def get_mapping(self, record: Reference) -> SemanticMapping:
        """Get a mapping by reference."""
        return self.mappings[record]

    def add_mapping(self, mapping: SemanticMapping) -> None:
        """Add a mapping."""
        if not mapping.record:
            raise ValueError
        self.mappings[mapping.record] = mapping

    def delete_mapping(self, record: Reference) -> None:
        """Delete a mapping by reference."""
        del self.mappings[record]

    def count_mappings(self) -> int:
        """Count mappings."""
        return len(self.mappings)

    def hash_mapping(self, mapping: SemanticMapping) -> Reference:
        """Get the mapping's reference."""
        if mapping.record is None:
            raise ValueError
        return mapping.record

    def get_subject(self, subject: Reference) -> list[SemanticMapping]:
        """Get mappings with the given subject."""
        return [mapping for mapping in self.mappings.values() if mapping.subject == subject]

    def get_object(self, obj: Reference) -> list[SemanticMapping]:
        """Get mappings with the given object."""
        return [mapping for mapping in self.mappings.values() if mapping.object == obj]
