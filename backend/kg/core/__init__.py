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
    "EntitySchema",
    "FieldDefinition",
    "FileSchemaLoader",
    "RelationshipDefinition",
    "SchemaInheritanceError",
    "SchemaLoadError",
    "SchemaLoadResult",
    "SchemaLoader",
    "SchemaValidationError",
]
