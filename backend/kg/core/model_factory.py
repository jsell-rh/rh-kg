"""Dynamic Pydantic model generator for EntitySchema definitions.

This module provides a factory class that creates Pydantic models at runtime
from EntitySchema definitions loaded by the schema system. It handles type
mapping, validation rules, and generates complete YAML validation models.
"""

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    create_model,
    field_validator,
)

from .schema import EntitySchema, FieldDefinition

# Type alias for all possible field types used in Pydantic model creation
FieldType = (
    # Base types from _type_mappings
    type[str]
    | type[int]
    | type[bool]
    | type[datetime]
    | type[dict[str, Any]]  # For object fields
    | type[list[Any]]  # For generic array fields
    # Pydantic validation types
    | type[EmailStr]
    | type[HttpUrl]
    # Specific array types
    | type[list[str]]
    | type[list[int]]
    | type[list[bool]]
    | type[list[datetime]]
    | type[list[EmailStr]]
)


class DynamicModelFactory:
    """Factory for creating Pydantic models from EntitySchema definitions.

    This factory converts EntitySchema objects into runtime Pydantic model classes
    with full validation support, type safety, and compliance with schema
    specifications.
    """

    def __init__(self) -> None:
        """Initialize the model factory with type mappings."""
        self._type_mappings: dict[str, type] = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "datetime": datetime,
            "array": list,
            "object": dict,
        }

        self._validation_mappings = {
            "email": EmailStr,
            "url": HttpUrl,
        }

        # Cache for generated models to avoid recreation
        self._model_cache: dict[str, type[BaseModel]] = {}

    def create_entity_model(self, schema: EntitySchema) -> type[BaseModel]:
        """Create a Pydantic model class from an EntitySchema.

        Args:
            schema: The EntitySchema to convert into a Pydantic model

        Returns:
            A Pydantic model class that validates data according to the schema

        Raises:
            ValueError: If schema contains unsupported field types or validation rules
        """
        # Check cache first
        cache_key = f"{schema.entity_type}_{schema.schema_version}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        # Collect all fields from the schema
        field_definitions: dict[str, Any] = {}
        validators: dict[str, Any] = {}

        # Process required fields
        for field_def in schema.required_fields:
            field_type, field_constraints = self._convert_field_definition(field_def)
            # Handle enum validation separately
            enum_values = field_constraints.pop("_enum_values", None)
            if enum_values:
                # Create validator for enum field
                validators[f"validate_{field_def.name}"] = self._create_enum_validator(
                    field_def.name, enum_values
                )
            field_definitions[field_def.name] = (field_type, Field(**field_constraints))

        # Process optional fields
        for field_def in schema.optional_fields:
            field_type, field_constraints = self._convert_field_definition(field_def)
            # Handle enum validation separately
            enum_values = field_constraints.pop("_enum_values", None)
            if enum_values:
                # Create validator for enum field
                validators[f"validate_{field_def.name}"] = self._create_enum_validator(
                    field_def.name, enum_values
                )
            # Make optional fields truly optional with default None
            field_definitions[field_def.name] = (
                field_type | None,
                Field(default=None, **field_constraints),
            )

        # Process readonly fields
        for field_def in schema.readonly_fields:
            field_type, field_constraints = self._convert_field_definition(field_def)
            # Handle enum validation separately
            enum_values = field_constraints.pop("_enum_values", None)
            if enum_values:
                # Create validator for enum field
                validators[f"validate_{field_def.name}"] = self._create_enum_validator(
                    field_def.name, enum_values
                )
            # Readonly fields are optional and typically set by the system
            field_definitions[field_def.name] = (
                field_type | None,
                Field(default=None, **field_constraints),
            )

        # Add custom validators based on field validation rules
        validators.update(self._create_field_validators(schema))

        # Create the model
        model_name = f"{schema.entity_type.title()}Model"

        # Create model with proper configuration
        class StrictBaseModel(BaseModel):
            model_config = ConfigDict(
                str_strip_whitespace=True,
                validate_assignment=True,
                extra="forbid",  # Strict validation - no unknown fields
            )

        model = create_model(
            model_name,
            **field_definitions,
            __validators__=validators,
            __base__=StrictBaseModel,
        )

        # Cache and return
        self._model_cache[cache_key] = model
        return model

    def create_root_model(self, schemas: dict[str, EntitySchema]) -> type[BaseModel]:
        """Create the root YAML file model that validates complete knowledge graph files.

        Args:
            schemas: Dictionary of all available entity schemas

        Returns:
            Root model class that validates entire YAML files
        """
        # Create entity container model
        entity_container_fields = {}

        for entity_type, _schema in schemas.items():
            # Each entity type is an optional list of entity dictionaries
            entity_container_fields[entity_type] = (
                list[dict[str, Any]] | None,
                None,  # Default value
            )

        # Create EntityContainer model
        class EntityBaseModel(BaseModel):
            model_config = ConfigDict(
                extra="forbid",
                validate_assignment=True,
            )

        EntityContainer = create_model(  # type: ignore[call-overload]
            "EntityContainer",
            __base__=EntityBaseModel,
            **entity_container_fields,
        )

        # Create validators for the root model
        root_validators = {
            "validate_schema_version": field_validator("schema_version")(
                self._validate_schema_version
            ),
            "validate_namespace": field_validator("namespace")(
                self._validate_namespace
            ),
        }

        # Create root model for complete YAML files
        class RootBaseModel(BaseModel):
            model_config = ConfigDict(
                extra="forbid",
                validate_assignment=True,
                str_strip_whitespace=True,
            )

        KnowledgeGraphFile = create_model(
            "KnowledgeGraphFile",
            schema_version=(
                str,
                Field(
                    description="Schema version in semver format",
                    pattern=r"^\d+\.\d+\.\d+$",
                ),
            ),
            namespace=(
                str,
                Field(
                    description="Namespace for grouping related entities",
                    pattern=r"^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$",
                ),
            ),
            entity=(
                EntityContainer,
                Field(description="Container for all entity definitions"),
            ),
            __validators__=root_validators,
            __base__=RootBaseModel,
        )

        return KnowledgeGraphFile

    def create_models_from_schemas(
        self, schemas: dict[str, EntitySchema]
    ) -> dict[str, type[BaseModel]]:
        """Create all models from a collection of schemas.

        Args:
            schemas: Dictionary mapping entity types to their schemas

        Returns:
            Dictionary mapping entity types to their model classes,
            plus a special '_root' key for the root YAML model
        """
        models = {}

        # Create individual entity models
        for entity_type, schema in schemas.items():
            models[entity_type] = self.create_entity_model(schema)

        # Create root model
        models["_root"] = self.create_root_model(schemas)

        return models

    def _convert_field_definition(
        self, field_def: FieldDefinition
    ) -> tuple[FieldType, dict[str, Any]]:
        """Convert a FieldDefinition to Pydantic field type and constraints.

        Args:
            field_def: The field definition to convert

        Returns:
            Tuple of (field_type, field_constraints)

        Raises:
            ValueError: If field type or validation is unsupported
        """
        base_type = self._get_base_type(field_def)
        field_type = self._apply_validation_type(base_type, field_def)
        field_type = self._apply_array_type(field_type, field_def)
        constraints = self._build_field_constraints(field_def)

        return field_type, constraints

    def _get_base_type(self, field_def: FieldDefinition) -> type[Any]:
        """Get the base Python type for a field definition."""
        base_type = self._type_mappings.get(field_def.type)
        if base_type is None:
            raise ValueError(f"Unsupported field type: {field_def.type}")
        return base_type

    def _apply_validation_type(
        self, base_type: type[Any], field_def: FieldDefinition
    ) -> FieldType:
        """Apply validation rules to get the appropriate type."""
        field_type = base_type

        # Handle validation rules
        if field_def.validation == "email":
            field_type = EmailStr
        elif field_def.validation == "url":
            field_type = HttpUrl
        elif field_def.validation == "enum":
            # Keep base type for enum, validation handled by custom validator
            field_type = base_type

        return field_type

    def _apply_array_type(
        self, field_type: FieldType, field_def: FieldDefinition
    ) -> FieldType:
        """Convert type to array type if needed."""
        if field_def.type != "array":
            return field_type

        return self._get_array_type(field_type, field_def)

    def _get_array_type(  # noqa: PLR0911
        self, field_type: FieldType, field_def: FieldDefinition
    ) -> FieldType:
        """Get the appropriate array type for the field."""
        # Handle specific array item types based on items field
        if field_def.items:
            match field_def.items:
                case "string":
                    return (
                        list[EmailStr] if field_def.validation == "email" else list[str]
                    )
                case "integer":
                    return list[int]
                case "boolean":
                    return list[bool]
                case "datetime":
                    return list[datetime]
                case _:
                    return list[str]

        # Handle based on field_type when items not specified
        if field_type is EmailStr:
            return list[EmailStr]
        elif field_type is str:
            return list[str]
        return list[Any]

    def _build_field_constraints(self, field_def: FieldDefinition) -> dict[str, Any]:
        """Build Pydantic field constraints."""
        constraints: dict[str, Any] = {}

        # Add description
        if field_def.description:
            constraints["description"] = field_def.description

        # Array constraints
        if field_def.type == "array":
            if field_def.min_items is not None:
                constraints["min_length"] = field_def.min_items
            if field_def.max_items is not None:
                constraints["max_length"] = field_def.max_items

        # String constraints
        elif field_def.type == "string":
            if field_def.min_length is not None:
                constraints["min_length"] = field_def.min_length
            if field_def.max_length is not None:
                constraints["max_length"] = field_def.max_length
            if field_def.pattern:
                constraints["pattern"] = field_def.pattern

        # Handle enum validation
        if field_def.validation == "enum" and field_def.allowed_values:
            constraints["_enum_values"] = field_def.allowed_values

        return constraints

    def _create_field_validators(self, schema: EntitySchema) -> dict[str, Any]:
        """Create custom field validators for complex validation rules.

        Args:
            schema: The entity schema to create validators for

        Returns:
            Dictionary of validator functions
        """
        validators = {}

        # Add dependency reference validation for repositories
        # Only add the validator if the field actually exists
        has_depends_on = any(
            field.name == "depends_on"
            for field in schema.required_fields + schema.optional_fields
        )

        if schema.entity_type == "repository" and has_depends_on:
            validators["validate_depends_on"] = field_validator("depends_on")(
                self._validate_dependency_references
            )

        return validators

    @staticmethod
    def _validate_schema_version(v: str) -> str:
        """Validate schema version format."""
        import re

        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError('Schema version must be in semver format (e.g., "1.0.0")')
        return v

    @staticmethod
    def _validate_namespace(v: str) -> str:
        """Validate namespace format."""
        import re

        if not re.match(r"^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$", v):
            raise ValueError(
                "Namespace must be kebab-case: start with lowercase letter, "
                "contain only lowercase letters, numbers, underscores, hyphens, "
                "and end with lowercase letter or number"
            )
        return v

    @staticmethod
    def _validate_dependency_references(v: list[str] | None) -> list[str] | None:
        """Validate dependency reference URIs."""
        if v is None:
            return v

        import re

        for dep in v:
            # Check external dependency format (allow @ in package names for npm scoped packages)
            external_pattern = (
                r"^external://[a-zA-Z0-9._-]+/[a-zA-Z0-9@._/-]+/[a-zA-Z0-9._-]+$"
            )
            # Check internal dependency format
            internal_pattern = r"^internal://[a-z][a-z0-9_-]*[a-z0-9]/[a-zA-Z0-9._-]+$"

            if not (re.match(external_pattern, dep) or re.match(internal_pattern, dep)):
                raise ValueError(
                    f'Invalid dependency reference "{dep}". Must be either '
                    '"external://<ecosystem>/<package>/<version>" or '
                    '"internal://<namespace>/<entity-name>"'
                )

        return v

    def _create_enum_validator(self, field_name: str, allowed_values: list[str]) -> Any:
        """Create a field validator for enum validation.

        Args:
            field_name: Name of the field to validate
            allowed_values: List of allowed string values

        Returns:
            Field validator function
        """

        def validate_enum(_cls: Any, v: Any) -> Any:
            if v is not None and v not in allowed_values:
                raise ValueError(
                    f"Invalid value '{v}' for field '{field_name}'. "
                    f"Must be one of: {', '.join(allowed_values)}"
                )
            return v

        # Return validator with proper decorator
        return field_validator(field_name)(validate_enum)

    def clear_cache(self) -> None:
        """Clear the model cache. Useful for testing or when schemas change."""
        self._model_cache.clear()
