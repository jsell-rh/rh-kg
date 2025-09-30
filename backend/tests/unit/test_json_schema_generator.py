"""Comprehensive unit tests for JSON Schema generation functionality.

Tests cover JSON Schema generation from YAML schema definitions, field mapping,
validation rule translation, and VSCode integration requirements.
"""

from pathlib import Path
import tempfile

import pytest
import pytest_asyncio
import yaml

from kg.core.json_schema_generator import JSONSchemaExporter, JSONSchemaGenerator
from kg.core.schema import EntitySchema, FieldDefinition, RelationshipDefinition
from kg.core.schema_loader import FileSchemaLoader


class TestJSONSchemaFieldMapping:
    """Test mapping from YAML schema fields to JSON Schema properties."""

    def test_string_field_mapping(self):
        """Test mapping string field to JSON Schema."""
        field = FieldDefinition(
            name="test_field", type="string", required=True, description="Test field"
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["type"] == "string"
        assert json_prop["description"] == "Test field"

    def test_array_field_mapping(self):
        """Test mapping array field to JSON Schema."""
        field = FieldDefinition(
            name="owners",
            type="array",
            required=True,
            items="string",
            min_items=1,
            description="Owner emails",
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["type"] == "array"
        assert json_prop["items"]["type"] == "string"
        assert json_prop["minItems"] == 1
        assert json_prop["description"] == "Owner emails"

    def test_integer_field_mapping(self):
        """Test mapping integer field to JSON Schema."""
        field = FieldDefinition(
            name="count", type="integer", required=False, description="Item count"
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["type"] == "integer"
        assert json_prop["description"] == "Item count"

    def test_boolean_field_mapping(self):
        """Test mapping boolean field to JSON Schema."""
        field = FieldDefinition(
            name="deprecated", type="bool", required=False, description="Is deprecated"
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["type"] == "boolean"
        assert json_prop["description"] == "Is deprecated"

    def test_datetime_field_mapping(self):
        """Test mapping datetime field to JSON Schema."""
        field = FieldDefinition(
            name="created_at",
            type="datetime",
            required=False,
            description="Creation timestamp",
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["type"] == "string"
        assert json_prop["format"] == "date-time"
        assert json_prop["description"] == "Creation timestamp"


class TestJSONSchemaValidationMapping:
    """Test mapping validation rules to JSON Schema constraints."""

    def test_email_validation_mapping(self):
        """Test email validation maps to JSON Schema format and pattern."""
        field = FieldDefinition(
            name="owner", type="string", required=True, validation="email"
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["format"] == "email"
        assert "pattern" in json_prop
        assert "@" in json_prop["pattern"]  # Email pattern includes @

    def test_url_validation_mapping(self):
        """Test URL validation maps to JSON Schema format and pattern."""
        field = FieldDefinition(
            name="git_repo_url", type="string", required=True, validation="url"
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["format"] == "uri"
        assert json_prop["pattern"] == "^https?://"

    def test_pattern_validation_mapping(self):
        """Test custom pattern validation maps correctly."""
        field = FieldDefinition(
            name="namespace",
            type="string",
            required=True,
            pattern="^[a-z][a-z0-9_-]*[a-z0-9]$",
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["pattern"] == "^[a-z][a-z0-9_-]*[a-z0-9]$"

    def test_min_max_length_mapping(self):
        """Test min/max length constraints map correctly."""
        field = FieldDefinition(
            name="description",
            type="string",
            required=False,
            min_length=10,
            max_length=500,
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["minLength"] == 10
        assert json_prop["maxLength"] == 500

    def test_min_max_items_mapping(self):
        """Test min/max items constraints for arrays."""
        field = FieldDefinition(
            name="tags",
            type="array",
            required=False,
            items="string",
            min_items=1,
            max_items=10,
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["minItems"] == 1
        assert json_prop["maxItems"] == 10

    def test_allowed_values_enum_mapping(self):
        """Test allowed_values maps to JSON Schema enum."""
        field = FieldDefinition(
            name="ecosystem",
            type="string",
            required=True,
            allowed_values=["pypi", "npm", "golang.org", "github.com"],
        )

        json_prop = JSONSchemaGenerator._field_to_json_schema(field)

        assert json_prop["enum"] == ["pypi", "npm", "golang.org", "github.com"]


class TestJSONSchemaEntityGeneration:
    """Test generation of entity definitions in JSON Schema."""

    @pytest.fixture
    def sample_repository_schema(self) -> EntitySchema:
        """Create sample repository schema for testing."""
        return EntitySchema(
            entity_type="repository",
            schema_version="1.0.0",
            description="Code repository entity",
            extends="base_internal",
            required_fields=[
                FieldDefinition(
                    name="owners",
                    type="array",
                    required=True,
                    items="string",
                    validation="email",
                    min_items=1,
                    description="Owner email addresses",
                ),
                FieldDefinition(
                    name="git_repo_url",
                    type="string",
                    required=True,
                    validation="url",
                    description="Git repository URL",
                ),
            ],
            optional_fields=[],
            readonly_fields=[],
            relationships=[
                RelationshipDefinition(
                    name="depends_on",
                    description="External dependencies",
                    target_types=["external_dependency_version"],
                    cardinality="one_to_many",
                    direction="outbound",
                ),
                RelationshipDefinition(
                    name="internal_depends_on",
                    description="Internal dependencies",
                    target_types=["repository"],
                    cardinality="one_to_many",
                    direction="outbound",
                ),
            ],
            validation_rules={},
            dgraph_type="Repository",
            dgraph_predicates={},
        )

    def test_entity_definition_structure(self, sample_repository_schema):
        """Test entity definition has correct JSON Schema structure."""
        json_def = JSONSchemaGenerator._generate_entity_definition(
            sample_repository_schema
        )

        assert json_def["type"] == "object"
        assert json_def["minProperties"] == 1
        assert json_def["maxProperties"] == 1
        assert "additionalProperties" in json_def

    def test_entity_required_fields(self, sample_repository_schema):
        """Test required fields are marked in entity definition."""
        json_def = JSONSchemaGenerator._generate_entity_definition(
            sample_repository_schema
        )

        entity_props = json_def["additionalProperties"]
        assert "owners" in entity_props["required"]
        assert "git_repo_url" in entity_props["required"]

    def test_entity_field_properties(self, sample_repository_schema):
        """Test entity field properties are generated correctly."""
        json_def = JSONSchemaGenerator._generate_entity_definition(
            sample_repository_schema
        )

        props = json_def["additionalProperties"]["properties"]
        assert "owners" in props
        assert "git_repo_url" in props
        assert props["owners"]["type"] == "array"
        assert props["git_repo_url"]["type"] == "string"

    def test_entity_relationship_properties(self, sample_repository_schema):
        """Test relationships are included as array properties."""
        json_def = JSONSchemaGenerator._generate_entity_definition(
            sample_repository_schema
        )

        props = json_def["additionalProperties"]["properties"]
        assert "depends_on" in props
        assert "internal_depends_on" in props
        assert props["depends_on"]["type"] == "array"
        assert props["internal_depends_on"]["type"] == "array"

    def test_entity_additional_properties_false(self, sample_repository_schema):
        """Test strict validation - no additional properties allowed."""
        json_def = JSONSchemaGenerator._generate_entity_definition(
            sample_repository_schema
        )

        entity_props = json_def["additionalProperties"]
        assert entity_props["additionalProperties"] is False

    def test_readonly_fields_excluded(self):
        """Test readonly fields are not included in entity definition."""
        schema = EntitySchema(
            entity_type="test",
            schema_version="1.0.0",
            description="Test",
            extends=None,
            required_fields=[
                FieldDefinition(name="field1", type="string", required=True)
            ],
            optional_fields=[],
            readonly_fields=[
                FieldDefinition(
                    name="created_at",
                    type="datetime",
                    required=False,
                    description="Read-only",
                )
            ],
            relationships=[],
            validation_rules={},
            dgraph_type="Test",
            dgraph_predicates={},
        )

        json_def = JSONSchemaGenerator._generate_entity_definition(schema)
        props = json_def["additionalProperties"]["properties"]

        assert "field1" in props
        assert "created_at" not in props  # Readonly field excluded


class TestJSONSchemaTopLevelStructure:
    """Test generation of top-level JSON Schema structure."""

    @pytest_asyncio.fixture
    async def temp_schemas(self) -> Path:
        """Create temporary schema directory with minimal schemas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_dir = Path(tmpdir)

            # Create base_internal schema (versioned directory structure)
            base_internal = {
                "schema_type": "base_internal",
                "schema_version": "1.0.0",
                "governance": "strict",
                "readonly_metadata": {
                    "created_at": {"type": "datetime", "description": "Creation time"}
                },
                "validation_rules": {"unknown_fields": "reject"},
                "deletion_policy": {"type": "reference_counted"},
                "allow_custom_fields": False,
            }

            # Create repository schema (versioned directory structure)
            repository_schema = {
                "entity_type": "repository",
                "schema_version": "1.0.0",
                "extends": "base_internal",
                "description": "Code repository",
                "required_metadata": {
                    "owners": {
                        "type": "array",
                        "items": "string",
                        "validation": "email",
                        "min_items": 1,
                    },
                    "git_repo_url": {"type": "string", "validation": "url"},
                },
                "optional_metadata": {},
                "relationships": {},
                "dgraph_type": "Repository",
            }

            # Create versioned directory structure
            # Base schemas go in _base directory
            base_internal_dir = schema_dir / "_base" / "base_internal"
            base_internal_dir.mkdir(parents=True)
            (base_internal_dir / "1.0.0.yaml").write_text(
                yaml.dump(base_internal), encoding="utf-8"
            )

            # Entity schemas get their own versioned directories
            repository_dir = schema_dir / "repository"
            repository_dir.mkdir(parents=True)
            (repository_dir / "1.0.0.yaml").write_text(
                yaml.dump(repository_schema), encoding="utf-8"
            )

            yield schema_dir

    @pytest.mark.asyncio
    async def test_json_schema_root_structure(self, temp_schemas):
        """Test root JSON Schema has correct structure."""
        loader = FileSchemaLoader(str(temp_schemas))
        generator = JSONSchemaGenerator(loader)

        json_schema = await generator.generate()

        assert json_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert "$id" in json_schema
        assert json_schema["type"] == "object"
        assert json_schema["title"] == "Red Hat Knowledge Graph Schema"

    @pytest.mark.asyncio
    async def test_json_schema_required_fields(self, temp_schemas):
        """Test required top-level fields are marked."""
        loader = FileSchemaLoader(str(temp_schemas))
        generator = JSONSchemaGenerator(loader)

        json_schema = await generator.generate()

        assert set(json_schema["required"]) == {"namespace", "entity"}

    @pytest.mark.asyncio
    async def test_json_schema_properties(self, temp_schemas):
        """Test top-level properties are present."""
        loader = FileSchemaLoader(str(temp_schemas))
        generator = JSONSchemaGenerator(loader)

        json_schema = await generator.generate()

        assert "namespace" in json_schema["properties"]
        assert "entity" in json_schema["properties"]

    @pytest.mark.asyncio
    async def test_namespace_definition(self, temp_schemas):
        """Test namespace property definition."""
        loader = FileSchemaLoader(str(temp_schemas))
        generator = JSONSchemaGenerator(loader)

        json_schema = await generator.generate()

        namespace_prop = json_schema["properties"]["namespace"]
        assert namespace_prop["type"] == "string"
        assert "pattern" in namespace_prop
        assert "description" in namespace_prop

    @pytest.mark.asyncio
    async def test_entity_container_structure(self, temp_schemas):
        """Test entity container has correct structure."""
        loader = FileSchemaLoader(str(temp_schemas))
        generator = JSONSchemaGenerator(loader)

        json_schema = await generator.generate()

        entity_prop = json_schema["properties"]["entity"]
        assert entity_prop["type"] == "object"
        assert entity_prop["additionalProperties"] is False

    @pytest.mark.asyncio
    async def test_entity_types_included(self, temp_schemas):
        """Test all entity types are included in entity container."""
        # Verify fixture created files (versioned structure)
        assert (temp_schemas / "repository" / "1.0.0.yaml").exists()
        assert (temp_schemas / "_base" / "base_internal" / "1.0.0.yaml").exists()

        loader = FileSchemaLoader(str(temp_schemas))
        generator = JSONSchemaGenerator(loader)

        json_schema = await generator.generate()

        entity_props = json_schema["properties"]["entity"]["properties"]
        assert "repository" in entity_props

    @pytest.mark.asyncio
    async def test_definitions_section(self, temp_schemas):
        """Test $defs section contains entity and reference definitions."""
        # Verify fixture created files (versioned structure)
        assert (temp_schemas / "repository" / "1.0.0.yaml").exists()

        loader = FileSchemaLoader(str(temp_schemas))
        generator = JSONSchemaGenerator(loader)

        json_schema = await generator.generate()

        assert "$defs" in json_schema
        assert "repositoryEntity" in json_schema["$defs"]
        assert "externalDependencyReference" in json_schema["$defs"]
        assert "internalDependencyReference" in json_schema["$defs"]


class TestDependencyReferenceSchemas:
    """Test generation of dependency reference schemas."""

    def test_external_dependency_reference_schema(self):
        """Test external dependency reference JSON Schema."""
        ref_schema = JSONSchemaGenerator._generate_external_dependency_reference()

        assert ref_schema["type"] == "string"
        assert "pattern" in ref_schema
        assert "external://" in ref_schema["description"]
        assert len(ref_schema["examples"]) > 0

    def test_internal_dependency_reference_schema(self):
        """Test internal dependency reference JSON Schema."""
        ref_schema = JSONSchemaGenerator._generate_internal_dependency_reference()

        assert ref_schema["type"] == "string"
        assert "pattern" in ref_schema
        assert "internal://" in ref_schema["description"]
        assert len(ref_schema["examples"]) > 0

    def test_external_dependency_pattern(self):
        """Test external dependency pattern matches valid references."""
        ref_schema = JSONSchemaGenerator._generate_external_dependency_reference()
        pattern = ref_schema["pattern"]

        import re

        # Valid references should match
        assert re.match(pattern, "external://pypi/requests/2.31.0")
        assert re.match(pattern, "external://npm/@types/node/18.15.0")
        assert re.match(pattern, "external://github.com/stretchr/testify/v1.8.0")

        # Invalid references should not match
        assert not re.match(pattern, "external://pypi/requests")  # Missing version
        assert not re.match(pattern, "pypi/requests/2.31.0")  # Missing prefix

    def test_internal_dependency_pattern(self):
        """Test internal dependency pattern matches valid references."""
        ref_schema = JSONSchemaGenerator._generate_internal_dependency_reference()
        pattern = ref_schema["pattern"]

        import re

        # Valid references should match
        assert re.match(pattern, "internal://shared-utils/logging-library")
        assert re.match(pattern, "internal://openshift-auth/auth-service")

        # Invalid references should not match
        assert not re.match(
            pattern, "internal://SharedUtils/LoggingLibrary"
        )  # Wrong case
        assert not re.match(pattern, "shared-utils/logging-library")  # Missing prefix


class TestJSONSchemaExporter:
    """Test JSON Schema exporter with file output."""

    @pytest.mark.asyncio
    async def test_export_to_file(self):
        """Test exporting JSON Schema to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            output_file = Path(tmpdir) / "schema.json"

            # Create minimal schema (versioned directory structure)
            base_internal = {
                "schema_type": "base_internal",
                "schema_version": "1.0.0",
                "governance": "strict",
                "readonly_metadata": {},
                "validation_rules": {},
                "deletion_policy": {"type": "reference_counted"},
                "allow_custom_fields": False,
            }

            repository = {
                "entity_type": "repository",
                "schema_version": "1.0.0",
                "extends": "base_internal",
                "description": "Test",
                "required_metadata": {
                    "owners": {"type": "array", "items": "string", "min_items": 1}
                },
                "optional_metadata": {},
                "relationships": {},
                "dgraph_type": "Repository",
            }

            base_internal_dir = schema_dir / "_base" / "base_internal"
            base_internal_dir.mkdir(parents=True)
            (base_internal_dir / "1.0.0.yaml").write_text(
                yaml.dump(base_internal), encoding="utf-8"
            )
            repository_dir = schema_dir / "repository"
            repository_dir.mkdir(parents=True)
            (repository_dir / "1.0.0.yaml").write_text(
                yaml.dump(repository), encoding="utf-8"
            )

            # Export schema
            exporter = JSONSchemaExporter(str(schema_dir))
            await exporter.export(str(output_file), pretty=True)

            # Verify file exists and is valid JSON
            assert output_file.exists()

            import json

            loaded = json.loads(output_file.read_text(encoding="utf-8"))

            assert loaded["$schema"] == "https://json-schema.org/draft/2020-12/schema"
            assert "properties" in loaded

    @pytest.mark.asyncio
    async def test_export_pretty_formatting(self):
        """Test pretty formatting option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            output_file = Path(tmpdir) / "schema.json"

            # Create minimal schema (versioned directory structure)
            base = {
                "schema_type": "base_internal",
                "schema_version": "1.0.0",
                "governance": "strict",
                "readonly_metadata": {},
                "validation_rules": {},
                "deletion_policy": {"type": "reference_counted"},
                "allow_custom_fields": False,
            }

            base_internal_dir = schema_dir / "_base" / "base_internal"
            base_internal_dir.mkdir(parents=True)
            (base_internal_dir / "1.0.0.yaml").write_text(
                yaml.dump(base), encoding="utf-8"
            )

            # Export with pretty formatting
            exporter = JSONSchemaExporter(str(schema_dir))
            await exporter.export(str(output_file), pretty=True)

            content = output_file.read_text()
            # Pretty formatted JSON should have newlines and indentation
            assert "\n" in content
            assert "  " in content  # Indentation

    @pytest.mark.asyncio
    async def test_export_compact_formatting(self):
        """Test compact formatting option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_dir = Path(tmpdir) / "schemas"
            schema_dir.mkdir()
            output_file = Path(tmpdir) / "schema.json"

            # Create minimal schema (versioned directory structure)
            base = {
                "schema_type": "base_internal",
                "schema_version": "1.0.0",
                "governance": "strict",
                "readonly_metadata": {},
                "validation_rules": {},
                "deletion_policy": {"type": "reference_counted"},
                "allow_custom_fields": False,
            }

            base_internal_dir = schema_dir / "_base" / "base_internal"
            base_internal_dir.mkdir(parents=True)
            (base_internal_dir / "1.0.0.yaml").write_text(
                yaml.dump(base), encoding="utf-8"
            )

            # Export without pretty formatting
            exporter = JSONSchemaExporter(str(schema_dir))
            await exporter.export(str(output_file), pretty=False)

            content = output_file.read_text()
            # Compact JSON should be single line
            lines = content.strip().split("\n")
            assert len(lines) == 1


class TestJSONSchemaValidation:
    """Test that generated JSON Schema validates YAML files correctly."""

    @pytest.mark.asyncio
    async def test_valid_yaml_passes_validation(self):
        """Test that valid YAML passes JSON Schema validation."""
        # This test would use a JSON Schema validator library
        # to validate a sample YAML file against the generated schema
        # Implementation requires jsonschema library
        pytest.skip("Requires jsonschema library integration")

    @pytest.mark.asyncio
    async def test_invalid_yaml_fails_validation(self):
        """Test that invalid YAML fails JSON Schema validation."""
        pytest.skip("Requires jsonschema library integration")

    @pytest.mark.asyncio
    async def test_missing_required_field_fails(self):
        """Test that missing required fields fail validation."""
        pytest.skip("Requires jsonschema library integration")

    @pytest.mark.asyncio
    async def test_unknown_field_fails(self):
        """Test that unknown fields fail validation (strict mode)."""
        pytest.skip("Requires jsonschema library integration")
