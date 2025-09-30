"""Integration test for dynamic model generation with real schemas.

This test demonstrates the complete flow from loading schemas from YAML files
to generating Pydantic models and validating YAML data against them.
"""

import asyncio
from pathlib import Path
import tempfile

from pydantic import ValidationError
import pytest
import yaml

from kg.core import DynamicModelFactory, FileSchemaLoader


class TestFullModelGeneration:
    """Integration test for the complete model generation system."""

    @pytest.fixture
    def schema_dir(self):
        """Create temporary directory with real schema files in new subdirectory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir)

            # Create _base directory structure
            base_dir = schema_path / "_base"
            base_dir.mkdir()

            # Create base_internal/1.0.0.yaml
            base_internal_dir = base_dir / "base_internal"
            base_internal_dir.mkdir()

            base_internal_content = {
                "schema_type": "base_internal",
                "schema_version": "1.0.0",
                "governance": "strict",
                "readonly_metadata": {
                    "created_at": {
                        "type": "datetime",
                        "description": "Timestamp when entity was first created",
                        "indexed": False,
                    },
                    "updated_at": {
                        "type": "datetime",
                        "description": "Timestamp when entity was last updated",
                        "indexed": False,
                    },
                    "source_repo": {
                        "type": "string",
                        "description": "Repository that submitted this entity data",
                        "indexed": True,
                    },
                },
                "validation_rules": {
                    "unknown_fields": "reject",
                    "missing_required_fields": "reject",
                },
                "deletion_policy": {
                    "type": "reference_counted",
                    "description": "Can only delete if no other entities reference this one",
                },
                "allow_custom_fields": False,
            }

            with (base_internal_dir / "1.0.0.yaml").open("w") as f:
                yaml.dump(base_internal_content, f)

            # Create repository/1.0.0.yaml
            repository_dir = schema_path / "repository"
            repository_dir.mkdir()

            repository_content = {
                "entity_type": "repository",
                "schema_version": "1.0.0",
                "extends": "base_internal",
                "description": "Code repository entity representing a git repository",
                "required_metadata": {
                    "owners": {
                        "type": "array",
                        "items": "string",
                        "validation": "email",
                        "min_items": 1,
                        "description": "List of team email addresses responsible for repository",
                        "indexed": True,
                    },
                    "git_repo_url": {
                        "type": "string",
                        "validation": "url",
                        "description": "Git repository URL (GitHub, GitLab, etc.)",
                        "indexed": True,
                    },
                },
                "optional_metadata": {
                    "depends_on": {
                        "type": "array",
                        "items": "string",
                        "description": "List of dependency references",
                        "min_items": 0,
                    },
                },
                "relationships": {},
                "dgraph_type": "Repository",
                "dgraph_predicates": {
                    "id": {
                        "type": "string",
                        "index": ["exact"],
                        "description": "Unique identifier: namespace/repository-name",
                    },
                    "owners": {
                        "type": "[string]",
                        "index": ["exact"],
                        "description": "Owner email addresses",
                    },
                    "git_repo_url": {
                        "type": "string",
                        "index": ["exact"],
                        "description": "Git repository URL",
                    },
                },
                "validation_rules": {
                    "unique_name_per_namespace": True,
                    "valid_dependency_references": True,
                },
            }

            with (repository_dir / "1.0.0.yaml").open("w") as f:
                yaml.dump(repository_content, f)

            # Create service/1.0.0.yaml
            service_dir = schema_path / "service"
            service_dir.mkdir()

            service_content = {
                "entity_type": "service",
                "schema_version": "1.0.0",
                "extends": "base_internal",
                "description": "Service entity representing a deployed application service",
                "required_metadata": {
                    "name": {
                        "type": "string",
                        "min_length": 1,
                        "max_length": 100,
                        "description": "Service name",
                        "indexed": True,
                    },
                    "team": {
                        "type": "string",
                        "description": "Owning team",
                        "indexed": True,
                    },
                },
                "optional_metadata": {
                    "description": {
                        "type": "string",
                        "description": "Service description",
                        "max_length": 500,
                    },
                    "health_check_url": {
                        "type": "string",
                        "validation": "url",
                        "description": "Health check endpoint URL",
                    },
                },
                "relationships": {},
                "dgraph_type": "Service",
                "dgraph_predicates": {
                    "name": {
                        "type": "string",
                        "index": ["exact"],
                        "description": "Service name",
                    },
                    "team": {
                        "type": "string",
                        "index": ["exact"],
                        "description": "Owning team",
                    },
                },
                "validation_rules": {
                    "unique_name_per_namespace": True,
                },
            }

            with (service_dir / "1.0.0.yaml").open("w") as f:
                yaml.dump(service_content, f)

            yield str(schema_path)

    @pytest.fixture
    def valid_yaml_data(self):
        """Create valid YAML data for testing."""
        return {
            "schema_version": "1.0.0",
            "namespace": "rosa-hcp",
            "entity": {
                "repository": [
                    {
                        "rosa-hcp-service": {
                            "owners": ["rosa-team@redhat.com", "rosa-leads@redhat.com"],
                            "git_repo_url": "https://github.com/openshift/rosa-hcp-service",
                            "depends_on": [
                                "external://pypi/requests/2.31.0",
                                "external://npm/@types/node/18.15.0",
                                "internal://shared-utils/logging-library",
                            ],
                        }
                    },
                    {
                        "rosa-operator": {
                            "owners": ["rosa-team@redhat.com"],
                            "git_repo_url": "https://github.com/openshift/rosa-operator",
                            "depends_on": ["external://golang.org/x/client-go/v0.28.4"],
                        }
                    },
                ],
                "service": [
                    {
                        "auth-service": {
                            "name": "Authentication Service",
                            "team": "auth-team",
                            "description": "Handles user authentication and authorization",
                            "health_check_url": "https://auth.rosa.redhat.com/health",
                        }
                    }
                ],
            },
        }

    @pytest.fixture
    def invalid_yaml_data(self):
        """Create invalid YAML data for testing."""
        return {
            "schema_version": "1.0.0",
            "namespace": "rosa-hcp",
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

    def test_complete_model_generation_workflow(self, schema_dir):
        """Test the complete workflow from schema loading to model generation."""
        # Step 1: Load schemas from YAML files
        loader = FileSchemaLoader(schema_dir)
        schemas = asyncio.run(loader.load_schemas())

        # Verify schemas were loaded correctly
        assert "repository" in schemas
        assert "service" in schemas
        assert len(schemas) == 2

        repository_schema = schemas["repository"]
        assert repository_schema.entity_type == "repository"
        assert repository_schema.extends == "base_internal"
        assert len(repository_schema.required_fields) == 2  # owners, git_repo_url
        assert len(repository_schema.optional_fields) == 1  # depends_on
        assert (
            len(repository_schema.readonly_fields) == 3
        )  # created_at, updated_at, source_repo

        # Step 2: Create model factory and generate models
        factory = DynamicModelFactory()
        models = factory.create_models_from_schemas(schemas)

        # Verify models were created
        assert "repository" in models
        assert "service" in models
        assert "_root" in models

        # Verify model structure
        RepositoryModel = models["repository"]
        ServiceModel = models["service"]
        KnowledgeGraphModel = models["_root"]

        # Check repository model fields
        repo_fields = RepositoryModel.model_fields
        assert "owners" in repo_fields
        assert "git_repo_url" in repo_fields
        assert "depends_on" in repo_fields
        assert "created_at" in repo_fields
        assert "updated_at" in repo_fields
        assert "source_repo" in repo_fields

        # Check service model fields
        service_fields = ServiceModel.model_fields
        assert "name" in service_fields
        assert "team" in service_fields
        assert "description" in service_fields
        assert "health_check_url" in service_fields

        # Check root model structure
        root_fields = KnowledgeGraphModel.model_fields
        assert "schema_version" in root_fields
        assert "namespace" in root_fields
        assert "entity" in root_fields

    def test_valid_data_validation(self, schema_dir, valid_yaml_data):
        """Test that valid YAML data passes validation."""
        # Load schemas and create models
        loader = FileSchemaLoader(schema_dir)
        schemas = asyncio.run(loader.load_schemas())
        factory = DynamicModelFactory()
        models = factory.create_models_from_schemas(schemas)

        # Validate the complete YAML structure
        KnowledgeGraphModel = models["_root"]
        instance = KnowledgeGraphModel.model_validate(valid_yaml_data)

        # Verify the data was parsed correctly
        assert instance.schema_version == "1.0.0"
        assert instance.namespace == "rosa-hcp"
        assert instance.entity is not None

        # Check repository data
        repos = instance.entity.repository
        assert repos is not None
        assert len(repos) == 2

        # Check first repository
        first_repo = repos[0]
        rosa_service_data = first_repo["rosa-hcp-service"]
        assert rosa_service_data.owners == [
            "rosa-team@redhat.com",
            "rosa-leads@redhat.com",
        ]
        assert (
            str(rosa_service_data.git_repo_url)
            == "https://github.com/openshift/rosa-hcp-service"
        )
        assert len(rosa_service_data.depends_on) == 3

        # Check service data
        services = instance.entity.service
        assert services is not None
        assert len(services) == 1

        auth_service = services[0]["auth-service"]
        assert auth_service.name == "Authentication Service"
        assert auth_service.team == "auth-team"

    def test_invalid_data_rejection(self, schema_dir, invalid_yaml_data):
        """Test that invalid YAML data is properly rejected."""
        # Load schemas and create models
        loader = FileSchemaLoader(schema_dir)
        schemas = asyncio.run(loader.load_schemas())
        factory = DynamicModelFactory()
        models = factory.create_models_from_schemas(schemas)

        # Try to validate invalid data
        KnowledgeGraphModel = models["_root"]
        with pytest.raises(ValidationError) as exc_info:
            KnowledgeGraphModel.model_validate(invalid_yaml_data)

        error_str = str(exc_info.value)
        # Should contain validation errors for email, URL, and unknown field
        assert (
            "value is not a valid email address" in error_str
            or "Input should be a valid URL" in error_str
        )

    def test_individual_entity_validation(self, schema_dir):
        """Test validating individual entities with their specific models."""
        # Load schemas and create models
        loader = FileSchemaLoader(schema_dir)
        schemas = asyncio.run(loader.load_schemas())
        factory = DynamicModelFactory()
        models = factory.create_models_from_schemas(schemas)

        RepositoryModel = models["repository"]
        ServiceModel = models["service"]

        # Test valid repository data
        valid_repo_data = {
            "owners": ["team@redhat.com"],
            "git_repo_url": "https://github.com/test/repo",
            "depends_on": ["external://pypi/requests/2.31.0"],
        }
        repo_instance = RepositoryModel.model_validate(valid_repo_data)
        assert repo_instance.owners == ["team@redhat.com"]
        assert len(repo_instance.depends_on) == 1

        # Test valid service data
        valid_service_data = {
            "name": "Test Service",
            "team": "test-team",
            "description": "A test service",
        }
        service_instance = ServiceModel.model_validate(valid_service_data)
        assert service_instance.name == "Test Service"
        assert service_instance.team == "test-team"

        # Test invalid repository data
        with pytest.raises(ValidationError):
            RepositoryModel.model_validate(
                {
                    "owners": ["invalid-email"],
                    "git_repo_url": "not-a-url",
                }
            )

        # Test invalid service data (missing required field)
        with pytest.raises(ValidationError):
            ServiceModel.model_validate(
                {
                    "team": "test-team",
                    # Missing required 'name' field
                }
            )

    def test_schema_inheritance_resolution(self, schema_dir):
        """Test that schema inheritance is properly resolved in models."""
        # Load schemas and create models
        loader = FileSchemaLoader(schema_dir)
        schemas = asyncio.run(loader.load_schemas())
        factory = DynamicModelFactory()
        models = factory.create_models_from_schemas(schemas)

        RepositoryModel = models["repository"]
        ServiceModel = models["service"]

        # Both should have inherited readonly fields from base_internal
        repo_fields = RepositoryModel.model_fields
        service_fields = ServiceModel.model_fields

        # Check inherited fields are present
        inherited_fields = ["created_at", "updated_at", "source_repo"]
        for field in inherited_fields:
            assert field in repo_fields, f"Repository missing inherited field: {field}"
            assert field in service_fields, f"Service missing inherited field: {field}"

        # Check that inherited fields are optional (from readonly_metadata)
        for field in inherited_fields:
            assert not repo_fields[
                field
            ].is_required(), f"Inherited field {field} should be optional"
            assert not service_fields[
                field
            ].is_required(), f"Inherited field {field} should be optional"

    def test_model_caching_across_schemas(self, schema_dir):
        """Test that model caching works correctly across multiple schemas."""
        # Load schemas and create models
        loader = FileSchemaLoader(schema_dir)
        schemas = asyncio.run(loader.load_schemas())
        factory = DynamicModelFactory()

        # Create models twice
        models1 = factory.create_models_from_schemas(schemas)
        models2 = factory.create_models_from_schemas(schemas)

        # Should be the same objects due to caching
        assert models1["repository"] is models2["repository"]
        assert models1["service"] is models2["service"]

        # Clear cache and create again
        factory.clear_cache()
        models3 = factory.create_models_from_schemas(schemas)

        # Should be different objects after cache clear
        assert models1["repository"] is not models3["repository"]
        assert models1["service"] is not models3["service"]

    def test_error_handling_with_real_schemas(self, schema_dir):
        """Test error handling with realistic error scenarios."""
        # Load schemas and create models
        loader = FileSchemaLoader(schema_dir)
        schemas = asyncio.run(loader.load_schemas())
        factory = DynamicModelFactory()
        models = factory.create_models_from_schemas(schemas)

        KnowledgeGraphModel = models["_root"]

        # Test schema version validation
        with pytest.raises(ValidationError) as exc_info:
            KnowledgeGraphModel.model_validate(
                {
                    "schema_version": "invalid-version",
                    "namespace": "test",
                    "entity": {},
                }
            )
        assert "String should match pattern" in str(exc_info.value)

        # Test namespace validation
        with pytest.raises(ValidationError) as exc_info:
            KnowledgeGraphModel.model_validate(
                {
                    "schema_version": "1.0.0",
                    "namespace": "Invalid-Namespace",
                    "entity": {},
                }
            )
        assert "String should match pattern" in str(exc_info.value)

        # Test unknown entity type
        with pytest.raises(ValidationError) as exc_info:
            KnowledgeGraphModel.model_validate(
                {
                    "schema_version": "1.0.0",
                    "namespace": "test",
                    "entity": {"unknown_entity_type": [{"test": {"name": "test"}}]},
                }
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)
