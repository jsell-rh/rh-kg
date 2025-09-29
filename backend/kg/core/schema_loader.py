"""Schema loader implementation for dynamic schema loading from YAML files.

This module provides the schema loading interface and file-based implementation
that reads YAML schema files and creates runtime schema definitions with
inheritance resolution and validation.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .schema import (
    EntitySchema,
    FieldDefinition,
    RelationshipDefinition,
    SchemaInheritanceError,
    SchemaLoadError,
    SchemaLoadResult,
    SchemaValidationError,
)


class SchemaLoader(ABC):
    """Interface for loading and managing schemas."""

    @abstractmethod
    async def load_schemas(self, schema_dir: str) -> dict[str, EntitySchema]:
        """Load all schemas from directory."""
        pass

    @abstractmethod
    async def reload_schemas(self) -> dict[str, EntitySchema]:
        """Reload schemas from disk."""
        pass

    @abstractmethod
    async def validate_schema_consistency(
        self, schemas: dict[str, EntitySchema]
    ) -> list[str]:
        """Validate schema consistency and return errors."""
        pass

    @abstractmethod
    async def get_entity_schema(self, entity_type: str) -> EntitySchema | None:
        """Get schema for specific entity type."""
        pass


class FileSchemaLoader(SchemaLoader):
    """File-based schema loader implementation.

    Loads schemas from YAML files in a directory structure, resolves
    inheritance from base schemas, and provides hot-reload capabilities.
    """

    def __init__(self, schema_dir: str):
        """Initialize with schema directory path.

        Args:
            schema_dir: Path to directory containing schema YAML files
        """
        self.schema_dir = Path(schema_dir)
        self.schemas: dict[str, EntitySchema] = {}
        self.last_loaded: datetime | None = None

    async def load_schemas(
        self, schema_dir: str | None = None
    ) -> dict[str, EntitySchema]:
        """Load all schema files from directory.

        Args:
            schema_dir: Optional override for schema directory

        Returns:
            Dictionary mapping entity types to their schemas

        Raises:
            SchemaLoadError: If schema loading fails
            SchemaValidationError: If schema validation fails
        """
        schema_path = Path(schema_dir) if schema_dir else self.schema_dir

        if not schema_path.exists():
            raise SchemaLoadError(f"Schema directory does not exist: {schema_path}")

        try:
            # Load base schemas first
            base_schemas = await self._load_base_schemas(schema_path)

            # Load entity schemas
            entity_schemas = await self._load_entity_schemas(schema_path, base_schemas)

            # Validate consistency
            errors = await self.validate_schema_consistency(entity_schemas)
            if errors:
                raise SchemaValidationError(
                    f"Schema validation failed: {errors}", errors
                )

            self.schemas = entity_schemas
            self.last_loaded = datetime.now(UTC)

            return self.schemas

        except (
            yaml.YAMLError,
            FileNotFoundError,
            KeyError,
            SchemaInheritanceError,
        ) as e:
            raise SchemaLoadError(f"Failed to load schemas: {e}") from e

    async def reload_schemas(self) -> dict[str, EntitySchema]:
        """Reload schemas from disk.

        Returns:
            Updated schemas dictionary
        """
        return await self.load_schemas()

    async def validate_schema_consistency(
        self, schemas: dict[str, EntitySchema]
    ) -> list[str]:
        """Validate schema consistency and return errors.

        Args:
            schemas: Dictionary of schemas to validate

        Returns:
            List of validation error messages
        """
        errors = []

        for entity_type, schema in schemas.items():
            # Validate relationship target types exist
            for relationship in schema.relationships:
                for target_type in relationship.target_types:
                    if target_type not in schemas:
                        errors.append(
                            f"Entity '{entity_type}' has relationship '{relationship.name}' "
                            f"targeting unknown entity type '{target_type}'"
                        )

            # Validate field names are unique within schema
            all_field_names: list[str] = []
            for field_list in [
                schema.required_fields,
                schema.optional_fields,
                schema.readonly_fields,
            ]:
                all_field_names.extend(field.name for field in field_list)

            if len(all_field_names) != len(set(all_field_names)):
                errors.append(f"Entity '{entity_type}' has duplicate field names")

            # Validate no conflicts between field names and relationship names
            relationship_names = {rel.name for rel in schema.relationships}
            field_names_set = set(all_field_names)

            name_conflicts = relationship_names.intersection(field_names_set)
            if name_conflicts:
                for conflict_name in name_conflicts:
                    errors.append(
                        f"Entity '{entity_type}' has naming conflict: "
                        f"'{conflict_name}' is defined as both a field and a relationship. "
                        f"Relationships and fields must have unique names within an entity schema."
                    )

            # Validate dgraph_type is set
            if not schema.dgraph_type:
                errors.append(f"Entity '{entity_type}' missing dgraph_type")

        return errors

    async def get_entity_schema(self, entity_type: str) -> EntitySchema | None:
        """Get schema for specific entity type.

        Args:
            entity_type: The entity type to get schema for

        Returns:
            EntitySchema if found, None otherwise
        """
        return self.schemas.get(entity_type)

    async def _load_base_schemas(self, schema_path: Path) -> dict[str, dict[str, Any]]:
        """Load base schema definitions.

        Args:
            schema_path: Path to schema directory

        Returns:
            Dictionary of base schema data
        """
        base_schemas = {}

        for base_file in ["base_internal.yaml", "base_external.yaml"]:
            file_path = schema_path / base_file
            if file_path.exists():
                try:
                    with file_path.open(encoding="utf-8") as f:
                        schema_data = yaml.safe_load(f)

                    base_name = base_file.replace(".yaml", "")
                    base_schemas[base_name] = schema_data

                except (OSError, yaml.YAMLError) as e:
                    raise SchemaLoadError(
                        f"Failed to load base schema '{base_file}': {e}"
                    ) from e

        return base_schemas

    async def _load_entity_schemas(
        self, schema_path: Path, base_schemas: dict[str, dict[str, Any]]
    ) -> dict[str, EntitySchema]:
        """Load entity schema files and resolve inheritance.

        Args:
            schema_path: Path to schema directory
            base_schemas: Previously loaded base schemas

        Returns:
            Dictionary of resolved entity schemas
        """
        schemas = {}

        for schema_file in schema_path.glob("*.yaml"):
            if schema_file.name.startswith("base_"):
                continue  # Skip base schemas

            try:
                with schema_file.open(encoding="utf-8") as f:
                    schema_data = yaml.safe_load(f)

                # Skip if not an entity schema (has entity_type field)
                if "entity_type" not in schema_data:
                    continue

                # Resolve inheritance
                resolved_schema = await self._resolve_inheritance(
                    schema_data, base_schemas
                )

                # Convert to EntitySchema object
                entity_schema = await self._parse_entity_schema(resolved_schema)
                schemas[entity_schema.entity_type] = entity_schema

            except (OSError, yaml.YAMLError, KeyError) as e:
                raise SchemaLoadError(
                    f"Failed to load schema '{schema_file.name}': {e}"
                ) from e

        return schemas

    async def _resolve_inheritance(
        self, schema_data: dict[str, Any], base_schemas: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Resolve schema inheritance from base schemas.

        Args:
            schema_data: Entity schema data
            base_schemas: Available base schemas

        Returns:
            Schema data with inheritance resolved

        Raises:
            SchemaInheritanceError: If inheritance resolution fails
        """
        extends = schema_data.get("extends")
        if not extends:
            return schema_data

        if extends not in base_schemas:
            raise SchemaInheritanceError(
                f"Schema extends unknown base '{extends}'. Available: {list(base_schemas.keys())}"
            )

        base_schema = base_schemas[extends].copy()
        resolved = schema_data.copy()

        # Merge readonly metadata (base + entity-specific)
        readonly_metadata = base_schema.get("readonly_metadata", {}).copy()
        readonly_metadata.update(schema_data.get("readonly_metadata", {}))
        resolved["readonly_metadata"] = readonly_metadata

        # Merge validation rules (base + entity-specific)
        validation_rules = base_schema.get("validation_rules", {}).copy()
        validation_rules.update(schema_data.get("validation_rules", {}))
        resolved["validation_rules"] = validation_rules

        # Inherit deletion policy if not specified
        if "deletion_policy" not in resolved:
            resolved["deletion_policy"] = base_schema.get("deletion_policy")

        # Inherit governance and other base properties
        resolved["governance"] = base_schema.get("governance")
        resolved["allow_custom_fields"] = base_schema.get("allow_custom_fields", False)

        return resolved

    async def _parse_entity_schema(self, schema_data: dict[str, Any]) -> EntitySchema:
        """Convert schema data dictionary to EntitySchema object.

        Args:
            schema_data: Raw schema data from YAML

        Returns:
            Parsed EntitySchema object

        Raises:
            SchemaLoadError: If required fields are missing
        """
        try:
            # Parse field definitions
            required_fields = self._parse_field_definitions(
                schema_data.get("required_metadata", {}), required=True
            )
            optional_fields = self._parse_field_definitions(
                schema_data.get("optional_metadata", {}), required=False
            )
            readonly_fields = self._parse_field_definitions(
                schema_data.get("readonly_metadata", {}), required=False
            )

            # Parse relationships
            relationships = self._parse_relationships(
                schema_data.get("relationships", {})
            )

            return EntitySchema(
                entity_type=schema_data["entity_type"],
                schema_version=schema_data["schema_version"],
                description=schema_data.get("description", ""),
                extends=schema_data.get("extends"),
                required_fields=required_fields,
                optional_fields=optional_fields,
                readonly_fields=readonly_fields,
                relationships=relationships,
                validation_rules=schema_data.get("validation_rules", {}),
                dgraph_type=schema_data.get("dgraph_type", ""),
                dgraph_predicates=schema_data.get("dgraph_predicates", {}),
                governance=schema_data.get("governance"),
                deletion_policy=schema_data.get("deletion_policy"),
                auto_creation=schema_data.get("auto_creation"),
                allow_custom_fields=schema_data.get("allow_custom_fields", False),
            )

        except KeyError as e:
            raise SchemaLoadError(f"Required field missing in schema: {e}") from e

    def _parse_field_definitions(
        self, fields_data: dict[str, Any], required: bool
    ) -> list[FieldDefinition]:
        """Parse field definitions from schema data.

        Args:
            fields_data: Field definitions from schema
            required: Whether these fields are required

        Returns:
            List of FieldDefinition objects
        """
        fields = []

        for field_name, field_config in fields_data.items():
            field_def = FieldDefinition(
                name=field_name,
                type=field_config.get("type", "string"),
                required=required,
                validation=field_config.get("validation"),
                indexed=field_config.get("indexed", False),
                description=field_config.get("description", ""),
                min_length=field_config.get("min_length"),
                max_length=field_config.get("max_length"),
                min_items=field_config.get("min_items"),
                max_items=field_config.get("max_items"),
                allowed_values=field_config.get("allowed_values"),
                pattern=field_config.get("pattern"),
                items=field_config.get("items"),
            )
            fields.append(field_def)

        return fields

    def _parse_relationships(
        self, relationships_data: dict[str, Any]
    ) -> list[RelationshipDefinition]:
        """Parse relationship definitions from schema data.

        Args:
            relationships_data: Relationship definitions from schema

        Returns:
            List of RelationshipDefinition objects
        """
        relationships = []

        for rel_name, rel_config in relationships_data.items():
            rel_def = RelationshipDefinition(
                name=rel_name,
                description=rel_config.get("description", ""),
                target_types=rel_config.get("target_types", []),
                cardinality=rel_config.get("cardinality", "one_to_many"),
                direction=rel_config.get("direction", "outbound"),
            )
            relationships.append(rel_def)

        return relationships

    def get_load_result(self) -> SchemaLoadResult | None:
        """Get detailed result of last schema load operation.

        Returns:
            SchemaLoadResult with metadata about loaded schemas
        """
        if not self.last_loaded:
            return None

        base_schemas = []
        entity_schemas = []

        for schema in self.schemas.values():
            if schema.extends:
                entity_schemas.append(schema.entity_type)
            else:
                base_schemas.append(schema.entity_type)

        return SchemaLoadResult(
            schemas=self.schemas.copy(),
            loaded_at=self.last_loaded,
            schema_count=len(self.schemas),
            base_schemas=base_schemas,
            entity_schemas=entity_schemas,
            errors=[],
        )
