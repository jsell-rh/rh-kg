"""Individual validation layers for the multi-layer validation pipeline.

This module implements each validation layer as specified in the validation
specification, providing focused validation logic for different aspects
of the knowledge graph data.
"""

import re
from typing import Any, ClassVar, Protocol

from pydantic import ValidationError as PydanticValidationError
import yaml

from kg.validation.validators import DependencyReferenceValidator

from ..core import DynamicModelFactory, EntitySchema
from .errors import ValidationError


class StorageInterface(Protocol):
    """Storage interface for reference validation."""

    async def entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists in storage."""
        ...


class YamlSyntaxValidator:
    """Validates YAML syntax and structure (Layer 1)."""

    def validate(
        self, content: str
    ) -> tuple[bool, dict[str, Any] | None, list[ValidationError]]:
        """
        Validate YAML syntax.

        Args:
            content: The YAML content to validate

        Returns:
            Tuple of (is_valid, parsed_data, errors)
        """
        try:
            data = yaml.safe_load(content)
            if data is None:
                return (
                    False,
                    None,
                    [
                        ValidationError(
                            type="empty_yaml_content",
                            message="YAML content is empty or contains only whitespace",
                            help="Ensure the file contains valid YAML content",
                        )
                    ],
                )
            return True, data, []
        except yaml.YAMLError as e:
            line = None
            column = None

            # Extract line and column information if available
            if hasattr(e, "problem_mark") and e.problem_mark:
                line = e.problem_mark.line + 1  # YAML uses 0-based indexing
                column = e.problem_mark.column + 1

            error = ValidationError(
                type="yaml_syntax_error",
                message=f"Invalid YAML syntax: {e}",
                line=line,
                column=column,
                help="Ensure the file contains valid YAML syntax",
            )
            return False, None, [error]


class SchemaStructureValidator:
    """Validates schema structure and version (Layer 2)."""

    SUPPORTED_VERSIONS: ClassVar[list[str]] = ["1.0.0"]
    REQUIRED_FIELDS: ClassVar[list[str]] = ["schema_version", "namespace", "entity"]

    def validate(self, data: dict[str, Any]) -> list[ValidationError]:
        """Validate schema structure.

        Args:
            data: The parsed YAML data to validate

        Returns:
            List of validation errors
        """
        errors = []

        # Check required top-level fields
        for field in self.REQUIRED_FIELDS:
            if field not in data:
                errors.append(
                    ValidationError(
                        type="missing_required_field",
                        field=field,
                        message=f"Missing required top-level field '{field}'",
                        help=f"All knowledge graph files must include '{field}'",
                    )
                )

        # Validate schema version
        if "schema_version" in data:
            version = data["schema_version"]
            if not isinstance(version, str):
                errors.append(
                    ValidationError(
                        type="invalid_field_type",
                        field="schema_version",
                        message="Schema version must be a string",
                        help='Example: schema_version: "1.0.0"',
                    )
                )
            elif version not in self.SUPPORTED_VERSIONS:
                errors.append(
                    ValidationError(
                        type="unsupported_schema_version",
                        field="schema_version",
                        message=f"Unsupported schema version '{version}'",
                        help=f"Supported versions: {', '.join(self.SUPPORTED_VERSIONS)}",
                    )
                )

        # Validate namespace format
        if "namespace" in data:
            namespace = data["namespace"]
            if not isinstance(namespace, str):
                errors.append(
                    ValidationError(
                        type="invalid_field_type",
                        field="namespace",
                        message="Namespace must be a string",
                        help='Example: namespace: "my-project"',
                    )
                )
            elif not re.match(r"^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$", namespace):
                errors.append(
                    ValidationError(
                        type="invalid_namespace_format",
                        field="namespace",
                        message=f"Invalid namespace format '{namespace}'",
                        help="Namespace must be kebab-case: start with lowercase letter, contain only lowercase letters, numbers, underscores, hyphens, and end with lowercase letter or number",
                    )
                )

        # Validate entity structure
        if "entity" in data:
            entity_data = data["entity"]
            if not isinstance(entity_data, dict):
                errors.append(
                    ValidationError(
                        type="invalid_field_type",
                        field="entity",
                        message="Entity section must be a dictionary",
                        help="Example: entity:\\n  repository: []",
                    )
                )

        return errors


class FieldFormatValidator:
    """Validates field formats using dynamic schemas (Layer 3)."""

    def __init__(self, entity_schemas: dict[str, EntitySchema]):
        """Initialize with entity schemas."""
        self.entity_schemas = entity_schemas
        self.model_factory = DynamicModelFactory()

    def validate(
        self, data: dict[str, Any]
    ) -> tuple[Any | None, list[ValidationError]]:
        """
        Validate field formats using dynamic schemas.

        Args:
            data: The parsed YAML data to validate

        Returns:
            Tuple of (parsed_model, validation_errors)
        """
        errors = []

        # Validate entities section
        entities = data.get("entity", {})

        # Check for unknown entity types
        for entity_type in entities:
            if entity_type not in self.entity_schemas:
                errors.append(
                    ValidationError(
                        type="unknown_entity_type",
                        field="entity",
                        message=f"Unknown entity type '{entity_type}'",
                        help=f"Supported entity types: {', '.join(self.entity_schemas.keys())}",
                    )
                )

        # Validate each entity instance
        for entity_type, entity_list in entities.items():
            if entity_type not in self.entity_schemas:
                continue  # Skip unknown types (already reported above)

            schema = self.entity_schemas[entity_type]
            entity_model = self.model_factory.create_entity_model(schema)

            if not isinstance(entity_list, list):
                errors.append(
                    ValidationError(
                        type="invalid_field_type",
                        field=entity_type,
                        message=f"Entity type '{entity_type}' must be a list",
                        help=f"Example: {entity_type}: []",
                    )
                )
                continue

            for entity_data in entity_list:
                if not isinstance(entity_data, dict):
                    errors.append(
                        ValidationError(
                            type="invalid_entity_structure",
                            field=entity_type,
                            message=f"Each entity in '{entity_type}' must be a dictionary",
                            help="Example: - entity-name: { metadata: {...} }",
                        )
                    )
                    continue

                for entity_name, entity_fields in entity_data.items():
                    try:
                        # Validate entity using dynamic model
                        entity_model(**entity_fields)
                    except PydanticValidationError as e:
                        # Convert Pydantic errors to our format
                        entity_errors = self._convert_pydantic_errors(e, entity_name)
                        errors.extend(entity_errors)

        # Try to create root model if no format errors
        if not errors:
            try:
                root_model = self.model_factory.create_root_model(self.entity_schemas)
                model = root_model(**data)
                return model, []
            except PydanticValidationError as e:
                errors = self._convert_pydantic_errors(e)
                return None, errors

        return None, errors

    def _convert_pydantic_errors(
        self, pydantic_error: PydanticValidationError, entity_name: str | None = None
    ) -> list[ValidationError]:
        """Convert Pydantic validation errors to our format."""
        errors = []

        for error in pydantic_error.errors():
            location = error["loc"]
            error_type = error["type"]
            message = error["msg"]

            # Map Pydantic error types to our error types
            mapped_type = self._map_error_type(error_type)

            # Extract field and entity context
            field, extracted_entity = self._extract_context(location)

            # Use provided entity name if available, otherwise use extracted
            final_entity = entity_name or extracted_entity

            validation_error = ValidationError(
                type=mapped_type,
                field=field,
                entity=final_entity,
                message=self._format_message(message, location, final_entity),
                help=self._get_help_text(mapped_type, field, final_entity),
            )
            errors.append(validation_error)

        return errors

    def _map_error_type(self, pydantic_type: str) -> str:
        """Map Pydantic error types to our validation types."""
        mapping = {
            "missing": "missing_required_field",
            "value_error.email": "invalid_email_format",
            "value_error.url": "invalid_url_format",
            "value_error.list.min_items": "empty_required_array",
            "list_type": "invalid_field_type",
            "url_type": "invalid_field_type",
            "type_error.str": "invalid_field_type",
            "type_error.integer": "invalid_field_type",
            "type_error.bool": "invalid_field_type",
            "type_error.list": "invalid_field_type",
            "value_error": "invalid_field_value",
            "string_too_short": "field_too_short",
            "string_too_long": "field_too_long",
            "string_pattern_mismatch": "pattern_mismatch",
            "too_short": "empty_required_array",
        }
        return mapping.get(pydantic_type, "invalid_field_type")

    def _extract_context(
        self, location: tuple[Any, ...]
    ) -> tuple[str | None, str | None]:
        """Extract field and entity context from Pydantic error location."""
        if not location:
            return None, None

        field = None
        entity = None

        # For our dynamic models, locations are typically simple: ('field_name',)
        # The entity context comes from the entity_name parameter passed to _convert_pydantic_errors
        if len(location) >= 1:
            field = str(location[0])  # First element is the field name

        # For complex paths like ('entity', 'repository', 0, 'repo-name', 'owners')
        if len(location) >= 4:
            entity = str(location[3])  # The entity name
            if len(location) >= 5:
                field = str(location[4])  # The field name in complex paths

        return field, entity

    def _format_message(
        self, message: str, _location: tuple[Any, ...], entity: str | None
    ) -> str:
        """Format validation message with context."""
        if entity:
            return f"{message} in entity '{entity}'"
        return message

    def _get_help_text(  # noqa: PLR0911
        self, error_type: str, field: str | None, entity_name: str | None = None
    ) -> str:
        """Get helpful guidance text for different error types."""
        # Enhanced help for missing fields with type information
        if error_type == "missing_required_field" and field and entity_name:
            field_info = self._get_field_info(field, entity_name)
            if field_info:
                return f"Field '{field}' is required. Expected: {field_info}"
            else:
                return f"Field '{field}' is required and cannot be empty"

        # Enhanced help for invalid field types
        if error_type == "invalid_field_type" and field and entity_name:
            field_info = self._get_field_info(field, entity_name)
            if field_info:
                return f"Field '{field}' has wrong type. Expected: {field_info}"
            else:
                return f"Field '{field}' has incorrect data type"

        # Enhanced help for empty arrays
        if error_type == "empty_required_array" and field and entity_name:
            field_info = self._get_field_info(field, entity_name)
            if field_info:
                return f"Field '{field}' cannot be empty. Expected: {field_info}"
            else:
                return "Array cannot be empty"

        help_texts = {
            "missing_required_field": f"Field '{field}' is required and cannot be empty",
            "invalid_email_format": "Email must be in valid format (user@domain.com)",
            "invalid_url_format": "URL must be a valid HTTP/HTTPS URL",
            "empty_required_array": "Array cannot be empty",
            "invalid_field_type": "Check the expected data type for this field",
            "field_too_short": "Value is shorter than the minimum required length",
            "field_too_long": "Value exceeds the maximum allowed length",
            "pattern_mismatch": "Value does not match the required pattern",
        }
        return help_texts.get(error_type, "Check the field value and try again")

    def _get_field_info(self, field_name: str, _entity_name: str) -> str | None:  # noqa: PLR0912
        """Get detailed field information for help messages."""
        # Find the entity type from the entity_name context
        # We need to look through our schemas to find field definitions
        for _entity_type, schema in self.entity_schemas.items():
            # Check all field types in the schema
            all_fields = (
                schema.required_fields + schema.optional_fields + schema.readonly_fields
            )

            for field_def in all_fields:
                if field_def.name == field_name:
                    # Build detailed field info
                    field_info_parts = []

                    # Basic type
                    if field_def.type == "array":
                        if field_def.items:
                            field_info_parts.append(f"array of {field_def.items}")
                        else:
                            field_info_parts.append("array")
                    else:
                        field_info_parts.append(field_def.type)

                    # Validation requirements
                    if field_def.validation:
                        if field_def.validation == "email":
                            field_info_parts.append("(valid email address)")
                        elif field_def.validation == "url":
                            field_info_parts.append("(valid URL)")
                        elif (
                            field_def.validation == "enum" and field_def.allowed_values
                        ):
                            values = ", ".join(field_def.allowed_values)
                            field_info_parts.append(f"(one of: {values})")

                    # Array constraints
                    if field_def.type == "array" and field_def.min_items:
                        if field_def.min_items == 1:
                            field_info_parts.append("(at least 1 item)")
                        else:
                            field_info_parts.append(
                                f"(at least {field_def.min_items} items)"
                            )

                    # Pattern constraints
                    if field_def.pattern:
                        field_info_parts.append(f"(pattern: {field_def.pattern})")

                    return " ".join(field_info_parts)

        return None


class BusinessLogicValidator:
    """Validates business rules and constraints (Layer 4)."""

    def __init__(self, entity_schemas: dict[str, EntitySchema]):
        """Initialize with entity schemas."""
        self.entity_schemas = entity_schemas

    def validate(self, model: Any) -> list[ValidationError]:
        """Validate business logic rules.

        Args:
            model: The validated Pydantic model

        Returns:
            List of validation errors
        """
        errors = []

        # Validate dependency references
        errors.extend(self._validate_dependency_references(model))

        # Validate owner domain consistency
        errors.extend(self._validate_owner_domains(model))

        # Validate unique entity names
        errors.extend(self._validate_unique_names(model))

        return errors

    def _validate_dependency_references(self, model: Any) -> list[ValidationError]:
        """Validate dependency reference formats."""
        errors = []

        # Access entities through the model structure
        if hasattr(model, "entity") and model.entity:
            # Check if repository entities exist
            repositories = getattr(model.entity, "repository", None) or []

            for repo_dict in repositories:
                for repo_name, repo_data in repo_dict.items():
                    depends_on = getattr(repo_data, "depends_on", None) or []

                    for dep_ref in depends_on:
                        if dep_ref.startswith("external://"):
                            error = self._validate_external_dependency(
                                dep_ref, repo_name
                            )
                            if error:
                                errors.append(error)
                        elif dep_ref.startswith("internal://"):
                            error = self._validate_internal_dependency(
                                dep_ref, repo_name
                            )
                            if error:
                                errors.append(error)
                        else:
                            errors.append(
                                ValidationError(
                                    type="invalid_dependency_reference",
                                    field="depends_on",
                                    entity=repo_name,
                                    message=f"Invalid dependency reference '{dep_ref}'",
                                    help="Must start with 'external://' or 'internal://'",
                                )
                            )

        return errors

    def _validate_external_dependency(
        self, dep_ref: str, repo_name: str
    ) -> ValidationError | None:
        """Validate external dependency reference format."""
        # Remove external:// prefix
        ref_parts = dep_ref[11:].split("/")

        if len(ref_parts) < 3:
            return ValidationError(
                type="invalid_external_dependency",
                field="depends_on",
                entity=repo_name,
                message=f"Invalid external dependency format '{dep_ref}'",
                help="Format: external://<ecosystem>/<package>/<version>",
            )

        ecosystem = ref_parts[0]
        package = "/".join(ref_parts[1:-1])
        version = ref_parts[-1]

        # Validate ecosystem
        supported_ecosystems = DependencyReferenceValidator.SUPPORTED_ECOSYSTEMS

        if ecosystem not in supported_ecosystems:
            return ValidationError(
                type="unsupported_ecosystem",
                field="depends_on",
                entity=repo_name,
                message=f"Unsupported ecosystem '{ecosystem}' in '{dep_ref}'",
                help=f"Supported: {', '.join(supported_ecosystems)}",
            )

        # Validate package name is not empty
        if not package:
            return ValidationError(
                type="empty_package_name",
                field="depends_on",
                entity=repo_name,
                message=f"Empty package name in '{dep_ref}'",
                help="Package name cannot be empty",
            )

        # Validate version is not empty
        if not version:
            return ValidationError(
                type="empty_version",
                field="depends_on",
                entity=repo_name,
                message=f"Empty version in '{dep_ref}'",
                help="Version cannot be empty",
            )

        return None

    def _validate_internal_dependency(
        self, dep_ref: str, repo_name: str
    ) -> ValidationError | None:
        """Validate internal dependency reference format."""
        # Remove internal:// prefix
        ref_parts = dep_ref[11:].split("/")

        if len(ref_parts) != 2:
            return ValidationError(
                type="invalid_internal_dependency",
                field="depends_on",
                entity=repo_name,
                message=f"Invalid internal dependency format '{dep_ref}'",
                help="Format: internal://<namespace>/<entity-name>",
            )

        namespace, entity_name = ref_parts

        # Validate namespace format
        if not re.match(r"^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$", namespace):
            return ValidationError(
                type="invalid_internal_namespace",
                field="depends_on",
                entity=repo_name,
                message=f"Invalid namespace '{namespace}' in '{dep_ref}'",
                help="Namespace must be kebab-case",
            )

        # Validate entity name is not empty
        if not entity_name:
            return ValidationError(
                type="empty_entity_name",
                field="depends_on",
                entity=repo_name,
                message=f"Empty entity name in '{dep_ref}'",
                help="Entity name cannot be empty",
            )

        return None

    def _validate_owner_domains(self, model: Any) -> list[ValidationError]:
        """Validate owner email domains are consistent within namespace."""
        errors = []

        # Collect all domains used in this namespace
        domains = set()

        if hasattr(model, "entity") and model.entity:
            repositories = getattr(model.entity, "repository", None) or []

            for repo_dict in repositories:
                for _repo_name, repo_data in repo_dict.items():
                    # Check for direct owners field (current schema structure)
                    owners = getattr(repo_data, "owners", None) or []
                    for owner in owners:
                        if "@" in str(owner):
                            domain = str(owner).split("@")[1]
                            domains.add(domain)

        # Warn if multiple domains (organizational policy)
        if len(domains) > 1:
            namespace = getattr(model, "namespace", "unknown")
            errors.append(
                ValidationError(
                    type="multiple_owner_domains",
                    field="owners",
                    message=f"Multiple email domains in namespace '{namespace}': {', '.join(domains)}",
                    help="Consider using consistent email domain within namespace",
                )
            )

        return errors

    def _validate_unique_names(self, model: Any) -> list[ValidationError]:
        """Validate that entity names are unique within their type."""
        errors = []

        if hasattr(model, "entity") and model.entity:
            # Check repository names
            repositories = getattr(model.entity, "repository", None) or []
            repo_names = set()

            for repo_dict in repositories:
                for repo_name in repo_dict:
                    if repo_name in repo_names:
                        errors.append(
                            ValidationError(
                                type="duplicate_entity_name",
                                field="repository",
                                entity=repo_name,
                                message=f"Duplicate repository name '{repo_name}'",
                                help="Entity names must be unique within their type",
                            )
                        )
                    repo_names.add(repo_name)

        return errors


class ReferenceValidator:
    """Validates that referenced entities exist (Layer 5)."""

    def __init__(self, storage: StorageInterface | None = None):
        """Initialize with optional storage interface."""
        self.storage = storage

    async def validate(self, model: Any) -> list[ValidationError]:
        """Validate entity references exist.

        Args:
            model: The validated Pydantic model

        Returns:
            List of validation errors
        """
        if not self.storage:
            return []  # Skip validation if no storage available

        errors = []

        if hasattr(model, "entity") and model.entity:
            repositories = getattr(model.entity, "repository", None) or []

            for repo_dict in repositories:
                for repo_name, repo_data in repo_dict.items():
                    depends_on = getattr(repo_data, "depends_on", None) or []

                    for dep_ref in depends_on:
                        if dep_ref.startswith("internal://"):
                            # Extract entity ID from internal reference
                            entity_id = dep_ref[11:]  # Remove "internal://"

                            if not await self.storage.entity_exists(entity_id):
                                errors.append(
                                    ValidationError(
                                        type="reference_not_found",
                                        field="depends_on",
                                        entity=repo_name,
                                        message=f"Referenced entity '{entity_id}' not found",
                                        help="Ensure the referenced entity exists or will be created",
                                    )
                                )

        return errors
