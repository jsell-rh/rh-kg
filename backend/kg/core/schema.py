"""Core schema data structures for dynamic schema loading.

This module defines the data structures used to represent entity schemas
loaded from YAML files. These structures support inheritance, validation,
and Dgraph schema generation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FieldDefinition:
    """Definition of a metadata field.

    Represents a single field in an entity schema with its type,
    validation constraints, and indexing information.
    """

    name: str
    type: str
    required: bool
    validation: str | None = None
    indexed: bool = False
    description: str = ""

    # Type-specific constraints
    min_length: int | None = None
    max_length: int | None = None
    min_items: int | None = None
    max_items: int | None = None
    allowed_values: list[str] | None = None
    pattern: str | None = None
    items: str | None = None  # For array types

    # Deprecation metadata
    deprecated: bool = False
    deprecated_since: str | None = None
    deprecated_reason: str | None = None
    removal_planned: str | None = None
    migration_guide: str | None = None


@dataclass
class RelationshipDefinition:
    """Definition of an entity relationship.

    Represents a relationship between entity types with cardinality
    and direction constraints.
    """

    name: str
    description: str
    target_types: list[str]
    cardinality: str
    direction: str

    # Deprecation metadata
    deprecated: bool = False
    deprecated_since: str | None = None
    deprecated_reason: str | None = None
    removal_planned: str | None = None
    migration_guide: str | None = None


@dataclass
class EntitySchema:
    """Complete entity schema definition.

    Represents a fully resolved entity schema with all inherited
    fields, relationships, and metadata.
    """

    entity_type: str
    schema_version: str
    description: str
    extends: str | None
    required_fields: list[FieldDefinition]
    optional_fields: list[FieldDefinition]
    readonly_fields: list[FieldDefinition]
    relationships: list[RelationshipDefinition]
    validation_rules: dict[str, Any]
    dgraph_type: str
    dgraph_predicates: dict[str, Any]

    # Additional schema metadata
    governance: str | None = None
    deletion_policy: dict[str, Any] | None = None
    auto_creation: dict[str, Any] | None = None
    allow_custom_fields: bool = False


@dataclass
class SchemaLoadResult:
    """Result of schema loading operation.

    Contains loaded schemas and metadata about the loading process.
    """

    schemas: dict[str, EntitySchema]
    loaded_at: datetime
    schema_count: int
    base_schemas: list[str] = field(default_factory=list)
    entity_schemas: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class SchemaLoadError(Exception):
    """Raised when schema loading fails."""

    pass


class SchemaInheritanceError(Exception):
    """Raised when schema inheritance resolution fails."""

    pass
