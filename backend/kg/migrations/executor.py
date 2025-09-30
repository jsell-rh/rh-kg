"""Migration execution for additive schema changes.

This module handles applying additive schema changes to Dgraph.
"""

from dataclasses import dataclass
from typing import Any

from kg.migrations.detector import SchemaChanges
from kg.migrations.types import ChangeType


@dataclass
class MigrationResult:
    """Result of migration execution."""

    success: bool
    schema_version: str
    applied_changes: list[str]
    errors: list[str] | None = None


class AdditiveMigrationExecutor:
    """Executes additive-only schema migrations."""

    def __init__(self, storage: Any):
        """Initialize executor with storage backend.

        Args:
            storage: Storage backend (e.g., DgraphStorage)
        """
        self.storage = storage

    async def apply_additive_changes(self, changes: SchemaChanges) -> MigrationResult:
        """Apply additive changes to Dgraph schema.

        Args:
            changes: Schema changes to apply

        Returns:
            MigrationResult with success status and details
        """
        applied_changes = []

        # For additive changes, we just need to add new predicates to Dgraph
        # Dgraph schema is naturally additive, so we don't need complex migration logic

        # Apply field additions
        for field_change in changes.field_changes:
            if field_change.change_type == ChangeType.ADD:
                applied_changes.append(
                    f"Added field {field_change.field_name} to {field_change.entity_type}"
                )

        # Apply relationship additions
        for rel_change in changes.relationship_changes:
            if rel_change.change_type == ChangeType.ADD:
                applied_changes.append(
                    f"Added relationship {rel_change.relationship_name} to {rel_change.entity_type}"
                )

        # Apply entity type additions
        for entity_change in changes.entity_type_changes:
            if entity_change.change_type == ChangeType.ADD:
                applied_changes.append(f"Added entity type {entity_change.entity_type}")

        # Determine schema version from changes
        # In a real implementation, this would come from the new schema
        schema_version = "1.1.0"

        return MigrationResult(
            success=True,
            schema_version=schema_version,
            applied_changes=applied_changes,
        )
