# REST API Specification

## Overview

This specification defines the REST API endpoints for the knowledge graph server. The API provides programmatic access to repository data, dependency queries, and system management functions.

## Base Configuration

### Base URL
```
https://kg.redhat.com/api/v1
```

### Content Type
- **Request:** `application/json` or `application/yaml`
- **Response:** `application/json`

### Authentication
- **Development:** None (local development)
- **Production:** Bearer token authentication
- **Header:** `Authorization: Bearer <token>`

### Versioning
- **Strategy:** URL path versioning (`/api/v1/`)
- **Current version:** `v1`
- **Backwards compatibility:** Maintained within major versions

## Graph Submission Endpoints

### Submit Repository Data

Submit or update repository data from YAML files.

#### Endpoint
```http
POST /api/v1/graph/submit
```

#### Request Headers
```http
Content-Type: application/yaml
Authorization: Bearer <token>
X-Source-Repo: github.com/org/repo
X-Source-Commit: abc123def456
```

#### Request Body
```yaml
schema_version: "1.0.0"
namespace: "rosa-hcp"
entity:
  repository:
    - rosa-hcp-service:
        metadata:
          owners: ["rosa-team@redhat.com"]
          git_repo_url: "https://github.com/openshift/rosa-hcp-service"
        depends_on: ["external://pypi/requests/2.31.0"]
```

#### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Repository data updated successfully",
  "data": {
    "namespace": "rosa-hcp",
    "entities_processed": {
      "repositories": 1
    },
    "dependencies_processed": {
      "external_created": 2,
      "external_updated": 0,
      "internal_linked": 0
    },
    "processing_time_ms": 156
  },
  "warnings": []
}
```

#### Validation Error Response (400 Bad Request)
```json
{
  "status": "error",
  "error_type": "validation_error",
  "message": "YAML validation failed",
  "errors": [
    {
      "type": "missing_required_field",
      "field": "owners",
      "entity": "test-repo",
      "line": 8,
      "message": "Missing required field 'owners' in repository 'test-repo'",
      "help": "All repositories must specify at least one owner."
    }
  ],
  "error_count": 1
}
```

#### Conflict Error Response (409 Conflict)
```json
{
  "status": "error",
  "error_type": "ownership_conflict",
  "message": "Entity ownership conflict detected",
  "conflicts": [
    {
      "entity_id": "shared-utils/common-lib",
      "current_owners": ["team-a@redhat.com"],
      "submitted_owners": ["team-b@redhat.com"],
      "message": "Entity shared-utils/common-lib already owned by different team"
    }
  ]
}
```

#### Server Error Response (500 Internal Server Error)
```json
{
  "status": "error",
  "error_type": "internal_error",
  "message": "Internal server error occurred",
  "request_id": "req_abc123def456",
  "timestamp": "2025-01-15T14:22:00Z"
}
```

### Validate Repository Data

Validate YAML without submitting to the graph.

#### Endpoint
```http
POST /api/v1/graph/validate
```

#### Request Headers
```http
Content-Type: application/yaml
```

#### Request Body
Same YAML format as submit endpoint.

#### Success Response (200 OK)
```json
{
  "status": "valid",
  "message": "Validation successful",
  "data": {
    "schema_version": "1.0.0",
    "namespace": "rosa-hcp",
    "entities": {
      "repositories": 1
    },
    "dependencies": {
      "external": 3,
      "internal": 1
    }
  },
  "checks": [
    {"name": "schema_format", "status": "pass"},
    {"name": "required_fields", "status": "pass"},
    {"name": "dependency_references", "status": "pass"}
  ]
}
```

#### Validation Error Response (400 Bad Request)
Same format as submit endpoint validation errors.

## Query Endpoints

### Get Repository

Retrieve repository information by ID.

#### Endpoint
```http
GET /api/v1/repositories/{namespace}/{name}
```

#### Path Parameters
- `namespace` (string): Repository namespace
- `name` (string): Repository name

#### Success Response (200 OK)
```json
{
  "status": "success",
  "data": {
    "id": "rosa-hcp/rosa-hcp-service",
    "namespace": "rosa-hcp",
    "name": "rosa-hcp-service",
    "metadata": {
      "owners": ["rosa-team@redhat.com", "rosa-leads@redhat.com"],
      "git_repo_url": "https://github.com/openshift/rosa-hcp-service"
    },
    "dependencies": {
      "external": [
        {
          "id": "external://pypi/requests/2.31.0",
          "package": "requests",
          "version": "2.31.0",
          "ecosystem": "pypi"
        }
      ],
      "internal": [
        {
          "id": "shared-utils/logging-library",
          "namespace": "shared-utils",
          "name": "logging-library"
        }
      ]
    },
    "system_metadata": {
      "created_at": "2025-01-10T09:15:00Z",
      "updated_at": "2025-01-15T14:22:00Z",
      "source_repo": "github.com/openshift/rosa-hcp-service",
      "source_commit": "abc123def456"
    }
  }
}
```

#### Not Found Response (404 Not Found)
```json
{
  "status": "error",
  "error_type": "not_found",
  "message": "Repository not found",
  "requested_id": "rosa-hcp/nonexistent-repo"
}
```

### List Repositories

List repositories with optional filtering.

#### Endpoint
```http
GET /api/v1/repositories
```

#### Query Parameters
- `namespace` (string, optional): Filter by namespace
- `owner` (string, optional): Filter by owner email
- `limit` (integer, optional): Maximum results (default: 50, max: 200)
- `offset` (integer, optional): Results offset (default: 0)
- `sort` (string, optional): Sort field (name, updated_at)
- `order` (string, optional): Sort order (asc, desc, default: asc)

#### Example Request
```http
GET /api/v1/repositories?namespace=rosa-hcp&owner=rosa-team@redhat.com&limit=10&sort=updated_at&order=desc
```

#### Success Response (200 OK)
```json
{
  "status": "success",
  "data": {
    "repositories": [
      {
        "id": "rosa-hcp/rosa-hcp-service",
        "namespace": "rosa-hcp",
        "name": "rosa-hcp-service",
        "metadata": {
          "owners": ["rosa-team@redhat.com"],
          "git_repo_url": "https://github.com/openshift/rosa-hcp-service"
        },
        "dependency_count": {
          "external": 4,
          "internal": 1
        },
        "updated_at": "2025-01-15T14:22:00Z"
      }
    ],
    "pagination": {
      "total": 127,
      "limit": 10,
      "offset": 0,
      "has_more": true
    }
  }
}
```

### Get Repository Dependencies

Get detailed dependency information for a repository.

#### Endpoint
```http
GET /api/v1/repositories/{namespace}/{name}/dependencies
```

#### Query Parameters
- `type` (string, optional): Filter by dependency type (external, internal, all)
- `ecosystem` (string, optional): Filter external deps by ecosystem (pypi, npm, etc.)

#### Success Response (200 OK)
```json
{
  "status": "success",
  "data": {
    "repository_id": "rosa-hcp/rosa-hcp-service",
    "dependencies": {
      "external": [
        {
          "id": "external://pypi/requests/2.31.0",
          "package": "requests",
          "version": "2.31.0",
          "ecosystem": "pypi",
          "canonical_package_id": "external://pypi/requests"
        }
      ],
      "internal": [
        {
          "id": "shared-utils/logging-library",
          "namespace": "shared-utils",
          "name": "logging-library",
          "owners": ["platform-team@redhat.com"]
        }
      ]
    },
    "summary": {
      "total_external": 4,
      "total_internal": 1,
      "ecosystems": ["pypi", "npm"]
    }
  }
}
```

### Find Repositories Using Package

Find repositories that depend on a specific external package.

#### Endpoint
```http
GET /api/v1/packages/{ecosystem}/{package}/dependents
```

#### Path Parameters
- `ecosystem` (string): Package ecosystem (pypi, npm, etc.)
- `package` (string): Package name

#### Query Parameters
- `version` (string, optional): Specific version (if omitted, shows all versions)
- `limit` (integer, optional): Maximum results
- `offset` (integer, optional): Results offset

#### Example Request
```http
GET /api/v1/packages/pypi/requests/dependents?version=2.31.0&limit=20
```

#### Success Response (200 OK)
```json
{
  "status": "success",
  "data": {
    "package": {
      "ecosystem": "pypi",
      "name": "requests",
      "canonical_id": "external://pypi/requests"
    },
    "version_filter": "2.31.0",
    "dependents": [
      {
        "repository_id": "rosa-hcp/rosa-hcp-service",
        "namespace": "rosa-hcp",
        "name": "rosa-hcp-service",
        "owners": ["rosa-team@redhat.com"],
        "dependency_version": "2.31.0"
      }
    ],
    "summary": {
      "total_dependents": 12,
      "unique_repositories": 12,
      "versions_in_use": ["2.31.0", "2.30.0", "2.28.1"]
    },
    "pagination": {
      "total": 12,
      "limit": 20,
      "offset": 0,
      "has_more": false
    }
  }
}
```

## System Endpoints

### Health Check

Check system health and readiness.

#### Endpoint
```http
GET /api/v1/health
```

#### Success Response (200 OK)
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T14:22:00Z",
  "version": "1.0.0",
  "dependencies": {
    "dgraph": {
      "status": "healthy",
      "response_time_ms": 23
    }
  },
  "metrics": {
    "total_repositories": 347,
    "total_external_dependencies": 1205,
    "total_namespaces": 28
  }
}
```

#### Unhealthy Response (503 Service Unavailable)
```json
{
  "status": "unhealthy",
  "timestamp": "2025-01-15T14:22:00Z",
  "dependencies": {
    "dgraph": {
      "status": "error",
      "error": "Connection timeout"
    }
  }
}
```

### System Information

Get system version and configuration information.

#### Endpoint
```http
GET /api/v1/info
```

#### Success Response (200 OK)
```json
{
  "status": "success",
  "data": {
    "version": "1.0.0",
    "schema_version": "1.0.0",
    "supported_schema_versions": ["1.0.0"],
    "supported_ecosystems": ["pypi", "npm", "golang.org/x", "github.com"],
    "deployment": {
      "environment": "production",
      "deployed_at": "2025-01-10T08:00:00Z",
      "commit": "abc123def456"
    },
    "features": {
      "validation": true,
      "submission": true,
      "analytics": true
    }
  }
}
```

## Error Handling

### Error Response Format

All errors follow this standard format:

```json
{
  "status": "error",
  "error_type": "error_category",
  "message": "Human-readable error message",
  "request_id": "req_abc123def456",
  "timestamp": "2025-01-15T14:22:00Z",
  "details": {
    // Error-specific details
  }
}
```

### Error Types

#### Client Errors (4xx)

**400 Bad Request**
- `validation_error`: YAML validation failed
- `invalid_request`: Malformed request
- `unsupported_schema`: Unsupported schema version

**401 Unauthorized**
- `authentication_required`: Missing or invalid authentication
- `token_expired`: Authentication token expired

**403 Forbidden**
- `insufficient_permissions`: User lacks required permissions
- `rate_limit_exceeded`: Request rate limit exceeded

**404 Not Found**
- `not_found`: Requested resource not found
- `endpoint_not_found`: API endpoint does not exist

**409 Conflict**
- `ownership_conflict`: Entity ownership conflict
- `namespace_conflict`: Namespace ownership conflict

**422 Unprocessable Entity**
- `dependency_not_found`: Referenced dependency does not exist
- `circular_dependency`: Circular dependency detected

#### Server Errors (5xx)

**500 Internal Server Error**
- `internal_error`: Unexpected server error
- `database_error`: Database operation failed

**502 Bad Gateway**
- `upstream_error`: Dependency service unavailable

**503 Service Unavailable**
- `maintenance_mode`: System in maintenance mode
- `overloaded`: System temporarily overloaded

## Rate Limiting

### Rate Limit Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642262400
```

### Rate Limit Response (429 Too Many Requests)
```json
{
  "status": "error",
  "error_type": "rate_limit_exceeded",
  "message": "Rate limit exceeded",
  "retry_after": 60,
  "limits": {
    "requests_per_minute": 100,
    "requests_per_hour": 1000
  }
}
```

## Request/Response Examples

### Complete Submit Example

#### Request
```http
POST /api/v1/graph/submit HTTP/1.1
Host: kg.redhat.com
Content-Type: application/yaml
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Source-Repo: github.com/openshift/rosa-hcp-service
X-Source-Commit: abc123def456

schema_version: "1.0.0"
namespace: "rosa-hcp"
entity:
  repository:
    - rosa-hcp-service:
        metadata:
          owners:
            - "rosa-team@redhat.com"
            - "rosa-leads@redhat.com"
          git_repo_url: "https://github.com/openshift/rosa-hcp-service"
        depends_on:
          - "external://pypi/requests/2.31.0"
          - "external://pypi/pydantic/2.5.0"
          - "internal://shared-utils/logging-library"
```

#### Response
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: req_abc123def456

{
  "status": "success",
  "message": "Repository data updated successfully",
  "data": {
    "namespace": "rosa-hcp",
    "entities_processed": {
      "repositories": 1
    },
    "dependencies_processed": {
      "external_created": 2,
      "external_updated": 0,
      "internal_linked": 1
    },
    "processing_time_ms": 156
  },
  "warnings": []
}
```

## OpenAPI Specification

The complete OpenAPI 3.0 specification will be available at:
```
GET /api/v1/openapi.json
```

This endpoint returns the full machine-readable API specification for integration with tools like Swagger UI, Postman, and API clients.
