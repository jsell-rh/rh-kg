"""Error and result data structures for the validation engine.

This module defines the data structures used by the validation engine to
represent validation errors, warnings, and results according to the
validation specification.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationError:
    """Represents a validation error.

    Contains detailed information about what went wrong during validation,
    including context information to help users fix the issue.
    """

    type: str
    message: str
    field: str | None = None
    entity: str | None = None
    line: int | None = None
    column: int | None = None
    help: str | None = None

    def __str__(self) -> str:
        """Return a formatted string representation of the error."""
        parts = [f"{self.type}: {self.message}"]

        if self.entity:
            parts.append(f"(entity: {self.entity})")
        if self.field:
            parts.append(f"(field: {self.field})")
        if self.line is not None or self.column is not None:
            location = f"line {self.line or 0}, column {self.column or 0}"
            parts.append(f"({location})")
        if self.help:
            parts.append(f"Help: {self.help}")

        return " ".join(parts)


@dataclass
class ValidationWarning:
    """Represents a validation warning.

    Similar to ValidationError but for non-critical issues that don't
    prevent validation from succeeding.
    """

    type: str
    message: str
    field: str | None = None
    entity: str | None = None
    help: str | None = None

    def __str__(self) -> str:
        """Return a formatted string representation of the warning."""
        parts = [f"{self.type}: {self.message}"]

        if self.entity:
            parts.append(f"(entity: {self.entity})")
        if self.field:
            parts.append(f"(field: {self.field})")
        if self.help:
            parts.append(f"Help: {self.help}")

        return " ".join(parts)


@dataclass
class ValidationResult:
    """Complete validation result.

    Contains the overall validation status, all errors and warnings found,
    and the validated model if validation succeeded.
    """

    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    model: Any | None = None

    @property
    def error_count(self) -> int:
        """Number of validation errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Number of validation warnings."""
        return len(self.warnings)

    def add_error(self, error: ValidationError) -> None:
        """Add a validation error to the result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: ValidationWarning) -> None:
        """Add a validation warning to the result."""
        self.warnings.append(warning)

    def extend_errors(self, errors: list[ValidationError]) -> None:
        """Add multiple validation errors to the result."""
        self.errors.extend(errors)
        if errors:
            self.is_valid = False

    def extend_warnings(self, warnings: list[ValidationWarning]) -> None:
        """Add multiple validation warnings to the result."""
        self.warnings.extend(warnings)

    def has_critical_errors(self) -> bool:
        """Check if result contains critical errors that should stop validation."""
        critical_types = {
            "yaml_syntax_error",
            "missing_required_field",
            "unsupported_schema_version",
        }
        return any(error.type in critical_types for error in self.errors)

    def __str__(self) -> str:
        """Return a formatted string representation of the validation result."""
        if self.is_valid:
            status = (
                f"✅ Valid ({self.warning_count} warnings)"
                if self.warnings
                else "✅ Valid"
            )
        else:
            status = (
                f"❌ Invalid ({self.error_count} errors, {self.warning_count} warnings)"
            )

        lines = [status]

        if self.errors:
            lines.append("\nErrors:")
            for error in self.errors:
                lines.append(f"  - {error}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)
