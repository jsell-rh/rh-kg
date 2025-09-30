"""Additive-only schema change validation.

This module validates that schema changes follow the additive-only rule,
preventing breaking changes that could corrupt data or break queries.
"""

from dataclasses import dataclass, field
from typing import Any

from kg.migrations.detector import SchemaChanges
from kg.migrations.types import ChangeType, ViolationType


@dataclass
class ValidationViolation:
    """Represents a violation of additive-only rules."""

    violation_type: ViolationType
    entity_type: str
    element_name: str
    message: str
    old_definition: dict[str, Any] | None = None
    new_definition: dict[str, Any] | None = None


@dataclass
class ValidationResult:
    """Result of additive-only validation."""

    is_valid: bool
    violations: list[ValidationViolation] = field(default_factory=list)


class AdditiveChangeValidator:
    """Validates that schema changes are additive-only."""

    def validate_additive_only(self, changes: SchemaChanges) -> ValidationResult:
        """Validate that all changes are additive-only.

        Args:
            changes: Detected schema changes

        Returns:
            ValidationResult with is_valid flag and list of violations
        """
        violations: list[ValidationViolation] = []

        # Check field changes
        for field_change in changes.field_changes:
            field_violations = self._validate_field_change(field_change)
            violations.extend(field_violations)

        # Check relationship changes
        for rel_change in changes.relationship_changes:
            rel_violations = self._validate_relationship_change(rel_change)
            violations.extend(rel_violations)

        # Check entity type changes
        for entity_change in changes.entity_type_changes:
            entity_violations = self._validate_entity_type_change(entity_change)
            violations.extend(entity_violations)

        return ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
        )

    def _validate_field_change(self, field_change: Any) -> list[ValidationViolation]:
        """Validate a single field change."""
        violations = []

        if field_change.change_type == ChangeType.REMOVE:
            # FORBIDDEN: Removing fields breaks existing data
            violations.append(
                ValidationViolation(
                    violation_type=ViolationType.FIELD_REMOVED,
                    entity_type=field_change.entity_type,
                    element_name=field_change.field_name,
                    message=f"Field '{field_change.field_name}' was removed from '{field_change.entity_type}'. "
                    "Use deprecation instead of removal.",
                    old_definition=field_change.old_definition,
                    new_definition=None,
                )
            )

        elif field_change.change_type == ChangeType.MODIFY:
            # Check for type changes
            old_type = field_change.old_definition.type
            new_type = field_change.new_definition.type

            if old_type != new_type:
                violations.append(
                    ValidationViolation(
                        violation_type=ViolationType.FIELD_TYPE_CHANGED,
                        entity_type=field_change.entity_type,
                        element_name=field_change.field_name,
                        message=f"Field '{field_change.field_name}' type changed from '{old_type}' to '{new_type}'. "
                        "Type changes are forbidden.",
                        old_definition=field_change.old_definition,
                        new_definition=field_change.new_definition,
                    )
                )

            # Check if optional field became required
            old_required = field_change.old_definition.required
            new_required = field_change.new_definition.required

            if not old_required and new_required:
                violations.append(
                    ValidationViolation(
                        violation_type=ViolationType.FIELD_MADE_REQUIRED,
                        entity_type=field_change.entity_type,
                        element_name=field_change.field_name,
                        message=f"Field '{field_change.field_name}' changed from optional to required. "
                        "Making fields required is forbidden.",
                        old_definition=field_change.old_definition,
                        new_definition=field_change.new_definition,
                    )
                )

        elif (
            field_change.change_type == ChangeType.ADD
            and field_change.new_definition.required
        ):
            violations.append(
                ValidationViolation(
                    violation_type=ViolationType.REQUIRED_FIELD_ADDED,
                    entity_type=field_change.entity_type,
                    element_name=field_change.field_name,
                    message=f"New required field '{field_change.field_name}' added to '{field_change.entity_type}'. "
                    "New fields must be optional.",
                    old_definition=None,
                    new_definition=field_change.new_definition,
                )
            )

        return violations

    def _validate_relationship_change(
        self, rel_change: Any
    ) -> list[ValidationViolation]:
        """Validate a single relationship change."""
        violations = []

        if rel_change.change_type == ChangeType.REMOVE:
            # FORBIDDEN: Removing relationships breaks existing data
            violations.append(
                ValidationViolation(
                    violation_type=ViolationType.RELATIONSHIP_REMOVED,
                    entity_type=rel_change.entity_type,
                    element_name=rel_change.relationship_name,
                    message=f"Relationship '{rel_change.relationship_name}' was removed from '{rel_change.entity_type}'. "
                    "Use deprecation instead of removal.",
                    old_definition=rel_change.old_definition,
                    new_definition=None,
                )
            )

        elif rel_change.change_type == ChangeType.MODIFY:
            # Check if target types were removed
            old_targets = set(rel_change.old_definition.target_types)
            new_targets = set(rel_change.new_definition.target_types)

            removed_targets = old_targets - new_targets
            if removed_targets:
                violations.append(
                    ValidationViolation(
                        violation_type=ViolationType.RELATIONSHIP_TARGETS_REMOVED,
                        entity_type=rel_change.entity_type,
                        element_name=rel_change.relationship_name,
                        message=f"Relationship '{rel_change.relationship_name}' had target types removed: {removed_targets}. "
                        "Removing target types is forbidden.",
                        old_definition=rel_change.old_definition,
                        new_definition=rel_change.new_definition,
                    )
                )

        # Adding relationships is always allowed (no violations)

        return violations

    def _validate_entity_type_change(
        self, entity_change: Any
    ) -> list[ValidationViolation]:
        """Validate an entity type change."""
        violations = []

        if entity_change.change_type == ChangeType.REMOVE:
            # FORBIDDEN: Removing entity types breaks existing data
            violations.append(
                ValidationViolation(
                    violation_type=ViolationType.ENTITY_TYPE_REMOVED,
                    entity_type=entity_change.entity_type,
                    element_name=entity_change.entity_type,
                    message=f"Entity type '{entity_change.entity_type}' was removed. "
                    "Use deprecation instead of removal.",
                    old_definition=entity_change.schema,
                    new_definition=None,
                )
            )

        # Adding entity types is always allowed (no violations)

        return violations
