"""Mock storage implementation for testing and development.

This module provides an in-memory mock storage that implements the
StorageInterface using strongly-typed Pydantic models. It's useful
for testing and development scenarios where a real storage backend
is not available.
"""

from datetime import datetime
import time
from typing import Any

from ..core import EntitySchema, FileSchemaLoader
from .exceptions import StorageOperationError
from .interface import StorageInterface
from .models import (
    DryRunResult,
    EntityCounts,
    EntityData,
    EntityOperation,
    HealthCheckResult,
    HealthStatus,
    QueryResult,
    RelationshipData,
    SystemMetrics,
    ValidationIssue,
)


class MockStorage(StorageInterface):
    """In-memory mock storage for testing and development.

    This implementation stores all data in memory using dictionaries
    and provides basic filtering and relationship support. All operations
    return strongly-typed Pydantic models.

    Useful for:
    - Unit testing
    - Development without external dependencies
    - Integration testing
    - Demonstrating the storage interface
    """

    def __init__(self) -> None:
        """Initialize mock storage with empty data structures."""
        # entity_type -> entity_id -> entity_data
        self.entities: dict[str, dict[str, dict[str, Any]]] = {}
        self.connected = False
        self.entity_schemas: dict[str, EntitySchema] = {}
        self.connection_time: datetime | None = None

    # Connection Management

    async def connect(self) -> None:
        """Mock connection - always succeeds."""
        self.connected = True
        self.connection_time = datetime.utcnow()

    async def disconnect(self) -> None:
        """Mock disconnection."""
        self.connected = False
        self.connection_time = None

    async def health_check(self) -> HealthCheckResult:
        """Mock health check with realistic response times."""
        # Simulate some response time
        response_time = 1.0 + (time.time() % 5.0)

        return HealthCheckResult(
            status=HealthStatus.HEALTHY
            if self.connected
            else HealthStatus.DISCONNECTED,
            response_time_ms=response_time,
            backend_version="mock-1.0.0",
            additional_info={
                "entities_stored": sum(
                    len(entities) for entities in self.entities.values()
                ),
                "schema_types": len(self.entity_schemas),
                "memory_usage_mb": 1.5,  # Mock memory usage
            },
        )

    # Schema Management

    async def load_schemas(self, schema_dir: str) -> dict[str, EntitySchema]:
        """Load schemas using the real schema loader."""
        try:
            schema_loader = FileSchemaLoader(schema_dir)
            self.entity_schemas = await schema_loader.load_schemas()
            return self.entity_schemas
        except Exception as e:
            raise StorageOperationError(f"Failed to load schemas: {e}") from e

    async def reload_schemas(self) -> dict[str, EntitySchema]:
        """Mock schema reload - returns current schemas."""
        return self.entity_schemas

    # Entity Operations

    async def store_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_data: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:
        """Store entity in memory with timestamps."""
        if entity_type not in self.entities:
            self.entities[entity_type] = {}

        # Build complete entity data
        system_metadata = {
            **metadata,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        # Add created_at if this is a new entity
        if entity_id not in self.entities[entity_type]:
            system_metadata["created_at"] = datetime.utcnow().isoformat() + "Z"

        complete_data = {
            "id": entity_id,
            "entity_type": entity_type,
            "metadata": entity_data.copy(),
            "system_metadata": system_metadata,
        }

        self.entities[entity_type][entity_id] = complete_data
        return entity_id

    async def get_entity(self, entity_type: str, entity_id: str) -> EntityData | None:
        """Get entity from memory and return as EntityData model."""
        entity_data = self.entities.get(entity_type, {}).get(entity_id)
        if not entity_data:
            return None

        return EntityData(
            id=entity_data["id"],
            entity_type=entity_data["entity_type"],
            metadata=entity_data.get("metadata", {}),
            relationships=self._extract_relationships(entity_data),
            system_metadata=entity_data.get("system_metadata", {}),
        )

    async def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity from memory."""
        if entity_type in self.entities and entity_id in self.entities[entity_type]:
            del self.entities[entity_type][entity_id]
            return True
        return False

    async def list_entities(
        self,
        entity_type: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EntityData]:
        """List entities with basic filtering and pagination."""
        entities_data = list(self.entities.get(entity_type, {}).values())

        # Apply basic filtering
        if filters:
            filtered_entities = []
            for entity in entities_data:
                match = True
                for field, value in filters.items():
                    # Check in both metadata and system_metadata
                    entity_value = entity.get("metadata", {}).get(field) or entity.get(
                        "system_metadata", {}
                    ).get(field)
                    if entity_value != value:
                        match = False
                        break
                if match:
                    filtered_entities.append(entity)
            entities_data = filtered_entities

        # Apply pagination
        paginated_entities = entities_data[offset : offset + limit]

        # Convert to EntityData models
        result = []
        for entity_data in paginated_entities:
            result.append(
                EntityData(
                    id=entity_data["id"],
                    entity_type=entity_data["entity_type"],
                    metadata=entity_data.get("metadata", {}),
                    relationships=self._extract_relationships(entity_data),
                    system_metadata=entity_data.get("system_metadata", {}),
                )
            )

        return result

    # Reference Validation

    async def entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists across all entity types."""
        for entity_type_data in self.entities.values():
            if entity_id in entity_type_data:
                return True
        return False

    # Relationship Operations

    async def find_entities_with_relationship(
        self,
        entity_type: str,
        relationship_name: str,
        target_entity_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EntityData]:
        """Find entities with specific relationship (basic implementation)."""
        # Basic implementation - searches through all entities
        matching_entities = []

        for _entity_id, entity_data in self.entities.get(entity_type, {}).items():
            entity_relationships = entity_data.get("metadata", {})
            if relationship_name in entity_relationships:
                relationship_targets = entity_relationships[relationship_name]
                if (
                    isinstance(relationship_targets, list)
                    and target_entity_id in relationship_targets
                ):
                    matching_entities.append(
                        EntityData(
                            id=entity_data["id"],
                            entity_type=entity_data["entity_type"],
                            metadata=entity_data.get("metadata", {}),
                            relationships=self._extract_relationships(entity_data),
                            system_metadata=entity_data.get("system_metadata", {}),
                        )
                    )

        # Apply pagination
        return matching_entities[offset : offset + limit]

    async def get_entity_relationships(
        self, entity_type: str, entity_id: str
    ) -> list[RelationshipData]:
        """Get all relationships for an entity."""
        entity_data = self.entities.get(entity_type, {}).get(entity_id)
        if not entity_data:
            return []

        relationships = []
        entity_metadata = entity_data.get("metadata", {})

        # Look for relationship fields based on loaded schemas
        if entity_type in self.entity_schemas:
            schema = self.entity_schemas[entity_type]
            for relationship in schema.relationships:
                if relationship.name in entity_metadata:
                    target_ids = entity_metadata[relationship.name]
                    if isinstance(target_ids, list):
                        # For each target, create mock EntityData
                        target_entities = []
                        for target_id in target_ids:
                            target_entities.append(
                                EntityData(
                                    id=target_id,
                                    entity_type="unknown",  # Mock doesn't track target types
                                    metadata={},
                                    relationships={},
                                    system_metadata={},
                                )
                            )

                        relationships.append(
                            RelationshipData(
                                relationship_name=relationship.name,
                                target_entities=target_entities,
                                relationship_metadata={},
                            )
                        )

        return relationships

    # System Operations

    async def get_system_metrics(self) -> SystemMetrics:
        """Get system metrics with actual counts from stored data."""
        entity_counts = EntityCounts(
            repository=len(self.entities.get("repository", {})),
            external_dependency_package=len(
                self.entities.get("external_dependency_package", {})
            ),
            external_dependency_version=len(
                self.entities.get("external_dependency_version", {})
            ),
            total=-1,
        )

        # Count relationships (simplified)
        total_relationships = 0
        for entity_type_data in self.entities.values():
            for entity_data in entity_type_data.values():
                metadata = entity_data.get("metadata", {})
                for value in metadata.values():
                    if isinstance(value, list):
                        total_relationships += len(value)

        return SystemMetrics(
            entity_counts=entity_counts,
            total_relationships=total_relationships,
            storage_size_mb=2.5,  # Mock storage size
            last_updated=datetime.utcnow(),
            backend_specific={
                "mock_implementation": True,
                "memory_entities": len(self.entities),
            },
        )

    async def execute_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> QueryResult:
        """Mock query execution."""
        start_time = time.time()

        # Mock query processing
        if "error" in query.lower():
            return QueryResult(
                success=False,
                data={},
                execution_time_ms=(time.time() - start_time) * 1000,
                error_message="Mock query error",
            )

        return QueryResult(
            success=True,
            data={"mock": True, "query": query, "variables": variables or {}},
            execution_time_ms=(time.time() - start_time) * 1000,
            backend_specific={"mock_implementation": True},
        )

    # Dry Run Operations

    async def dry_run_apply(self, entities: list[dict[str, Any]]) -> DryRunResult:
        """Simulate applying entities and return what would happen."""
        would_create = []
        would_update = []
        validation_issues = []

        for entity in entities:
            entity_type = entity.get("entity_type")
            entity_id = entity.get("entity_id")

            if not entity_type or not entity_id:
                validation_issues.append(
                    ValidationIssue(
                        severity="error",
                        message="Entity missing required entity_type or entity_id",
                        suggestion="Ensure all entities have entity_type and entity_id fields",
                    )
                )
                continue

            # Check if entity exists
            exists = entity_id in self.entities.get(entity_type, {})

            if exists:
                would_update.append(
                    EntityOperation(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        operation_type="update",
                        changes={"metadata": entity.get("metadata", {})},
                    )
                )
            else:
                would_create.append(
                    EntityOperation(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        operation_type="create",
                        changes={"metadata": entity.get("metadata", {})},
                    )
                )

        # Mock some warnings
        if len(would_create) > 5:
            validation_issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"Creating {len(would_create)} new entities",
                    suggestion="Consider applying in smaller batches",
                )
            )

        return DryRunResult(
            would_create=would_create,
            would_update=would_update,
            would_delete=[],  # Mock doesn't implement deletion detection
            validation_issues=validation_issues,
            summary={
                "total_operations": len(would_create) + len(would_update),
                "new_entities": len(would_create),
                "updated_entities": len(would_update),
            },
        )

    def _extract_relationships(
        self, entity_data: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Extract relationships from entity metadata (helper method)."""
        relationships = {}
        metadata = entity_data.get("metadata", {})

        # Look for fields that are lists (potential relationships)
        for field_name, field_value in metadata.items():
            if isinstance(field_value, list) and field_name.endswith(
                ("_on", "_to", "_from")
            ):
                relationships[field_name] = [
                    {"id": target_id, "type": "unknown"} for target_id in field_value
                ]

        return relationships
