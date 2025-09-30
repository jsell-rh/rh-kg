"""Abstract storage interface for knowledge graph operations.

This module defines the storage interface contract using strongly-typed
Pydantic models for all return types, ensuring type safety and clear contracts.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..core import EntitySchema
from .models import (
    DryRunResult,
    EntityData,
    HealthCheckResult,
    QueryResult,
    RelationshipData,
    SystemMetrics,
)


class StorageInterface(ABC):
    """Abstract interface for knowledge graph storage operations.

    This interface provides a consistent, strongly-typed API for all storage
    operations, abstracting away backend-specific details and enabling
    testability through mock implementations.

    All storage backends must implement this interface to ensure
    compatibility with the validation engine and CLI commands.
    """

    # Connection Management

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to storage backend.

        Raises:
            StorageConnectionError: If connection cannot be established
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to storage backend.

        Should not raise exceptions - errors should be logged.
        """
        pass

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Check storage backend health and return typed status.

        Returns:
            HealthCheckResult with status, response time, and backend info
        """
        pass

    # Schema Management

    @abstractmethod
    async def load_schemas(self, schema_dir: str) -> dict[str, EntitySchema]:
        """Load entity schemas from directory and initialize backend schema.

        Args:
            schema_dir: Path to directory containing schema YAML files

        Returns:
            Dictionary mapping entity types to their schemas

        Raises:
            StorageOperationError: If schema loading fails
        """
        pass

    @abstractmethod
    async def reload_schemas(self) -> dict[str, EntitySchema]:
        """Reload schemas from disk and update backend schema.

        Returns:
            Updated schemas dictionary

        Raises:
            StorageOperationError: If schema reload fails
        """
        pass

    # Entity Operations (CRUD)

    @abstractmethod
    async def store_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_data: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:
        """Store or update entity in storage backend.

        Args:
            entity_type: Type of entity (e.g., "repository")
            entity_id: Unique identifier for the entity
            entity_data: Entity field data from YAML
            metadata: System metadata (timestamps, source info)

        Returns:
            The entity ID that was stored

        Raises:
            StorageOperationError: If storage operation fails
            StorageValidationError: If entity data is invalid
        """
        pass

    @abstractmethod
    async def get_entity(self, entity_type: str, entity_id: str) -> EntityData | None:
        """Retrieve entity by type and ID.

        Args:
            entity_type: Type of entity to retrieve
            entity_id: Unique identifier of the entity

        Returns:
            EntityData if found, None if not found

        Raises:
            StorageQueryError: If query execution fails
        """
        pass

    @abstractmethod
    async def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity from storage.

        Args:
            entity_type: Type of entity to delete
            entity_id: Unique identifier of the entity

        Returns:
            True if entity was deleted, False if not found

        Raises:
            StorageOperationError: If deletion fails (e.g., references exist)
        """
        pass

    @abstractmethod
    async def list_entities(
        self,
        entity_type: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EntityData]:
        """List entities of given type with optional filtering.

        Args:
            entity_type: Type of entities to list
            filters: Optional field filters (field_name -> value)
            limit: Maximum number of entities to return
            offset: Number of entities to skip (for pagination)

        Returns:
            List of EntityData objects

        Raises:
            StorageQueryError: If query execution fails
        """
        pass

    # Reference Validation (for Layer 5 validation)

    @abstractmethod
    async def entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists in storage (for reference validation).

        This method is used by Layer 5 validation to check if
        internally referenced entities exist.

        Args:
            entity_id: Entity ID to check (e.g., "namespace/entity-name")

        Returns:
            True if entity exists, False otherwise

        Raises:
            StorageQueryError: If query execution fails
        """
        pass

    # Relationship Operations

    @abstractmethod
    async def create_relationship(
        self,
        source_entity_type: str,
        source_entity_id: str,
        relationship_type: str,
        target_entity_type: str,
        target_entity_id: str,
    ) -> bool:
        """Create a relationship between two entities.

        Args:
            source_entity_type: Type of the source entity
            source_entity_id: ID of the source entity
            relationship_type: Type of relationship (e.g., "depends_on", "has_version")
            target_entity_type: Type of the target entity
            target_entity_id: ID of the target entity

        Returns:
            True if relationship was created successfully

        Raises:
            StorageOperationError: If relationship creation fails

        Example:
            Create "depends_on" relationship from repository to external dependency
        """
        pass

    @abstractmethod
    async def find_entities_with_relationship(
        self,
        entity_type: str,
        relationship_name: str,
        target_entity_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EntityData]:
        """Find entities that have a specific relationship to target entity.

        Args:
            entity_type: Type of entities to search
            relationship_name: Name of the relationship
            target_entity_id: ID of the target entity
            limit: Maximum number of entities to return
            offset: Number of entities to skip

        Returns:
            List of EntityData objects that have the relationship

        Example:
            Find all repositories that depend on "external://pypi/requests/2.31.0"
        """
        pass

    @abstractmethod
    async def remove_relationship(
        self,
        source_entity_type: str,
        source_entity_id: str,
        relationship_type: str,
        target_entity_type: str,
        target_entity_id: str,
    ) -> bool:
        """Remove a specific relationship between two entities.

        Args:
            source_entity_type: Type of the source entity
            source_entity_id: ID of the source entity
            relationship_type: Type of relationship to remove
            target_entity_type: Type of the target entity
            target_entity_id: ID of the target entity

        Returns:
            True if relationship was removed successfully

        Raises:
            StorageOperationError: If relationship removal fails
        """
        pass

    @abstractmethod
    async def remove_relationships_by_type(
        self,
        source_entity_type: str,
        source_entity_id: str,
        relationship_type: str,
    ) -> int:
        """Remove all relationships of a specific type from an entity.

        Args:
            source_entity_type: Type of the source entity
            source_entity_id: ID of the source entity
            relationship_type: Type of relationships to remove

        Returns:
            Number of relationships removed

        Raises:
            StorageOperationError: If relationship removal fails
        """
        pass

    @abstractmethod
    async def get_entity_relationships(
        self, entity_type: str, entity_id: str
    ) -> list[RelationshipData]:
        """Get all relationships for an entity.

        Args:
            entity_type: Type of the entity
            entity_id: ID of the entity

        Returns:
            List of RelationshipData objects for the entity

        Example:
            Returns relationships like "depends_on", "internal_depends_on"
            with their target entities
        """
        pass

    # System Operations

    @abstractmethod
    async def get_system_metrics(self) -> SystemMetrics:
        """Get system-wide metrics for monitoring and analytics.

        Returns:
            SystemMetrics with entity counts, storage info, etc.
        """
        pass

    @abstractmethod
    async def execute_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> QueryResult:
        """Execute raw backend query for advanced use cases.

        Args:
            query: Backend-specific query string
            variables: Optional query variables

        Returns:
            QueryResult with execution results and metadata

        Raises:
            StorageQueryError: If query execution fails

        Warning:
            This method bypasses the abstraction layer and should
            only be used for advanced use cases.
        """
        pass

    # Dry Run Operations (for apply --dry-run)

    @abstractmethod
    async def dry_run_apply(self, entities: list[dict[str, Any]]) -> DryRunResult:
        """Simulate applying entities without making changes.

        This method performs all validation and preparation steps
        that would be done during actual storage, but does not
        commit any changes to the backend.

        Args:
            entities: List of entity data to simulate storing

        Returns:
            DryRunResult with detailed simulation results
        """
        pass
