"""Schema change detection for additive-only evolution.

This module detects changes between schema versions and categorizes them
into field changes, relationship changes, and entity type changes.
"""

from dataclasses import dataclass, field
from typing import Any

from kg.migrations.types import ChangeType


@dataclass
class FieldChange:
    """Represents a change to a field."""

    entity_type: str
    field_name: str
    change_type: ChangeType
    old_definition: dict[str, Any] | None = None
    new_definition: dict[str, Any] | None = None


@dataclass
class RelationshipChange:
    """Represents a change to a relationship."""

    entity_type: str
    relationship_name: str
    change_type: ChangeType
    old_definition: dict[str, Any] | None = None
    new_definition: dict[str, Any] | None = None


@dataclass
class EntityTypeChange:
    """Represents a change to an entity type."""

    entity_type: str
    change_type: ChangeType
    schema: dict[str, Any] | None = None


@dataclass
class SchemaChanges:
    """Container for all detected schema changes."""

    field_changes: list[FieldChange] = field(default_factory=list)
    relationship_changes: list[RelationshipChange] = field(default_factory=list)
    entity_type_changes: list[EntityTypeChange] = field(default_factory=list)


class SchemaChangeDetector:
    """Detects changes between schema versions."""

    def detect_changes(
        self, old_schemas: dict[str, Any], new_schemas: dict[str, Any]
    ) -> SchemaChanges:
        """Detect changes between old and new schemas.

        Args:
            old_schemas: Dictionary of old entity schemas (entity_type -> EntitySchema)
            new_schemas: Dictionary of new entity schemas (entity_type -> EntitySchema)

        Returns:
            SchemaChanges object containing all detected changes
        """
        changes = SchemaChanges()

        # Detect entity type changes (additions and removals)
        old_types = set(old_schemas.keys())
        new_types = set(new_schemas.keys())

        for added_type in new_types - old_types:
            changes.entity_type_changes.append(
                EntityTypeChange(
                    entity_type=added_type,
                    change_type=ChangeType.ADD,
                    schema=new_schemas[added_type],
                )
            )

        for removed_type in old_types - new_types:
            changes.entity_type_changes.append(
                EntityTypeChange(
                    entity_type=removed_type,
                    change_type=ChangeType.REMOVE,
                    schema=old_schemas[removed_type],
                )
            )

        # Detect field and relationship changes for existing entity types
        for entity_type in old_types & new_types:
            old_schema = old_schemas[entity_type]
            new_schema = new_schemas[entity_type]

            # Detect field changes
            self._detect_field_changes(entity_type, old_schema, new_schema, changes)

            # Detect relationship changes
            self._detect_relationship_changes(
                entity_type, old_schema, new_schema, changes
            )

        return changes

    def _detect_field_changes(
        self,
        entity_type: str,
        old_schema: Any,
        new_schema: Any,
        changes: SchemaChanges,
    ) -> None:
        """Detect changes in fields between old and new schema."""
        # Get all fields from both schemas
        old_fields = self._get_all_fields(old_schema)
        new_fields = self._get_all_fields(new_schema)

        old_field_names = set(old_fields.keys())
        new_field_names = set(new_fields.keys())

        # Detect added fields
        for added_field in new_field_names - old_field_names:
            changes.field_changes.append(
                FieldChange(
                    entity_type=entity_type,
                    field_name=added_field,
                    change_type=ChangeType.ADD,
                    old_definition=None,
                    new_definition=new_fields[added_field],
                )
            )

        # Detect removed fields
        for removed_field in old_field_names - new_field_names:
            changes.field_changes.append(
                FieldChange(
                    entity_type=entity_type,
                    field_name=removed_field,
                    change_type=ChangeType.REMOVE,
                    old_definition=old_fields[removed_field],
                    new_definition=None,
                )
            )

        # Detect modified fields
        for common_field in old_field_names & new_field_names:
            old_def = old_fields[common_field]
            new_def = new_fields[common_field]

            # Check if field definition changed
            if self._field_definitions_differ(old_def, new_def):
                changes.field_changes.append(
                    FieldChange(
                        entity_type=entity_type,
                        field_name=common_field,
                        change_type=ChangeType.MODIFY,
                        old_definition=old_def,
                        new_definition=new_def,
                    )
                )

    def _detect_relationship_changes(
        self,
        entity_type: str,
        old_schema: Any,
        new_schema: Any,
        changes: SchemaChanges,
    ) -> None:
        """Detect changes in relationships between old and new schema."""
        old_relationships = {rel.name: rel for rel in old_schema.relationships}
        new_relationships = {rel.name: rel for rel in new_schema.relationships}

        old_rel_names = set(old_relationships.keys())
        new_rel_names = set(new_relationships.keys())

        # Detect added relationships
        for added_rel in new_rel_names - old_rel_names:
            changes.relationship_changes.append(
                RelationshipChange(
                    entity_type=entity_type,
                    relationship_name=added_rel,
                    change_type=ChangeType.ADD,
                    old_definition=None,
                    new_definition=new_relationships[added_rel],
                )
            )

        # Detect removed relationships
        for removed_rel in old_rel_names - new_rel_names:
            changes.relationship_changes.append(
                RelationshipChange(
                    entity_type=entity_type,
                    relationship_name=removed_rel,
                    change_type=ChangeType.REMOVE,
                    old_definition=old_relationships[removed_rel],
                    new_definition=None,
                )
            )

        # Detect modified relationships
        for common_rel in old_rel_names & new_rel_names:
            old_def = old_relationships[common_rel]
            new_def = new_relationships[common_rel]

            # Check if relationship definition changed (e.g., target types)
            if self._relationship_definitions_differ(old_def, new_def):
                changes.relationship_changes.append(
                    RelationshipChange(
                        entity_type=entity_type,
                        relationship_name=common_rel,
                        change_type=ChangeType.MODIFY,
                        old_definition=old_def,
                        new_definition=new_def,
                    )
                )

    def _get_all_fields(self, schema: Any) -> dict[str, Any]:
        """Get all fields (required and optional) from schema as a dict."""
        fields = {}

        # Add required fields
        for field_def in schema.required_fields:
            fields[field_def.name] = field_def

        # Add optional fields
        for field_def in schema.optional_fields:
            fields[field_def.name] = field_def

        # Add readonly fields
        for field_def in schema.readonly_fields:
            fields[field_def.name] = field_def

        return fields

    def _field_definitions_differ(self, old_def: Any, new_def: Any) -> bool:
        """Check if two field definitions differ in a meaningful way."""
        # Compare field types
        if old_def.type != new_def.type:
            return True

        # Compare required status
        if old_def.required != new_def.required:
            return True

        # Compare validation rules if present
        return (
            hasattr(old_def, "validation")
            and hasattr(new_def, "validation")
            and old_def.validation != new_def.validation
        )

    def _relationship_definitions_differ(self, old_def: Any, new_def: Any) -> bool:
        """Check if two relationship definitions differ."""
        # Compare target types
        if set(old_def.target_types) != set(new_def.target_types):
            return True

        # Compare cardinality
        return bool(old_def.cardinality != new_def.cardinality)
