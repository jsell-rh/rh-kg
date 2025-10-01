# MCP Server Specification

## Overview

This specification defines the Model Context Protocol (MCP) server for AI-native access to the knowledge graph. The MCP server provides read-only GraphQL query capabilities to AI assistants like Claude Code, enabling conversational graph exploration and dependency analysis.

### Key Principles

1. **Read-Only Operations**: The MCP server MUST reject all mutation operations
2. **Network-Accessible Service**: Runs as HTTP/SSE service, not subprocess (enables multi-user access, authentication, load balancing)
3. **GraphQL Native**: Leverages Dgraph's auto-generated GraphQL endpoint
4. **AI-Optimized**: Designed for conversational, iterative querying by AI assistants
5. **Zero Custom Resolvers**: Uses Dgraph's native GraphQL generation from entity schemas
6. **Security First**: Multiple layers of validation and enforcement

## Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────┐
│                     Knowledge Graph System                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐                    ┌──────────────┐       │
│  │  AI Clients  │                    │  Human/Apps  │       │
│  │ (Claude Code)│                    │  (CI/CD)     │       │
│  └──────┬───────┘                    └──────┬───────┘       │
│         │                                    │               │
│         │ MCP Protocol                       │ HTTP/REST     │
│         │ (SSE/HTTP)                         │               │
│         ▼                                    ▼               │
│  ┌──────────────┐                    ┌──────────────┐       │
│  │  MCP Server  │                    │  REST API    │       │
│  │              │                    │              │       │
│  │ - Resources  │                    │ - Submit     │       │
│  │ - Tools      │                    │ - Validate   │       │
│  │ - Prompts    │                    │ - Health     │       │
│  │              │                    │              │       │
│  │ READ-ONLY    │                    │ READ/WRITE   │       │
│  └──────┬───────┘                    └──────┬───────┘       │
│         │                                    │               │
│         │ GraphQL (queries only)             │ DQL/GraphQL   │
│         │                                    │ (all ops)     │
│         ▼                                    ▼               │
│  ┌─────────────────────────────────────────────────┐        │
│  │              Dgraph Database                     │        │
│  │                                                  │        │
│  │  - Native GraphQL Endpoint (auto-generated)     │        │
│  │  - Schema from entity YAML files                │        │
│  │  - Graph storage and querying                   │        │
│  └─────────────────────────────────────────────────┘        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### MCP Server

- Accept MCP protocol requests (SSE/HTTP transport)
- Run as network-accessible service alongside REST API
- Provide schema discovery resources
- Expose GraphQL query tools
- Provide common query prompt templates
- **Validate read-only operations** (no mutations)
- Forward validated queries to Dgraph GraphQL endpoint

#### Dgraph Database

- Auto-generate GraphQL schema from entity definitions
- Execute GraphQL queries
- Return graph data
- Enforce read-only permissions for MCP service account

## Read-Only Validation

### Validation Strategy

The MCP server uses **defense in depth** with multiple layers of protection:

1. **Layer 1: GraphQL AST Parsing** (Primary)
   - Parse incoming GraphQL queries into Abstract Syntax Tree
   - Inspect operation definitions for mutation operations
   - Reject queries containing `mutation` operations
   - Fast fail with clear error messages

2. **Layer 2: Database Permissions** (Backstop)
   - Dgraph service account for MCP has read-only permissions
   - Prevents mutations even if validation is bypassed
   - Security backstop

### Implementation Approach

#### GraphQL AST Validation

Uses the `graphql-core` library to parse and validate queries:

```python
from graphql import parse, DocumentNode, OperationDefinitionNode, GraphQLError

def validate_read_only_query(query: str) -> tuple[bool, str | None]:
    """Validate that GraphQL query contains only read operations.

    Args:
        query: GraphQL query string to validate

    Returns:
        (is_valid, error_message): Tuple of validation result and error if invalid

    Raises:
        ValidationError: Never raises, returns validation errors as tuple
    """
    try:
        # Parse GraphQL query into Abstract Syntax Tree
        document: DocumentNode = parse(query)

        # Inspect each operation definition in the document
        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                # Check operation type
                if definition.operation == "mutation":
                    operation_name = definition.name.value if definition.name else "anonymous"
                    return (
                        False,
                        f"Mutation operation '{operation_name}' is not allowed. "
                        f"The MCP server only permits read-only query operations."
                    )
                elif definition.operation == "subscription":
                    operation_name = definition.name.value if definition.name else "anonymous"
                    return (
                        False,
                        f"Subscription operation '{operation_name}' is not supported. "
                        f"Only query operations are permitted."
                    )

        # All operations are queries or introspection - valid
        return (True, None)

    except GraphQLError as e:
        return (False, f"Invalid GraphQL syntax: {str(e)}")
```

### Allowed Operations

#### ✅ Allowed

- **Query operations**: `query { repository { name } }`
- **Introspection queries**: `{ __schema { types { name } } }`
- **Anonymous queries**: `{ repository { name } }` (implicitly a query)
- **Fragments**: Field selections within queries
- **Variables**: Query parameters
- **Multiple queries**: Multiple query operations in one document

#### ❌ Rejected

- **Mutation operations**: `mutation { createRepository(...) { id } }`
- **Subscription operations**: `subscription { repositoryUpdated { id } }`
- **Mixed operations**: Documents containing both queries and mutations

### Edge Cases

1. **Field names containing "mutation"**:
   - Example: `{ repository { mutation_count } }`
   - Result: ✅ Allowed (AST parsing handles this correctly)

2. **Comments mentioning mutations**:
   - Example: `# This mutation is disabled \n query { ... }`
   - Result: ✅ Allowed (comments are ignored by parser)

3. **String values containing "mutation"**:
   - Example: `query { search(keyword: "mutation") { name } }`
   - Result: ✅ Allowed (string values don't affect operation type)

4. **Empty documents**:
   - Example: `""`
   - Result: ❌ Rejected (invalid GraphQL syntax)

5. **Only fragments, no operations**:
   - Example: `fragment Repo on Repository { name }`
   - Result: ❌ Rejected (no executable operations)

## MCP Protocol Implementation

### Server Metadata

```json
{
  "name": "kg-server",
  "version": "1.0.0",
  "description": "Red Hat Knowledge Graph MCP Server - Read-only GraphQL query access",
  "capabilities": {
    "resources": true,
    "tools": true,
    "prompts": true
  },
  "transport": ["sse", "http"]
}
```

### Resources

Resources expose read-only data that clients can subscribe to.

#### `kg://schema`

GraphQL schema introspection.

```json
{
  "uri": "kg://schema",
  "name": "GraphQL Schema",
  "description": "Complete GraphQL schema for the knowledge graph",
  "mimeType": "application/graphql"
}
```

**Response**:

```graphql
type Repository {
  id: ID!
  namespace: String!
  name: String!
  owners: [String!]!
  git_repo_url: String!
  depends_on: [ExternalDependencyVersion!]
  internal_depends_on: [Repository!]
  created_at: DateTime!
  updated_at: DateTime!
}

type ExternalDependencyPackage {
  id: ID!
  ecosystem: String!
  package_name: String!
  has_version: [ExternalDependencyVersion!]
}

type ExternalDependencyVersion {
  id: ID!
  ecosystem: String!
  package_name: String!
  version: String!
  package: ExternalDependencyPackage!
  referenced_by: [Repository!]
}

type Query {
  repository(namespace: String!, name: String!): Repository
  queryRepository(
    filter: RepositoryFilter
    order: RepositoryOrder
    first: Int
    offset: Int
  ): [Repository!]!

  externalDependencyPackage(
    ecosystem: String!
    package_name: String!
  ): ExternalDependencyPackage
  queryExternalDependencyPackage(
    filter: ExternalDependencyPackageFilter
    first: Int
    offset: Int
  ): [ExternalDependencyPackage!]!

  externalDependencyVersion(
    ecosystem: String!
    package_name: String!
    version: String!
  ): ExternalDependencyVersion
  queryExternalDependencyVersion(
    filter: ExternalDependencyVersionFilter
    first: Int
    offset: Int
  ): [ExternalDependencyVersion!]!
}

# Note: No mutations exposed in MCP server context
```

#### `kg://schema/types`

List of entity types in the knowledge graph.

```json
{
  "uri": "kg://schema/types",
  "name": "Entity Types",
  "description": "List of all entity types available in the knowledge graph",
  "mimeType": "application/json"
}
```

**Response**:

```json
{
  "entity_types": [
    {
      "name": "Repository",
      "description": "Code repository entity representing a git repository",
      "schema_version": "1.0.0",
      "fields": [
        { "name": "namespace", "type": "String!", "required": true },
        { "name": "name", "type": "String!", "required": true },
        { "name": "owners", "type": "[String!]!", "required": true },
        { "name": "git_repo_url", "type": "String!", "required": true }
      ],
      "relationships": [
        {
          "name": "depends_on",
          "target_type": "ExternalDependencyVersion",
          "cardinality": "many"
        },
        {
          "name": "internal_depends_on",
          "target_type": "Repository",
          "cardinality": "many"
        }
      ]
    },
    {
      "name": "ExternalDependencyPackage",
      "description": "External package from an ecosystem (pypi, npm, etc.)",
      "schema_version": "1.0.0",
      "fields": [
        { "name": "ecosystem", "type": "String!", "required": true },
        { "name": "package_name", "type": "String!", "required": true }
      ],
      "relationships": [
        {
          "name": "has_version",
          "target_type": "ExternalDependencyVersion",
          "cardinality": "many"
        }
      ]
    },
    {
      "name": "ExternalDependencyVersion",
      "description": "Specific version of an external package",
      "schema_version": "1.0.0",
      "fields": [
        { "name": "ecosystem", "type": "String!", "required": true },
        { "name": "package_name", "type": "String!", "required": true },
        { "name": "version", "type": "String!", "required": true }
      ],
      "relationships": [
        {
          "name": "package",
          "target_type": "ExternalDependencyPackage",
          "cardinality": "one"
        },
        {
          "name": "referenced_by",
          "target_type": "Repository",
          "cardinality": "many"
        }
      ]
    }
  ]
}
```

#### `kg://entities/{type}`

List entities of a specific type.

```json
{
  "uri": "kg://entities/repository",
  "name": "Repository List",
  "description": "List of all repository entities",
  "mimeType": "application/json"
}
```

**Example Response**:

```json
{
  "entity_type": "repository",
  "total_count": 347,
  "sample_entities": [
    {
      "id": "rosa-hcp/rosa-hcp-service",
      "namespace": "rosa-hcp",
      "name": "rosa-hcp-service"
    },
    {
      "id": "shared-utils/logging-library",
      "namespace": "shared-utils",
      "name": "logging-library"
    }
  ],
  "namespaces": ["rosa-hcp", "shared-utils", "openshift-auth"]
}
```

### Tools

Tools allow the AI assistant to execute operations.

#### `query_graph`

Execute a read-only GraphQL query against the knowledge graph.

**Input Schema**:

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "GraphQL query to execute (read-only, no mutations allowed)"
    },
    "variables": {
      "type": "object",
      "description": "Optional variables for the GraphQL query",
      "additionalProperties": true
    }
  },
  "required": ["query"]
}
```

**Example Request**:

```json
{
  "query": "query GetRepo($namespace: String!, $name: String!) {\n  repository(namespace: $namespace, name: $name) {\n    id\n    owners\n    git_repo_url\n    depends_on {\n      id\n      ecosystem\n      package_name\n      version\n    }\n  }\n}",
  "variables": {
    "namespace": "rosa-hcp",
    "name": "rosa-hcp-service"
  }
}
```

**Success Response**:

```json
{
  "data": {
    "repository": {
      "id": "rosa-hcp/rosa-hcp-service",
      "owners": ["rosa-team@redhat.com"],
      "git_repo_url": "https://github.com/openshift/rosa-hcp-service",
      "depends_on": [
        {
          "id": "external://pypi/requests/2.31.0",
          "ecosystem": "pypi",
          "package_name": "requests",
          "version": "2.31.0"
        }
      ]
    }
  }
}
```

**Error Response (Mutation Attempted)**:

```json
{
  "error": {
    "type": "validation_error",
    "message": "Mutation operation 'CreateRepo' is not allowed. The MCP server only permits read-only query operations.",
    "details": {
      "operation_type": "mutation",
      "operation_name": "CreateRepo"
    }
  }
}
```

**Error Response (Invalid GraphQL)**:

```json
{
  "error": {
    "type": "graphql_syntax_error",
    "message": "Invalid GraphQL syntax: Syntax Error: Expected Name, found '}'",
    "details": {
      "line": 3,
      "column": 5
    }
  }
}
```

#### `find_dependencies`

Find all dependencies of a repository (convenience wrapper for common query).

**Input Schema**:

```json
{
  "type": "object",
  "properties": {
    "namespace": {
      "type": "string",
      "description": "Repository namespace"
    },
    "name": {
      "type": "string",
      "description": "Repository name"
    },
    "type": {
      "type": "string",
      "enum": ["all", "external", "internal"],
      "description": "Filter by dependency type",
      "default": "all"
    },
    "ecosystem": {
      "type": "string",
      "description": "Filter external dependencies by ecosystem (pypi, npm, etc.)",
      "optional": true
    }
  },
  "required": ["namespace", "name"]
}
```

**Example Request**:

```json
{
  "namespace": "rosa-hcp",
  "name": "rosa-hcp-service",
  "type": "external",
  "ecosystem": "pypi"
}
```

**Response**:

```json
{
  "repository": {
    "id": "rosa-hcp/rosa-hcp-service",
    "namespace": "rosa-hcp",
    "name": "rosa-hcp-service"
  },
  "dependencies": {
    "external": [
      {
        "id": "external://pypi/requests/2.31.0",
        "ecosystem": "pypi",
        "package_name": "requests",
        "version": "2.31.0"
      },
      {
        "id": "external://pypi/pydantic/2.5.0",
        "ecosystem": "pypi",
        "package_name": "pydantic",
        "version": "2.5.0"
      }
    ],
    "internal": []
  },
  "summary": {
    "total_external": 2,
    "total_internal": 0,
    "ecosystems": ["pypi"]
  }
}
```

#### `find_dependents`

Find all repositories that depend on a specific package (reverse dependency lookup).

**Input Schema**:

```json
{
  "type": "object",
  "properties": {
    "ecosystem": {
      "type": "string",
      "description": "Package ecosystem (pypi, npm, etc.)"
    },
    "package_name": {
      "type": "string",
      "description": "Package name"
    },
    "version": {
      "type": "string",
      "description": "Specific version (optional - if omitted, shows all versions)",
      "optional": true
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of results",
      "default": 50,
      "maximum": 200
    }
  },
  "required": ["ecosystem", "package_name"]
}
```

**Example Request**:

```json
{
  "ecosystem": "pypi",
  "package_name": "requests",
  "version": "2.31.0",
  "limit": 20
}
```

**Response**:

```json
{
  "package": {
    "ecosystem": "pypi",
    "package_name": "requests",
    "version_filter": "2.31.0"
  },
  "dependents": [
    {
      "id": "rosa-hcp/rosa-hcp-service",
      "namespace": "rosa-hcp",
      "name": "rosa-hcp-service",
      "owners": ["rosa-team@redhat.com"],
      "dependency_version": "2.31.0"
    },
    {
      "id": "shared-utils/http-client",
      "namespace": "shared-utils",
      "name": "http-client",
      "owners": ["platform-team@redhat.com"],
      "dependency_version": "2.31.0"
    }
  ],
  "summary": {
    "total_dependents": 12,
    "unique_repositories": 12,
    "versions_in_use": ["2.31.0", "2.30.0", "2.28.1"]
  }
}
```

#### `traverse_graph`

Advanced graph traversal with custom path patterns.

**Input Schema**:

```json
{
  "type": "object",
  "properties": {
    "start_node": {
      "type": "object",
      "description": "Starting node for traversal",
      "properties": {
        "entity_type": { "type": "string" },
        "id": { "type": "string" }
      },
      "required": ["entity_type", "id"]
    },
    "path": {
      "type": "string",
      "description": "Graph traversal path pattern (e.g., 'depends_on.package.has_version')",
      "examples": [
        "depends_on.referenced_by",
        "internal_depends_on.depends_on",
        "depends_on.package.has_version"
      ]
    },
    "max_depth": {
      "type": "integer",
      "description": "Maximum traversal depth",
      "default": 3,
      "maximum": 10
    }
  },
  "required": ["start_node", "path"]
}
```

**Example Request** (Find transitive dependencies):

```json
{
  "start_node": {
    "entity_type": "repository",
    "id": "rosa-hcp/rosa-hcp-service"
  },
  "path": "internal_depends_on.depends_on",
  "max_depth": 3
}
```

**Response**:

```json
{
  "traversal": {
    "start_node": {
      "entity_type": "repository",
      "id": "rosa-hcp/rosa-hcp-service"
    },
    "path": "internal_depends_on.depends_on",
    "max_depth": 3,
    "results": [
      {
        "depth": 1,
        "node": {
          "entity_type": "repository",
          "id": "shared-utils/logging-library",
          "namespace": "shared-utils",
          "name": "logging-library"
        },
        "path_from_start": ["internal_depends_on"]
      },
      {
        "depth": 2,
        "node": {
          "entity_type": "external_dependency_version",
          "id": "external://pypi/structlog/23.1.0",
          "ecosystem": "pypi",
          "package_name": "structlog",
          "version": "23.1.0"
        },
        "path_from_start": ["internal_depends_on", "depends_on"]
      }
    ],
    "summary": {
      "total_nodes_visited": 15,
      "unique_nodes": 12,
      "max_depth_reached": 2
    }
  }
}
```

### Prompts

Prompts provide template queries for common use cases.

#### `analyze-dependencies`

Analyze dependencies for a repository.

```json
{
  "name": "analyze-dependencies",
  "description": "Analyze all dependencies for a repository, including transitive dependencies",
  "arguments": [
    {
      "name": "namespace",
      "description": "Repository namespace",
      "required": true
    },
    {
      "name": "name",
      "description": "Repository name",
      "required": true
    }
  ]
}
```

**Generated Prompt**:

```
Analyze all dependencies for the repository {namespace}/{name}:

1. List all direct external dependencies
2. List all direct internal dependencies
3. Identify any outdated package versions
4. Find transitive dependencies (dependencies of dependencies)
5. Highlight any circular dependencies
6. Suggest dependency consolidation opportunities

Use the query_graph and traverse_graph tools to explore the dependency graph.
```

#### `find-package-usage`

Find all repositories using a specific package.

```json
{
  "name": "find-package-usage",
  "description": "Find all repositories that depend on a specific package",
  "arguments": [
    {
      "name": "ecosystem",
      "description": "Package ecosystem (pypi, npm, etc.)",
      "required": true
    },
    {
      "name": "package_name",
      "description": "Package name",
      "required": true
    }
  ]
}
```

**Generated Prompt**:

```
Find all repositories that use the package {ecosystem}/{package_name}:

1. Show all versions of this package in use
2. List repositories for each version
3. Identify the most commonly used version
4. Highlight repositories using outdated versions
5. Show the owner teams for affected repositories

Use the find_dependents tool and query_graph for detailed information.
```

#### `explore-namespace`

Explore all entities in a namespace.

```json
{
  "name": "explore-namespace",
  "description": "Explore all repositories and relationships within a namespace",
  "arguments": [
    {
      "name": "namespace",
      "description": "Namespace to explore",
      "required": true
    }
  ]
}
```

**Generated Prompt**:

```
Explore the {namespace} namespace:

1. List all repositories in this namespace
2. Show ownership information
3. Map internal dependencies between repositories in this namespace
4. List external dependencies used by this namespace
5. Identify the most heavily depended-upon repositories

Use query_graph with filters to explore the namespace systematically.
```

## Security & Performance

### Query Complexity Limits

To prevent expensive queries, the MCP server enforces:

1. **Depth Limit**: Maximum query depth of 10 levels
2. **Complexity Score**: Maximum query complexity of 10,000 points
   - Each field: 1 point
   - Each array field: 10 points × expected items
   - Each nested level: multiplier of 2
3. **Timeout**: Maximum query execution time of 30 seconds
4. **Rate Limiting**: Maximum 100 queries per minute per client

**Example Complexity Calculation**:

```graphql
query {
  queryRepository(first: 100) {
    # 100 items
    name # 1 × 100 = 100
    depends_on {
      # 10 × 100 = 1000 (nested array)
      package_name # 1 × 1000 = 1000
      referenced_by {
        # 10 × 1000 = 10000 (nested array)
        name # Would exceed limit
      }
    }
  }
}
# Total complexity: ~12,100 - REJECTED (exceeds 10,000 limit)
```

### Database Permissions

The MCP server connects to Dgraph using a dedicated service account with restricted permissions:

```yaml
# Dgraph ACL configuration for MCP service account
user: mcp-server
groups:
  - read-only

permissions:
  read-only:
    - predicate: "*"
      permission: "read"
    - predicate: "*"
      permission: "query"
```

This ensures that even if validation is bypassed, mutations cannot be executed at the database level.

### Error Message Sanitization

Error messages are sanitized to prevent information leakage while remaining helpful:

**Internal Error** (Dgraph connection failure):

```json
{
  "error": {
    "type": "internal_error",
    "message": "Unable to execute query due to a system error",
    "request_id": "req_abc123",
    "timestamp": "2025-01-15T14:22:00Z"
  }
}
```

**User Error** (Invalid query):

```json
{
  "error": {
    "type": "validation_error",
    "message": "Invalid GraphQL syntax: Expected Name, found '}'",
    "help": "Check your GraphQL query syntax. The query must be valid GraphQL."
  }
}
```

### Audit Logging

All MCP queries are logged with:

- Client identifier (if available)
- Query text (sanitized)
- Variables (sanitized)
- Execution time
- Result status (success/error)
- Validation result

**Example Audit Log Entry**:

```json
{
  "timestamp": "2025-01-15T14:22:00Z",
  "event_type": "mcp_query",
  "client_id": "claude-code-session-abc123",
  "query_hash": "sha256:...",
  "query_summary": "query GetRepo($namespace: String!, $name: String!)",
  "variables": { "namespace": "rosa-hcp", "name": "rosa-hcp-service" },
  "validation": {
    "read_only": true,
    "complexity_score": 45,
    "depth": 3
  },
  "execution": {
    "status": "success",
    "duration_ms": 156,
    "rows_returned": 1
  }
}
```

## Implementation Checklist

### Phase 1: Core MCP Server

- [ ] Implement MCP protocol handler (FastMCP)
- [ ] Add SSE transport layer for streaming responses
- [ ] Add HTTP transport layer for request/response
- [ ] Implement network server (host/port configuration)
- [ ] Add GraphQL AST validation for read-only enforcement
- [ ] Create Dgraph GraphQL client wrapper
- [ ] Implement error handling and sanitization
- [ ] Add comprehensive logging

### Phase 2: Resources

- [ ] Implement `kg://schema` resource (GraphQL introspection)
- [ ] Implement `kg://schema/types` resource (entity type listing)
- [ ] Implement `kg://entities/{type}` resource (entity listings)

### Phase 3: Tools

- [ ] Implement `query_graph` tool (raw GraphQL execution)
- [ ] Implement `find_dependencies` tool
- [ ] Implement `find_dependents` tool
- [ ] Implement `traverse_graph` tool

### Phase 4: Prompts

- [ ] Create `analyze-dependencies` prompt template
- [ ] Create `find-package-usage` prompt template
- [ ] Create `explore-namespace` prompt template

### Phase 5: Security & Performance

- [ ] Implement query complexity analysis
- [ ] Add query depth limits
- [ ] Configure Dgraph ACL for MCP service account
- [ ] Implement rate limiting
- [ ] Add query timeouts
- [ ] Create audit logging system

### Phase 6: Deployment & Infrastructure

- [ ] Create systemd service unit file
- [ ] Create Docker container with health checks
- [ ] Configure reverse proxy (nginx/tracer) for SSL termination
- [ ] Set up load balancer configuration for horizontal scaling
- [ ] Create Kubernetes deployment manifests (if applicable)
- [ ] Configure monitoring and alerting (Prometheus/Grafana)

### Phase 7: Testing & Documentation

- [ ] Unit tests for read-only validation
- [ ] Integration tests with Dgraph
- [ ] MCP protocol compliance tests
- [ ] Load testing for concurrent client scenarios
- [ ] Performance benchmarks
- [ ] User documentation with examples
- [ ] Deployment runbook for operations
- [ ] Troubleshooting guide

## Usage Examples

### Example 1: Basic Repository Query

**AI Assistant Request**:

> "Show me information about the rosa-hcp-service repository"

**MCP Tool Call**:

```json
{
  "tool": "query_graph",
  "arguments": {
    "query": "query GetRepo {\n  repository(namespace: \"rosa-hcp\", name: \"rosa-hcp-service\") {\n    id\n    owners\n    git_repo_url\n    depends_on {\n      ecosystem\n      package_name\n      version\n    }\n  }\n}"
  }
}
```

**Response**:

```json
{
  "data": {
    "repository": {
      "id": "rosa-hcp/rosa-hcp-service",
      "owners": ["rosa-team@redhat.com"],
      "git_repo_url": "https://github.com/openshift/rosa-hcp-service",
      "depends_on": [
        {
          "ecosystem": "pypi",
          "package_name": "requests",
          "version": "2.31.0"
        },
        { "ecosystem": "pypi", "package_name": "pydantic", "version": "2.5.0" }
      ]
    }
  }
}
```

### Example 2: Find Package Dependents

**AI Assistant Request**:

> "Which repositories use the requests package from PyPI?"

**MCP Tool Call**:

```json
{
  "tool": "find_dependents",
  "arguments": {
    "ecosystem": "pypi",
    "package_name": "requests",
    "limit": 50
  }
}
```

**Response**:

```json
{
  "package": {
    "ecosystem": "pypi",
    "package_name": "requests"
  },
  "dependents": [
    {
      "id": "rosa-hcp/rosa-hcp-service",
      "namespace": "rosa-hcp",
      "name": "rosa-hcp-service",
      "owners": ["rosa-team@redhat.com"],
      "dependency_version": "2.31.0"
    },
    {
      "id": "shared-utils/http-client",
      "namespace": "shared-utils",
      "name": "http-client",
      "owners": ["platform-team@redhat.com"],
      "dependency_version": "2.30.0"
    }
  ],
  "summary": {
    "total_dependents": 12,
    "versions_in_use": ["2.31.0", "2.30.0", "2.28.1"]
  }
}
```

### Example 3: Transitive Dependency Analysis

**AI Assistant Request**:

> "What are the transitive dependencies of rosa-hcp-service through its internal dependencies?"

**MCP Tool Call**:

```json
{
  "tool": "traverse_graph",
  "arguments": {
    "start_node": {
      "entity_type": "repository",
      "id": "rosa-hcp/rosa-hcp-service"
    },
    "path": "internal_depends_on.depends_on",
    "max_depth": 3
  }
}
```

**Response**:

```json
{
  "traversal": {
    "results": [
      {
        "depth": 1,
        "node": {
          "entity_type": "repository",
          "id": "shared-utils/logging-library"
        }
      },
      {
        "depth": 2,
        "node": {
          "entity_type": "external_dependency_version",
          "id": "external://pypi/structlog/23.1.0"
        }
      }
    ],
    "summary": {
      "total_nodes_visited": 8,
      "unique_nodes": 6
    }
  }
}
```

### Example 4: Rejected Mutation Attempt

**AI Assistant Request** (incorrectly tries to modify):

> "Create a new repository called test-repo"

**MCP Tool Call**:

```json
{
  "tool": "query_graph",
  "arguments": {
    "query": "mutation CreateRepo {\n  createRepository(input: {namespace: \"test\", name: \"test-repo\", ...}) {\n    id\n  }\n}"
  }
}
```

**Error Response**:

```json
{
  "error": {
    "type": "validation_error",
    "message": "Mutation operation 'CreateRepo' is not allowed. The MCP server only permits read-only query operations.",
    "details": {
      "operation_type": "mutation",
      "operation_name": "CreateRepo"
    },
    "help": "Use the REST API at /api/v1/graph/submit to modify the knowledge graph. The MCP server is read-only."
  }
}
```

## Deployment

### Running the MCP Server

The MCP server runs as a network-accessible service alongside the REST API:

**Development (Local)**:

```bash
# Start the MCP server on port 8001
kg mcp serve --host 0.0.0.0 --port 8001
```

**Production (Service)**:

```bash
# Run as systemd service
sudo systemctl start kg-mcp-server

# Or via Docker
docker run -p 8001:8001 \
  -e KG_DGRAPH_URL=http://dgraph:8080 \
  kg-server mcp serve
```

**Configuration**:

```yaml
# /etc/kg/mcp-server.yaml
server:
  host: 0.0.0.0
  port: 8001
  transport: sse # Primary transport
  enable_http: true # Also support HTTP for compatibility

dgraph:
  url: http://localhost:8080
  graphql_endpoint: /graphql

security:
  max_query_complexity: 10000
  max_query_depth: 10
  query_timeout_seconds: 30
  rate_limit_per_minute: 100

logging:
  level: info
  format: json
  audit_log_path: /var/log/kg/mcp-audit.log
```

### Default Endpoints

- **SSE Endpoint**: `http://localhost:8001/mcp/sse`
- **HTTP Endpoint**: `http://localhost:8001/mcp/http`
- **Health Check**: `http://localhost:8001/mcp/health`
- **Server Info**: `http://localhost:8001/mcp/info`

## Integration with Claude Code

### Configuration

Users configure the MCP server in their Claude Code settings to connect to the network service:

```json
{
  "mcpServers": {
    "kg-server": {
      "url": "http://localhost:8001/mcp/sse",
      "transport": "sse",
      "name": "Knowledge Graph Server"
    }
  }
}
```

**Production Configuration**:

```json
{
  "mcpServers": {
    "kg-server": {
      "url": "https://kg.redhat.com/mcp/sse",
      "transport": "sse",
      "name": "Knowledge Graph Server",
      "headers": {
        "Authorization": "Bearer ${KG_MCP_TOKEN}"
      }
    }
  }
}
```

### Conversational Usage

Once configured, users can conversationally query the knowledge graph:

**User**: "What dependencies does the rosa-hcp-service use?"

**Claude Code**: Uses the `find_dependencies` tool automatically:

```
The rosa-hcp-service repository has the following dependencies:

External Dependencies (PyPI):
- requests 2.31.0
- pydantic 2.5.0
- fastapi 0.104.0
- sqlalchemy 2.0.0

Internal Dependencies:
- shared-utils/logging-library
- shared-utils/config-loader

Total: 4 external, 2 internal dependencies
```

**User**: "Which teams own the internal dependencies?"

**Claude Code**: Follows up with additional queries:

```
The internal dependencies are owned by:

- shared-utils/logging-library → Platform Team (platform-team@redhat.com)
- shared-utils/config-loader → Platform Team (platform-team@redhat.com)

Both internal dependencies are owned by the Platform Team.
```

**User**: "Are any of the PyPI packages outdated?"

**Claude Code**: Would typically fetch latest versions (outside MCP scope) and compare:

```
Based on the versions in the knowledge graph:
- requests 2.31.0 (in use) - Latest is 2.31.0 ✓
- pydantic 2.5.0 (in use) - Latest is 2.5.3 (minor update available)
- fastapi 0.104.0 (in use) - Latest is 0.109.0 (minor updates available)
- sqlalchemy 2.0.0 (in use) - Latest is 2.0.25 (patch updates available)

Recommendations:
- Consider updating pydantic, fastapi, and sqlalchemy
- All are backward-compatible minor/patch updates
- Test in development environment first
```

## Comparison: MCP vs REST

### When to Use MCP Server

- ✅ Exploratory data analysis
- ✅ Conversational querying by AI assistants
- ✅ Complex graph traversals
- ✅ Iterative dependency analysis
- ✅ Ad-hoc investigations
- ✅ Development and debugging

### When to Use REST API

- ✅ Submitting/updating repository data
- ✅ CI/CD pipeline integrations
- ✅ Automated validation workflows
- ✅ Traditional application integrations
- ✅ Webhook triggers
- ✅ Batch operations

### Capabilities Comparison

| Capability            | MCP Server             | REST API                |
| --------------------- | ---------------------- | ----------------------- |
| **Read Operations**   | ✅ GraphQL queries     | ✅ Predefined endpoints |
| **Write Operations**  | ❌ Read-only           | ✅ Submit/Update        |
| **Query Flexibility** | ✅ Arbitrary GraphQL   | ⚠️ Fixed endpoints      |
| **Graph Traversal**   | ✅ Native GraphQL      | ⚠️ Limited              |
| **AI Integration**    | ✅ Native MCP protocol | ⚠️ Requires custom code |
| **Rate Limiting**     | ✅ Per-client          | ✅ Per-token            |
| **Authentication**    | ⚠️ Local/development   | ✅ Production tokens    |
| **Audit Logging**     | ✅ Query-level         | ✅ Operation-level      |

## Future Enhancements

### Planned Features

1. **Subscription Support**: Real-time updates for graph changes
2. **Query Result Caching**: Cache frequently accessed queries
3. **Saved Queries**: Named queries for common patterns
4. **Query Optimization Hints**: Suggest more efficient queries
5. **Visual Graph Explorer**: MCP resource for graph visualization data
6. **Aggregation Tools**: Built-in analytics and metrics tools
7. **Export Tools**: Export query results to CSV/JSON/YAML

### Research Topics

1. **Query Cost Prediction**: Estimate query cost before execution
2. **Automatic Query Optimization**: Rewrite inefficient queries
3. **Federated Queries**: Query multiple knowledge graphs
4. **Natural Language to GraphQL**: Convert NL queries to GraphQL
