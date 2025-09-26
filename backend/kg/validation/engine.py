"""Main validation engine that orchestrates all validation layers.

This module implements the KnowledgeGraphValidator class that coordinates
the multi-layer validation pipeline according to the validation specification.
"""

from typing import Any

from ..core import EntitySchema
from .errors import ValidationError, ValidationResult, ValidationWarning
from .layers import (
    BusinessLogicValidator,
    FieldFormatValidator,
    ReferenceValidator,
    SchemaStructureValidator,
    StorageInterface,
    YamlSyntaxValidator,
)


class KnowledgeGraphValidator:
    """Main validator that orchestrates all validation layers.

    This class implements the complete validation pipeline as specified
    in the validation specification, coordinating all validation layers
    and managing early exit behavior for critical failures.
    """

    def __init__(
        self,
        entity_schemas: dict[str, EntitySchema],
        storage: StorageInterface | None = None,
        strict_mode: bool = True,
    ):
        """Initialize the validator with schemas and configuration.

        Args:
            entity_schemas: Dictionary of loaded entity schemas
            storage: Optional storage interface for reference validation
            strict_mode: Whether to use strict validation mode (default: True)
        """
        self.entity_schemas = entity_schemas
        self.storage = storage
        self.strict_mode = strict_mode

        # Initialize validators with dynamic schemas
        self.yaml_validator = YamlSyntaxValidator()
        self.structure_validator = SchemaStructureValidator()
        self.format_validator = FieldFormatValidator(entity_schemas)
        self.business_validator = BusinessLogicValidator(entity_schemas)
        self.reference_validator = ReferenceValidator(storage)

    async def validate(self, content: str) -> ValidationResult:
        """
        Perform complete validation of YAML content.

        Implements the multi-layer validation pipeline with early exit
        for critical failures as specified in the validation specification.

        Args:
            content: The YAML content to validate

        Returns:
            ValidationResult with all errors, warnings, and validated model
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        # Layer 1: YAML Syntax Validation
        # Critical failure - must exit immediately if YAML is invalid
        is_valid_yaml, data, yaml_errors = self.yaml_validator.validate(content)
        if not is_valid_yaml:
            return ValidationResult(
                is_valid=False, errors=yaml_errors, warnings=warnings, model=None
            )

        # Layer 2: Schema Structure Validation
        # Critical failure for missing required fields or unsupported versions
        if data is not None:
            structure_errors = self.structure_validator.validate(data)
        else:
            structure_errors = []
        errors.extend(structure_errors)

        # Check for critical structure errors that should stop validation
        critical_structure_errors = [
            error
            for error in structure_errors
            if error.type in ["missing_required_field", "unsupported_schema_version"]
        ]

        if critical_structure_errors:
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, model=None
            )

        # Layer 3: Field Format Validation
        # Continue validation to collect all format errors
        if data is not None:
            model, format_errors = self.format_validator.validate(data)
        else:
            model, format_errors = None, []
        errors.extend(format_errors)

        # If format validation failed, we cannot proceed to business logic
        if not model:
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, model=None
            )

        # Layer 4: Business Logic Validation
        # Collect all business logic errors - don't exit early
        business_errors = self.business_validator.validate(model)

        # Convert business logic errors that should be warnings in permissive mode
        for error in business_errors:
            if error.type == "multiple_owner_domains":
                # This is more of a warning than an error
                warnings.append(
                    ValidationWarning(
                        type=error.type,
                        message=error.message,
                        field=error.field,
                        entity=error.entity,
                        help=error.help,
                    )
                )
            else:
                errors.append(error)

        # Layer 5: Reference Validation (if storage available)
        # Optional validation - only run if storage interface is provided
        if self.storage:
            reference_errors = await self.reference_validator.validate(model)
            errors.extend(reference_errors)

        # Determine final validation result
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            model=model if is_valid else None,
        )

    def validate_sync(self, content: str) -> ValidationResult:
        """
        Synchronous version of validate that skips reference validation.

        This method performs validation without the optional reference
        validation layer, making it suitable for synchronous usage.

        Args:
            content: The YAML content to validate

        Returns:
            ValidationResult with all errors, warnings, and validated model
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        # Layer 1: YAML Syntax Validation
        is_valid_yaml, data, yaml_errors = self.yaml_validator.validate(content)
        if not is_valid_yaml:
            return ValidationResult(
                is_valid=False, errors=yaml_errors, warnings=warnings, model=None
            )

        # Layer 2: Schema Structure Validation
        if data is not None:
            structure_errors = self.structure_validator.validate(data)
        else:
            structure_errors = []
        errors.extend(structure_errors)

        # Check for critical structure errors
        critical_structure_errors = [
            error
            for error in structure_errors
            if error.type in ["missing_required_field", "unsupported_schema_version"]
        ]

        if critical_structure_errors:
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, model=None
            )

        # Layer 3: Field Format Validation
        if data is not None:
            model, format_errors = self.format_validator.validate(data)
        else:
            model, format_errors = None, []
        errors.extend(format_errors)

        if not model:
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, model=None
            )

        # Layer 4: Business Logic Validation
        business_errors = self.business_validator.validate(model)

        for error in business_errors:
            if error.type == "multiple_owner_domains":
                warnings.append(
                    ValidationWarning(
                        type=error.type,
                        message=error.message,
                        field=error.field,
                        entity=error.entity,
                        help=error.help,
                    )
                )
            else:
                errors.append(error)

        # Skip Layer 5 (Reference Validation) in synchronous mode

        # Determine final validation result
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            model=model if is_valid else None,
        )

    def get_validator_info(self) -> dict[str, Any]:
        """Get information about the validator configuration.

        Returns:
            Dictionary with validator configuration details
        """
        return {
            "entity_schemas": list(self.entity_schemas.keys()),
            "schema_count": len(self.entity_schemas),
            "strict_mode": self.strict_mode,
            "has_storage": self.storage is not None,
            "supported_versions": SchemaStructureValidator.SUPPORTED_VERSIONS,
        }
