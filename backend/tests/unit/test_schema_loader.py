"""Comprehensive unit tests for schema loading functionality.

Tests cover loading individual schema files, inheritance resolution,
validation, error handling, and hot-reload capabilities.
"""

from datetime import datetime
from pathlib import Path
import tempfile

import pytest
import yaml

from kg.core.schema import (
    EntitySchema,
    FieldDefinition,
    RelationshipDefinition,
    SchemaLoadError,
    SchemaLoadResult,
)
from kg.core.schema_loader import FileSchemaLoader


class TestFieldDefinition:
    """Test FieldDefinition data structure."""

    def test_field_definition_creation(self):
        """Test creating a FieldDefinition."""
        field = FieldDefinition(
            name="test_field",
            type="string",
            required=True,
            validation="email",
            indexed=True,
            description="Test field",
            min_length=5,
            max_length=100,
        )

        assert field.name == "test_field"
        assert field.type == "string"
        assert field.required is True
        assert field.validation == "email"
        assert field.indexed is True
        assert field.description == "Test field"
        assert field.min_length == 5
        assert field.max_length == 100

    def test_field_definition_defaults(self):
        """Test FieldDefinition with default values."""
        field = FieldDefinition(name="simple", type="string", required=False)

        assert field.validation is None
        assert field.indexed is False
        assert field.description == ""
        assert field.min_length is None
        assert field.max_length is None


class TestRelationshipDefinition:
    """Test RelationshipDefinition data structure."""

    def test_relationship_definition_creation(self):
        """Test creating a RelationshipDefinition."""
        rel = RelationshipDefinition(
            name="depends_on",
            description="Dependencies",
            target_types=["external_dependency"],
            cardinality="one_to_many",
            direction="outbound",
        )

        assert rel.name == "depends_on"
        assert rel.description == "Dependencies"
        assert rel.target_types == ["external_dependency"]
        assert rel.cardinality == "one_to_many"
        assert rel.direction == "outbound"


class TestEntitySchema:
    """Test EntitySchema data structure."""

    def test_entity_schema_creation(self):
        """Test creating an EntitySchema."""
        required_fields = [FieldDefinition("id", "string", True)]
        optional_fields = [FieldDefinition("name", "string", False)]
        readonly_fields = [FieldDefinition("created_at", "datetime", False)]
        relationships = [
            RelationshipDefinition("rel", "test", ["other"], "one_to_one", "outbound")
        ]

        schema = EntitySchema(
            entity_type="test_entity",
            schema_version="1.0.0",
            description="Test entity",
            extends="base_internal",
            required_fields=required_fields,
            optional_fields=optional_fields,
            readonly_fields=readonly_fields,
            relationships=relationships,
            validation_rules={"strict": True},
            dgraph_type="TestEntity",
            dgraph_predicates={"id": {"type": "string", "index": ["exact"]}},
        )

        assert schema.entity_type == "test_entity"
        assert schema.schema_version == "1.0.0"
        assert schema.description == "Test entity"
        assert schema.extends == "base_internal"
        assert len(schema.required_fields) == 1
        assert len(schema.optional_fields) == 1
        assert len(schema.readonly_fields) == 1
        assert len(schema.relationships) == 1
        assert schema.validation_rules == {"strict": True}
        assert schema.dgraph_type == "TestEntity"


class TestFileSchemaLoader:
    """Test FileSchemaLoader implementation."""

    @pytest.fixture
    def temp_schema_dir(self):
        """Create temporary directory with test schema files in new subdirectory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)

            # Create _base directory structure
            base_dir = schema_dir / "_base"
            base_dir.mkdir()

            # Create base_internal/1.0.0.yaml
            base_internal_dir = base_dir / "base_internal"
            base_internal_dir.mkdir()

            base_internal = {
                "schema_type": "base_internal",
                "schema_version": "1.0.0",
                "governance": "strict",
                "readonly_metadata": {
                    "created_at": {
                        "type": "datetime",
                        "description": "Creation timestamp",
                        "indexed": False,
                    }
                },
                "validation_rules": {"unknown_fields": "reject"},
                "deletion_policy": {"type": "reference_counted"},
            }

            with (base_internal_dir / "1.0.0.yaml").open("w") as f:
                yaml.dump(base_internal, f)

            # Create base_external/1.0.0.yaml
            base_external_dir = base_dir / "base_external"
            base_external_dir.mkdir()

            base_external = {
                "schema_type": "base_external",
                "schema_version": "1.0.0",
                "governance": "permissive",
                "readonly_metadata": {
                    "created_at": {
                        "type": "datetime",
                        "description": "Creation timestamp",
                        "indexed": False,
                    }
                },
                "validation_rules": {"unknown_fields": "warn"},
            }

            with (base_external_dir / "1.0.0.yaml").open("w") as f:
                yaml.dump(base_external, f)

            # Create test_entity/1.0.0.yaml
            test_entity_dir = schema_dir / "test_entity"
            test_entity_dir.mkdir()

            test_entity = {
                "entity_type": "test_entity",
                "schema_version": "1.0.0",
                "extends": "base_internal",
                "description": "Test entity for unit tests",
                "required_metadata": {
                    "name": {
                        "type": "string",
                        "description": "Entity name",
                        "indexed": True,
                        "min_length": 1,
                        "max_length": 100,
                    }
                },
                "optional_metadata": {
                    "description": {
                        "type": "string",
                        "description": "Optional description",
                    }
                },
                "relationships": {
                    "related_to": {
                        "description": "Related entities",
                        "target_types": ["test_entity"],
                        "cardinality": "one_to_many",
                        "direction": "outbound",
                    }
                },
                "dgraph_type": "TestEntity",
                "dgraph_predicates": {"name": {"type": "string", "index": ["exact"]}},
            }

            with (test_entity_dir / "1.0.0.yaml").open("w") as f:
                yaml.dump(test_entity, f)

            yield schema_dir

    @pytest.mark.asyncio
    async def test_load_schemas_success(self, temp_schema_dir):
        """Test successful schema loading."""
        loader = FileSchemaLoader(str(temp_schema_dir))
        schemas = await loader.load_schemas()

        assert len(schemas) == 1
        assert "test_entity" in schemas

        schema = schemas["test_entity"]
        assert schema.entity_type == "test_entity"
        assert schema.extends == "base_internal"
        assert schema.governance == "strict"  # Inherited from base
        assert len(schema.required_fields) == 1
        assert len(schema.readonly_fields) == 1  # Inherited from base
        assert schema.required_fields[0].name == "name"
        assert schema.readonly_fields[0].name == "created_at"

    @pytest.mark.asyncio
    async def test_load_schemas_nonexistent_directory(self):
        """Test loading from non-existent directory."""
        loader = FileSchemaLoader("/nonexistent/path")

        with pytest.raises(SchemaLoadError, match="Schema directory does not exist"):
            await loader.load_schemas()

    @pytest.mark.asyncio
    async def test_inheritance_resolution(self, temp_schema_dir):
        """Test schema inheritance from base schemas."""
        loader = FileSchemaLoader(str(temp_schema_dir))
        schemas = await loader.load_schemas()

        schema = schemas["test_entity"]

        # Should inherit governance from base_internal
        assert schema.governance == "strict"

        # Should inherit readonly metadata
        readonly_names = [f.name for f in schema.readonly_fields]
        assert "created_at" in readonly_names

        # Should inherit validation rules
        assert "unknown_fields" in schema.validation_rules
        assert schema.validation_rules["unknown_fields"] == "reject"

        # Should inherit deletion policy
        assert schema.deletion_policy is not None
        assert schema.deletion_policy["type"] == "reference_counted"

    @pytest.mark.asyncio
    async def test_field_parsing(self, temp_schema_dir):
        """Test parsing of field definitions."""
        loader = FileSchemaLoader(str(temp_schema_dir))
        schemas = await loader.load_schemas()

        schema = schemas["test_entity"]

        # Check required field
        name_field = next(f for f in schema.required_fields if f.name == "name")
        assert name_field.type == "string"
        assert name_field.required is True
        assert name_field.indexed is True
        assert name_field.min_length == 1
        assert name_field.max_length == 100

        # Check optional field
        desc_field = next(f for f in schema.optional_fields if f.name == "description")
        assert desc_field.type == "string"
        assert desc_field.required is False

    @pytest.mark.asyncio
    async def test_relationship_parsing(self, temp_schema_dir):
        """Test parsing of relationship definitions."""
        loader = FileSchemaLoader(str(temp_schema_dir))
        schemas = await loader.load_schemas()

        schema = schemas["test_entity"]
        assert len(schema.relationships) == 1

        rel = schema.relationships[0]
        assert rel.name == "related_to"
        assert rel.description == "Related entities"
        assert rel.target_types == ["test_entity"]
        assert rel.cardinality == "one_to_many"
        assert rel.direction == "outbound"

    @pytest.mark.asyncio
    async def test_get_entity_schema(self, temp_schema_dir):
        """Test retrieving specific entity schema."""
        loader = FileSchemaLoader(str(temp_schema_dir))
        await loader.load_schemas()

        # Existing schema
        schema = await loader.get_entity_schema("test_entity")
        assert schema is not None
        assert schema.entity_type == "test_entity"

        # Non-existent schema
        schema = await loader.get_entity_schema("nonexistent")
        assert schema is None

    @pytest.mark.asyncio
    async def test_reload_schemas(self, temp_schema_dir):
        """Test schema reloading."""
        loader = FileSchemaLoader(str(temp_schema_dir))

        # Initial load
        schemas1 = await loader.load_schemas()
        assert len(schemas1) == 1

        # Reload should work
        schemas2 = await loader.reload_schemas()
        assert len(schemas2) == 1
        assert schemas1.keys() == schemas2.keys()

    @pytest.mark.asyncio
    async def test_validation_consistency_success(self, temp_schema_dir):
        """Test schema consistency validation (success case)."""
        loader = FileSchemaLoader(str(temp_schema_dir))
        schemas = await loader.load_schemas()

        errors = await loader.validate_schema_consistency(schemas)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validation_consistency_failure(self, temp_schema_dir):
        """Test schema consistency validation (failure case)."""
        loader = FileSchemaLoader(str(temp_schema_dir))

        # Create schema with invalid relationship target
        bad_schema = EntitySchema(
            entity_type="bad_entity",
            schema_version="1.0.0",
            description="Bad entity",
            extends=None,
            required_fields=[],
            optional_fields=[],
            readonly_fields=[],
            relationships=[
                RelationshipDefinition(
                    name="bad_rel",
                    description="Bad relationship",
                    target_types=["nonexistent_entity"],
                    cardinality="one_to_one",
                    direction="outbound",
                )
            ],
            validation_rules={},
            dgraph_type="",  # Missing dgraph_type
            dgraph_predicates={},
        )

        schemas = {"bad_entity": bad_schema}
        errors = await loader.validate_schema_consistency(schemas)

        # Should have errors for unknown target type and missing dgraph_type
        assert len(errors) >= 2
        assert any("unknown entity type" in error.lower() for error in errors)
        assert any("missing dgraph_type" in error.lower() for error in errors)

    @pytest.mark.asyncio
    async def test_inheritance_error_unknown_base(self, temp_schema_dir):
        """Test error when schema extends unknown base."""
        # Create schema with invalid base in proper subdirectory
        bad_entity_dir = temp_schema_dir / "bad_entity"
        bad_entity_dir.mkdir()

        bad_entity = {
            "entity_type": "bad_entity",
            "schema_version": "1.0.0",
            "extends": "unknown_base",
            "description": "Entity with bad inheritance",
            "required_metadata": {},
            "dgraph_type": "BadEntity",
            "dgraph_predicates": {},
        }

        with (bad_entity_dir / "1.0.0.yaml").open("w") as f:
            yaml.dump(bad_entity, f)

        loader = FileSchemaLoader(str(temp_schema_dir))

        with pytest.raises(
            SchemaLoadError, match="Failed to load entity schema.*unknown base"
        ):
            await loader.load_schemas()

    @pytest.mark.asyncio
    async def test_malformed_yaml(self, temp_schema_dir):
        """Test handling of malformed YAML files."""
        # Create malformed YAML file in proper subdirectory
        malformed_dir = temp_schema_dir / "malformed_entity"
        malformed_dir.mkdir()

        with (malformed_dir / "1.0.0.yaml").open("w") as f:
            f.write("invalid: yaml: content: [unclosed")

        loader = FileSchemaLoader(str(temp_schema_dir))

        with pytest.raises(SchemaLoadError, match="Failed to load"):
            await loader.load_schemas()

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, temp_schema_dir):
        """Test handling of schema missing required fields."""
        # Create schema missing required fields in proper subdirectory
        incomplete_dir = temp_schema_dir / "incomplete_entity"
        incomplete_dir.mkdir()

        incomplete_entity = {
            "entity_type": "incomplete_entity",  # Has entity_type so it will be processed
            # Missing schema_version which is required
            "description": "Incomplete entity",
        }

        with (incomplete_dir / "1.0.0.yaml").open("w") as f:
            yaml.dump(incomplete_entity, f)

        loader = FileSchemaLoader(str(temp_schema_dir))

        with pytest.raises(
            SchemaLoadError, match="Schema file.*missing required 'schema_version'"
        ):
            await loader.load_schemas()

    def test_get_load_result_no_load(self):
        """Test get_load_result when no schemas have been loaded."""
        loader = FileSchemaLoader("/tmp")
        result = loader.get_load_result()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_load_result_with_data(self, temp_schema_dir):
        """Test get_load_result after successful load."""
        loader = FileSchemaLoader(str(temp_schema_dir))
        await loader.load_schemas()

        result = loader.get_load_result()
        assert result is not None
        assert isinstance(result, SchemaLoadResult)
        assert result.schema_count == 1
        assert result.loaded_at is not None
        assert isinstance(result.loaded_at, datetime)
        assert "test_entity" in result.entity_schemas
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_hot_reload_simulation(self, temp_schema_dir):
        """Test hot reload by modifying files between loads."""
        loader = FileSchemaLoader(str(temp_schema_dir))

        # Initial load
        await loader.load_schemas()
        load_time1 = loader.last_loaded

        # Simulate file modification delay
        import time

        time.sleep(0.1)

        # Create a new schema file in proper subdirectory
        new_entity_dir = temp_schema_dir / "new_entity"
        new_entity_dir.mkdir()

        new_entity = {
            "entity_type": "new_entity",
            "schema_version": "1.0.0",
            "extends": "base_internal",
            "description": "Newly added entity",
            "required_metadata": {"id": {"type": "string", "description": "Entity ID"}},
            "dgraph_type": "NewEntity",
            "dgraph_predicates": {"id": {"type": "string", "index": ["exact"]}},
        }

        with (new_entity_dir / "1.0.0.yaml").open("w") as f:
            yaml.dump(new_entity, f)

        # Reload
        schemas2 = await loader.reload_schemas()
        load_time2 = loader.last_loaded

        assert load_time1 is not None
        assert load_time2 is not None

        # Should have more schemas and updated load time
        assert len(schemas2) == 2
        assert "new_entity" in schemas2
        assert load_time2 > load_time1

    @pytest.mark.asyncio
    async def test_empty_schema_directory(self, tmp_path):
        """Test loading from empty directory."""
        loader = FileSchemaLoader(str(tmp_path))
        schemas = await loader.load_schemas()
        assert len(schemas) == 0

    @pytest.mark.asyncio
    async def test_schema_with_no_relationships(self, temp_schema_dir):
        """Test schema without relationships."""
        # Create schema in proper subdirectory
        simple_entity_dir = temp_schema_dir / "simple_entity"
        simple_entity_dir.mkdir()

        simple_entity = {
            "entity_type": "simple_entity",
            "schema_version": "1.0.0",
            "description": "Simple entity without relationships",
            "required_metadata": {"name": {"type": "string", "description": "Name"}},
            "dgraph_type": "SimpleEntity",
            "dgraph_predicates": {"name": {"type": "string"}},
        }

        with (simple_entity_dir / "1.0.0.yaml").open("w") as f:
            yaml.dump(simple_entity, f)

        loader = FileSchemaLoader(str(temp_schema_dir))
        schemas = await loader.load_schemas()

        assert "simple_entity" in schemas
        schema = schemas["simple_entity"]
        assert len(schema.relationships) == 0
        assert schema.extends is None


@pytest.mark.asyncio
async def test_real_schema_files():
    """Integration test with actual schema files from spec/schemas."""

    # Get path to actual schema files
    current_dir = Path(__file__).parent
    schema_dir = current_dir.parent.parent / "schemas"

    if not schema_dir.exists():
        pytest.skip("Real schema files not found")

    loader = FileSchemaLoader(str(schema_dir))
    schemas = await loader.load_schemas()

    # Should load the three entity schemas
    expected_entities = [
        "repository",
        "external_dependency_package",
        "external_dependency_version",
    ]
    assert len(schemas) >= len(expected_entities)

    for entity_type in expected_entities:
        assert entity_type in schemas, f"Missing schema for {entity_type}"

        schema = schemas[entity_type]
        assert schema.entity_type == entity_type
        assert schema.schema_version
        assert schema.description
        assert schema.dgraph_type

    # Validate consistency
    errors = await loader.validate_schema_consistency(schemas)
    assert len(errors) == 0, f"Real schemas have consistency errors: {errors}"
