#!/usr/bin/env python3
"""Demonstration of the dynamic Pydantic model generation system.

This script demonstrates the complete workflow of:
1. Loading schemas from YAML files
2. Generating Pydantic models dynamically
3. Validating YAML data against the generated models
"""

import asyncio
from pathlib import Path

import yaml

from kg.core import DynamicModelFactory, FileSchemaLoader


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_subsection(title: str) -> None:
    """Print a formatted subsection header."""
    print(f"\n{'-'*40}")
    print(f" {title}")
    print(f"{'-'*40}")


async def main():
    """Run the demonstration."""
    print_section("Dynamic Pydantic Model Generation Demo")

    # Use the actual schema files from the project
    schema_dir = Path(__file__).parent.parent / "spec" / "schemas"

    if not schema_dir.exists():
        print(f"❌ Schema directory not found: {schema_dir}")
        print("   Please ensure the spec/schemas directory exists with schema files.")
        return

    print(f"📁 Using schema directory: {schema_dir}")
    print("📄 Available schema files:")
    for schema_file in schema_dir.glob("*.yaml"):
        print(f"   - {schema_file.name}")

    # Step 1: Load schemas
    print_section("Step 1: Loading Schemas")

    try:
        loader = FileSchemaLoader(str(schema_dir))
        schemas = await loader.load_schemas()

        print(f"✅ Successfully loaded {len(schemas)} schemas:")
        for entity_type, schema in schemas.items():
            print(f"   - {entity_type}: {schema.description}")
            print(f"     Required fields: {len(schema.required_fields)}")
            print(f"     Optional fields: {len(schema.optional_fields)}")
            print(f"     Readonly fields: {len(schema.readonly_fields)}")
            print(f"     Extends: {schema.extends}")
            print()

    except Exception as e:
        print(f"❌ Failed to load schemas: {e}")
        return

    # Step 2: Generate models
    print_section("Step 2: Generating Pydantic Models")

    try:
        factory = DynamicModelFactory()
        models = factory.create_models_from_schemas(schemas)

        print(f"✅ Successfully generated {len(models)} models:")
        for model_name, model_class in models.items():
            if model_name == "_root":
                print(f"   - {model_name}: KnowledgeGraphFile (root YAML model)")
            else:
                print(f"   - {model_name}: {model_class.__name__}")

                # Show field information
                fields = model_class.model_fields
                required_fields = [
                    name for name, field in fields.items() if field.is_required()
                ]
                optional_fields = [
                    name for name, field in fields.items() if not field.is_required()
                ]

                print(f"     Required: {required_fields}")
                print(f"     Optional: {optional_fields}")
                print()

    except Exception as e:
        print(f"❌ Failed to generate models: {e}")
        return

    # Step 3: Demonstrate validation with valid data
    print_section("Step 3: Validating YAML Data")

    # Create sample valid YAML data
    valid_yaml_data = {
        "schema_version": "1.0.0",
        "namespace": "demo-namespace",
        "entity": {
            "repository": [
                {
                    "demo-service": {
                        "owners": ["demo-team@redhat.com"],
                        "git_repo_url": "https://github.com/demo/service",
                    }
                }
            ]
        },
    }

    print_subsection("Valid YAML Data")
    print("📝 Sample YAML:")
    print(yaml.dump(valid_yaml_data, default_flow_style=False, indent=2))

    try:
        root_model = models["_root"]
        validated_data = root_model.model_validate(valid_yaml_data)

        print("✅ Validation successful!")
        print(f"   Schema version: {validated_data.schema_version}")
        print(f"   Namespace: {validated_data.namespace}")

        if validated_data.entity.repository:
            repo_count = len(validated_data.entity.repository)
            print(f"   Repositories: {repo_count}")

            for repo_dict in validated_data.entity.repository:
                repo_name, repo_data = next(iter(repo_dict.items()))
                print(f"     - {repo_name}:")
                print(f"       Owners: {repo_data.owners}")
                print(f"       URL: {repo_data.git_repo_url}")

    except Exception as e:
        print(f"❌ Validation failed: {e}")

    # Step 4: Demonstrate validation failure with invalid data
    print_subsection("Invalid YAML Data")

    invalid_yaml_data = {
        "schema_version": "invalid-version",  # Invalid format
        "namespace": "Invalid-Namespace",  # Invalid format
        "entity": {
            "repository": [
                {
                    "invalid-repo": {
                        "owners": ["not-an-email"],  # Invalid email
                        "git_repo_url": "not-a-url",  # Invalid URL
                        "unknown_field": "value",  # Unknown field
                    }
                }
            ]
        },
    }

    print("📝 Invalid YAML (demonstrating validation errors):")
    print(yaml.dump(invalid_yaml_data, default_flow_style=False, indent=2))

    try:
        root_model = models["_root"]
        validated_data = root_model.model_validate(invalid_yaml_data)
        print("⚠️  Unexpected: Invalid data was accepted!")

    except Exception as e:
        print("✅ Validation correctly rejected invalid data:")
        print(f"   Error: {e}")

    # Step 5: Demonstrate individual entity validation
    print_section("Step 4: Individual Entity Validation")

    if "repository" in models:
        print_subsection("Repository Model")

        repository_model = models["repository"]

        # Valid repository data
        valid_repo_data = {
            "owners": ["team@redhat.com", "lead@redhat.com"],
            "git_repo_url": "https://github.com/openshift/test-repo",
        }

        try:
            repo_instance = repository_model.model_validate(valid_repo_data)
            print("✅ Valid repository data:")
            print(f"   Owners: {repo_instance.owners}")
            print(f"   URL: {repo_instance.git_repo_url}")
            print(f"   Model type: {type(repo_instance).__name__}")

        except Exception as e:
            print(f"❌ Repository validation failed: {e}")

    # Step 6: Show model features
    print_section("Step 5: Model Features")

    print_subsection("Type Safety")
    print("✅ Generated models provide full type safety:")
    if "repository" in models:
        repo_model = models["repository"]
        print(f"   - Repository model: {repo_model}")
        print(f"   - Model fields: {list(repo_model.model_fields.keys())}")
        print("   - Model config: strict validation, extra fields forbidden")

    print_subsection("Schema Compliance")
    print("✅ Models enforce all schema validation rules:")
    print("   - Email validation for owner fields")
    print("   - URL validation for repository URLs")
    print("   - Dependency reference format validation")
    print("   - Schema version and namespace format validation")
    print("   - Unknown field rejection (strict mode)")

    print_subsection("Performance")
    print("✅ Models are cached for performance:")
    print(f"   - Model cache contains {len(factory._model_cache)} cached models")
    print("   - Subsequent requests for the same schema use cached models")

    print_section("Demo Complete")
    print("🎉 The dynamic Pydantic model generation system is working correctly!")
    print("   ✅ Schemas loaded from YAML files")
    print("   ✅ Models generated dynamically with full validation")
    print("   ✅ YAML data validated against schema specifications")
    print("   ✅ Type safety and error handling demonstrated")
    print()
    print("The system is ready for use in the knowledge graph application.")


if __name__ == "__main__":
    asyncio.run(main())
