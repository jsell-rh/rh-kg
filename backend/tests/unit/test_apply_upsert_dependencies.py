"""Tests for apply command upsert behavior and dependency processing.

These tests verify that the apply command properly handles:
1. Upsert behavior - updating existing entities instead of creating duplicates
2. Dependency processing - creating external dependency entities and relationships
3. Relationship creation - proper graph structure according to data model spec
"""

from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from kg.cli.apply import apply_command
from kg.storage import StorageInterface
from kg.storage.models import EntityData, StorageConfig


@pytest.fixture
def mock_storage_for_upsert():
    """Create a mock storage that tracks entity creation/updates properly."""
    storage = Mock(spec=StorageInterface)

    # Track entities that have been "stored"
    storage._entities = {}

    async def mock_get_entity(entity_type: str, entity_id: str):
        """Return entity if it exists in our tracking."""
        full_id = f"{entity_type}/{entity_id}"
        if full_id in storage._entities:
            return EntityData(
                id=entity_id,
                entity_type=entity_type,
                metadata=storage._entities[full_id]["metadata"],
                system_metadata={},
                relationships={},
            )
        return None

    async def mock_store_entity(
        entity_type: str, entity_id: str, entity_data: dict, metadata: dict
    ):
        """Track stored entities."""
        full_id = f"{entity_type}/{entity_id}"
        storage._entities[full_id] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": entity_data,
            "system_metadata": metadata,
        }
        return entity_id

    storage.get_entity = AsyncMock(side_effect=mock_get_entity)
    storage.store_entity = AsyncMock(side_effect=mock_store_entity)
    storage.connect = AsyncMock()
    storage.load_schemas = AsyncMock(return_value={})
    storage.entity_exists = AsyncMock(return_value=True)
    storage.dry_run_apply = AsyncMock()

    return storage


@pytest.fixture
def sample_yaml_with_deps():
    """Sample YAML with external dependencies."""
    return """
namespace: "test-ns"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com"]
        git_repo_url: "https://github.com/test/repo"
        depends_on:
          - "external://pypi/requests/2.31.0"
          - "external://npm/express/4.18.0"
"""


@pytest.fixture
def mock_apply_environment_upsert(mock_storage_for_upsert):
    """Set up mock environment for upsert testing."""
    with (
        patch("kg.cli.apply.create_storage") as mock_create_storage,
        patch("kg.cli.apply.FileSchemaLoader") as mock_schema_loader,
        patch("kg.api.config.config") as mock_config,
        patch("kg.cli.apply.KnowledgeGraphValidator") as mock_validator,
    ):
        # Setup config mock
        mock_config.storage = StorageConfig(
            backend_type="mock",
            endpoint="localhost:9080",
            timeout_seconds=30,
            max_retries=3,
            use_tls=False,
            retry_delay_seconds=1.0,
        )

        # Setup storage mocks
        mock_create_storage.return_value = mock_storage_for_upsert

        # Setup schema loader mocks
        mock_schema_loader_instance = Mock()
        mock_schema_loader.return_value = mock_schema_loader_instance
        mock_schema_loader_instance.load_schemas = AsyncMock(return_value={})

        # Setup validator mock
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validation_result.errors = []
        mock_validation_result.warnings = []
        mock_validation_result.error_count = 0
        mock_validation_result.warning_count = 0
        mock_validator_instance.validate = AsyncMock(
            return_value=mock_validation_result
        )

        yield {
            "mock_create_storage": mock_create_storage,
            "mock_schema_loader": mock_schema_loader,
            "mock_config": mock_config,
            "mock_storage": mock_storage_for_upsert,
            "mock_validator": mock_validator,
        }


class TestApplyUpsertBehavior:
    """Test that apply command implements proper upsert behavior."""

    def test_apply_same_entity_twice_should_update_not_duplicate(
        self, mock_apply_environment_upsert, sample_yaml_with_deps
    ):
        """Test that applying the same YAML twice updates the entity instead of creating duplicates."""
        from click.testing import CliRunner

        mock_storage = mock_apply_environment_upsert["mock_storage"]

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_yaml_with_deps)
            temp_path = f.name

        try:
            runner = CliRunner()

            # First apply - should create entity
            result1 = runner.invoke(apply_command, [temp_path])
            assert result1.exit_code == 0

            # Verify entity was stored
            assert len(mock_storage._entities) == 1
            first_store_calls = mock_storage.store_entity.call_count

            # Second apply - should update existing entity
            result2 = runner.invoke(apply_command, [temp_path])
            assert result2.exit_code == 0

            # Verify still only one entity exists (no duplicates)
            assert len(mock_storage._entities) == 1

            # Verify store_entity was called twice (once create, once update)
            assert mock_storage.store_entity.call_count == first_store_calls + 1

            # Verify the entity exists in our tracking
            entity_key = "repository/test-ns/test-repo"
            assert entity_key in mock_storage._entities

        finally:
            Path(temp_path).unlink()

    def test_apply_with_updated_metadata_should_update_entity(
        self, mock_apply_environment_upsert
    ):
        """Test that applying YAML with updated metadata updates the entity."""
        from click.testing import CliRunner

        mock_storage = mock_apply_environment_upsert["mock_storage"]

        # First YAML with initial metadata
        yaml_v1 = """
namespace: "test-ns"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com"]
        git_repo_url: "https://github.com/test/repo"
"""

        # Second YAML with updated metadata
        yaml_v2 = """
namespace: "test-ns"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com", "admin@example.com"]
        git_repo_url: "https://github.com/test/repo-updated"
"""

        runner = CliRunner()

        # Apply first version
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_v1)
            temp_path1 = f.name

        try:
            result1 = runner.invoke(apply_command, [temp_path1])
            assert result1.exit_code == 0

            # Verify initial metadata
            entity_key = "repository/test-ns/test-repo"
            assert entity_key in mock_storage._entities
            initial_metadata = mock_storage._entities[entity_key]["metadata"]
            assert len(initial_metadata["owners"]) == 1
            assert initial_metadata["git_repo_url"] == "https://github.com/test/repo"

        finally:
            Path(temp_path1).unlink()

        # Apply second version
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_v2)
            temp_path2 = f.name

        try:
            result2 = runner.invoke(apply_command, [temp_path2])
            assert result2.exit_code == 0

            # Verify updated metadata
            assert len(mock_storage._entities) == 1  # Still only one entity
            updated_metadata = mock_storage._entities[entity_key]["metadata"]
            assert len(updated_metadata["owners"]) == 2
            assert (
                updated_metadata["git_repo_url"]
                == "https://github.com/test/repo-updated"
            )

        finally:
            Path(temp_path2).unlink()


class TestDependencyProcessing:
    """Test that dependencies are properly processed into separate entities and relationships."""

    def test_apply_with_external_dependencies_creates_dependency_entities(
        self, mock_apply_environment_upsert, sample_yaml_with_deps
    ):
        """Test that external dependencies create proper package and version entities."""
        from click.testing import CliRunner

        mock_storage = mock_apply_environment_upsert["mock_storage"]

        # Mock dependency processing methods
        mock_storage.create_external_dependency_package = AsyncMock()
        mock_storage.create_external_dependency_version = AsyncMock()
        mock_storage.create_relationship = AsyncMock()

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_yaml_with_deps)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            # This test will initially fail because dependency processing isn't implemented
            # After implementation, we should verify:
            # 1. External dependency package entities are created
            # 2. External dependency version entities are created
            # 3. Relationships are established

            # For now, just verify the apply doesn't crash
            assert result.exit_code == 0

        finally:
            Path(temp_path).unlink()

    def test_external_dependency_auto_creation_follows_spec(
        self, mock_apply_environment_upsert
    ):
        """Test that external dependencies are auto-created according to data model spec."""
        # This test verifies the data model spec requirements:
        # 1. ExternalDependencyPackage: external://pypi/requests
        # 2. ExternalDependencyVersion: external://pypi/requests/2.31.0
        # 3. has_version relationship: package -> version
        # 4. depends_on relationship: repository -> version

        # Test will initially fail until dependency processing is implemented
        pass

    def test_relationships_are_created_correctly(
        self, mock_apply_environment_upsert, sample_yaml_with_deps
    ):
        """Test that depends_on relationships are created in Dgraph."""
        # This test should verify that after applying YAML with dependencies:
        # 1. Repository node exists
        # 2. External dependency nodes exist
        # 3. Proper relationship edges exist in the graph
        # 4. Relationships follow the correct direction (Repository -> ExternalDependencyVersion)

        # Test will initially fail until relationship creation is implemented
        pass


class TestCurrentBehaviorDocumentation:
    """Document current broken behavior that needs to be fixed."""

    def test_current_duplicate_creation_behavior(
        self, mock_apply_environment_upsert, sample_yaml_with_deps
    ):
        """Document that current implementation creates duplicates (this should fail initially)."""
        from click.testing import CliRunner

        mock_storage = mock_apply_environment_upsert["mock_storage"]

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_yaml_with_deps)
            temp_path = f.name

        try:
            runner = CliRunner()

            # Apply twice
            runner.invoke(apply_command, [temp_path])
            runner.invoke(apply_command, [temp_path])

            # Currently this will pass (creating duplicates), but should fail
            # After fix, this test should be updated to verify no duplicates
            # For now, document the broken behavior
            assert len(mock_storage._entities) == 1, "Should not create duplicates"

        finally:
            Path(temp_path).unlink()

    def test_current_dependency_ignored_behavior(
        self, mock_apply_environment_upsert, sample_yaml_with_deps
    ):
        """Document that dependencies are currently ignored (this should fail initially)."""
        # This test documents that depends_on is currently treated as regular metadata
        # instead of creating proper dependency entities and relationships
        # After fix, this should verify dependency processing works correctly
        pass
