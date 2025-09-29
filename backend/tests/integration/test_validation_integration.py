"""Integration tests for the validation engine with real schema files.

This module tests the complete validation pipeline using actual schema
files and realistic YAML content, demonstrating the validation engine
in action.
"""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from kg.core import FileSchemaLoader
from kg.validation import KnowledgeGraphValidator


class TestValidationIntegration:
    """Integration tests using real schema files."""

    @pytest_asyncio.fixture
    async def loaded_schemas(self):
        """Load actual schemas from the spec directory."""
        schema_path = Path(__file__).parent.parent.parent / "schemas"
        loader = FileSchemaLoader(str(schema_path))

        schemas = await loader.load_schemas()
        return schemas

    @pytest.mark.asyncio
    async def test_valid_repository_yaml(self, loaded_schemas):
        """Test validation of a valid repository YAML file."""
        validator = KnowledgeGraphValidator(loaded_schemas)

        valid_yaml = """
        schema_version: "1.0.0"
        namespace: "red-hat-insights"
        entity:
          repository:
            - insights-api:
                owners: ["api-team@redhat.com"]
                git_repo_url: "https://github.com/RedHatInsights/insights-api"

            - insights-frontend:
                owners: ["frontend-team@redhat.com"]
                git_repo_url: "https://github.com/RedHatInsights/insights-frontend"
        """

        result = await validator.validate(valid_yaml)

        print("\\n=== Validation Result ===")
        print(f"Valid: {result.is_valid}")
        print(f"Errors: {result.error_count}")
        print(f"Warnings: {result.warning_count}")

        if result.errors:
            print("\\nErrors:")
            for error in result.errors:
                print(f"  - {error}")

        if result.warnings:
            print("\\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

        # Should be valid (may have warnings about multiple domains)
        assert result.error_count == 0
        assert result.model is not None

    @pytest.mark.asyncio
    async def test_multiple_validation_errors(self, loaded_schemas):
        """Test validation of YAML with multiple types of errors."""
        validator = KnowledgeGraphValidator(loaded_schemas)

        invalid_yaml = """
        schema_version: "2.0.0"  # Unsupported version
        namespace: "Invalid_Namespace"  # Invalid format - capitals not allowed
        entity:
          repository:
            - test-repo:
                owners: []  # Empty array - should have at least one owner
                git_repo_url: "not-a-valid-url"  # Invalid URL format

          unknown_entity_type:  # This entity type doesn't exist in schemas
            - test-entity:
                field: "value"
        """

        result = await validator.validate(invalid_yaml)

        print("\\n=== Multiple Errors Test ===")
        print(f"Valid: {result.is_valid}")
        print(f"Errors: {result.error_count}")
        print(f"Warnings: {result.warning_count}")

        print("\\nErrors found:")
        for error in result.errors:
            print(f"  - {error.type}: {error.message}")
            if error.help:
                print(f"    Help: {error.help}")

        # Should have multiple errors but early exit on unsupported version
        assert result.is_valid is False
        assert result.error_count > 0

        # Check that we get the expected critical error
        error_types = [error.type for error in result.errors]
        assert "unsupported_schema_version" in error_types

    @pytest.mark.asyncio
    async def test_yaml_syntax_error(self, loaded_schemas):
        """Test validation with YAML syntax errors."""
        validator = KnowledgeGraphValidator(loaded_schemas)

        invalid_yaml = """
        schema_version: "1.0.0"
        namespace: "test"
        entity:
          repository:
            - test-repo:
                owners: ["test@example.com"  # Missing closing bracket
                git_repo_url: "https://github.com/test/repo"
        """

        result = await validator.validate(invalid_yaml)

        print("\\n=== YAML Syntax Error Test ===")
        print(f"Valid: {result.is_valid}")
        print(f"Errors: {result.error_count}")

        if result.errors:
            error = result.errors[0]
            print(f"Error Type: {error.type}")
            print(f"Message: {error.message}")
            print(f"Line: {error.line}")
            print(f"Column: {error.column}")
            print(f"Help: {error.help}")

        assert result.is_valid is False
        assert result.error_count == 1
        assert result.errors[0].type == "yaml_syntax_error"
        # Should have line/column information
        assert result.errors[0].line is not None

    @pytest.mark.asyncio
    async def test_business_logic_validation(self, loaded_schemas):
        """Test business logic validation with dependency references."""
        validator = KnowledgeGraphValidator(loaded_schemas)

        yaml_with_dependencies = """
        schema_version: "1.0.0"
        namespace: "test-project"
        entity:
          repository:
            - api-service:
                owners: ["api-team@company.com"]
                git_repo_url: "https://github.com/company/api-service"

            - frontend-app:
                owners: ["frontend-team@company.com"]
                git_repo_url: "https://github.com/company/frontend"

            - shared-library:
                owners: ["platform-team@company.com"]
                git_repo_url: "https://github.com/company/shared"
        """

        result = await validator.validate(yaml_with_dependencies)

        print("\\n=== Business Logic Validation Test ===")
        print(f"Valid: {result.is_valid}")
        print(f"Errors: {result.error_count}")
        print(f"Warnings: {result.warning_count}")

        if result.errors:
            print("\\nErrors:")
            for error in result.errors:
                print(f"  - {error}")

        if result.warnings:
            print("\\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

        # Should be valid - all dependencies are properly formatted
        assert result.error_count == 0
        assert result.model is not None

    def test_synchronous_validation(self, loaded_schemas):
        """Test synchronous validation method."""
        validator = KnowledgeGraphValidator(loaded_schemas)

        simple_yaml = """
        schema_version: "1.0.0"
        namespace: "simple-test"
        entity:
          repository:
            - simple-repo:
                owners: ["dev@company.com"]
                git_repo_url: "https://github.com/company/simple"
        """

        result = validator.validate_sync(simple_yaml)

        print("\\n=== Synchronous Validation Test ===")
        print(f"Valid: {result.is_valid}")
        print(f"Errors: {result.error_count}")
        print(f"Model: {result.model is not None}")

        assert result.is_valid is True
        assert result.error_count == 0
        assert result.model is not None

    @pytest.mark.asyncio
    async def test_validator_configuration_info(self, loaded_schemas):
        """Test validator information and configuration."""
        validator = KnowledgeGraphValidator(loaded_schemas)
        info = validator.get_validator_info()

        print("\\n=== Validator Configuration ===")
        print(f"Entity Schemas: {info['entity_schemas']}")
        print(f"Schema Count: {info['schema_count']}")
        print(f"Strict Mode: {info['strict_mode']}")
        print(f"Has Storage: {info['has_storage']}")
        print(f"Supported Versions: {info['supported_versions']}")

        assert "repository" in info["entity_schemas"]
        assert info["schema_count"] > 0
        assert info["strict_mode"] is True
        assert info["has_storage"] is False
        assert "1.0.0" in info["supported_versions"]


class TestErrorMessageQuality:
    """Test the quality and helpfulness of error messages."""

    @pytest_asyncio.fixture
    async def validator(self):
        """Create validator with real schemas."""
        schema_path = Path(__file__).parent.parent.parent / "schemas"
        loader = FileSchemaLoader(str(schema_path))
        schemas = await loader.load_schemas()
        return KnowledgeGraphValidator(schemas)

    @pytest.mark.asyncio
    async def test_helpful_error_messages(self, validator):
        """Test that error messages provide helpful guidance."""
        yaml_with_errors = """
        schema_version: "2.0.0"
        namespace: "test"
        entity: {}
        """

        result = validator.validate_sync(yaml_with_errors)

        assert result.is_valid is False
        error = result.errors[0]

        # Error message should be specific
        assert "2.0.0" in error.message
        assert error.field == "schema_version"
        assert error.type == "unsupported_schema_version"

        # Help text should be actionable
        assert error.help is not None
        assert "1.0.0" in error.help

    @pytest.mark.asyncio
    async def test_error_context_information(self, validator):
        """Test that errors include proper context information."""
        yaml_with_context_error = """
        schema_version: "1.0.0"
        namespace: "test"
        entity:
          unknown_type:
            - test: {}
        """

        result = validator.validate_sync(yaml_with_context_error)

        assert result.is_valid is False

        # Find the unknown entity type error
        unknown_type_errors = [
            e for e in result.errors if e.type == "unknown_entity_type"
        ]
        assert len(unknown_type_errors) == 1

        error = unknown_type_errors[0]
        assert "unknown_type" in error.message
        assert error.field == "entity"


def demonstrate_validation_engine():
    """Demonstration function showing the validation engine in action."""

    async def run_demo():
        # Load real schemas
        schema_path = Path(__file__).parent.parent.parent / "schemas"
        loader = FileSchemaLoader(str(schema_path))
        result = await loader.load_schemas()
        schemas = result.schemas

        # Create validator
        validator = KnowledgeGraphValidator(schemas)

        print("=" * 60)
        print("KNOWLEDGE GRAPH VALIDATION ENGINE DEMONSTRATION")
        print("=" * 60)

        # Example 1: Valid YAML
        print("\\n1. VALID YAML EXAMPLE:")
        print("-" * 30)

        valid_yaml = """
schema_version: "1.0.0"
namespace: "demo-project"
entity:
  repository:
    - web-api:
        owners: ["backend-team@company.com"]
        git_repo_url: "https://github.com/company/web-api"

    - mobile-app:
        owners: ["mobile-team@company.com"]
        git_repo_url: "https://github.com/company/mobile-app"
        """

        result = await validator.validate(valid_yaml)
        print(f"✅ Valid: {result.is_valid}")
        print(f"📊 Errors: {result.error_count}, Warnings: {result.warning_count}")

        if result.warnings:
            for warning in result.warnings:
                print(f"⚠️  {warning}")

        # Example 2: Multiple Errors
        print("\\n\\n2. MULTIPLE ERRORS EXAMPLE:")
        print("-" * 30)

        invalid_yaml = """
schema_version: "2.0.0"
namespace: "Invalid_Name"
entity:
  repository:
    - bad-repo:
        owners: []
        git_repo_url: "not-a-url"
  unknown_entity:
    - test: {}
        """

        result = await validator.validate(invalid_yaml)
        print(f"❌ Valid: {result.is_valid}")
        print(f"📊 Errors: {result.error_count}, Warnings: {result.warning_count}")

        print("\\nErrors found:")
        for error in result.errors:
            print(f"  🔴 {error.type}: {error.message}")
            if error.help:
                print(f"     💡 {error.help}")

        # Example 3: YAML Syntax Error
        print("\\n\\n3. YAML SYNTAX ERROR EXAMPLE:")
        print("-" * 30)

        syntax_error_yaml = """
schema_version: "1.0.0"
namespace: "test"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com"  # Missing closing bracket
        """

        result = await validator.validate(syntax_error_yaml)
        print(f"❌ Valid: {result.is_valid}")

        if result.errors:
            error = result.errors[0]
            print(f"🔴 {error.type}: {error.message}")
            print(f"📍 Location: Line {error.line}, Column {error.column}")
            print(f"💡 {error.help}")

        print("\\n" + "=" * 60)
        print("DEMONSTRATION COMPLETE")
        print("=" * 60)

    # Run the demonstration
    asyncio.run(run_demo())


if __name__ == "__main__":
    demonstrate_validation_engine()
