"""Core functionality for the knowledge graph."""

from .logging import (
    StorageOperationLogger,
    StructlogMiddleware,
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)
from .model_factory import DynamicModelFactory
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

# Export all components
__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "StorageOperationLogger",
    "StructlogMiddleware",
    # Schema and model components
    "DynamicModelFactory",
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
