"""Specific validator implementations and utilities.

This module provides specialized validator implementations and utility
functions for common validation patterns used throughout the validation
engine.
"""

import re
from typing import Any, ClassVar

from .errors import ValidationError


class DependencyReferenceValidator:
    """Specialized validator for dependency reference formats."""

    EXTERNAL_PATTERN = r"^external://[a-zA-Z0-9._-]+/[a-zA-Z0-9@._/-]+/[a-zA-Z0-9._-]+$"
    INTERNAL_PATTERN = r"^internal://[a-z][a-z0-9_-]*[a-z0-9]/[a-zA-Z0-9._-]+$"

    SUPPORTED_ECOSYSTEMS: ClassVar[list[str]] = [
        "pypi",
        "npm",
        "golang.org",
        "github.com",
        "crates.io",
    ]

    @classmethod
    def validate_reference(
        cls, reference: str, entity_name: str | None = None
    ) -> ValidationError | None:
        """Validate a single dependency reference.

        Args:
            reference: The dependency reference to validate
            entity_name: Optional entity name for error context

        Returns:
            ValidationError if invalid, None if valid
        """
        if reference.startswith("external://"):
            return cls._validate_external_reference(reference, entity_name)
        elif reference.startswith("internal://"):
            return cls._validate_internal_reference(reference, entity_name)
        else:
            return ValidationError(
                type="invalid_dependency_reference",
                field="depends_on",
                entity=entity_name,
                message=f"Invalid dependency reference '{reference}'",
                help="Must start with 'external://' or 'internal://'",
            )

    @classmethod
    def _validate_external_reference(
        cls, reference: str, entity_name: str | None
    ) -> ValidationError | None:
        """Validate external dependency reference."""
        if not re.match(cls.EXTERNAL_PATTERN, reference):
            return ValidationError(
                type="invalid_external_dependency",
                field="depends_on",
                entity=entity_name,
                message=f"Invalid external dependency format '{reference}'",
                help="Format: external://<ecosystem>/<package>/<version>",
            )

        # Parse components
        parts = reference[11:].split("/")  # Remove "external://"
        if len(parts) < 3:
            return ValidationError(
                type="invalid_external_dependency",
                field="depends_on",
                entity=entity_name,
                message=f"Invalid external dependency format '{reference}'",
                help="Format: external://<ecosystem>/<package>/<version>",
            )

        ecosystem = parts[0]
        if ecosystem not in cls.SUPPORTED_ECOSYSTEMS:
            return ValidationError(
                type="unsupported_ecosystem",
                field="depends_on",
                entity=entity_name,
                message=f"Unsupported ecosystem '{ecosystem}' in '{reference}'",
                help=f"Supported: {', '.join(cls.SUPPORTED_ECOSYSTEMS)}",
            )

        return None

    @classmethod
    def _validate_internal_reference(
        cls, reference: str, entity_name: str | None
    ) -> ValidationError | None:
        """Validate internal dependency reference."""
        if not re.match(cls.INTERNAL_PATTERN, reference):
            return ValidationError(
                type="invalid_internal_dependency",
                field="depends_on",
                entity=entity_name,
                message=f"Invalid internal dependency format '{reference}'",
                help="Format: internal://<namespace>/<entity-name>",
            )

        return None


class EmailValidator:
    """Specialized validator for email addresses."""

    EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    @classmethod
    def validate_email(
        cls, email: str, field_name: str = "email", entity_name: str | None = None
    ) -> ValidationError | None:
        """Validate an email address.

        Args:
            email: The email address to validate
            field_name: Name of the field being validated
            entity_name: Optional entity name for error context

        Returns:
            ValidationError if invalid, None if valid
        """
        if not re.match(cls.EMAIL_PATTERN, email):
            return ValidationError(
                type="invalid_email_format",
                field=field_name,
                entity=entity_name,
                message=f"Invalid email '{email}'",
                help="Email must be in valid format (user@domain.com)",
            )

        return None

    @classmethod
    def extract_domain(cls, email: str) -> str | None:
        """Extract domain from email address.

        Args:
            email: The email address

        Returns:
            Domain part of email, or None if invalid format
        """
        if "@" in email:
            return email.split("@")[1]
        return None


class NamespaceValidator:
    """Specialized validator for namespace formats."""

    NAMESPACE_PATTERN = r"^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$"

    @classmethod
    def validate_namespace(
        cls, namespace: str, field_name: str = "namespace"
    ) -> ValidationError | None:
        """Validate a namespace format.

        Args:
            namespace: The namespace to validate
            field_name: Name of the field being validated

        Returns:
            ValidationError if invalid, None if valid
        """
        if not re.match(cls.NAMESPACE_PATTERN, namespace):
            return ValidationError(
                type="invalid_namespace_format",
                field=field_name,
                message=f"Invalid namespace format '{namespace}'",
                help="Namespace must be kebab-case: start with lowercase letter, "
                "contain only lowercase letters, numbers, underscores, hyphens, "
                "and end with lowercase letter or number",
            )

        return None


class SchemaVersionValidator:
    """Specialized validator for schema versions."""

    VERSION_PATTERN = r"^\d+\.\d+\.\d+$"

    @classmethod
    def validate_version(
        cls, version: str, supported_versions: list[str]
    ) -> ValidationError | None:
        """Validate a schema version.

        Args:
            version: The version string to validate
            supported_versions: List of supported version strings

        Returns:
            ValidationError if invalid, None if valid
        """
        if not re.match(cls.VERSION_PATTERN, version):
            return ValidationError(
                type="invalid_schema_version_format",
                field="schema_version",
                message=f"Invalid schema version format '{version}'",
                help="Schema version must be in semver format (e.g., '1.0.0')",
            )

        if version not in supported_versions:
            return ValidationError(
                type="unsupported_schema_version",
                field="schema_version",
                message=f"Unsupported schema version '{version}'",
                help=f"Supported versions: {', '.join(supported_versions)}",
            )

        return None


def validate_required_fields(
    data: dict[str, Any], required_fields: list[str], context: str = ""
) -> list[ValidationError]:
    """Validate that all required fields are present.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        context: Optional context for error messages

    Returns:
        List of validation errors for missing fields
    """
    errors = []
    context_suffix = f" in {context}" if context else ""

    for field in required_fields:
        if field not in data:
            errors.append(
                ValidationError(
                    type="missing_required_field",
                    field=field,
                    message=f"Missing required field '{field}'{context_suffix}",
                    help=f"Field '{field}' is required and must be provided",
                )
            )

    return errors


def validate_field_types(
    data: dict[str, Any], field_types: dict[str, type], context: str = ""
) -> list[ValidationError]:
    """Validate field types match expected types.

    Args:
        data: Dictionary to validate
        field_types: Mapping of field names to expected types
        context: Optional context for error messages

    Returns:
        List of validation errors for incorrect types
    """
    errors = []
    context_suffix = f" in {context}" if context else ""

    for field, expected_type in field_types.items():
        if field in data and not isinstance(data[field], expected_type):
            errors.append(
                ValidationError(
                    type="invalid_field_type",
                    field=field,
                    message=f"Field '{field}' must be of type {expected_type.__name__}{context_suffix}",
                    help=f"Ensure '{field}' is a {expected_type.__name__}",
                )
            )

    return errors
