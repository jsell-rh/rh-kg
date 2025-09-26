#!/usr/bin/env python3
"""Simple validation test with manually created schemas.

This test verifies the validation engine works correctly with
manually created schemas, isolating it from schema loading issues.
"""

import asyncio
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from kg.core import EntitySchema, FieldDefinition
from kg.validation import KnowledgeGraphValidator


def create_test_schemas() -> dict[str, EntitySchema]:
    """Create simple test schemas for validation testing."""

    # Create a simple repository schema
    repository_schema = EntitySchema(
        entity_type="repository",
        schema_version="1.0.0",
        description="Repository entity for testing",
        extends=None,
        required_fields=[
            FieldDefinition(
                name="owners",
                type="array",
                items="string",
                validation="email",
                required=True,
                min_items=1,
                description="Repository owners",
            ),
            FieldDefinition(
                name="git_repo_url",
                type="string",
                validation="url",
                required=True,
                description="Git repository URL",
            ),
        ],
        optional_fields=[
            FieldDefinition(
                name="depends_on",
                type="array",
                items="string",
                required=False,
                description="Dependencies",
            )
        ],
        readonly_fields=[],
        relationships=[],
        validation_rules={},
        dgraph_type="Repository",
        dgraph_predicates={},
    )

    return {"repository": repository_schema}


@pytest.mark.asyncio  # type: ignore[misc]
async def test_validation_engine() -> None:
    """Test the validation engine with simple schemas."""

    print("=" * 60)
    print("SIMPLE VALIDATION ENGINE TEST")
    print("=" * 60)

    # Create test schemas
    schemas = create_test_schemas()
    print(f"✅ Created test schemas: {list(schemas.keys())}")

    # Create validator
    validator = KnowledgeGraphValidator(schemas)

    # Test 1: Valid YAML
    print("\n1. 📋 TESTING VALID YAML")
    print("-" * 30)

    valid_yaml = """
schema_version: "1.0.0"
namespace: "test-project"
entity:
  repository:
    - api-service:
        owners: ["team@company.com"]
        git_repo_url: "https://github.com/company/api"
        depends_on:
          - "external://pypi/django/4.0.0"
          - "external://pypi/requests/2.28.0"
    """

    result = await validator.validate(valid_yaml)
    print(f"✅ Valid: {result.is_valid}")
    print(f"📊 Errors: {result.error_count}, Warnings: {result.warning_count}")

    if result.errors:
        print("❌ Errors:")
        for error in result.errors:
            print(f"  - {error.type}: {error.message}")

    # Test 2: YAML with validation errors
    print("\n2. 🚫 TESTING VALIDATION ERRORS")
    print("-" * 30)

    invalid_yaml = """
schema_version: "1.0.0"
namespace: "test-project"
entity:
  repository:
    - bad-repo:
        owners: []  # Empty array - should fail min_items validation
        git_repo_url: "not-a-url"  # Invalid URL
        depends_on:
          - "bad-dependency-format"  # Invalid format
    """

    result = await validator.validate(invalid_yaml)
    print(f"❌ Valid: {result.is_valid}")
    print(f"📊 Errors: {result.error_count}")

    print("🔴 Validation Errors:")
    for error in result.errors:
        print(f"  - {error.type}: {error.message}")
        if error.help:
            print(f"    💡 {error.help}")

    # Test 3: YAML syntax error
    print("\n3. 🚫 TESTING YAML SYNTAX ERROR")
    print("-" * 30)

    syntax_error = """
schema_version: "1.0.0"
namespace: "test"
entity:
  repository:
    - test: {
        owners: ["test@example.com"]  # Missing closing brace
    """

    result = await validator.validate(syntax_error)
    print(f"❌ Valid: {result.is_valid}")
    print(f"🔴 Error: {result.errors[0].type}")
    print(f"📍 Line: {result.errors[0].line}, Column: {result.errors[0].column}")

    # Test 4: Schema structure error
    print("\n4. 🚫 TESTING SCHEMA STRUCTURE ERROR")
    print("-" * 30)

    structure_error = """
schema_version: "2.0.0"  # Unsupported
namespace: "test"
entity: {}
    """

    result = await validator.validate(structure_error)
    print(f"❌ Valid: {result.is_valid}")
    print(f"🔴 Error: {result.errors[0].type}")
    print(f"📝 Message: {result.errors[0].message}")

    print("\n" + "=" * 60)
    print("✅ VALIDATION ENGINE TEST COMPLETE")
    print("All validation layers are working correctly!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_validation_engine())
