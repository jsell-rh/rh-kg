# Dgraph Storage Interface Specification

## Overview

This specification defines the storage interface for interacting with Dgraph, including connection management, CRUD operations, query patterns, and error handling. The interface abstracts Dgraph specifics to enable testing and potential future database migrations.

## Storage Interface Contract

### Abstract Storage Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from kg.core.models import Repository, ExternalDependency, KnowledgeGraphFile

class StorageInterface(ABC):
    """Abstract interface for knowledge graph storage operations."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to storage backend."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to storage backend."""
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check storage backend health and return status."""
        pass

    @abstractmethod
    async def load_schemas(self, schema_dir: str) -> dict[str, EntitySchema]:
        """Load entity schemas from directory."""
        pass

    @abstractmethod
    async def reload_schemas(self) -> dict[str, EntitySchema]:
        """Reload schemas and update backend schema."""
        pass

    # Generic entity operations
    @abstractmethod
    async def store_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_data: dict[str, Any],
        metadata: dict[str, Any]
    ) -> str:
        """Store or update entity. Returns entity ID."""
        pass

    @abstractmethod
    async def get_entity(self, entity_type: str, entity_id: str) -> Optional[dict[str, Any]]:
        """Retrieve entity by type and ID. Returns None if not found."""
        pass

    @abstractmethod
    async def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    async def list_entities(
        self,
        entity_type: str,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List entities of given type with optional filtering."""
        pass

    # Generic relationship operations
    @abstractmethod
    async def find_entities_with_relationship(
        self,
        entity_type: str,
        relationship_name: str,
        target_entity_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Find entities that have a specific relationship to target entity."""
        pass

    @abstractmethod
    async def get_entity_relationships(
        self,
        entity_type: str,
        entity_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Get all relationships for an entity, grouped by relationship type."""
        pass

    # System operations
    @abstractmethod
    async def get_system_metrics(self) -> dict[str, Any]:
        """Get system-wide metrics."""
        pass

    @abstractmethod
    async def execute_query(self, query: str, variables: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Execute raw backend query for advanced use cases."""
        pass
```

## Dgraph Implementation

### Connection Management

#### Configuration

```python
from pydantic_settings import BaseSettings

class DgraphSettings(BaseSettings):
    """Dgraph connection settings."""

    endpoint: str = "localhost:9080"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Authentication (production)
    username: Optional[str] = None
    password: Optional[str] = None

    # TLS (production)
    use_tls: bool = False
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None

    class Config:
        env_prefix = "DGRAPH_"
```

#### Connection Lifecycle

```python
class DgraphStorage(StorageInterface):
    """Dgraph implementation of storage interface."""

    def __init__(self, settings: DgraphSettings, schema_dir: str = "schemas/"):
        self.settings = settings
        self.schema_dir = schema_dir
        self.client: Optional[pydgraph.DgraphClient] = None
        self.stub: Optional[pydgraph.DgraphClientStub] = None
        self.entity_schemas: Optional[dict[str, EntitySchema]] = None
        self.schema_loader: Optional[FileSchemaLoader] = None

    async def connect(self) -> None:
        """Establish connection to Dgraph."""
        try:
            # Create gRPC channel
            if self.settings.use_tls:
                credentials = grpc.ssl_channel_credentials(
                    root_certificates=self._load_ca_cert(),
                    private_key=self._load_client_key(),
                    certificate_chain=self._load_client_cert(),
                )
                channel = grpc.secure_channel(self.settings.endpoint, credentials)
            else:
                channel = grpc.insecure_channel(self.settings.endpoint)

            # Create Dgraph client
            self.stub = pydgraph.DgraphClientStub(channel)
            self.client = pydgraph.DgraphClient(self.stub)

            # Test connection
            await self._verify_connection()

        except Exception as e:
            raise StorageConnectionError(f"Failed to connect to Dgraph: {e}")

    async def disconnect(self) -> None:
        """Close connection to Dgraph."""
        if self.stub:
            self.stub.close()
            self.stub = None
            self.client = None

    async def health_check(self) -> dict[str, Any]:
        """Check Dgraph health."""
        if not self.client:
            return {"status": "disconnected"}

        try:
            start_time = time.time()
            # Simple query to test responsiveness
            query = "{ health(func: has(dgraph.type)) { count(uid) } }"
            response = self.client.txn(read_only=True).query(query)
            response_time_ms = (time.time() - start_time) * 1000

            return {
                "status": "healthy",
                "response_time_ms": round(response_time_ms, 2),
                "dgraph_version": self._get_dgraph_version(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
```

### Schema Management

#### Dynamic Schema Initialization

```python
from kg.core.schema_loader import FileSchemaLoader, DgraphSchemaGenerator

async def initialize_schema(self) -> None:
    """Initialize or update Dgraph schema from schema files."""
    try:
        # Load entity schemas from files
        schema_loader = FileSchemaLoader(schema_dir="schemas/")
        entity_schemas = await schema_loader.load_schemas()

        # Generate Dgraph schema
        schema_generator = DgraphSchemaGenerator(entity_schemas)
        dgraph_schema = await schema_generator.generate_schema()

        # Apply schema to Dgraph
        operation = pydgraph.Operation(schema=dgraph_schema)
        await self.client.alter(operation)

        # Store reference to loaded schemas
        self.entity_schemas = entity_schemas

    except Exception as e:
        raise StorageOperationError(f"Failed to initialize schema: {e}")

async def reload_schema(self) -> None:
    """Reload schema from files and update Dgraph."""
    await self.initialize_schema()
```

### Entity Operations

#### Generic Store Entity

```python
async def store_entity(
    self,
    entity_type: str,
    entity_id: str,
    entity_data: dict[str, Any],
    metadata: dict[str, Any]
) -> str:
    """Store or update entity in Dgraph using dynamic schema."""

    # Get entity schema
    entity_schema = self.entity_schemas.get(entity_type)
    if not entity_schema:
        raise StorageOperationError(f"Unknown entity type: {entity_type}")

    # Build entity data for Dgraph
    dgraph_data = await self._build_entity_data(
        entity_schema, entity_id, entity_data, metadata
    )

    # Process relationships
    await self._process_entity_relationships(
        entity_schema, entity_id, entity_data, dgraph_data
    )

    # Execute mutation
    txn = self.client.txn()
    try:
        # Check if entity exists
        existing_uid = await self._get_entity_uid(entity_type, entity_id, txn)
        if existing_uid:
            dgraph_data["uid"] = existing_uid
            # Clear existing relationships before adding new ones
            await self._clear_entity_relationships(entity_schema, existing_uid, txn)
        else:
            dgraph_data["created_at"] = datetime.utcnow().isoformat() + "Z"

        # Execute mutation
        mutation = pydgraph.Mutation(set_json=json.dumps(dgraph_data))
        response = txn.mutate(mutation)
        await txn.commit()

        return entity_id

    except Exception as e:
        await txn.discard()
        raise StorageOperationError(f"Failed to store {entity_type}: {e}")

async def _build_entity_data(
    self,
    entity_schema: EntitySchema,
    entity_id: str,
    entity_data: dict[str, Any],
    metadata: dict[str, Any]
) -> dict[str, Any]:
    """Build Dgraph entity data from schema and input data."""

    dgraph_data = {
        "uid": f"_:{entity_id}",
        "dgraph.type": entity_schema.dgraph_type,
        "id": entity_id,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }

    # Add metadata fields based on schema
    for field in entity_schema.required_fields + entity_schema.optional_fields:
        if field.name in entity_data:
            dgraph_data[field.name] = entity_data[field.name]

    # Add readonly fields from metadata
    for field in entity_schema.readonly_fields:
        if field.name in metadata:
            dgraph_data[field.name] = metadata[field.name]

    return dgraph_data

async def _process_entity_relationships(
    self,
    entity_schema: EntitySchema,
    entity_id: str,
    entity_data: dict[str, Any],
    dgraph_data: dict[str, Any]
) -> None:
    """Process entity relationships based on schema."""

    for relationship in entity_schema.relationships:
        if relationship.name in entity_data:
            relationship_targets = entity_data[relationship.name]

            if relationship_targets:
                processed_targets = []

                for target_ref in relationship_targets:
                    if target_ref.startswith("external://"):
                        # Auto-create external dependency if needed
                        target_uid = await self._ensure_external_dependency(target_ref)
                    else:
                        # Resolve internal entity reference
                        target_uid = await self._resolve_entity_reference(target_ref)

                    processed_targets.append({"uid": target_uid})

                dgraph_data[relationship.name] = processed_targets
```

#### Generic Get Entity

```python
async def get_entity(self, entity_type: str, entity_id: str) -> Optional[dict[str, Any]]:
    """Retrieve entity by type and ID using dynamic schema."""

    # Get entity schema
    entity_schema = self.entity_schemas.get(entity_type)
    if not entity_schema:
        raise StorageQueryError(f"Unknown entity type: {entity_type}")

    # Build dynamic query
    query = await self._build_get_entity_query(entity_schema)
    variables = {"$id": entity_id}

    try:
        txn = self.client.txn(read_only=True)
        response = txn.query(query, variables=variables)
        data = json.loads(response.json)

        entities = data.get("entity", [])
        if not entities:
            return None

        entity_data = entities[0]
        return await self._parse_entity_data(entity_schema, entity_data)

    except Exception as e:
        raise StorageQueryError(f"Failed to get {entity_type}: {e}")

async def _build_get_entity_query(self, entity_schema: EntitySchema) -> str:
    """Build Dgraph query for getting entity based on schema."""

    # Collect all fields to query
    fields = ["uid", "id"]

    # Add metadata fields
    for field in entity_schema.required_fields + entity_schema.optional_fields + entity_schema.readonly_fields:
        fields.append(field.name)

    # Add relationships with their target fields
    for relationship in entity_schema.relationships:
        if relationship.direction in ["outbound", "bidirectional"]:
            # For outbound relationships, get target entity details
            target_fields = ["id", "dgraph.type"]
            fields.append(f"{relationship.name} {{ {' '.join(target_fields)} }}")

    field_list = "\n            ".join(fields)

    return f"""
    query GetEntity($id: string) {{
        entity(func: eq(id, $id)) @filter(type({entity_schema.dgraph_type})) {{
            {field_list}
        }}
    }}
    """

async def _parse_entity_data(
    self, entity_schema: EntitySchema, raw_data: dict[str, Any]
) -> dict[str, Any]:
    """Parse raw Dgraph data into structured entity data."""

    parsed_data = {
        "id": raw_data.get("id"),
        "entity_type": entity_schema.entity_type,
        "metadata": {},
        "relationships": {},
    }

    # Extract metadata fields
    for field in entity_schema.required_fields + entity_schema.optional_fields + entity_schema.readonly_fields:
        if field.name in raw_data:
            parsed_data["metadata"][field.name] = raw_data[field.name]

    # Extract relationships
    for relationship in entity_schema.relationships:
        if relationship.name in raw_data:
            parsed_data["relationships"][relationship.name] = raw_data[relationship.name]

    return parsed_data
```

#### Generic List Entities

```python
async def list_entities(
    self,
    entity_type: str,
    filters: Optional[dict[str, Any]] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List entities of given type with optional filtering using dynamic schema."""

    # Get entity schema
    entity_schema = self.entity_schemas.get(entity_type)
    if not entity_schema:
        raise StorageQueryError(f"Unknown entity type: {entity_type}")

    # Build dynamic query
    query = await self._build_list_entities_query(entity_schema, filters)
    variables = {"$limit": limit, "$offset": offset}

    # Add filter variables
    if filters:
        for i, (field, value) in enumerate(filters.items()):
            variables[f"$filter_{i}"] = value

    try:
        txn = self.client.txn(read_only=True)
        response = txn.query(query, variables=variables)
        data = json.loads(response.json)

        entities = []
        for entity_data in data.get("entities", []):
            parsed_entity = await self._parse_entity_data(entity_schema, entity_data)
            entities.append(parsed_entity)

        return entities

    except Exception as e:
        raise StorageQueryError(f"Failed to list {entity_type}: {e}")

async def _build_list_entities_query(
    self, entity_schema: EntitySchema, filters: Optional[dict[str, Any]] = None
) -> str:
    """Build Dgraph query for listing entities based on schema."""

    # Collect all fields to query
    fields = ["uid", "id"]

    # Add metadata fields
    for field in entity_schema.required_fields + entity_schema.optional_fields + entity_schema.readonly_fields:
        fields.append(field.name)

    # Add relationships with their target fields
    for relationship in entity_schema.relationships:
        if relationship.direction in ["outbound", "bidirectional"]:
            target_fields = ["id", "dgraph.type"]
            fields.append(f"{relationship.name} {{ {' '.join(target_fields)} }}")
        if relationship.cardinality in ["one_to_many", "many_to_many"]:
            # Add count for multi-value relationships
            fields.append(f"{relationship.name}_count: count({relationship.name})")

    field_list = "\n            ".join(fields)

    # Build filter conditions
    filter_conditions = [f"type({entity_schema.dgraph_type})"]
    if filters:
        for i, (field, value) in enumerate(filters.items()):
            filter_conditions.append(f'eq({field}, $filter_{i})')

    filter_clause = " AND ".join(filter_conditions)

    return f"""
    query ListEntities($limit: int, $offset: int) {{
        entities(func: type({entity_schema.dgraph_type}),
                first: $limit,
                offset: $offset) @filter({filter_clause}) {{
            {field_list}
        }}
    }}
    """
```

### Dependency Operations

#### Ensure External Dependency

```python
async def _ensure_external_dependency(self, dep_ref: str) -> str:
    """Ensure external dependency exists, create if needed."""
    # Parse dependency reference
    parts = dep_ref.replace("external://", "").split("/")
    ecosystem = parts[0]
    package = "/".join(parts[1:-1])
    version = parts[-1]

    package_id = f"external://{ecosystem}/{package}"
    version_id = dep_ref

    txn = self.client.txn()
    try:
        # Check if package exists
        package_uid = await self._get_or_create_package(
            package_id, ecosystem, package, txn
        )

        # Check if version exists
        version_uid = await self._get_or_create_version(
            version_id, ecosystem, package, version, package_uid, txn
        )

        await txn.commit()
        return version_uid

    except Exception as e:
        await txn.discard()
        raise StorageOperationError(f"Failed to ensure dependency: {e}")
```

#### Generic Find Entities with Relationship

```python
async def find_entities_with_relationship(
    self,
    entity_type: str,
    relationship_name: str,
    target_entity_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Find entities that have a specific relationship to target entity using dynamic schema."""

    # Get entity schema
    entity_schema = self.entity_schemas.get(entity_type)
    if not entity_schema:
        raise StorageQueryError(f"Unknown entity type: {entity_type}")

    # Find relationship definition
    relationship = next(
        (r for r in entity_schema.relationships if r.name == relationship_name),
        None
    )
    if not relationship:
        raise StorageQueryError(
            f"Unknown relationship '{relationship_name}' for entity type '{entity_type}'"
        )

    # Build query based on relationship direction
    if relationship.direction == "outbound":
        # Find entities that point TO the target
        query = await self._build_outbound_relationship_query(
            entity_schema, relationship_name, target_entity_id
        )
    elif relationship.direction == "inbound":
        # Find entities that are pointed to BY the target (reverse lookup)
        query = await self._build_inbound_relationship_query(
            entity_schema, relationship_name, target_entity_id
        )
    else:  # bidirectional
        # Find entities in either direction
        query = await self._build_bidirectional_relationship_query(
            entity_schema, relationship_name, target_entity_id
        )

    variables = {
        "$target_id": target_entity_id,
        "$limit": limit,
        "$offset": offset
    }

    try:
        txn = self.client.txn(read_only=True)
        response = txn.query(query, variables=variables)
        data = json.loads(response.json)

        entities = []
        for entity_data in data.get("entities", []):
            parsed_entity = await self._parse_entity_data(entity_schema, entity_data)
            entities.append(parsed_entity)

        return entities

    except Exception as e:
        raise StorageQueryError(f"Failed to find entities with relationship: {e}")

async def _build_outbound_relationship_query(
    self, entity_schema: EntitySchema, relationship_name: str, target_entity_id: str
) -> str:
    """Build query for finding entities with outbound relationship to target."""
    fields = await self._get_entity_query_fields(entity_schema)
    field_list = "\n            ".join(fields)

    return f"""
    query FindEntitiesWithRelationship($target_id: string, $limit: int, $offset: int) {{
        target(func: eq(id, $target_id)) {{
            ~{relationship_name} (first: $limit, offset: $offset) @filter(type({entity_schema.dgraph_type})) {{
                {field_list}
            }}
        }}
    }}
    """

async def _build_inbound_relationship_query(
    self, entity_schema: EntitySchema, relationship_name: str, target_entity_id: str
) -> str:
    """Build query for finding entities with inbound relationship from target."""
    fields = await self._get_entity_query_fields(entity_schema)
    field_list = "\n            ".join(fields)

    return f"""
    query FindEntitiesWithRelationship($target_id: string, $limit: int, $offset: int) {{
        source(func: eq(id, $target_id)) {{
            {relationship_name} (first: $limit, offset: $offset) @filter(type({entity_schema.dgraph_type})) {{
                {field_list}
            }}
        }}
    }}
    """

async def _get_entity_query_fields(self, entity_schema: EntitySchema) -> list[str]:
    """Get all queryable fields for an entity schema."""
    fields = ["uid", "id"]

    # Add metadata fields
    for field in entity_schema.required_fields + entity_schema.optional_fields + entity_schema.readonly_fields:
        fields.append(field.name)

    # Add relationships with their target fields
    for relationship in entity_schema.relationships:
        if relationship.direction in ["outbound", "bidirectional"]:
            target_fields = ["id", "dgraph.type"]
            fields.append(f"{relationship.name} {{ {' '.join(target_fields)} }}")

    return fields
```

### Analytics Operations

#### Get Entity Relationships

```python
async def get_entity_relationships(
    self,
    entity_type: str,
    entity_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Get all relationships for an entity, grouped by relationship type using dynamic schema."""

    # Get entity schema
    entity_schema = self.entity_schemas.get(entity_type)
    if not entity_schema:
        raise StorageQueryError(f"Unknown entity type: {entity_type}")

    # Build query to get all relationships
    query = await self._build_relationships_query(entity_schema)
    variables = {"$id": entity_id}

    try:
        txn = self.client.txn(read_only=True)
        response = txn.query(query, variables=variables)
        data = json.loads(response.json)

        entities = data.get("entity", [])
        if not entities:
            return {}

        entity_data = entities[0]
        relationships = {}

        # Extract relationships based on schema
        for relationship in entity_schema.relationships:
            if relationship.name in entity_data:
                relationships[relationship.name] = entity_data[relationship.name]
            else:
                relationships[relationship.name] = []

        return relationships

    except Exception as e:
        raise StorageQueryError(f"Failed to get entity relationships: {e}")

async def _build_relationships_query(self, entity_schema: EntitySchema) -> str:
    """Build query to get all relationships for an entity."""

    # Collect relationship fields with target details
    relationship_fields = []
    for relationship in entity_schema.relationships:
        if relationship.direction in ["outbound", "bidirectional"]:
            target_fields = ["uid", "id", "dgraph.type"]
            relationship_fields.append(
                f"{relationship.name} {{ {' '.join(target_fields)} }}"
            )

    field_list = "\n            ".join(["uid", "id"] + relationship_fields)

    return f"""
    query GetEntityRelationships($id: string) {{
        entity(func: eq(id, $id)) @filter(type({entity_schema.dgraph_type})) {{
            {field_list}
        }}
    }}
    """
```

### Error Handling

#### Custom Exceptions

```python
class StorageError(Exception):
    """Base exception for storage operations."""
    pass

class StorageConnectionError(StorageError):
    """Error connecting to storage backend."""
    pass

class StorageOperationError(StorageError):
    """Error performing storage operation."""
    pass

class StorageQueryError(StorageError):
    """Error executing storage query."""
    pass

class StorageValidationError(StorageError):
    """Error validating storage data."""
    pass
```

#### Error Handling Patterns

```python
async def _handle_dgraph_error(self, error: Exception) -> None:
    """Handle Dgraph-specific errors and convert to storage errors."""
    error_msg = str(error)

    if "connection" in error_msg.lower():
        raise StorageConnectionError(f"Dgraph connection error: {error}")
    elif "parse" in error_msg.lower() or "syntax" in error_msg.lower():
        raise StorageQueryError(f"Invalid query syntax: {error}")
    elif "timeout" in error_msg.lower():
        raise StorageOperationError(f"Operation timeout: {error}")
    else:
        raise StorageOperationError(f"Dgraph operation failed: {error}")
```

### Testing Support

#### Mock Storage Implementation

```python
class MockStorage(StorageInterface):
    """In-memory mock storage for testing."""

    def __init__(self):
        self.entities: dict[str, dict[str, dict[str, Any]]] = {}  # entity_type -> entity_id -> data
        self.connected = False
        self.entity_schemas: dict[str, EntitySchema] = {}

    async def connect(self) -> None:
        """Mock connection."""
        self.connected = True

    async def disconnect(self) -> None:
        """Mock disconnection."""
        self.connected = False

    async def health_check(self) -> dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy" if self.connected else "disconnected",
            "response_time_ms": 1.0,
        }

    async def load_schemas(self, schema_dir: str) -> dict[str, EntitySchema]:
        """Mock schema loading."""
        # Return empty schemas for testing
        return self.entity_schemas

    async def reload_schemas(self) -> dict[str, EntitySchema]:
        """Mock schema reload."""
        return self.entity_schemas

    async def store_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_data: dict[str, Any],
        metadata: dict[str, Any]
    ) -> str:
        """Store entity in memory."""
        if entity_type not in self.entities:
            self.entities[entity_type] = {}

        self.entities[entity_type][entity_id] = {
            "id": entity_id,
            "entity_type": entity_type,
            "metadata": entity_data,
            **metadata
        }
        return entity_id

    async def get_entity(self, entity_type: str, entity_id: str) -> Optional[dict[str, Any]]:
        """Get entity from memory."""
        return self.entities.get(entity_type, {}).get(entity_id)

    async def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete entity from memory."""
        if entity_type in self.entities and entity_id in self.entities[entity_type]:
            del self.entities[entity_type][entity_id]
            return True
        return False

    async def list_entities(
        self,
        entity_type: str,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List entities from memory with basic filtering."""
        entities = list(self.entities.get(entity_type, {}).values())

        # Apply basic filtering
        if filters:
            filtered_entities = []
            for entity in entities:
                match = True
                for field, value in filters.items():
                    if entity.get(field) != value:
                        match = False
                        break
                if match:
                    filtered_entities.append(entity)
            entities = filtered_entities

        # Apply pagination
        return entities[offset:offset + limit]

    async def find_entities_with_relationship(
        self,
        entity_type: str,
        relationship_name: str,
        target_entity_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Mock relationship finding."""
        # Basic implementation for testing
        return []

    async def get_entity_relationships(
        self,
        entity_type: str,
        entity_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Mock relationship retrieval."""
        return {}

    async def get_system_metrics(self) -> dict[str, Any]:
        """Mock system metrics."""
        total_entities = sum(len(entities) for entities in self.entities.values())
        return {
            "total_entities": total_entities,
            "entity_types": len(self.entities),
            "connected": self.connected
        }

    async def execute_query(self, query: str, variables: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Mock query execution."""
        return {"mock": True, "query": query}
```

### Performance Considerations

#### Connection Pooling

```python
class DgraphConnectionPool:
    """Connection pool for Dgraph clients."""

    def __init__(self, settings: DgraphSettings, pool_size: int = 10):
        self.settings = settings
        self.pool_size = pool_size
        self.pool: queue.Queue[pydgraph.DgraphClient] = queue.Queue(pool_size)
        self._initialize_pool()

    def get_client(self) -> pydgraph.DgraphClient:
        """Get client from pool."""
        try:
            return self.pool.get_nowait()
        except queue.Empty:
            return self._create_client()

    def return_client(self, client: pydgraph.DgraphClient) -> None:
        """Return client to pool."""
        try:
            self.pool.put_nowait(client)
        except queue.Full:
            # Pool is full, close this client
            client.close()
```

#### Query Optimization

```python
# Use specific predicates instead of broad traversals
# Good:
query = "{ repos(func: eq(namespace, $ns)) { id name } }"

# Avoid:
query = "{ repos(func: type(Repository)) @filter(eq(namespace, $ns)) { id name } }"

# Use pagination for large result sets
query = """
{
    repos(func: type(Repository), first: $limit, offset: $offset) {
        id name
    }
}
"""

# Cache frequently accessed data
@lru_cache(maxsize=128, ttl=300)  # 5-minute cache
async def get_popular_packages(self) -> list[dict[str, Any]]:
    """Get cached popular packages."""
    # Implementation
```

This storage specification provides a complete abstraction layer over Dgraph while maintaining performance and enabling testability.
