"""Type definitions for schema migration system."""

from enum import Enum


class ChangeType(str, Enum):
    """Types of changes that can occur in schema evolution."""

    ADD = "add"
    REMOVE = "remove"
    MODIFY = "modify"


class ViolationType(str, Enum):
    """Types of violations of additive-only rules."""

    FIELD_REMOVED = "field_removed"
    REQUIRED_FIELD_ADDED = "required_field_added"
    FIELD_TYPE_CHANGED = "field_type_changed"
    FIELD_MADE_REQUIRED = "field_made_required"
    RELATIONSHIP_REMOVED = "relationship_removed"
    RELATIONSHIP_TARGETS_REMOVED = "relationship_targets_removed"
    ENTITY_TYPE_REMOVED = "entity_type_removed"
