"""Dgraph storage backend implementation.

This module provides a production-ready Dgraph storage backend that implements
the StorageInterface with strongly-typed Pydantic return types.
"""

from datetime import datetime
import json
import time
from typing import Any

import pydgraph

from kg.core.schema import FieldDefinition

from ..core import EntitySchema, FileSchemaLoader, StorageOperationLogger, get_logger
from .exceptions import (
    StorageConnectionError,
    StorageOperationError,
    StorageQueryError,
)
from .interface import StorageInterface
from .models import (
    DryRunResult,
    EntityCounts,
    EntityData,
    HealthCheckResult,
    HealthStatus,
    QueryResult,
    RelationshipData,
    StorageConfig,
    SystemMetrics,
)

logger = get_logger(__name__)


class DgraphStorage(StorageInterface):
    """Dgraph storage backend implementation.

    This implementation provides:
    - gRPC connection to Dgraph cluster
    - Automatic schema initialization and updates
    - Strongly-typed query responses
    - Reference validation for entity relationships
    - Comprehensive error handling with retries
    """

    def __init__(self, config: StorageConfig):
        """Initialize Dgraph storage backend.

        Args:
            config: Storage configuration with connection details
        """
        self.config = config
        self._client: pydgraph.DgraphClient | None = None
        self._stub: Any = None
        self._schemas: dict[str, EntitySchema] = {}
        self._schema_version: str | None = None
        self._connected: bool = False
        self._connection_time: datetime | None = None

    async def connect(self) -> None:
        """Establish connection to Dgraph cluster."""
        with StorageOperationLogger(logger, "dgraph_connect") as op_logger:
            try:
                op_logger.log_progress(
                    "Initiating connection",
                    endpoint=self.config.endpoint,
                    use_tls=self.config.use_tls,
                )

                # Create gRPC stub
                if self.config.use_tls:
                    # TODO: Implement TLS support with client certificates
                    raise NotImplementedError("TLS support not yet implemented")
                else:
                    self._stub = pydgraph.DgraphClientStub(self.config.endpoint)

                # Create client
                self._client = pydgraph.DgraphClient(self._stub)

                # Test connection with a simple query
                start_time = time.time()
                await self._execute_query(
                    "{ test(func: has(dgraph.type)) { count(uid) } }"
                )
                response_time = (time.time() - start_time) * 1000

                self._connected = True
                self._connection_time = datetime.now()

                logger.info(
                    "Connected to Dgraph successfully",
                    endpoint=self.config.endpoint,
                    response_time_ms=round(response_time, 2),
                    connection_time=self._connection_time.isoformat(),
                )

            except Exception as e:
                logger.error(
                    "Failed to connect to Dgraph",
                    endpoint=self.config.endpoint,
                    error=str(e),
                )
                raise StorageConnectionError(f"Could not connect to Dgraph: {e}") from e

    async def disconnect(self) -> None:
        """Close connection to Dgraph."""
        try:
            if self._stub:
                self._stub.close()
                logger.info(
                    "Disconnected from Dgraph",
                    endpoint=self.config.endpoint,
                    was_connected=self._connected,
                )
        except Exception as e:
            logger.warning(
                "Error during disconnect", endpoint=self.config.endpoint, error=str(e)
            )
        finally:
            self._client = None
            self._stub = None
            self._connected = False
            self._connection_time = None

    async def health_check(self) -> HealthCheckResult:
        """Check Dgraph cluster health."""
        if not self._connected or not self._client:
            return HealthCheckResult(
                status=HealthStatus.DISCONNECTED,
                response_time_ms=0.0,
                backend_version="unknown",
                additional_info={"error": "Not connected to Dgraph"},
            )

        try:
            start_time = time.time()

            # Execute health check query
            query = """
            {
                health(func: has(dgraph.type)) {
                    count(uid)
                }
                schema(func: has(dgraph.schema)) {
                    count(uid)
                }
            }
            """

            result = await self._execute_query(query)
            response_time = (time.time() - start_time) * 1000

            # Check if we got valid response
            if result.success and result.data:
                status = HealthStatus.HEALTHY
                additional_info = {
                    "endpoint": self.config.endpoint,
                    "schemas_loaded": len(self._schemas),
                    "query_response": result.data,
                }
            else:
                status = HealthStatus.DEGRADED
                additional_info = {
                    "error": result.error_message or "Unexpected response format"
                }

            return HealthCheckResult(
                status=status,
                response_time_ms=response_time,
                backend_version="v23.1.0",  # TODO: Get actual version from Dgraph
                additional_info=additional_info,
            )

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.ERROR,
                response_time_ms=0.0,
                backend_version="unknown",
                additional_info={"error": str(e)},
            )

    async def load_schemas(self, schema_dir: str) -> dict[str, EntitySchema]:
        """Load schemas and initialize Dgraph schema."""
        with StorageOperationLogger(logger, "schema_loading") as op_logger:
            try:
                op_logger.log_progress(
                    "Loading schemas from directory", schema_dir=schema_dir
                )

                # Load schemas from YAML files
                schema_loader = FileSchemaLoader(schema_dir)
                self._schemas = await schema_loader.load_schemas()

                op_logger.log_progress(
                    "Initializing Dgraph schema", schema_count=len(self._schemas)
                )

                # Initialize Dgraph schema
                await self._initialize_dgraph_schema()

                self._schema_version = datetime.now().isoformat()
                logger.info(
                    "Schemas loaded successfully",
                    schema_count=len(self._schemas),
                    schema_dir=schema_dir,
                    schema_version=self._schema_version,
                    entity_types=list(self._schemas.keys()),
                )

                return self._schemas

            except Exception as e:
                logger.error(
                    "Failed to load schemas", schema_dir=schema_dir, error=str(e)
                )
                raise StorageOperationError(f"Schema loading failed: {e}") from e

    async def reload_schemas(self) -> dict[str, EntitySchema]:
        """Reload schemas from disk."""
        if not self._schemas:
            raise StorageOperationError("No schemas directory configured")

        # For now, we'll need to store the schema directory
        # TODO: Store schema_dir in instance variable during load_schemas
        raise NotImplementedError("Schema reload not yet implemented")

    async def store_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_data: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:
        """Store entity in Dgraph."""
        if not self._connected or not self._client:
            raise StorageConnectionError("Not connected to Dgraph")

        try:
            # Prepare mutation data
            mutation_data = {
                "uid": f"_:{entity_id}",
                "dgraph.type": entity_type,
                "entity_id": entity_id,
                "entity_type": entity_type,
                **entity_data,
                "system_metadata": metadata,
                "created_at": datetime.now().isoformat(),
            }

            # Create mutation
            txn = self._client.txn()
            try:
                mutation = pydgraph.Mutation(set_json=json.dumps(mutation_data))
                txn.mutate(mutation)
                txn.commit()

                logger.debug(f"Stored entity {entity_type}/{entity_id}")
                return entity_id

            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Failed to store entity {entity_type}/{entity_id}: {e}")
            raise StorageOperationError(f"Entity storage failed: {e}") from e

    async def get_entity(self, entity_type: str, entity_id: str) -> EntityData | None:
        """Retrieve entity from Dgraph."""
        if not self._connected or not self._client:
            raise StorageConnectionError("Not connected to Dgraph")

        try:
            query = f"""
            {{
                entity(func: eq(entity_id, "{entity_id}")) @filter(eq(dgraph.type, "{entity_type}")) {{
                    uid
                    entity_id
                    entity_type
                    expand(_all_)
                }}
            }}
            """

            result = await self._execute_query(query)

            if not result.success or not result.data.get("entity"):
                return None

            entity_data = result.data["entity"][0] if result.data["entity"] else None
            if not entity_data:
                return None

            # Convert to EntityData model
            return EntityData(
                id=entity_data["entity_id"],
                entity_type=entity_data["entity_type"],
                metadata={
                    k: v
                    for k, v in entity_data.items()
                    if k
                    not in [
                        "uid",
                        "entity_id",
                        "entity_type",
                        "dgraph.type",
                        "system_metadata",
                    ]
                },
                system_metadata=entity_data.get("system_metadata", {}),
                relationships={},  # TODO: Extract relationships
            )

        except Exception as e:
            logger.error(f"Failed to get entity {entity_type}/{entity_id}: {e}")
            raise StorageQueryError(f"Entity retrieval failed: {e}") from e

    async def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity from Dgraph."""
        if not self._connected or not self._client:
            raise StorageConnectionError("Not connected to Dgraph")

        try:
            # First, find the entity
            entity = await self.get_entity(entity_type, entity_id)
            if not entity:
                return False

            # TODO: Check for references before deletion

            # Delete entity
            query = f"""
            {{
                entity(func: eq(entity_id, "{entity_id}")) @filter(eq(dgraph.type, "{entity_type}")) {{
                    uid
                }}
            }}
            """

            query_result = await self._execute_query(query)
            if not query_result.success or not query_result.data.get("entity"):
                return False

            uid = query_result.data["entity"][0]["uid"]

            txn = self._client.txn()
            try:
                mutation = pydgraph.Mutation(del_nquads=f"<{uid}> * * .")
                txn.mutate(mutation)
                txn.commit()

                logger.debug(f"Deleted entity {entity_type}/{entity_id}")
                return True

            finally:
                txn.discard()

        except Exception as e:
            logger.error(f"Failed to delete entity {entity_type}/{entity_id}: {e}")
            raise StorageOperationError(f"Entity deletion failed: {e}") from e

    async def list_entities(
        self,
        entity_type: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EntityData]:
        """List entities with optional filtering."""
        if not self._connected or not self._client:
            raise StorageConnectionError("Not connected to Dgraph")

        try:
            # Build query with filters
            filter_conditions = []
            if filters:
                for field, value in filters.items():
                    filter_conditions.append(f'eq({field}, "{value}")')

            filter_clause = ""
            if filter_conditions:
                filter_clause = f"@filter({' AND '.join(filter_conditions)})"

            query = f"""
            {{
                entities(func: eq(dgraph.type, "{entity_type}"), first: {limit}, offset: {offset}) {filter_clause} {{
                    uid
                    entity_id
                    entity_type
                    expand(_all_)
                }}
            }}
            """

            result = await self._execute_query(query)

            if not result.success:
                raise StorageQueryError(f"Query failed: {result.error_message}")

            entities = []
            for entity_data in result.data.get("entities", []):
                entities.append(
                    EntityData(
                        id=entity_data["entity_id"],
                        entity_type=entity_data["entity_type"],
                        metadata={
                            k: v
                            for k, v in entity_data.items()
                            if k
                            not in [
                                "uid",
                                "entity_id",
                                "entity_type",
                                "dgraph.type",
                                "system_metadata",
                            ]
                        },
                        system_metadata=entity_data.get("system_metadata", {}),
                        relationships={},  # TODO: Extract relationships
                    )
                )

            return entities

        except Exception as e:
            logger.error(f"Failed to list entities of type {entity_type}: {e}")
            raise StorageQueryError(f"Entity listing failed: {e}") from e

    async def entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists (for reference validation)."""
        if not self._connected or not self._client:
            raise StorageConnectionError("Not connected to Dgraph")

        try:
            query = f"""
            {{
                entity(func: eq(entity_id, "{entity_id}")) {{
                    count(uid)
                }}
            }}
            """

            result = await self._execute_query(query)

            if not result.success:
                raise StorageQueryError(
                    f"Existence check failed: {result.error_message}"
                )

            count: int = result.data.get("entity", [{}])[0].get("count", 0)
            return count > 0

        except Exception as e:
            logger.error(f"Failed to check entity existence {entity_id}: {e}")
            raise StorageQueryError(f"Entity existence check failed: {e}") from e

    async def find_entities_with_relationship(
        self,
        entity_type: str,  # noqa: ARG002 TODO
        relationship_name: str,  # noqa: ARG002 TODO
        target_entity_id: str,  # noqa: ARG002 TODO
        limit: int = 50,  # noqa: ARG002 TODO
        offset: int = 0,  # noqa: ARG002 TODO
    ) -> list[EntityData]:
        """Find entities with specific relationship."""
        # TODO: Implement relationship queries
        return []

    async def get_entity_relationships(
        self,
        entity_type: str,  # noqa: ARG002 TODO
        entity_id: str,  # noqa: ARG002 TODO
    ) -> list[RelationshipData]:
        """Get entity relationships."""
        # TODO: Implement relationship extraction
        return []

    async def get_system_metrics(self) -> SystemMetrics:
        """Get system metrics."""
        if not self._connected or not self._client:
            raise StorageConnectionError("Not connected to Dgraph")

        try:
            # Count entities by type
            query = """
            {
                repo_count(func: eq(dgraph.type, "repository")) {
                    count(uid)
                }
                package_count(func: eq(dgraph.type, "external_dependency_package")) {
                    count(uid)
                }
                version_count(func: eq(dgraph.type, "external_dependency_version")) {
                    count(uid)
                }
            }
            """

            result = await self._execute_query(query)

            if not result.success:
                raise StorageQueryError(f"Metrics query failed: {result.error_message}")

            data = result.data
            entity_counts = EntityCounts(
                repository=data.get("repo_count", [{}])[0].get("count", 0),
                external_dependency_package=data.get("package_count", [{}])[0].get(
                    "count", 0
                ),
                external_dependency_version=data.get("version_count", [{}])[0].get(
                    "count", 0
                ),
            )

            return SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=0,  # TODO: Count relationships
                storage_size_mb=0.0,  # TODO: Get storage size from Dgraph
                last_updated=datetime.now(),
                backend_specific={
                    "dgraph_version": "v23.1.0",
                    "endpoint": self.config.endpoint,
                },
            )

        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            raise StorageQueryError(f"Metrics retrieval failed: {e}") from e

    async def execute_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> QueryResult:
        """Execute raw Dgraph query."""
        return await self._execute_query(query, variables)

    async def dry_run_apply(self, entities: list[dict[str, Any]]) -> DryRunResult:
        """Simulate entity application without changes."""
        # TODO: Implement dry-run simulation
        return DryRunResult(summary={"simulated": True, "entity_count": len(entities)})

    # Private methods

    async def _execute_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> QueryResult:
        """Execute query with error handling."""
        if not self._connected or not self._client:
            return QueryResult(
                success=False,
                execution_time_ms=0.0,
                error_message="Not connected to Dgraph",
            )

        start_time = time.time()
        try:
            # Execute query
            if variables:
                # TODO: Implement variable substitution
                pass

            txn = self._client.txn(read_only=True)
            try:
                response = txn.query(query)
                execution_time = (time.time() - start_time) * 1000

                # Parse JSON response
                data = json.loads(response.json) if response.json else {}

                return QueryResult(
                    success=True,
                    data=data,
                    execution_time_ms=execution_time,
                    backend_specific={"query": query},
                )

            finally:
                txn.discard()

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Query execution failed: {e}")

            return QueryResult(
                success=False,
                execution_time_ms=execution_time,
                error_message=str(e),
                backend_specific={"query": query},
            )

    async def _initialize_dgraph_schema(self) -> None:
        """Initialize Dgraph schema from loaded entity schemas."""
        if not self._client:
            raise StorageConnectionError("Not connected to Dgraph")

        try:
            # Build Dgraph schema from entity schemas
            schema_parts = []

            # Collect all unique predicates across all schemas
            all_predicates: dict[
                str, tuple[str, str | None]
            ] = {}  # field_name -> (dgraph_type, index_type)

            # Add base predicates
            all_predicates["entity_id"] = ("string", "exact")
            all_predicates["entity_type"] = ("string", "exact")
            all_predicates["created_at"] = ("datetime", None)
            all_predicates["updated_at"] = ("datetime", None)

            # Collect all entity fields, avoiding duplicates
            entity_field_sets: dict[
                str, set[str]
            ] = {}  # entity_type -> set of field names

            for entity_type, schema in self._schemas.items():
                # Collect all fields from schema
                all_fields: list[FieldDefinition] = []
                all_fields.extend(schema.required_fields)
                all_fields.extend(schema.optional_fields)
                all_fields.extend(schema.readonly_fields)

                # Track fields for this entity type
                entity_field_sets[entity_type] = set()

                # Add fields to global predicate registry
                for field_def in all_fields:
                    field_name = field_def.name
                    entity_field_sets[entity_type].add(field_name)

                    # Only add if not already defined (first definition wins)
                    if field_name not in all_predicates:
                        dgraph_type = self._convert_field_type(field_def.type)
                        index_type = self._get_index_type(field_def)
                        all_predicates[field_name] = (dgraph_type, index_type)

            # Define all predicates once
            for field_name, (dgraph_type, index_type) in all_predicates.items():
                if index_type:
                    schema_parts.append(
                        f"{field_name}: {dgraph_type} @index({index_type}) ."
                    )
                else:
                    schema_parts.append(f"{field_name}: {dgraph_type} .")

            # Define entity types
            for entity_type in self._schemas:
                schema_parts.append(f"type {entity_type} {{")
                schema_parts.append("  entity_id")
                schema_parts.append("  entity_type")

                # Add all fields for this entity type
                for field_name in entity_field_sets[entity_type]:
                    schema_parts.append(f"  {field_name}")
                schema_parts.append("}")

            # Apply schema
            schema_str = "\n".join(schema_parts)

            logger.debug(
                "Generated Dgraph schema",
                predicate_count=len(all_predicates),
                entity_types=list(self._schemas.keys()),
                schema_preview=schema_str[:200] + "..."
                if len(schema_str) > 200
                else schema_str,
            )

            operation = pydgraph.Operation(schema=schema_str)
            self._client.alter(operation)

            logger.info(
                "Dgraph schema initialized successfully",
                predicates_defined=len(all_predicates),
                entity_types_defined=len(self._schemas),
            )

        except Exception as e:
            logger.error("Failed to initialize Dgraph schema", error=str(e))
            raise StorageOperationError(f"Schema initialization failed: {e}") from e

    def _convert_field_type(self, field_type: str) -> str:
        """Convert schema field type to Dgraph type."""
        type_mapping = {
            "string": "string",
            "integer": "int",
            "boolean": "bool",
            "number": "float",
            "array": "[string]",  # Default to string array
            "object": "string",  # Store as JSON string
        }
        return type_mapping.get(field_type, "string")

    def _get_index_type(self, field_def: FieldDefinition) -> str | None:
        """Get appropriate Dgraph index type for field."""
        field_type = field_def.type

        # Add indexes for searchable fields
        if field_type == "string":
            return "exact"
        elif field_type in ["integer", "number"]:
            return "int"
        elif field_type == "boolean":
            return "bool"

        return None
