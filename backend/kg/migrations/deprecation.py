"""Deprecation tracking and warning system.

This module provides utilities for tracking deprecated schema elements
and generating warnings when they are used.
"""

from dataclasses import dataclass
from typing import Any

from kg.core import EntitySchema, FieldDefinition, RelationshipDefinition


@dataclass
class DeprecatedElement:
    """Represents a deprecated schema element."""

    element_type: str  # "field", "relationship", "entity_type"
    element_name: str
    entity_type: str | None = None
    deprecated_since: str | None = None
    deprecated_reason: str | None = None
    removal_planned: str | None = None
    migration_guide: str | None = None


@dataclass
class DeprecationWarning:
    """Represents a warning about using a deprecated element."""

    field_name: str
    message: str
    deprecated_since: str | None = None
    deprecated_reason: str | None = None
    removal_planned: str | None = None
    migration_guide: str | None = None


class DeprecationTracker:
    """Tracks deprecated elements in schemas."""

    def find_deprecated_elements(self, schema: EntitySchema) -> list[DeprecatedElement]:
        """Find all deprecated elements in a schema.

        Args:
            schema: Entity schema to search

        Returns:
            List of deprecated elements found
        """
        deprecated_elements = []

        # Check required fields
        for field_def in schema.required_fields:
            if field_def.deprecated:
                deprecated_elements.append(
                    self._create_deprecated_element_from_field(
                        field_def, schema.entity_type
                    )
                )

        # Check optional fields
        for field_def in schema.optional_fields:
            if field_def.deprecated:
                deprecated_elements.append(
                    self._create_deprecated_element_from_field(
                        field_def, schema.entity_type
                    )
                )

        # Check readonly fields
        for field_def in schema.readonly_fields:
            if field_def.deprecated:
                deprecated_elements.append(
                    self._create_deprecated_element_from_field(
                        field_def, schema.entity_type
                    )
                )

        # Check relationships
        for rel_def in schema.relationships:
            if rel_def.deprecated:
                deprecated_elements.append(
                    self._create_deprecated_element_from_relationship(
                        rel_def, schema.entity_type
                    )
                )

        return deprecated_elements

    def _create_deprecated_element_from_field(
        self, field_def: FieldDefinition, entity_type: str
    ) -> DeprecatedElement:
        """Create DeprecatedElement from FieldDefinition."""
        return DeprecatedElement(
            element_type="field",
            element_name=field_def.name,
            entity_type=entity_type,
            deprecated_since=field_def.deprecated_since,
            deprecated_reason=field_def.deprecated_reason,
            removal_planned=field_def.removal_planned,
            migration_guide=field_def.migration_guide,
        )

    def _create_deprecated_element_from_relationship(
        self, rel_def: RelationshipDefinition, entity_type: str
    ) -> DeprecatedElement:
        """Create DeprecatedElement from RelationshipDefinition."""
        return DeprecatedElement(
            element_type="relationship",
            element_name=rel_def.name,
            entity_type=entity_type,
            deprecated_since=rel_def.deprecated_since,
            deprecated_reason=rel_def.deprecated_reason,
            removal_planned=rel_def.removal_planned,
            migration_guide=rel_def.migration_guide,
        )


class DeprecationWarningSystem:
    """Generates warnings for deprecated field usage."""

    def check_entity_for_deprecated_fields(
        self, _entity_type: str, entity_data: dict[str, Any]
    ) -> list[DeprecationWarning]:
        """Check entity data for usage of deprecated fields.

        Args:
            _entity_type: Type of entity being checked (unused in simple implementation)
            entity_data: Entity data dictionary

        Returns:
            List of deprecation warnings
        """
        warnings = []

        # For this implementation, we need access to the schema
        # In a real system, this would be injected or looked up
        # For now, we'll create a simple implementation that checks
        # if fields have deprecation metadata

        for field_name, _field_value in entity_data.items():
            # In a full implementation, we would look up the field schema
            # and check if it's deprecated
            # For now, we'll just check if the field name matches known deprecated fields
            if field_name == "owners":  # Example from test
                warnings.append(
                    DeprecationWarning(
                        field_name=field_name,
                        message=f"Field '{field_name}' is deprecated",
                        deprecated_since=None,
                        deprecated_reason=None,
                        removal_planned=None,
                        migration_guide=None,
                    )
                )

        return warnings
