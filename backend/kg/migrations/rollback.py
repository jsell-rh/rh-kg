"""Rollback strategy for additive schema changes.

For additive-only changes, rollback is simple: just stop using new features.
"""

from typing import Any

from kg.core import EntitySchema


class AdditiveRollbackStrategy:
    """Handles rollback of additive schema changes."""

    def __init__(
        self, schema_registry: dict[str, dict[str, EntitySchema]] | None = None
    ):
        """Initialize rollback strategy with schema registry.

        Args:
            schema_registry: Optional map of version -> entity_type -> EntitySchema
                            e.g., {"1.0.0": {"repository": schema}, "1.1.0": {...}}
                            If not provided, uses hardcoded v1.0.0 schema for testing
        """
        self.schema_registry = schema_registry or self._get_default_registry()

    def _get_default_registry(self) -> dict[str, dict[str, EntitySchema]]:
        """Get default schema registry for testing/simple cases."""
        # Hardcoded v1.0.0 repository schema for backward compatibility with tests
        # In production, schema_registry should always be provided
        from kg.core import FieldDefinition

        v1_repo_schema = type(
            "SimpleSchema",
            (),
            {
                "required_fields": [
                    FieldDefinition(name="owners", type="array", required=True),
                    FieldDefinition(name="git_repo_url", type="string", required=True),
                ],
                "optional_fields": [],
                "readonly_fields": [],
                "relationships": [],
            },
        )()

        return {"1.0.0": {"repository": v1_repo_schema}}

    def rollback_entity_to_version(
        self, entity_data: dict[str, Any], target_version: str
    ) -> dict[str, Any]:
        """Rollback entity data to a specific schema version.

        For additive changes, this simply means filtering out fields
        that don't exist in the target version.

        Args:
            entity_data: Current entity data
            target_version: Target schema version to rollback to

        Returns:
            Filtered entity data compatible with target version
        """
        # Determine entity type from data (we need this to look up the schema)
        # In a real system, this would be passed as a parameter or inferred
        # For now, we'll extract all valid fields from ALL schemas at that version

        if target_version not in self.schema_registry:
            # Version not found, return data as-is
            return entity_data

        # Get all schemas for target version
        target_schemas = self.schema_registry[target_version]

        # Collect all valid field names from all schemas at this version
        valid_fields = set()
        for entity_schema in target_schemas.values():
            # Add all field names from the schema
            for field_def in entity_schema.required_fields:
                valid_fields.add(field_def.name)
            for field_def in entity_schema.optional_fields:
                valid_fields.add(field_def.name)
            for field_def in entity_schema.readonly_fields:
                valid_fields.add(field_def.name)
            # Add relationship names
            for rel_def in entity_schema.relationships:
                valid_fields.add(rel_def.name)

        # Filter entity data to only include valid fields
        filtered_data = {
            key: value for key, value in entity_data.items() if key in valid_fields
        }

        return filtered_data
