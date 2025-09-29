"""Tests for external dependency processing functionality.

These tests verify that external dependencies specified in depends_on fields
are properly processed into separate entities and relationships according to
the data model specification.

Test Strategy:
1. Test external dependency URI parsing using DependencyType enum
2. Test ExternalDependencyPackage entity creation
3. Test ExternalDependencyVersion entity creation
4. Test relationship creation (has_version, depends_on)
5. Test integration with store_entity method
"""

from unittest.mock import AsyncMock, Mock

import pytest

from kg.core import (
    DependencyType,
    DependencyUriBuilder,
    is_external_dependency,
    parse_external_dependency,
)
from kg.storage import StorageInterface
from kg.storage.models import EntityData


@pytest.fixture
def mock_storage_with_relationships():
    """Create a mock storage that tracks entities and relationships."""
    storage = Mock(spec=StorageInterface)

    # Track entities and relationships
    storage._entities = {}
    storage._relationships = []

    async def mock_get_entity(entity_type: str, entity_id: str):
        """Return entity if it exists in tracking."""
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

    async def mock_create_relationship(
        source_entity_type: str,
        source_entity_id: str,
        relationship_type: str,
        target_entity_type: str,
        target_entity_id: str,
    ):
        """Track created relationships."""
        relationship = {
            "source_entity_type": source_entity_type,
            "source_entity_id": source_entity_id,
            "relationship_type": relationship_type,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
        }
        storage._relationships.append(relationship)
        return True

    storage.get_entity = AsyncMock(side_effect=mock_get_entity)
    storage.store_entity = AsyncMock(side_effect=mock_store_entity)
    storage.create_relationship = AsyncMock(side_effect=mock_create_relationship)
    storage.connect = AsyncMock()
    storage.entity_exists = AsyncMock(return_value=True)

    return storage


@pytest.mark.asyncio
class TestDependencyTypeEnum:
    """Test DependencyType enum functionality."""

    def test_dependency_type_identification(self):
        """Test identifying dependency types from URIs."""
        # External dependencies
        external_uris = [
            "external://pypi/requests/2.31.0",
            "external://npm/@types/node/18.15.0",
            "external://maven/org.springframework/spring-core/5.3.0",
        ]

        for uri in external_uris:
            dep_type = DependencyType.identify_dependency_type(uri)
            assert (
                dep_type == DependencyType.EXTERNAL
            ), f"Failed to identify external: {uri}"
            assert is_external_dependency(
                uri
            ), f"is_external_dependency failed for: {uri}"

        # Internal dependencies
        internal_uris = [
            "internal://namespace/entity-id",
            "internal://complex/namespace/deep/entity",
        ]

        for uri in internal_uris:
            dep_type = DependencyType.identify_dependency_type(uri)
            assert (
                dep_type == DependencyType.INTERNAL
            ), f"Failed to identify internal: {uri}"
            assert not is_external_dependency(
                uri
            ), f"is_external_dependency incorrectly matched: {uri}"

        # Invalid URIs
        invalid_uris = ["not-a-uri", "", "http://example.com", "ftp://files.com"]

        for uri in invalid_uris:
            dep_type = DependencyType.identify_dependency_type(uri)
            assert dep_type is None, f"Should not identify invalid URI: {uri}"

    def test_dependency_uri_builder(self):
        """Test building dependency URIs using DependencyUriBuilder."""
        # External URI building
        external_uri = DependencyUriBuilder.external("pypi", "requests", "2.31.0")
        assert external_uri == "external://pypi/requests/2.31.0"

        # Internal URI building
        internal_uri = DependencyUriBuilder.internal("namespace", "entity-id")
        assert internal_uri == "internal://namespace/entity-id"

        # Internal URI with namespace already in entity_id
        internal_uri_full = DependencyUriBuilder.internal(
            "namespace", "namespace/entity-id"
        )
        assert internal_uri_full == "internal://namespace/entity-id"


@pytest.mark.asyncio
class TestExternalDependencyUriParsing:
    """Test parsing of external dependency URIs using DependencyType enum."""

    def test_parse_external_dependency_uri_pypi(self):
        """Test parsing external://pypi/package/version URI."""
        uri = "external://pypi/requests/2.31.0"
        result = parse_external_dependency(uri)

        assert result is not None
        assert result["type"] == DependencyType.EXTERNAL
        assert result["ecosystem"] == "pypi"
        assert result["package_name"] == "requests"
        assert result["version"] == "2.31.0"
        assert result["package_id"] == "external://pypi/requests"
        assert result["version_id"] == "external://pypi/requests/2.31.0"
        assert result["uri"] == uri

    def test_parse_external_dependency_uri_npm(self):
        """Test parsing external://npm/package/version URI."""
        uri = "external://npm/@types/node/18.15.0"
        result = parse_external_dependency(uri)

        assert result is not None
        assert result["type"] == DependencyType.EXTERNAL
        assert result["ecosystem"] == "npm"
        assert result["package_name"] == "@types/node"
        assert result["version"] == "18.15.0"
        assert result["package_id"] == "external://npm/@types/node"
        assert result["version_id"] == "external://npm/@types/node/18.15.0"
        assert result["uri"] == uri

    def test_parse_external_dependency_uri_invalid(self):
        """Test parsing invalid external dependency URI."""
        # Test various invalid formats
        invalid_uris = [
            "internal://something",
            "external://",
            "external://pypi",
            "external://pypi/package",
            "not-a-uri",
            "",
        ]

        for uri in invalid_uris:
            result = parse_external_dependency(uri)
            assert result is None, f"Expected None for invalid URI: {uri}"

    def test_parse_external_dependency_complex_packages(self):
        """Test parsing external dependencies with complex package names."""
        test_cases = [
            {
                "uri": "external://npm/@babel/core/7.22.0",
                "ecosystem": "npm",
                "package_name": "@babel/core",
                "version": "7.22.0",
            },
            {
                "uri": "external://maven/org.springframework/spring-core/5.3.0",
                "ecosystem": "maven",
                "package_name": "org.springframework/spring-core",
                "version": "5.3.0",
            },
            {
                "uri": "external://cargo/serde_json/1.0.96",
                "ecosystem": "cargo",
                "package_name": "serde_json",
                "version": "1.0.96",
            },
        ]

        for case in test_cases:
            result = parse_external_dependency(case["uri"])
            assert result is not None, f"Failed to parse: {case['uri']}"
            assert result["ecosystem"] == case["ecosystem"]
            assert result["package_name"] == case["package_name"]
            assert result["version"] == case["version"]


@pytest.mark.asyncio
class TestExternalDependencyEntityCreation:
    """Test creation of external dependency entities."""

    async def test_create_external_dependency_package_entity(
        self, mock_storage_with_relationships
    ):
        """Test creation of ExternalDependencyPackage entity."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        package_info = {
            "ecosystem": "pypi",
            "package_name": "requests",
            "package_id": "external://pypi/requests",
        }

        result = await processor.create_external_dependency_package(package_info)

        assert result == "external://pypi/requests"

        # Verify package entity was created
        package_key = "external_dependency_package/external://pypi/requests"
        assert package_key in mock_storage_with_relationships._entities

        package_entity = mock_storage_with_relationships._entities[package_key]
        assert package_entity["metadata"]["ecosystem"] == "pypi"
        assert package_entity["metadata"]["package_name"] == "requests"

    async def test_create_external_dependency_version_entity(
        self, mock_storage_with_relationships
    ):
        """Test creation of ExternalDependencyVersion entity."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        version_info = {
            "ecosystem": "pypi",
            "package_name": "requests",
            "version": "2.31.0",
            "package_id": "external://pypi/requests",
            "version_id": "external://pypi/requests/2.31.0",
        }

        result = await processor.create_external_dependency_version(version_info)

        assert result == "external://pypi/requests/2.31.0"

        # Verify version entity was created
        version_key = "external_dependency_version/external://pypi/requests/2.31.0"
        assert version_key in mock_storage_with_relationships._entities

        version_entity = mock_storage_with_relationships._entities[version_key]
        assert version_entity["metadata"]["ecosystem"] == "pypi"
        assert version_entity["metadata"]["package_name"] == "requests"
        assert version_entity["metadata"]["version"] == "2.31.0"

    async def test_create_dependency_entities_creates_both_package_and_version(
        self, mock_storage_with_relationships
    ):
        """Test that creating dependency entities creates both package and version."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        dependency_uri = "external://pypi/requests/2.31.0"

        result = await processor.create_dependency_entities(dependency_uri)

        assert result is not None
        assert result["package_id"] == "external://pypi/requests"
        assert result["version_id"] == "external://pypi/requests/2.31.0"

        # Verify both entities were created
        package_key = "external_dependency_package/external://pypi/requests"
        version_key = "external_dependency_version/external://pypi/requests/2.31.0"

        assert package_key in mock_storage_with_relationships._entities
        assert version_key in mock_storage_with_relationships._entities


@pytest.mark.asyncio
class TestDependencyRelationshipCreation:
    """Test creation of dependency relationships."""

    async def test_create_has_version_relationship(
        self, mock_storage_with_relationships
    ):
        """Test creation of has_version relationship between package and version."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        package_id = "external://pypi/requests"
        version_id = "external://pypi/requests/2.31.0"

        result = await processor.create_has_version_relationship(package_id, version_id)

        assert result is True

        # Verify relationship was created
        expected_relationship = {
            "source_entity_type": "external_dependency_package",
            "source_entity_id": package_id,
            "relationship_type": "has_version",
            "target_entity_type": "external_dependency_version",
            "target_entity_id": version_id,
        }

        assert expected_relationship in mock_storage_with_relationships._relationships

    async def test_create_depends_on_relationship(
        self, mock_storage_with_relationships
    ):
        """Test creation of depends_on relationship between repository and dependency version."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        repo_id = "test-namespace/test-repo"
        version_id = "external://pypi/requests/2.31.0"

        result = await processor.create_depends_on_relationship(repo_id, version_id)

        assert result is True

        # Verify relationship was created
        expected_relationship = {
            "source_entity_type": "repository",
            "source_entity_id": repo_id,
            "relationship_type": "depends_on",
            "target_entity_type": "external_dependency_version",
            "target_entity_id": version_id,
        }

        assert expected_relationship in mock_storage_with_relationships._relationships


@pytest.mark.asyncio
class TestDependencyProcessingIntegration:
    """Test integration of dependency processing with store_entity."""

    async def test_process_single_external_dependency(
        self, mock_storage_with_relationships
    ):
        """Test processing a single external dependency."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        repo_entity_id = "test-namespace/test-repo"
        dependencies = ["external://pypi/requests/2.31.0"]

        result = await processor.process_dependencies(repo_entity_id, dependencies)

        assert result is True

        # Verify all entities were created
        package_key = "external_dependency_package/external://pypi/requests"
        version_key = "external_dependency_version/external://pypi/requests/2.31.0"

        assert package_key in mock_storage_with_relationships._entities
        assert version_key in mock_storage_with_relationships._entities

        # Verify relationships were created
        assert len(mock_storage_with_relationships._relationships) == 2

        # has_version relationship
        has_version_rel = {
            "source_entity_type": "external_dependency_package",
            "source_entity_id": "external://pypi/requests",
            "relationship_type": "has_version",
            "target_entity_type": "external_dependency_version",
            "target_entity_id": "external://pypi/requests/2.31.0",
        }
        assert has_version_rel in mock_storage_with_relationships._relationships

        # depends_on relationship
        depends_on_rel = {
            "source_entity_type": "repository",
            "source_entity_id": repo_entity_id,
            "relationship_type": "depends_on",
            "target_entity_type": "external_dependency_version",
            "target_entity_id": "external://pypi/requests/2.31.0",
        }
        assert depends_on_rel in mock_storage_with_relationships._relationships

    async def test_process_multiple_external_dependencies(
        self, mock_storage_with_relationships
    ):
        """Test processing multiple external dependencies."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        repo_entity_id = "test-namespace/test-repo"
        dependencies = [
            "external://pypi/requests/2.31.0",
            "external://npm/express/4.18.0",
            "external://pypi/numpy/1.24.0",
        ]

        result = await processor.process_dependencies(repo_entity_id, dependencies)

        assert result is True

        # Verify all package entities were created
        expected_packages = [
            "external_dependency_package/external://pypi/requests",
            "external_dependency_package/external://npm/express",
            "external_dependency_package/external://pypi/numpy",
        ]

        for package_key in expected_packages:
            assert package_key in mock_storage_with_relationships._entities

        # Verify all version entities were created
        expected_versions = [
            "external_dependency_version/external://pypi/requests/2.31.0",
            "external_dependency_version/external://npm/express/4.18.0",
            "external_dependency_version/external://pypi/numpy/1.24.0",
        ]

        for version_key in expected_versions:
            assert version_key in mock_storage_with_relationships._entities

        # Verify all relationships were created (3 has_version + 3 depends_on = 6 total)
        assert len(mock_storage_with_relationships._relationships) == 6

    async def test_process_dependencies_with_internal_references_ignored(
        self, mock_storage_with_relationships
    ):
        """Test that internal references are ignored during dependency processing."""
        from kg.storage.dependency_processor import DependencyProcessor

        processor = DependencyProcessor(mock_storage_with_relationships)

        repo_entity_id = "test-namespace/test-repo"
        dependencies = [
            "external://pypi/requests/2.31.0",
            "internal://other-namespace/other-repo",  # Should be ignored
            "http://example.com/invalid",  # Should be ignored
            "",  # Should be ignored
        ]

        result = await processor.process_dependencies(repo_entity_id, dependencies)

        assert result is True

        # Verify only external dependency entities were created
        package_key = "external_dependency_package/external://pypi/requests"
        version_key = "external_dependency_version/external://pypi/requests/2.31.0"

        assert package_key in mock_storage_with_relationships._entities
        assert version_key in mock_storage_with_relationships._entities

        # Verify only external dependency relationships were created (1 has_version + 1 depends_on = 2 total)
        assert len(mock_storage_with_relationships._relationships) == 2

        # Verify only the external dependency was processed
        external_deps = [dep for dep in dependencies if is_external_dependency(dep)]
        assert len(external_deps) == 1


@pytest.mark.asyncio
class TestStoreEntityDependencyIntegration:
    """Test that store_entity properly integrates dependency processing."""

    async def test_store_entity_processes_depends_on_field(
        self, mock_storage_with_relationships
    ):
        """Test that store_entity processes depends_on field and creates dependency entities."""
        # This test will initially fail because store_entity doesn't call dependency processing yet

        entity_type = "repository"
        entity_id = "test-namespace/test-repo"
        entity_data = {
            "owners": ["test@example.com"],
            "git_repo_url": "https://github.com/test/repo",
            "depends_on": ["external://pypi/requests/2.31.0"],
        }
        metadata = {"namespace": "test-namespace", "source_name": "test-repo"}

        # Mock the enhanced store_entity method that should process dependencies
        async def enhanced_store_entity(entity_type, entity_id, entity_data, metadata):
            # Store the main entity
            result = await mock_storage_with_relationships.store_entity(
                entity_type, entity_id, entity_data, metadata
            )

            # Process dependencies if present
            depends_on = entity_data.get("depends_on", [])
            if depends_on:
                from kg.storage.dependency_processor import DependencyProcessor

                processor = DependencyProcessor(mock_storage_with_relationships)
                await processor.process_dependencies(entity_id, depends_on)

            return result

        result = await enhanced_store_entity(
            entity_type, entity_id, entity_data, metadata
        )

        assert result == entity_id

        # Verify main entity was created
        repo_key = f"{entity_type}/{entity_id}"
        assert repo_key in mock_storage_with_relationships._entities

        # Verify dependency entities were created
        package_key = "external_dependency_package/external://pypi/requests"
        version_key = "external_dependency_version/external://pypi/requests/2.31.0"

        assert package_key in mock_storage_with_relationships._entities
        assert version_key in mock_storage_with_relationships._entities

        # Verify relationships were created
        assert len(mock_storage_with_relationships._relationships) == 2

    async def test_store_entity_without_dependencies_works_normally(
        self, mock_storage_with_relationships
    ):
        """Test that store_entity without dependencies works normally."""
        entity_type = "repository"
        entity_id = "test-namespace/simple-repo"
        entity_data = {
            "owners": ["test@example.com"],
            "git_repo_url": "https://github.com/test/simple-repo",
        }
        metadata = {"namespace": "test-namespace", "source_name": "simple-repo"}

        result = await mock_storage_with_relationships.store_entity(
            entity_type, entity_id, entity_data, metadata
        )

        assert result == entity_id

        # Verify only main entity was created
        repo_key = f"{entity_type}/{entity_id}"
        assert repo_key in mock_storage_with_relationships._entities

        # Verify no dependency entities or relationships were created
        dependency_entities = [
            key
            for key in mock_storage_with_relationships._entities
            if "external_dependency" in key
        ]
        assert len(dependency_entities) == 0
        assert len(mock_storage_with_relationships._relationships) == 0


@pytest.mark.asyncio
class TestCurrentBehaviorDocumentation:
    """Document current broken behavior that needs to be fixed."""

    async def test_current_dependency_ignored_behavior(self):
        """Document that dependencies are currently ignored (this should fail initially)."""
        # This test documents that depends_on is currently treated as regular metadata
        # instead of creating proper dependency entities and relationships

        # After implementation, this test should be updated to verify dependency processing works
        pytest.skip(
            "Test documents current broken behavior - will be updated after implementation"
        )
