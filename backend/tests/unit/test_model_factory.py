"""Tests for the DynamicModelFactory."""

from datetime import datetime
from typing import get_args, get_origin

from pydantic import BaseModel, EmailStr, HttpUrl, ValidationError
import pytest

from kg.core import (
    DynamicModelFactory,
    EntitySchema,
    FieldDefinition,
    RelationshipDefinition,
)


class TestDynamicModelFactory:
    """Test cases for the DynamicModelFactory class."""

    @pytest.fixture
    def factory(self):
        """Create a fresh model factory for each test."""
        return DynamicModelFactory()

    @pytest.fixture
    def basic_schema(self):
        """Create a basic entity schema for testing."""
        return EntitySchema(
            entity_type="test_entity",
            schema_version="1.0.0",
            description="Test entity for validation",
            extends=None,
            required_fields=[
                FieldDefinition(
                    name="name",
                    type="string",
                    required=True,
                    description="Entity name",
                    min_length=1,
                    max_length=100,
                ),
                FieldDefinition(
                    name="count",
                    type="integer",
                    required=True,
                    description="Some count value",
                ),
            ],
            optional_fields=[
                FieldDefinition(
                    name="description",
                    type="string",
                    required=False,
                    description="Optional description",
                ),
            ],
            readonly_fields=[
                FieldDefinition(
                    name="created_at",
                    type="datetime",
                    required=False,
                    description="Creation timestamp",
                ),
            ],
            relationships=[],
            validation_rules={},
            dgraph_type="TestEntity",
            dgraph_predicates={},
        )

    @pytest.fixture
    def repository_schema(self):
        """Create a repository schema that matches the spec."""
        return EntitySchema(
            entity_type="repository",
            schema_version="1.0.0",
            description="Repository entity",
            extends="base_internal",
            required_fields=[
                FieldDefinition(
                    name="owners",
                    type="array",
                    items="string",
                    required=True,
                    validation="email",
                    min_items=1,
                    description="List of owner email addresses",
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
            readonly_fields=[
                FieldDefinition(
                    name="created_at",
                    type="datetime",
                    required=False,
                    description="Creation timestamp",
                ),
                FieldDefinition(
                    name="updated_at",
                    type="datetime",
                    required=False,
                    description="Last update timestamp",
                ),
            ],
            relationships=[
                RelationshipDefinition(
                    name="depends_on",
                    description="External and internal dependencies",
                    target_types=["external_dependency_version", "repository"],
                    cardinality="one_to_many",
                    direction="outbound",
                ),
            ],
            validation_rules={},
            dgraph_type="Repository",
            dgraph_predicates={},
        )

    def test_create_entity_model_basic(self, factory, basic_schema):
        """Test creating a basic entity model."""
        model_class = factory.create_entity_model(basic_schema)

        # Check model name
        assert model_class.__name__ == "test_entityModel"

        # Check fields exist
        fields = model_class.model_fields
        assert "name" in fields
        assert "count" in fields
        assert "description" in fields
        assert "created_at" in fields

        # Check required fields
        required_fields = {
            name for name, field in fields.items() if field.is_required()
        }
        assert "name" in required_fields
        assert "count" in required_fields
        assert "description" not in required_fields
        assert "created_at" not in required_fields

    def test_create_entity_model_repository(self, factory, repository_schema):
        """Test creating a repository model with email and URL validation."""
        model_class = factory.create_entity_model(repository_schema)

        # Check model name
        assert model_class.__name__ == "repositoryModel"

        # Check fields
        fields = model_class.model_fields
        assert "owners" in fields
        assert "git_repo_url" in fields
        assert "created_at" in fields
        assert "updated_at" in fields

        # Check field types
        owners_field = fields["owners"]
        # Should be list[EmailStr] for email validation
        assert get_origin(owners_field.annotation) is list
        email_type = get_args(owners_field.annotation)[0]
        assert email_type == EmailStr

        # Check URL field type
        git_repo_field = fields["git_repo_url"]
        assert git_repo_field.annotation == HttpUrl

    def test_field_type_mapping(self, factory):
        """Test field type mapping from schema types to Python types."""
        # Test string type
        field_def = FieldDefinition(name="test", type="string", required=True)
        schema = EntitySchema(
            entity_type="test",
            schema_version="1.0.0",
            description="Test",
            extends=None,
            required_fields=[field_def],
            optional_fields=[],
            readonly_fields=[],
            relationships=[],
            validation_rules={},
            dgraph_type="Test",
            dgraph_predicates={},
        )

        model_class = factory.create_entity_model(schema)
        fields = model_class.model_fields
        assert fields["test"].annotation is str

        # Test integer type
        field_def.type = "integer"
        factory.clear_cache()  # Clear cache to force regeneration
        model_class = factory.create_entity_model(schema)
        fields = model_class.model_fields
        assert fields["test"].annotation is int

        # Test boolean type
        field_def.type = "boolean"
        factory.clear_cache()
        model_class = factory.create_entity_model(schema)
        fields = model_class.model_fields
        assert fields["test"].annotation is bool

        # Test datetime type
        field_def.type = "datetime"
        factory.clear_cache()
        model_class = factory.create_entity_model(schema)
        fields = model_class.model_fields
        assert fields["test"].annotation == datetime

    def test_array_type_handling(self, factory):
        """Test array type handling with items specification."""
        # Test array of strings
        field_def = FieldDefinition(
            name="tags",
            type="array",
            items="string",
            required=True,
            min_items=1,
            max_items=10,
        )
        schema = EntitySchema(
            entity_type="test",
            schema_version="1.0.0",
            description="Test",
            extends=None,
            required_fields=[field_def],
            optional_fields=[],
            readonly_fields=[],
            relationships=[],
            validation_rules={},
            dgraph_type="Test",
            dgraph_predicates={},
        )

        model_class = factory.create_entity_model(schema)
        fields = model_class.model_fields

        # Check it's a list type
        tags_field = fields["tags"]
        assert get_origin(tags_field.annotation) is list
        assert get_args(tags_field.annotation)[0] is str

        # Check constraints - they're in the metadata
        field_info = tags_field
        assert field_info.metadata is not None
        # Should have min/max length constraints
        constraint_types = [type(m).__name__ for m in field_info.metadata]
        assert "MinLen" in constraint_types
        assert "MaxLen" in constraint_types

    def test_validation_rules(self, factory, repository_schema):
        """Test validation rules are properly applied."""
        model_class = factory.create_entity_model(repository_schema)

        # Test valid data
        valid_data = {
            "owners": ["test@redhat.com", "team@redhat.com"],
            "git_repo_url": "https://github.com/test/repo",
        }
        instance = model_class.model_validate(valid_data)
        assert instance.owners == ["test@redhat.com", "team@redhat.com"]
        assert str(instance.git_repo_url) == "https://github.com/test/repo"

        # Test invalid email
        with pytest.raises(ValidationError) as exc_info:
            model_class.model_validate(
                {
                    "owners": ["not-an-email"],
                    "git_repo_url": "https://github.com/test/repo",
                }
            )
        assert "value is not a valid email address" in str(exc_info.value)

        # Test invalid URL
        with pytest.raises(ValidationError) as exc_info:
            model_class.model_validate(
                {
                    "owners": ["test@redhat.com"],
                    "git_repo_url": "not-a-url",
                }
            )
        assert "Input should be a valid URL" in str(exc_info.value)

    def test_dependency_validation(self, factory, repository_schema):
        """Test dependency reference validation."""
        # The repository schema already has a depends_on relationship defined
        # that should handle both external and internal dependencies
        model_class = factory.create_entity_model(repository_schema)

        # Test valid dependency references
        valid_data = {
            "owners": ["test@redhat.com"],
            "git_repo_url": "https://github.com/test/repo",
            "depends_on": [
                "external://pypi/requests/2.31.0",
                "external://npm/@types/node/18.15.0",
                "internal://shared-utils/logging-library",
            ],
        }
        instance = model_class.model_validate(valid_data)
        assert len(instance.depends_on) == 3

        # Test invalid dependency format
        with pytest.raises(ValidationError) as exc_info:
            model_class.model_validate(
                {
                    "owners": ["test@redhat.com"],
                    "git_repo_url": "https://github.com/test/repo",
                    "depends_on": ["invalid-dependency"],
                }
            )
        assert "Invalid dependency" in str(exc_info.value)

        # Test invalid external dependency (missing version)
        with pytest.raises(ValidationError) as exc_info:
            model_class.model_validate(
                {
                    "owners": ["test@redhat.com"],
                    "git_repo_url": "https://github.com/test/repo",
                    "depends_on": ["external://pypi/requests"],
                }
            )
        assert "Invalid dependency" in str(exc_info.value)

    def test_create_root_model(self, factory):
        """Test creating the root YAML validation model."""
        # Create test schemas
        schemas = {
            "repository": EntitySchema(
                entity_type="repository",
                schema_version="1.0.0",
                description="Repository entity",
                extends=None,
                required_fields=[
                    FieldDefinition(name="name", type="string", required=True),
                ],
                optional_fields=[],
                readonly_fields=[],
                relationships=[],
                validation_rules={},
                dgraph_type="Repository",
                dgraph_predicates={},
            ),
        }

        root_model = factory.create_root_model(schemas)

        # Check model structure
        assert root_model.__name__ == "KnowledgeGraphFile"
        fields = root_model.model_fields

        assert "schema_version" in fields
        assert "namespace" in fields
        assert "entity" in fields

        # Test valid root data
        valid_data = {
            "schema_version": "1.0.0",
            "namespace": "test-namespace",
            "entity": {"repository": [{"test-repo": {"name": "Test Repository"}}]},
        }
        instance = root_model.model_validate(valid_data)
        assert instance.schema_version == "1.0.0"
        assert instance.namespace == "test-namespace"

    def test_schema_version_validation(self, factory):
        """Test schema version validation."""
        schemas = {}
        root_model = factory.create_root_model(schemas)

        # Test valid schema version
        valid_data = {
            "schema_version": "1.0.0",
            "namespace": "test",
            "entity": {},
        }
        instance = root_model.model_validate(valid_data)
        assert instance.schema_version == "1.0.0"

        # Test invalid schema version formats
        invalid_versions = ["1.0", "v1.0.0", "1.0.0.0", "1.0.0-alpha"]
        for version in invalid_versions:
            with pytest.raises(ValidationError) as exc_info:
                root_model.model_validate(
                    {
                        "schema_version": version,
                        "namespace": "test",
                        "entity": {},
                    }
                )
            assert "String should match pattern" in str(exc_info.value)

    def test_namespace_validation(self, factory):
        """Test namespace validation."""
        schemas = {}
        root_model = factory.create_root_model(schemas)

        # Test valid namespaces
        valid_namespaces = ["a", "test", "test-namespace", "test_namespace", "test123"]
        for namespace in valid_namespaces:
            data = {
                "schema_version": "1.0.0",
                "namespace": namespace,
                "entity": {},
            }
            instance = root_model.model_validate(data)
            assert instance.namespace == namespace

        # Test invalid namespaces
        invalid_namespaces = [
            "Test",
            "test-",
            "-test",
            "test.namespace",
            "test space",
            "",
        ]
        for namespace in invalid_namespaces:
            with pytest.raises(ValidationError) as exc_info:
                root_model.model_validate(
                    {
                        "schema_version": "1.0.0",
                        "namespace": namespace,
                        "entity": {},
                    }
                )
            assert "String should match pattern" in str(exc_info.value)

    def test_model_caching(self, factory, basic_schema):
        """Test that models are cached to avoid recreation."""
        # Create model twice
        model1 = factory.create_entity_model(basic_schema)
        model2 = factory.create_entity_model(basic_schema)

        # Should be the same object due to caching
        assert model1 is model2

        # Clear cache and create again
        factory.clear_cache()
        model3 = factory.create_entity_model(basic_schema)

        # Should be different object after cache clear
        assert model1 is not model3
        assert model1.__name__ == model3.__name__

    def test_create_models_from_schemas(self, factory):
        """Test creating all models from a collection of schemas."""
        schemas = {
            "repository": EntitySchema(
                entity_type="repository",
                schema_version="1.0.0",
                description="Repository",
                extends=None,
                required_fields=[
                    FieldDefinition(name="name", type="string", required=True),
                ],
                optional_fields=[],
                readonly_fields=[],
                relationships=[],
                validation_rules={},
                dgraph_type="Repository",
                dgraph_predicates={},
            ),
            "service": EntitySchema(
                entity_type="service",
                schema_version="1.0.0",
                description="Service",
                extends=None,
                required_fields=[
                    FieldDefinition(name="name", type="string", required=True),
                ],
                optional_fields=[],
                readonly_fields=[],
                relationships=[],
                validation_rules={},
                dgraph_type="Service",
                dgraph_predicates={},
            ),
        }

        models = factory.create_models_from_schemas(schemas)

        # Check individual entity models
        assert "repository" in models
        assert "service" in models
        assert "_root" in models

        # Check models are proper Pydantic models
        assert issubclass(models["repository"], BaseModel)
        assert issubclass(models["service"], BaseModel)
        assert issubclass(models["_root"], BaseModel)

        # Check root model can validate data
        root_model = models["_root"]
        valid_data = {
            "schema_version": "1.0.0",
            "namespace": "test",
            "entity": {
                "repository": [{"test-repo": {"name": "Test"}}],
                "service": [{"test-service": {"name": "Service"}}],
            },
        }
        instance = root_model.model_validate(valid_data)
        assert instance.schema_version == "1.0.0"

    def test_strict_validation(self, factory, basic_schema):
        """Test that models reject unknown fields."""
        model_class = factory.create_entity_model(basic_schema)

        # Valid data should work
        valid_data = {"name": "test", "count": 42}
        instance = model_class.model_validate(valid_data)
        assert instance.name == "test"
        assert instance.count == 42

        # Unknown field should be rejected
        with pytest.raises(ValidationError) as exc_info:
            model_class.model_validate(
                {
                    "name": "test",
                    "count": 42,
                    "unknown_field": "value",
                }
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_unsupported_field_type(self, factory):
        """Test handling of unsupported field types."""
        schema = EntitySchema(
            entity_type="test",
            schema_version="1.0.0",
            description="Test",
            extends=None,
            required_fields=[
                FieldDefinition(
                    name="unsupported",
                    type="unsupported_type",
                    required=True,
                ),
            ],
            optional_fields=[],
            readonly_fields=[],
            relationships=[],
            validation_rules={},
            dgraph_type="Test",
            dgraph_predicates={},
        )

        with pytest.raises(ValueError) as exc_info:
            factory.create_entity_model(schema)
        assert "Unsupported field type: unsupported_type" in str(exc_info.value)
