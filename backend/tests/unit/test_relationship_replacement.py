"""Tests for relationship replacement functionality.

This module tests that relationship management works correctly:
1. Replaces existing relationships when YAML changes
2. Removes relationships not present in YAML
3. Handles multiple relationship types dynamically based on schema
4. Works for any entity type and relationship defined in schema
"""

from unittest.mock import AsyncMock, Mock

import pytest

from kg.core import EntitySchema, RelationshipDefinition, RelationshipTypes
from kg.storage.interface import StorageInterface
from kg.storage.relationship_processor import GenericRelationshipProcessor


@pytest.fixture
def mock_storage():
    """Create a mock storage with relationship tracking."""
    storage = Mock(spec=StorageInterface)

    # Track relationships for verification
    storage._relationships = []
    storage._removed_relationships = []

    async def mock_remove_relationships_by_type(
        source_entity_type, source_entity_id, relationship_type
    ):
        removed = []
        for rel in storage._relationships[:]:
            if (
                rel["source_entity_type"] == source_entity_type
                and rel["source_entity_id"] == source_entity_id
                and rel["relationship_type"] == relationship_type
            ):
                removed.append(rel)
                storage._relationships.remove(rel)
                storage._removed_relationships.append(rel)
        return len(removed)

    async def mock_create_relationship(
        source_entity_type,
        source_entity_id,
        relationship_type,
        target_entity_type,
        target_entity_id,
    ):
        relationship = {
            "source_entity_type": source_entity_type,
            "source_entity_id": source_entity_id,
            "relationship_type": relationship_type,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
        }
        storage._relationships.append(relationship)
        return True

    async def mock_store_entity(entity_type, entity_id, entity_data, metadata):
        return entity_id

    storage.remove_relationships_by_type = AsyncMock(
        side_effect=mock_remove_relationships_by_type
    )
    storage.create_relationship = AsyncMock(side_effect=mock_create_relationship)
    storage.store_entity = AsyncMock(side_effect=mock_store_entity)

    return storage


@pytest.fixture
def repository_schema():
    """Create a repository schema with multiple relationship types."""
    return EntitySchema(
        entity_type="repository",
        schema_version="1.0.0",
        description="Repository schema",
        extends=None,
        required_fields=[],
        optional_fields=[],
        readonly_fields=[],
        relationships=[
            RelationshipDefinition(
                name=RelationshipTypes.DEPENDS_ON,
                description="External dependencies",
                target_types=["external_dependency_version"],
                cardinality="one_to_many",
                direction="outbound",
            ),
            RelationshipDefinition(
                name=RelationshipTypes.INTERNAL_DEPENDS_ON,
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


@pytest.mark.asyncio
class TestGenericRelationshipReplacement:
    """Test generic relationship replacement based on schema definitions."""

    async def test_should_replace_existing_relationship_with_new_one(
        self, mock_storage, repository_schema
    ):
        """Test that existing relationships are replaced when YAML changes."""
        # Setup: Entity has existing depends_on relationship
        mock_storage._relationships = [
            {
                "source_entity_type": "repository",
                "source_entity_id": "test-namespace/test-repo",
                "relationship_type": RelationshipTypes.DEPENDS_ON,
                "target_entity_type": "external_dependency_version",
                "target_entity_id": "external://pypi/requests/2.31.0",
            }
        ]

        # Create a generic relationship processor that works with any schema
        processor = GenericRelationshipProcessor(
            mock_storage, {"repository": repository_schema}
        )

        # Apply new YAML with different dependency
        yaml_relationships = {
            RelationshipTypes.DEPENDS_ON: ["external://pypi/requests/2.32.0"]
        }

        await processor.replace_entity_relationships(
            entity_type="repository",
            entity_id="test-namespace/test-repo",
            yaml_relationships=yaml_relationships,
        )

        # Verify old relationship was removed
        assert len(mock_storage._removed_relationships) == 1
        assert (
            mock_storage._removed_relationships[0]["target_entity_id"]
            == "external://pypi/requests/2.31.0"
        )

        # Verify new relationship was created
        current_relationships = [
            r
            for r in mock_storage._relationships
            if r["relationship_type"] == RelationshipTypes.DEPENDS_ON
        ]
        assert len(current_relationships) == 1
        assert (
            current_relationships[0]["target_entity_id"]
            == "external://pypi/requests/2.32.0"
        )

    async def test_should_remove_relationships_not_in_yaml(
        self, mock_storage, repository_schema
    ):
        """Test that relationships not present in YAML are removed."""
        # Setup: Entity has both depends_on and internal_depends_on relationships
        mock_storage._relationships = [
            {
                "source_entity_type": "repository",
                "source_entity_id": "test-namespace/test-repo",
                "relationship_type": RelationshipTypes.DEPENDS_ON,
                "target_entity_type": "external_dependency_version",
                "target_entity_id": "external://pypi/requests/2.31.0",
            },
            {
                "source_entity_type": "repository",
                "source_entity_id": "test-namespace/test-repo",
                "relationship_type": RelationshipTypes.INTERNAL_DEPENDS_ON,
                "target_entity_type": "repository",
                "target_entity_id": "test-namespace/other-repo",
            },
        ]

        processor = GenericRelationshipProcessor(
            mock_storage, {"repository": repository_schema}
        )

        # Apply YAML with only depends_on (internal_depends_on should be removed)
        yaml_relationships = {
            RelationshipTypes.DEPENDS_ON: ["external://pypi/requests/2.32.0"]
        }

        await processor.replace_entity_relationships(
            entity_type="repository",
            entity_id="test-namespace/test-repo",
            yaml_relationships=yaml_relationships,
        )

        # Verify internal_depends_on was removed
        removed_internal = [
            r
            for r in mock_storage._removed_relationships
            if r["relationship_type"] == RelationshipTypes.INTERNAL_DEPENDS_ON
        ]
        assert len(removed_internal) == 1

        # Verify depends_on was updated
        current_depends_on = [
            r
            for r in mock_storage._relationships
            if r["relationship_type"] == RelationshipTypes.DEPENDS_ON
        ]
        assert len(current_depends_on) == 1
        assert (
            current_depends_on[0]["target_entity_id"]
            == "external://pypi/requests/2.32.0"
        )

    async def test_should_handle_multiple_relationship_types_in_yaml(
        self, mock_storage, repository_schema
    ):
        """Test that multiple relationship types in YAML are handled correctly."""
        processor = GenericRelationshipProcessor(
            mock_storage, {"repository": repository_schema}
        )

        # Apply YAML with both relationship types
        yaml_relationships = {
            RelationshipTypes.DEPENDS_ON: [
                "external://pypi/requests/2.32.0",
                "external://pypi/django/4.1.0",
            ],
            RelationshipTypes.INTERNAL_DEPENDS_ON: [
                "test-namespace/lib-repo",
                "test-namespace/utils-repo",
            ],
        }

        await processor.replace_entity_relationships(
            entity_type="repository",
            entity_id="test-namespace/test-repo",
            yaml_relationships=yaml_relationships,
        )

        # Verify both relationship types were created
        depends_on_rels = [
            r
            for r in mock_storage._relationships
            if r["relationship_type"] == RelationshipTypes.DEPENDS_ON
        ]
        internal_rels = [
            r
            for r in mock_storage._relationships
            if r["relationship_type"] == RelationshipTypes.INTERNAL_DEPENDS_ON
        ]

        assert len(depends_on_rels) == 2
        assert len(internal_rels) == 2

        # Verify specific relationships
        depends_on_targets = [r["target_entity_id"] for r in depends_on_rels]
        assert "external://pypi/requests/2.32.0" in depends_on_targets
        assert "external://pypi/django/4.1.0" in depends_on_targets

        internal_targets = [r["target_entity_id"] for r in internal_rels]
        assert "test-namespace/lib-repo" in internal_targets
        assert "test-namespace/utils-repo" in internal_targets

    async def test_should_remove_all_relationships_when_yaml_empty(
        self, mock_storage, repository_schema
    ):
        """Test that all relationships are removed when YAML has no relationships."""
        # Setup: Entity has existing relationships
        mock_storage._relationships = [
            {
                "source_entity_type": "repository",
                "source_entity_id": "test-namespace/test-repo",
                "relationship_type": RelationshipTypes.DEPENDS_ON,
                "target_entity_type": "external_dependency_version",
                "target_entity_id": "external://pypi/requests/2.31.0",
            },
            {
                "source_entity_type": "repository",
                "source_entity_id": "test-namespace/test-repo",
                "relationship_type": RelationshipTypes.INTERNAL_DEPENDS_ON,
                "target_entity_type": "repository",
                "target_entity_id": "test-namespace/other-repo",
            },
        ]

        processor = GenericRelationshipProcessor(
            mock_storage, {"repository": repository_schema}
        )

        # Apply YAML with no relationships
        yaml_relationships = {}

        await processor.replace_entity_relationships(
            entity_type="repository",
            entity_id="test-namespace/test-repo",
            yaml_relationships=yaml_relationships,
        )

        # Verify all relationships were removed
        assert len(mock_storage._removed_relationships) == 2

        # Verify no relationships remain for this entity
        remaining_rels = [
            r
            for r in mock_storage._relationships
            if r["source_entity_id"] == "test-namespace/test-repo"
        ]
        assert len(remaining_rels) == 0


@pytest.mark.asyncio
class TestDependencyProcessorIntegration:
    """Test that DependencyProcessor integrates with the new relationship system."""

    async def test_dependency_processor_should_use_generic_relationship_replacement(
        self, mock_storage
    ):
        """Test that DependencyProcessor uses the new generic system instead of hard-coded logic."""
        # This test will verify that we refactor DependencyProcessor to use
        # the new GenericRelationshipProcessor instead of hard-coded depends_on logic
        pytest.skip("TODO: Implement after refactoring DependencyProcessor")
