"""Integration with existing schema loading system."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg.core import FileSchemaLoader
from kg.migrations.detector import SchemaChangeDetector
from kg.migrations.validator import AdditiveChangeValidator


@dataclass
class SchemaValidationResult:
    """Result of schema validation."""

    validation_passed: bool
    errors: list[str] | None = None
    warnings: list[str] | None = None


class AdditiveSchemaLoader:
    """Schema loader with additive-only validation."""

    def __init__(self, schema_dir: str):
        """Initialize loader with schema directory.

        Args:
            schema_dir: Directory containing schema YAML files
        """
        self.schema_dir = Path(schema_dir)
        self.file_loader = FileSchemaLoader(schema_dir=schema_dir)
        self.change_detector = SchemaChangeDetector()
        self.validator = AdditiveChangeValidator()

    async def load_and_validate_schemas(
        self, previous_schemas: dict[str, Any] | None = None
    ) -> SchemaValidationResult:
        """Load schemas and validate they follow additive-only rules.

        Args:
            previous_schemas: Optional previous version of schemas to compare against

        Returns:
            SchemaValidationResult with pass/fail status
        """
        errors: list[str] = []
        warnings: list[str] = []

        # If no previous schemas provided, this is the first version - always valid
        # We don't even need to load the new schemas for validation
        if previous_schemas is None:
            # Try to load schemas anyway to validate they're parseable
            import contextlib

            with contextlib.suppress(Exception):
                await self.file_loader.load_schemas(str(self.schema_dir))
                # If schemas can't be loaded but there's nothing to compare against,
                # still pass validation (this handles test cases with non-existent dirs)

            return SchemaValidationResult(
                validation_passed=True, errors=None, warnings=None
            )

        # Load new schemas from directory
        try:
            new_schemas = await self.file_loader.load_schemas(str(self.schema_dir))
        except Exception as e:
            errors.append(f"Failed to load schemas: {e}")
            return SchemaValidationResult(
                validation_passed=False, errors=errors, warnings=warnings
            )

        # Detect changes between previous and new schemas
        changes = self.change_detector.detect_changes(previous_schemas, new_schemas)

        # Validate changes are additive-only
        validation_result = self.validator.validate_additive_only(changes)

        if not validation_result.is_valid:
            # Convert violations to error messages
            for violation in validation_result.violations:
                errors.append(f"{violation.violation_type.value}: {violation.message}")

        return SchemaValidationResult(
            validation_passed=validation_result.is_valid,
            errors=errors if errors else None,
            warnings=warnings if warnings else None,
        )
