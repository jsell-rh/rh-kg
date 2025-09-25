"""Core functionality for the knowledge graph."""

from .schema import (
    EntitySchema,
    FieldDefinition,
    RelationshipDefinition,
    SchemaInheritanceError,
    SchemaLoadError,
    SchemaLoadResult,
    SchemaValidationError,
)
from .schema_loader import FileSchemaLoader, SchemaLoader

# Export all schema-related components
__all__ = [
    # Schema data structures
    "FieldDefinition",
    "RelationshipDefinition",
    "EntitySchema",
    "SchemaLoadResult",
    # Schema exceptions
    "SchemaValidationError",
    "SchemaLoadError",
    "SchemaInheritanceError",
    # Schema loaders
    "SchemaLoader",
    "FileSchemaLoader",
]
