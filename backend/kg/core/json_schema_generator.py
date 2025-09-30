"""JSON Schema generator for knowledge graph YAML files.

This module generates JSON Schema (Draft 2020-12) from YAML schema definitions,
enabling VSCode autocomplete and validation for knowledge graph files.
"""

import json
from pathlib import Path
from typing import Any

from .schema import EntitySchema, FieldDefinition, RelationshipDefinition
from .schema_loader import FileSchemaLoader


class JSONSchemaGenerator:
    """Generate JSON Schema from entity schema definitions."""

    def __init__(self, schema_loader: FileSchemaLoader):
        """Initialize generator with schema loader.

        Args:
            schema_loader: Loader for YAML schema definitions
        """
        self.schema_loader = schema_loader

    async def generate(self) -> dict[str, Any]:
        """Generate complete JSON Schema for knowledge graph YAML files.

        Returns:
            JSON Schema dictionary (Draft 2020-12)
        """
        # Load schemas
        schemas = self.schema_loader.schemas
        if not schemas:
            await self.schema_loader.load_schemas()
            schemas = self.schema_loader.schemas

        # Build JSON Schema structure
        json_schema: dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://redhat.com/schemas/knowledge-graph/1.0.0",
            "title": "Red Hat Knowledge Graph Schema",
            "description": "Schema for Red Hat knowledge graph YAML files",
            "type": "object",
            "required": ["namespace", "entity"],
            "additionalProperties": False,
            "properties": {},
            "$defs": {},
        }

        # Add top-level properties
        json_schema["properties"]["namespace"] = self._generate_namespace_property()

        # Generate entity definitions
        entity_container = self._generate_entity_container(schemas)
        json_schema["properties"]["entity"] = entity_container

        # Add entity definitions to $defs
        for entity_type, entity_schema in schemas.items():
            entity_def = self._generate_entity_definition(entity_schema)
            json_schema["$defs"][f"{entity_type}Entity"] = entity_def

        # Add dependency reference definitions
        json_schema["$defs"]["externalDependencyReference"] = (
            self._generate_external_dependency_reference()
        )
        json_schema["$defs"]["internalDependencyReference"] = (
            self._generate_internal_dependency_reference()
        )

        return json_schema

    @staticmethod
    def _generate_namespace_property() -> dict[str, Any]:
        """Generate namespace property definition.

        Returns:
            JSON Schema property for namespace
        """
        return {
            "type": "string",
            "pattern": r"^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$",
            "description": "Namespace for grouping related entities (kebab-case format)",
            "examples": ["rosa-hcp", "shared-utils", "openshift-auth"],
        }

    def _generate_entity_container(
        self, schemas: dict[str, EntitySchema]
    ) -> dict[str, Any]:
        """Generate entity container property.

        Args:
            schemas: Dictionary of entity schemas

        Returns:
            JSON Schema property for entity container
        """
        container: dict[str, Any] = {
            "type": "object",
            "description": "Entity definitions for the knowledge graph",
            "properties": {},
            "additionalProperties": False,
        }

        for entity_type in schemas:
            container["properties"][entity_type] = {
                "type": "array",
                "description": f"{entity_type.capitalize()} entity definitions",
                "items": {"$ref": f"#/$defs/{entity_type}Entity"},
            }

        return container

    @staticmethod
    def _generate_entity_definition(entity_schema: EntitySchema) -> dict[str, Any]:
        """Generate JSON Schema definition for an entity type.

        Args:
            entity_schema: Entity schema to convert

        Returns:
            JSON Schema definition for the entity
        """
        # Entity definition structure: each array item is an object with one key
        # (the entity name) mapping to the entity properties
        entity_def: dict[str, Any] = {
            "type": "object",
            "description": entity_schema.description
            or f"A {entity_schema.entity_type} entity",
            "minProperties": 1,
            "maxProperties": 1,
            "additionalProperties": {
                "type": "object",
                "required": [],
                "additionalProperties": False,
                "properties": {},
            },
        }

        entity_props = entity_def["additionalProperties"]

        # Add required fields to properties
        for field in entity_schema.required_fields:
            entity_props["properties"][field.name] = (
                JSONSchemaGenerator._field_to_json_schema(field)
            )
            entity_props["required"].append(field.name)

        # Add optional fields to properties
        for field in entity_schema.optional_fields:
            entity_props["properties"][field.name] = (
                JSONSchemaGenerator._field_to_json_schema(field)
            )

        # Add relationships to properties (as arrays)
        for relationship in entity_schema.relationships:
            entity_props["properties"][relationship.name] = (
                JSONSchemaGenerator._relationship_to_json_schema(relationship)
            )

        # Sort required array for consistency
        entity_props["required"].sort()

        return entity_def

    @staticmethod
    def _field_to_json_schema(field: FieldDefinition) -> dict[str, Any]:
        """Convert field definition to JSON Schema property.

        Args:
            field: Field definition from YAML schema

        Returns:
            JSON Schema property definition
        """
        # Map field type
        if field.type == "array":
            prop = JSONSchemaGenerator._map_array_field(field)
        elif field.type == "integer":
            prop = {"type": "integer"}
        elif field.type == "bool":
            prop = {"type": "boolean"}
        elif field.type == "datetime":
            prop = {"type": "string", "format": "date-time"}
        else:  # string or default
            prop = JSONSchemaGenerator._map_string_field(field)

        # Handle enum values
        if field.allowed_values:
            prop["enum"] = field.allowed_values

        # Add description
        if field.description:
            prop["description"] = field.description

        return prop

    @staticmethod
    def _map_array_field(field: FieldDefinition) -> dict[str, Any]:
        """Map array field to JSON Schema.

        Args:
            field: Array field definition

        Returns:
            JSON Schema property for array
        """
        prop: dict[str, Any] = {"type": "array"}

        if field.items:
            prop["items"] = {"type": field.items}
        if field.min_items is not None:
            prop["minItems"] = field.min_items
        if field.max_items is not None:
            prop["maxItems"] = field.max_items

        return prop

    @staticmethod
    def _map_string_field(field: FieldDefinition) -> dict[str, Any]:
        """Map string field to JSON Schema with validation.

        Args:
            field: String field definition

        Returns:
            JSON Schema property for string
        """
        prop: dict[str, Any] = {"type": "string"}

        # Handle validation
        if field.validation == "email":
            prop["format"] = "email"
            # Email pattern from EmailValidator
            prop["pattern"] = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        elif field.validation == "url":
            prop["format"] = "uri"
            prop["pattern"] = "^https?://"

        # Handle custom pattern
        if field.pattern:
            prop["pattern"] = field.pattern

        # Handle length constraints
        if field.min_length is not None:
            prop["minLength"] = field.min_length
        if field.max_length is not None:
            prop["maxLength"] = field.max_length

        return prop

    @staticmethod
    def _relationship_to_json_schema(
        relationship: RelationshipDefinition,
    ) -> dict[str, Any]:
        """Convert relationship definition to JSON Schema property.

        Args:
            relationship: Relationship definition from YAML schema

        Returns:
            JSON Schema property definition for relationship
        """
        prop: dict[str, Any] = {
            "type": "array",
            "description": relationship.description
            or f"{relationship.name} relationships",
            "default": [],
        }

        # Determine reference type based on target types
        # This is a simplified mapping - could be enhanced
        if any("external" in target.lower() for target in relationship.target_types):
            prop["items"] = {"$ref": "#/$defs/externalDependencyReference"}
        elif any(
            "repository" in target.lower() for target in relationship.target_types
        ):
            prop["items"] = {"$ref": "#/$defs/internalDependencyReference"}
        else:
            # Generic reference
            prop["items"] = {"type": "string"}

        # Add examples
        if "external" in relationship.name or any(
            "external" in target.lower() for target in relationship.target_types
        ):
            prop["examples"] = [["external://pypi/requests/2.31.0"]]
        elif "internal" in relationship.name:
            prop["examples"] = [["internal://shared-utils/logging-library"]]

        return prop

    @staticmethod
    def _generate_external_dependency_reference() -> dict[str, Any]:
        """Generate external dependency reference definition.

        Returns:
            JSON Schema definition for external dependency references
        """
        return {
            "type": "string",
            "pattern": r"^external://[a-zA-Z0-9._-]+/[a-zA-Z0-9@._/-]+/[a-zA-Z0-9._-]+$",
            "description": "External dependency reference: external://<ecosystem>/<package>/<version>",
            "examples": [
                "external://pypi/requests/2.31.0",
                "external://npm/@types/node/18.15.0",
                "external://github.com/stretchr/testify/v1.8.0",
                "external://golang.org/x/client-go/v0.28.4",
            ],
        }

    @staticmethod
    def _generate_internal_dependency_reference() -> dict[str, Any]:
        """Generate internal dependency reference definition.

        Returns:
            JSON Schema definition for internal dependency references
        """
        return {
            "type": "string",
            "pattern": r"^internal://[a-z][a-z0-9_-]*[a-z0-9]/[a-zA-Z0-9._-]+$",
            "description": "Internal dependency reference: internal://<namespace>/<entity-name>",
            "examples": [
                "internal://shared-utils/logging-library",
                "internal://openshift-auth/auth-service",
                "internal://rosa-hcp/rosa-operator",
            ],
        }


class JSONSchemaExporter:
    """Export JSON Schema to files with formatting options."""

    def __init__(self, schema_dir: str):
        """Initialize exporter with schema directory.

        Args:
            schema_dir: Directory containing YAML schema definitions
        """
        self.schema_dir = schema_dir
        self.loader = FileSchemaLoader(schema_dir)
        self.generator = JSONSchemaGenerator(self.loader)

    async def export(self, output_path: str, pretty: bool = True) -> dict[str, Any]:
        """Export JSON Schema to file.

        Args:
            output_path: Path to output JSON file
            pretty: Whether to pretty-print JSON (default: True)

        Returns:
            Generated JSON Schema
        """
        # Load schemas if not already loaded
        if not self.loader.schemas:
            await self.loader.load_schemas()

        # Generate JSON Schema
        json_schema = await self.generator.generate()

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if pretty:
            output_file.write_text(
                json.dumps(json_schema, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        else:
            output_file.write_text(
                json.dumps(json_schema, ensure_ascii=False), encoding="utf-8"
            )

        return json_schema

    async def export_with_vscode_config(
        self, output_path: str = ".vscode/kg-schema.json"
    ) -> dict[str, Any]:
        """Export JSON Schema and configure VSCode settings.

        Args:
            output_path: Path to output JSON file (default: .vscode/kg-schema.json)

        Returns:
            Generated JSON Schema
        """
        # Export schema
        json_schema = await self.export(output_path, pretty=True)

        # Update VSCode settings
        vscode_settings_path = Path(".vscode/settings.json")
        vscode_settings_path.parent.mkdir(parents=True, exist_ok=True)

        if vscode_settings_path.exists():
            # Read existing settings
            existing_settings = json.loads(
                vscode_settings_path.read_text(encoding="utf-8")
            )
        else:
            existing_settings = {}

        # Add/update yaml.schemas configuration
        if "yaml.schemas" not in existing_settings:
            existing_settings["yaml.schemas"] = {}

        existing_settings["yaml.schemas"][output_path] = [
            "**/knowledge-graph.yaml",
            "tmp/**/knowledge-graph.yaml",
        ]

        # Write updated settings
        vscode_settings_path.write_text(
            json.dumps(existing_settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return json_schema
