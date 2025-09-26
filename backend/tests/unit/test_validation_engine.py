"""Comprehensive unit tests for the validation engine.

This module tests all components of the multi-layer validation engine,
including individual layers, error handling, and the complete validation
pipeline.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from kg.core import FileSchemaLoader
from kg.validation import (
    BusinessLogicValidator,
    FieldFormatValidator,
    KnowledgeGraphValidator,
    ReferenceValidator,
    SchemaStructureValidator,
    StorageInterface,
    ValidationError,
    ValidationResult,
    ValidationWarning,
    YamlSyntaxValidator,
)


class TestValidationErrors:
    """Test validation error data structures."""

    def test_validation_error_str_representation(self):
        """Test string representation of ValidationError."""
        error = ValidationError(
            type="test_error",
            message="Test message",
            field="test_field",
            entity="test_entity",
            line=10,
            column=5,
            help="Test help text",
        )

        str_repr = str(error)
        assert "test_error: Test message" in str_repr
        assert "(entity: test_entity)" in str_repr
        assert "(field: test_field)" in str_repr
        assert "(line 10, column 5)" in str_repr
        assert "Help: Test help text" in str_repr

    def test_validation_result_properties(self):
        """Test ValidationResult properties and methods."""
        errors = [ValidationError(type="error1", message="Message 1")]
        warnings = [ValidationWarning(type="warning1", message="Warning 1")]

        result = ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.has_critical_errors() is False

        # Test critical error detection
        critical_error = ValidationError(type="yaml_syntax_error", message="YAML error")
        result.add_error(critical_error)
        assert result.has_critical_errors() is True


class TestYamlSyntaxValidator:
    """Test YAML syntax validation layer."""

    def test_valid_yaml(self):
        """Test validation of valid YAML content."""
        validator = YamlSyntaxValidator()
        content = """
        key: value
        list:
          - item1
          - item2
        """

        is_valid, data, errors = validator.validate(content)

        assert is_valid is True
        assert data is not None
        assert len(errors) == 0
        assert data["key"] == "value"

    def test_invalid_yaml_syntax(self):
        """Test validation of invalid YAML syntax."""
        validator = YamlSyntaxValidator()
        content = """
        key: "unclosed quote
        invalid: yaml
        """

        is_valid, data, errors = validator.validate(content)

        assert is_valid is False
        assert data is None
        assert len(errors) == 1
        assert errors[0].type == "yaml_syntax_error"
        assert "Invalid YAML syntax" in errors[0].message

    def test_empty_yaml(self):
        """Test validation of empty YAML content."""
        validator = YamlSyntaxValidator()
        content = ""

        is_valid, data, errors = validator.validate(content)

        assert is_valid is False
        assert data is None
        assert len(errors) == 1
        assert errors[0].type == "empty_yaml_content"


class TestSchemaStructureValidator:
    """Test schema structure validation layer."""

    def test_valid_structure(self):
        """Test validation of valid schema structure."""
        validator = SchemaStructureValidator()
        data = {"schema_version": "1.0.0", "namespace": "test-namespace", "entity": {}}

        errors = validator.validate(data)
        assert len(errors) == 0

    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        validator = SchemaStructureValidator()
        data = {
            "schema_version": "1.0.0"
            # Missing namespace and entity
        }

        errors = validator.validate(data)
        assert len(errors) == 2

        error_types = [error.type for error in errors]
        assert "missing_required_field" in error_types

        missing_fields = [
            error.field for error in errors if error.type == "missing_required_field"
        ]
        assert "namespace" in missing_fields
        assert "entity" in missing_fields

    def test_unsupported_schema_version(self):
        """Test validation with unsupported schema version."""
        validator = SchemaStructureValidator()
        data = {
            "schema_version": "2.0.0",  # Unsupported
            "namespace": "test",
            "entity": {},
        }

        errors = validator.validate(data)
        assert len(errors) == 1
        assert errors[0].type == "unsupported_schema_version"
        assert "2.0.0" in errors[0].message

    def test_invalid_namespace_format(self):
        """Test validation with invalid namespace format."""
        validator = SchemaStructureValidator()
        data = {
            "schema_version": "1.0.0",
            "namespace": "Invalid-Namespace",  # Capital letters not allowed
            "entity": {},
        }

        errors = validator.validate(data)
        assert len(errors) == 1
        assert errors[0].type == "invalid_namespace_format"

    def test_invalid_field_types(self):
        """Test validation with invalid field types."""
        validator = SchemaStructureValidator()
        data = {
            "schema_version": 1.0,  # Should be string
            "namespace": 123,  # Should be string
            "entity": [],  # Should be dict
        }

        errors = validator.validate(data)
        assert len(errors) == 3

        error_types = [error.type for error in errors]
        assert error_types.count("invalid_field_type") == 3


class TestFieldFormatValidator:
    """Test field format validation layer."""

    @pytest_asyncio.fixture
    async def sample_schemas(self):
        """Load real entity schemas for testing."""
        schema_path = Path(__file__).parent.parent.parent.parent / "spec" / "schemas"
        loader = FileSchemaLoader(str(schema_path))
        schemas = await loader.load_schemas()
        return schemas

    @pytest.mark.asyncio
    async def test_unknown_entity_type(self, sample_schemas):
        """Test validation with unknown entity type."""
        validator = FieldFormatValidator(sample_schemas)
        data = {
            "schema_version": "1.0.0",
            "namespace": "test",
            "entity": {
                "unknown_type": []  # Not in schemas
            },
        }

        model, errors = validator.validate(data)
        assert model is None
        assert len(errors) == 1
        assert errors[0].type == "unknown_entity_type"
        assert "unknown_type" in errors[0].message

    @pytest.mark.asyncio
    async def test_invalid_entity_structure(self, sample_schemas):
        """Test validation with invalid entity structure."""
        validator = FieldFormatValidator(sample_schemas)
        data = {
            "schema_version": "1.0.0",
            "namespace": "test",
            "entity": {
                "repository": "not_a_list"  # Should be list
            },
        }

        model, errors = validator.validate(data)
        assert model is None
        assert len(errors) == 1
        assert errors[0].type == "invalid_field_type"


class TestBusinessLogicValidator:
    """Test business logic validation layer."""

    @pytest.fixture
    def sample_schemas(self):
        """Create sample entity schemas for testing."""
        return {"repository": Mock()}

    @pytest.fixture
    def sample_model(self):
        """Create a sample model for testing."""
        # Mock model structure
        repo_data = Mock()
        repo_data.depends_on = ["external://pypi/requests/2.31.0"]
        repo_data.owners = ["test@example.com"]  # Add proper owners field

        repo_dict = {"test-repo": repo_data}
        entity_container = Mock()
        entity_container.repository = [repo_dict]

        model = Mock()
        model.entity = entity_container
        model.namespace = "test"

        return model

    def test_valid_external_dependency(self, sample_schemas, sample_model):
        """Test validation of valid external dependency."""
        validator = BusinessLogicValidator(sample_schemas)
        errors = validator.validate(sample_model)

        # Should not have errors for valid external dependency
        dependency_errors = [e for e in errors if e.type.startswith("invalid_external")]
        assert len(dependency_errors) == 0

    def test_invalid_dependency_format(self, sample_schemas):
        """Test validation of invalid dependency format."""
        validator = BusinessLogicValidator(sample_schemas)

        # Create model with invalid dependency
        repo_data = Mock()
        repo_data.depends_on = ["invalid-format"]  # Missing protocol
        repo_data.owners = ["test@example.com"]  # Add proper owners field

        repo_dict = {"test-repo": repo_data}
        entity_container = Mock()
        entity_container.repository = [repo_dict]

        model = Mock()
        model.entity = entity_container

        errors = validator.validate(model)
        assert len(errors) > 0

        # Should have invalid dependency reference error
        dep_errors = [e for e in errors if e.type == "invalid_dependency_reference"]
        assert len(dep_errors) == 1
        assert "invalid-format" in dep_errors[0].message

    def test_unsupported_ecosystem(self, sample_schemas):
        """Test validation of unsupported ecosystem."""
        validator = BusinessLogicValidator(sample_schemas)

        # Create model with unsupported ecosystem
        repo_data = Mock()
        repo_data.depends_on = ["external://unsupported/package/1.0.0"]
        repo_data.owners = ["test@example.com"]  # Add proper owners field

        repo_dict = {"test-repo": repo_data}
        entity_container = Mock()
        entity_container.repository = [repo_dict]

        model = Mock()
        model.entity = entity_container

        errors = validator.validate(model)
        ecosystem_errors = [e for e in errors if e.type == "unsupported_ecosystem"]
        assert len(ecosystem_errors) == 1


class TestReferenceValidator:
    """Test reference validation layer."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage interface."""
        storage = Mock(spec=StorageInterface)
        return storage

    @pytest.fixture
    def sample_model(self):
        """Create sample model with internal references."""
        repo_data = Mock()
        repo_data.depends_on = ["internal://other-namespace/other-repo"]

        repo_dict = {"test-repo": repo_data}
        entity_container = Mock()
        entity_container.repository = [repo_dict]

        model = Mock()
        model.entity = entity_container

        return model

    @pytest.mark.asyncio
    async def test_reference_exists(self, mock_storage, sample_model):
        """Test validation when referenced entity exists."""
        mock_storage.entity_exists = AsyncMock(return_value=True)
        validator = ReferenceValidator(mock_storage)

        errors = await validator.validate(sample_model)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_reference_not_found(self, mock_storage, sample_model):
        """Test validation when referenced entity doesn't exist."""
        mock_storage.entity_exists = AsyncMock(return_value=False)
        validator = ReferenceValidator(mock_storage)

        errors = await validator.validate(sample_model)
        assert len(errors) == 1
        assert errors[0].type == "reference_not_found"

    @pytest.mark.asyncio
    async def test_no_storage_interface(self, sample_model):
        """Test validation without storage interface."""
        validator = ReferenceValidator(storage=None)

        errors = await validator.validate(sample_model)
        assert len(errors) == 0  # Should skip validation


class TestKnowledgeGraphValidator:
    """Test the main validation orchestrator."""

    @pytest_asyncio.fixture
    async def sample_schemas(self):
        """Load real entity schemas from spec directory."""
        schema_path = Path(__file__).parent.parent.parent.parent / "spec" / "schemas"
        loader = FileSchemaLoader(str(schema_path))
        schemas = await loader.load_schemas()
        return schemas

    @pytest.mark.asyncio
    async def test_valid_yaml_complete_pipeline(self, sample_schemas):
        """Test complete validation pipeline with valid YAML."""
        validator = KnowledgeGraphValidator(sample_schemas)

        yaml_content = """
        schema_version: "1.0.0"
        namespace: "test"
        entity:
          repository:
            - test-repo:
                owners: ["test@example.com"]
                git_repo_url: "https://github.com/test/repo"
        """

        result = await validator.validate(yaml_content)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.model is not None

    @pytest.mark.asyncio
    async def test_invalid_yaml_early_exit(self, sample_schemas):
        """Test early exit on YAML syntax error."""
        validator = KnowledgeGraphValidator(sample_schemas)

        yaml_content = """
        schema_version: "unclosed quote
        namespace: test
        """

        result = await validator.validate(yaml_content)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].type == "yaml_syntax_error"
        assert result.model is None

    @pytest.mark.asyncio
    async def test_missing_required_fields_early_exit(self, sample_schemas):
        """Test early exit on missing required fields."""
        validator = KnowledgeGraphValidator(sample_schemas)

        yaml_content = """
        schema_version: "1.0.0"
        # Missing namespace and entity
        """

        result = await validator.validate(yaml_content)

        assert result.is_valid is False
        assert any(e.type == "missing_required_field" for e in result.errors)
        assert result.model is None

    @pytest.mark.asyncio
    async def test_unsupported_version_early_exit(self, sample_schemas):
        """Test early exit on unsupported schema version."""
        validator = KnowledgeGraphValidator(sample_schemas)

        yaml_content = """
        schema_version: "2.0.0"
        namespace: "test"
        entity: {}
        """

        result = await validator.validate(yaml_content)

        assert result.is_valid is False
        assert any(e.type == "unsupported_schema_version" for e in result.errors)
        assert result.model is None

    def test_synchronous_validation(self, sample_schemas):
        """Test synchronous validation method."""
        validator = KnowledgeGraphValidator(sample_schemas)

        yaml_content = """
        schema_version: "1.0.0"
        namespace: "test"
        entity:
          repository: []
        """

        result = validator.validate_sync(yaml_content)

        assert result.is_valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_validator_info(self, sample_schemas):
        """Test validator information method."""
        validator = KnowledgeGraphValidator(sample_schemas)
        info = validator.get_validator_info()

        assert "entity_schemas" in info
        assert "repository" in info["entity_schemas"]
        assert (
            info["schema_count"] == 3
        )  # Real schemas: repository, external_dependency_package, external_dependency_version
        assert info["strict_mode"] is True
        assert info["has_storage"] is False


class TestIntegrationScenarios:
    """Test realistic validation scenarios."""

    @pytest_asyncio.fixture
    async def complete_schemas(self):
        """Load complete entity schemas for realistic testing."""
        schema_path = Path(__file__).parent.parent.parent.parent / "spec" / "schemas"
        loader = FileSchemaLoader(str(schema_path))
        schemas = await loader.load_schemas()
        return schemas

    @pytest.mark.asyncio
    async def test_realistic_valid_scenario(self, complete_schemas):
        """Test realistic valid knowledge graph file."""
        validator = KnowledgeGraphValidator(complete_schemas)

        yaml_content = """
        schema_version: "1.0.0"
        namespace: "red-hat-insights"
        entity:
          repository:
            - insights-api:
                owners: ["team@redhat.com"]
                git_repo_url: "https://github.com/RedHatInsights/insights-api"
            - insights-frontend:
                owners: ["frontend-team@redhat.com"]
                git_repo_url: "https://github.com/RedHatInsights/insights-frontend"
        """

        result = await validator.validate(yaml_content)

        # Should be valid but may have warnings about multiple domains
        assert len(result.errors) == 0  # No errors
        # May have warnings about multiple email domains

    @pytest.mark.asyncio
    async def test_realistic_invalid_scenario(self, complete_schemas):
        """Test realistic invalid knowledge graph file with multiple errors."""
        validator = KnowledgeGraphValidator(complete_schemas)

        yaml_content = """
        schema_version: "1.5.0"  # Unsupported version
        namespace: "Invalid_Namespace"  # Invalid format
        entity:
          repository:
            - insights-api:
                owners: []  # Empty required field
                git_repo_url: "https://github.com/test/repo"
          unknown_entity:  # Unknown entity type
            - test: {}
        """

        result = await validator.validate(yaml_content)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Should have early exit on unsupported version
        assert any(e.type == "unsupported_schema_version" for e in result.errors)

    @pytest.mark.asyncio
    async def test_error_message_quality(self, complete_schemas):
        """Test that error messages are helpful and actionable."""
        validator = KnowledgeGraphValidator(complete_schemas)

        yaml_content = """
        schema_version: "2.0.0"
        namespace: "test"
        entity: {}
        """

        result = validator.validate_sync(yaml_content)

        assert result.is_valid is False
        error = result.errors[0]

        # Error should have helpful information
        assert error.type == "unsupported_schema_version"
        assert "2.0.0" in error.message
        assert error.help is not None
        assert "1.0.0" in error.help  # Should mention supported version
