"""Tests for schema validation and conflict detection.

These tests ensure that schema loading catches design issues like naming
conflicts between fields and relationships, which could cause subtle bugs
in the storage layer.
"""

from pathlib import Path
import tempfile

import pytest

from kg.core.schema import SchemaLoadError, SchemaValidationError
from kg.core.schema_loader import FileSchemaLoader


@pytest.mark.asyncio
class TestSchemaNameConflictValidation:
    """Test that schema validation catches naming conflicts."""

    async def test_field_relationship_name_conflict_should_fail(self):
        """Test that having a field and relationship with the same name fails validation."""

        # Create a schema with a naming conflict
        schema_with_conflict = """
entity_type: test_entity
schema_version: "1.0.0"
extends: base_internal

description: "Test entity with naming conflict"

required_metadata:
  has_version:
    type: string
    description: "This conflicts with the relationship below"

optional_metadata: {}

relationships:
  has_version:
    description: "This conflicts with the field above"
    target_types: [external_dependency_version]
    cardinality: one_to_many
    direction: outbound

dgraph_type: TestEntity
"""

        # Create temporary schema directory
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)

            # Write base schema
            base_schema_path = schema_dir / "base_internal.yaml"
            base_schema_content = """
schema_type: base_internal
schema_version: "1.0.0"
governance: strict

readonly_metadata:
  created_at:
    type: datetime
    description: "Creation timestamp"
    indexed: false

validation_rules:
  unknown_fields: error
  missing_required_fields: error
  auto_create: false

deletion_policy:
  type: cascade
  description: "Internal entities can be deleted"

allow_custom_fields: false
"""
            base_schema_path.write_text(base_schema_content)

            # Write conflicting schema
            entity_schema_path = schema_dir / "test_entity.yaml"
            entity_schema_path.write_text(schema_with_conflict)

            # Create schema loader
            loader = FileSchemaLoader(str(schema_dir))

            # This should fail with a clear error about the naming conflict
            with pytest.raises(SchemaValidationError) as exc_info:
                await loader.load_schemas()

            error_message = str(exc_info.value)

            # Verify the error message is clear and specific
            assert "naming conflict" in error_message.lower()
            assert "has_version" in error_message
            assert "test_entity" in error_message
            assert "field and a relationship" in error_message.lower()

    async def test_different_field_relationship_names_should_pass(self):
        """Test that having distinct field and relationship names passes validation."""

        schema_without_conflict = """
entity_type: test_entity
schema_version: "1.0.0"
extends: base_internal

description: "Test entity without naming conflict"

required_metadata:
  version_string:
    type: string
    description: "Version as a string field"

optional_metadata: {}

relationships:
  version_relationship:
    description: "Relationship to version entities"
    target_types: [external_dependency_version]
    cardinality: one_to_many
    direction: outbound

dgraph_type: TestEntity
"""

        # Create temporary schema directory
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)

            # Write base schema
            base_schema_path = schema_dir / "base_internal.yaml"
            base_schema_content = """
schema_type: base_internal
schema_version: "1.0.0"
governance: strict

readonly_metadata:
  created_at:
    type: datetime
    description: "Creation timestamp"
    indexed: false

validation_rules:
  unknown_fields: error
  missing_required_fields: error
  auto_create: false

deletion_policy:
  type: cascade
  description: "Internal entities can be deleted"

allow_custom_fields: false
"""
            base_schema_path.write_text(base_schema_content)

            # Write external dependency version schema (referenced in relationship)
            ext_dep_schema_path = schema_dir / "external_dependency_version.yaml"
            ext_dep_schema_content = """
entity_type: external_dependency_version
schema_version: "1.0.0"
extends: base_external

description: "External dependency version"

required_metadata:
  ecosystem:
    type: string
    description: "Package ecosystem"

optional_metadata: {}
relationships: {}

dgraph_type: ExternalDependencyVersion
"""
            ext_dep_schema_path.write_text(ext_dep_schema_content)

            # Write base external schema
            base_external_path = schema_dir / "base_external.yaml"
            base_external_content = """
schema_type: base_external
schema_version: "1.0.0"
governance: permissive

readonly_metadata:
  created_at:
    type: datetime
    description: "Creation timestamp"

validation_rules:
  unknown_fields: warn
  auto_create: true

deletion_policy:
  type: never_delete

allow_custom_fields: false
"""
            base_external_path.write_text(base_external_content)

            # Write non-conflicting schema
            entity_schema_path = schema_dir / "test_entity.yaml"
            entity_schema_path.write_text(schema_without_conflict)

            # Create schema loader
            loader = FileSchemaLoader(str(schema_dir))

            # This should succeed
            schemas = await loader.load_schemas()

            # Verify schema was loaded correctly
            assert "test_entity" in schemas
            test_schema = schemas["test_entity"]

            # Verify field and relationship are both present with different names
            field_names = {
                field.name
                for field in test_schema.required_fields
                + test_schema.optional_fields
                + test_schema.readonly_fields
            }
            relationship_names = {rel.name for rel in test_schema.relationships}

            assert "version_string" in field_names
            assert "version_relationship" in relationship_names
            assert field_names.isdisjoint(relationship_names)  # No overlap

    async def test_multiple_name_conflicts_should_list_all(self):
        """Test that multiple naming conflicts are all reported."""

        schema_with_multiple_conflicts = """
entity_type: test_entity
schema_version: "1.0.0"
extends: base_internal

description: "Test entity with multiple naming conflicts"

required_metadata:
  has_version:
    type: string
    description: "First conflict"

  depends_on:
    type: array
    description: "Second conflict"

optional_metadata: {}

relationships:
  has_version:
    description: "First conflict with field"
    target_types: [external_dependency_version]
    cardinality: one_to_many
    direction: outbound

  depends_on:
    description: "Second conflict with field"
    target_types: [external_dependency_version]
    cardinality: one_to_many
    direction: outbound

dgraph_type: TestEntity
"""

        # Create temporary schema directory
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)

            # Write base schema
            base_schema_path = schema_dir / "base_internal.yaml"
            base_schema_content = """
schema_type: base_internal
schema_version: "1.0.0"
governance: strict

readonly_metadata:
  created_at:
    type: datetime
    description: "Creation timestamp"

validation_rules:
  unknown_fields: error
  auto_create: false

deletion_policy:
  type: cascade

allow_custom_fields: false
"""
            base_schema_path.write_text(base_schema_content)

            # Write external dependency version schema
            ext_dep_schema_path = schema_dir / "external_dependency_version.yaml"
            ext_dep_schema_content = """
entity_type: external_dependency_version
schema_version: "1.0.0"
extends: base_external

description: "External dependency version"

required_metadata:
  ecosystem:
    type: string

optional_metadata: {}
relationships: {}

dgraph_type: ExternalDependencyVersion
"""
            ext_dep_schema_path.write_text(ext_dep_schema_content)

            # Write base external schema
            base_external_path = schema_dir / "base_external.yaml"
            base_external_content = """
schema_type: base_external
schema_version: "1.0.0"
governance: permissive

readonly_metadata:
  created_at:
    type: datetime

validation_rules:
  auto_create: true

deletion_policy:
  type: never_delete

allow_custom_fields: false
"""
            base_external_path.write_text(base_external_content)

            # Write schema with multiple conflicts
            entity_schema_path = schema_dir / "test_entity.yaml"
            entity_schema_path.write_text(schema_with_multiple_conflicts)

            # Create schema loader
            loader = FileSchemaLoader(str(schema_dir))

            # This should fail
            with pytest.raises(SchemaValidationError) as exc_info:
                await loader.load_schemas()

            error_message = str(exc_info.value)

            # Verify both conflicts are reported
            assert "has_version" in error_message
            assert "depends_on" in error_message
            assert error_message.count("naming conflict") >= 2

    async def test_existing_schemas_should_load_successfully(self):
        """Test that the current schema files load successfully without conflicts."""

        # Test the actual schema files we have
        schema_dir = Path(__file__).parent.parent.parent / "schemas"
        loader = FileSchemaLoader(str(schema_dir))

        # This should succeed now that we fixed the relationship-to-field conversion bug
        schemas = await loader.load_schemas()

        # Verify the schemas loaded correctly
        assert "external_dependency_package" in schemas
        assert "external_dependency_version" in schemas
        assert "repository" in schemas

        # Verify external_dependency_package has the expected structure
        pkg_schema = schemas["external_dependency_package"]
        field_names = {
            f.name
            for f in pkg_schema.required_fields
            + pkg_schema.optional_fields
            + pkg_schema.readonly_fields
        }
        relationship_names = {r.name for r in pkg_schema.relationships}

        # Verify no conflicts exist
        assert field_names.isdisjoint(
            relationship_names
        ), f"Found conflicts between fields {field_names} and relationships {relationship_names}"

        # Verify specific expected fields and relationships
        assert "ecosystem" in field_names
        assert "package_name" in field_names
        assert "has_version" in relationship_names


@pytest.mark.asyncio
class TestSchemaValidationRobustness:
    """Test schema validation handles edge cases correctly."""

    async def test_empty_schema_directory_should_fail(self):
        """Test that an empty schema directory fails gracefully."""

        with tempfile.TemporaryDirectory() as temp_dir:
            loader = FileSchemaLoader(temp_dir)

            # Should fail because no schemas found
            with pytest.raises((SchemaLoadError, SchemaValidationError)):
                await loader.load_schemas()

    async def test_schema_with_missing_base_should_fail(self):
        """Test that schema extending non-existent base fails."""

        schema_with_missing_base = """
entity_type: test_entity
schema_version: "1.0.0"
extends: nonexistent_base

description: "Test entity"
required_metadata: {}
optional_metadata: {}
relationships: {}

dgraph_type: TestEntity
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)

            entity_schema_path = schema_dir / "test_entity.yaml"
            entity_schema_path.write_text(schema_with_missing_base)

            loader = FileSchemaLoader(str(schema_dir))

            # Should fail due to missing base
            with pytest.raises((SchemaLoadError, SchemaValidationError)):
                await loader.load_schemas()
