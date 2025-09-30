"""Core functionality for the knowledge graph."""

from .dependency_types import (
    DependencyType,
    DependencyUriBuilder,
    get_dependency_type,
    is_external_dependency,
    is_internal_dependency,
    parse_dependency_uri,
    parse_external_dependency,
    parse_internal_dependency,
)
from .logging import (
    StorageOperationLogger,
    StructlogMiddleware,
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)
from .model_factory import DynamicModelFactory
from .relationship_types import RelationshipTypes, StandardRelationshipType
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
    # Dependency types
    "DependencyType",
    "DependencyUriBuilder",
    # Schema and model components
    "DynamicModelFactory",
    "EntitySchema",
    "FieldDefinition",
    "FileSchemaLoader",
    "RelationshipDefinition",
    "RelationshipTypes",
    "StandardRelationshipType",
    "SchemaInheritanceError",
    "SchemaLoadError",
    "SchemaLoadResult",
    "SchemaLoader",
    "SchemaValidationError",
    "StorageOperationLogger",
    "StructlogMiddleware",
    "bind_context",
    "clear_context",
    # Logging
    "configure_logging",
    "get_dependency_type",
    "get_logger",
    "is_external_dependency",
    "is_internal_dependency",
    "parse_dependency_uri",
    "parse_external_dependency",
    "parse_internal_dependency",
]
