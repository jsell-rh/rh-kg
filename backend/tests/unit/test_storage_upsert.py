"""Unit tests for storage upsert behavior.

These tests specifically target the store_entity method to ensure it implements
proper upsert behavior (update existing entities instead of creating duplicates).
"""

import pytest

from kg.api.config import config
from kg.storage import create_storage


@pytest.mark.asyncio
class TestStorageUpsertBehavior:
    """Test that storage backend implements proper upsert behavior."""

    async def test_store_entity_twice_should_update_not_duplicate(self):
        """Test that storing the same entity twice updates instead of creating duplicates.

        This test should FAIL initially, demonstrating the duplicate creation bug.
        After fixing store_entity, this test should PASS.
        """
        # Create storage backend
        storage = create_storage(config.storage)
        assert storage is not None

        await storage.connect()

        try:
            # Define test entity with unique ID for this test run
            import time

            timestamp = str(
                int(time.time() * 1000)
            )  # millisecond timestamp for uniqueness
            entity_type = "repository"
            entity_id = f"test-upsert/test-repo-{timestamp}"
            entity_data_v1 = {
                "owners": ["test@example.com"],
                "git_repo_url": "https://github.com/test/repo",
            }
            metadata = {"namespace": "test-upsert", "source_name": "test-repo"}

            # Store entity first time
            result1 = await storage.store_entity(
                entity_type, entity_id, entity_data_v1, metadata
            )
            assert result1 == entity_id

            # Verify entity exists
            entity_after_first = await storage.get_entity(entity_type, entity_id)
            assert entity_after_first is not None
            assert entity_after_first.id == entity_id
            assert (
                entity_after_first.metadata["git_repo_url"]
                == "https://github.com/test/repo"
            )

            # Store same entity again with updated data
            entity_data_v2 = {
                "owners": ["test@example.com", "admin@example.com"],
                "git_repo_url": "https://github.com/test/repo-updated",
            }

            result2 = await storage.store_entity(
                entity_type, entity_id, entity_data_v2, metadata
            )
            assert result2 == entity_id

            # Verify entity was updated, not duplicated
            entity_after_second = await storage.get_entity(entity_type, entity_id)
            assert entity_after_second is not None
            assert entity_after_second.id == entity_id
            assert (
                entity_after_second.metadata["git_repo_url"]
                == "https://github.com/test/repo-updated"
            )
            assert len(entity_after_second.metadata["owners"]) == 2

            # CRITICAL TEST: Query Dgraph directly to verify no duplicates exist
            query = f"""
            {{
                entities(func: eq(id, "{entity_id}")) @filter(eq(dgraph.type, "{entity_type}")) {{
                    uid
                    id
                    entity_type
                }}
            }}
            """

            query_result = await storage.execute_query(query)
            assert query_result.success

            entities = query_result.data.get("entities", [])

            # This is the key assertion that will FAIL initially
            assert (
                len(entities) == 1
            ), f"Expected 1 entity, found {len(entities)} duplicates: {entities}"

        finally:
            await storage.disconnect()

    async def test_store_entity_with_different_ids_creates_separate_entities(self):
        """Test that storing entities with different IDs creates separate entities.

        This ensures our fix doesn't break normal entity creation.
        """
        storage = create_storage(config.storage)
        assert storage is not None

        await storage.connect()

        try:
            # Store first entity
            entity_type = "repository"
            entity_id_1 = "test-separate/repo-1"
            entity_data_1 = {
                "owners": ["team1@example.com"],
                "git_repo_url": "https://github.com/test/repo-1",
            }
            metadata_1 = {"namespace": "test-separate", "source_name": "repo-1"}

            result1 = await storage.store_entity(
                entity_type, entity_id_1, entity_data_1, metadata_1
            )
            assert result1 == entity_id_1

            # Store second entity with different ID
            entity_id_2 = "test-separate/repo-2"
            entity_data_2 = {
                "owners": ["team2@example.com"],
                "git_repo_url": "https://github.com/test/repo-2",
            }
            metadata_2 = {"namespace": "test-separate", "source_name": "repo-2"}

            result2 = await storage.store_entity(
                entity_type, entity_id_2, entity_data_2, metadata_2
            )
            assert result2 == entity_id_2

            # Verify both entities exist separately
            entity1 = await storage.get_entity(entity_type, entity_id_1)
            entity2 = await storage.get_entity(entity_type, entity_id_2)

            assert entity1 is not None
            assert entity2 is not None
            assert entity1.id != entity2.id
            assert entity1.metadata["git_repo_url"] != entity2.metadata["git_repo_url"]

        finally:
            await storage.disconnect()

    async def test_store_entity_preserves_created_at_on_update(self):
        """Test that updating an entity preserves created_at but updates updated_at.

        This test verifies proper timestamp handling during updates.
        """
        storage = create_storage(config.storage)
        assert storage is not None

        await storage.connect()

        try:
            entity_type = "repository"
            entity_id = "test-timestamps/test-repo"
            entity_data = {
                "owners": ["test@example.com"],
                "git_repo_url": "https://github.com/test/repo",
            }
            metadata = {"namespace": "test-timestamps", "source_name": "test-repo"}

            # Store entity first time
            await storage.store_entity(entity_type, entity_id, entity_data, metadata)

            # Get entity and check created_at exists
            entity_after_create = await storage.get_entity(entity_type, entity_id)
            assert entity_after_create is not None
            original_created_at = entity_after_create.metadata.get("created_at")
            assert original_created_at is not None

            # Wait a bit and update entity
            import asyncio

            await asyncio.sleep(0.1)  # Small delay to ensure different timestamps

            updated_data = {
                "owners": ["test@example.com", "admin@example.com"],
                "git_repo_url": "https://github.com/test/repo-updated",
            }

            await storage.store_entity(entity_type, entity_id, updated_data, metadata)

            # Verify created_at is preserved but updated_at is new
            entity_after_update = await storage.get_entity(entity_type, entity_id)
            assert entity_after_update is not None

            # created_at should be preserved
            assert entity_after_update.metadata.get("created_at") == original_created_at

            # updated_at should exist and be different
            updated_at = entity_after_update.metadata.get("updated_at")
            assert updated_at is not None
            assert updated_at != original_created_at

        finally:
            await storage.disconnect()


@pytest.mark.asyncio
class TestCurrentBugDocumentation:
    """Document the current bug that exists before our fix."""

    async def test_document_current_duplicate_creation_bug(self):
        """This test documents the current bug and should initially PASS.

        After we fix the bug, this test should be updated or removed.
        It shows that the current implementation creates duplicates.
        """
        storage = create_storage(config.storage)
        assert storage is not None

        await storage.connect()

        try:
            entity_type = "repository"
            entity_id = "test-bug-demo/duplicate-repo"
            entity_data = {
                "owners": ["test@example.com"],
                "git_repo_url": "https://github.com/test/repo",
            }
            metadata = {"namespace": "test-bug-demo", "source_name": "duplicate-repo"}

            # Store entity twice
            await storage.store_entity(entity_type, entity_id, entity_data, metadata)
            await storage.store_entity(entity_type, entity_id, entity_data, metadata)

            # Query to count duplicates
            query = f"""
            {{
                entities(func: eq(entity_id, "{entity_id}")) @filter(eq(dgraph.type, "{entity_type}")) {{
                    uid
                    entity_id
                }}
            }}
            """

            query_result = await storage.execute_query(query)
            assert query_result.success

            entities = query_result.data.get("entities", [])

            # This currently passes (showing the bug) but should fail after fix
            print(f"Found {len(entities)} entities with ID {entity_id}")
            if len(entities) > 1:
                print("✅ BUG CONFIRMED: Duplicate entities created!")
            else:
                print("❌ Bug not reproduced - fix may already be in place")

        finally:
            await storage.disconnect()
