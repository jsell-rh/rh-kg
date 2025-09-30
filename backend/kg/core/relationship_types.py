"""Standard relationship types used throughout the knowledge graph system.

This module defines enums for relationship types that have special semantics
or are commonly used across the system, avoiding magic string literals.
"""

from enum import Enum


class StandardRelationshipType(Enum):
    """Standard relationship types with special processing semantics.

    These relationship types have special meaning in the system and may
    trigger additional processing beyond basic relationship creation.
    """

    # External dependency relationships
    DEPENDS_ON = "depends_on"
    """External or internal dependency relationship.

    When processing depends_on relationships:
    1. External dependencies automatically create ExternalDependencyPackage
       and ExternalDependencyVersion entities
    2. Automatically creates has_version relationships between packages and versions
    3. Creates the actual depends_on relationship from source to version entity
    """

    HAS_VERSION = "has_version"
    """Package to version relationship for external dependencies.

    This relationship links ExternalDependencyPackage entities to their
    specific ExternalDependencyVersion entities. Automatically created
    when processing depends_on relationships.
    """

    # Internal relationships
    INTERNAL_DEPENDS_ON = "internal_depends_on"
    """Internal repository dependencies.

    Used for dependencies between repositories within the same organization
    or knowledge graph instance.
    """


class RelationshipTypes:
    """Convenience class providing string constants for relationship types.

    Use this when you need the actual string values rather than enum instances.
    """

    DEPENDS_ON = StandardRelationshipType.DEPENDS_ON.value
    HAS_VERSION = StandardRelationshipType.HAS_VERSION.value
    INTERNAL_DEPENDS_ON = StandardRelationshipType.INTERNAL_DEPENDS_ON.value


# Export both enum and constants for different use cases
__all__ = [
    "StandardRelationshipType",
    "RelationshipTypes",
]
