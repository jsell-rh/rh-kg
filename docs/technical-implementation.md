# Technical Implementation Guide

## Overview

This document provides detailed technical specifications for the Red Hat Knowledge Graph system. The architecture uses a rigid schema approach with planned evolution phases, implemented on Dgraph with GitHub Actions automation.

**Core Principles:**

- Strict validation ensuring consistent data quality
- Schema versioning for controlled evolution
- Separate governance for internal vs external entities
- Package/version separation for external dependencies
- Reference counting for safe entity deletion

## YAML Schema Specification

### Phase 1: Minimal Viable Schema

The initial schema supports only essential fields for dependency mapping and ownership tracking.

#### Repository Entity Example

```yaml
schema_version: "1.0.0"
namespace: rosa-hcp

entity:
  repository:
    - rosa-hcp-service:
        metadata:
          owners:
            - "rosa-team@redhat.com"
            - "rosa-leads@redhat.com"
          git_repo_url: "https://github.com/openshift/rosa-hcp-service"
        depends_on:
          - external://pypi/requests/2.31.0
          - external://npm/@types/node/18.15.0
          - internal://openshift-auth/auth-service

    - rosa-operator:
        metadata:
          owners:
            - "rosa-team@redhat.com"
            - "platform-team@redhat.com"
          git_repo_url: "https://github.com/openshift/rosa-operator"
        depends_on:
          - external://golang.org/x/client-go/v0.28.4
          - internal://rosa-hcp/rosa-hcp-service
```

#### Required Fields

**Global:**

- `schema_version`: Exact version string for validation and migration
- `namespace`: Explicit namespace declaration (conflicts detected across repos)

**Repository Entity:**

- `metadata.owners`: List of email addresses of owning teams (REQUIRED, minimum 1)
- `metadata.git_repo_url`: Git repository URL (REQUIRED)
- `depends_on`: List of dependency references (can be empty list, cannot be omitted)

#### Validation Rules

**Strict validation rejects:**

- Unknown fields at any level
- Invalid entity types
- Missing required fields
- Malformed email addresses
- Invalid Git repository URLs
- Invalid dependency references

**Example validation errors:**

```yaml
# ❌ INVALID - unknown field
entity:
  repository:
    - test-repo:
        custom_field: "value"  # REJECTED: unknown field

# ❌ INVALID - missing required field
entity:
  repository:
    - test-repo:
        metadata:
          owners: ["team@redhat.com"]
          # REJECTED: missing metadata.git_repo_url
        depends_on: [...]

# ❌ INVALID - malformed reference
entity:
  repository:
    - test-repo:
        metadata:
          owners: ["team@redhat.com"]
          git_repo_url: "https://github.com/redhat/test-repo"
        depends_on:
          - "invalid-reference"  # REJECTED: must be external:// or internal://
```

### External Dependency Reference Format

External dependencies use a structured URI format with automatic canonicalization.

#### Format Specification

```
external://<ecosystem>/<package>/<version>
```

**Ecosystem Detection:**

- Automatic detection from repository context (package.json → npm, requirements.txt → pypi)
- Manual specification supported: `external://pypi/requests/2.31.0`

**Examples:**

```yaml
depends_on:
  # Python packages
  - external://pypi/requests/2.31.0
  - external://pypi/django/4.2.1

  # Node.js packages
  - external://npm/express/4.18.0
  - external://npm/@types/node/18.15.0

  # Go modules
  - external://golang.org/x/client-go/v0.28.4
  - external://github.com/stretchr/testify/v1.8.0

  # Internal references
  - internal://openshift-auth/auth-service
  - internal://shared-utils/logging-library
```

#### Canonicalization Rules

The server automatically canonicalizes external dependency names to prevent duplicates:

```yaml
# These all resolve to: external://pypi/requests/2.31.0
- external://pypi/requests/2.31.0 # Canonical form
- external://pypi/python-requests/2.31.0 # Auto-corrected
- requests/2.31.0 # Context-detected (pypi)
```

## Graph Data Model

### Package/Version Separation

External dependencies are modeled as separate package and version nodes to enable both package-level and version-specific queries.

#### Node Structure

```
external://pypi/requests (package node)
├── external://pypi/requests/2.31.0 (version node)
├── external://pypi/requests/2.30.0 (version node)
└── external://pypi/requests/2.28.1 (version node)
```

#### Dgraph Schema

```graphql
type Repository {
  id: string @id
  namespace: string @index(exact)
  owners: [string] @index(exact)
  git_repo_url: string @index(exact)
  depends_on: [ExternalDependencyVersion] @reverse
  created_at: datetime
  updated_at: datetime
  source_repo: string
  source_commit: string
}

type ExternalDependencyPackage {
  id: string @id  # external://pypi/requests
  ecosystem: string @index(exact)
  name: string @index(exact)
  has_version: [ExternalDependencyVersion] @reverse
}

type ExternalDependencyVersion {
  id: string @id  # external://pypi/requests/2.31.0
  package: ExternalDependencyPackage
  version: string @index(exact)
  created_at: datetime
  first_referenced_by: string
}
```

#### Query Examples

**Find all repositories using any version of requests:**

```graphql
{
  package(func: eq(id, "external://pypi/requests")) {
    has_version {
      ~depends_on {
        id
        namespace
        owners
      }
    }
  }
}
```

**Find repositories using specific version:**

```graphql
{
  version(func: eq(id, "external://pypi/requests/2.31.0")) {
    ~depends_on {
      id
      namespace
      owners
    }
  }
}
```

## Schema System

### Inheritance Architecture

Schema definitions use inheritance to handle different governance models for internal vs external entities.

#### Base Schema Files

**schemas/base_internal.yaml:**

```yaml
base_internal:
  governance: strict
  required_metadata:
    - owner:
        type: string
        validation: email
  readonly_metadata:
    - created_at: datetime
    - updated_at: datetime
    - source_repo: string
    - source_commit: string
  allow_custom: false
  deletion_policy: reference_counted
```

**schemas/base_external.yaml:**

```yaml
base_external:
  governance: permissive
  required_metadata: []
  readonly_metadata:
    - created_at: datetime
    - first_referenced_by: string
    - reference_count: integer
  allow_custom: false
  deletion_policy: never_delete
  auto_create: true
```

#### Entity Type Schemas

**schemas/repository.yaml:**

```yaml
entity_type: repository
schema_version: "1.0.0"
extends: base_internal

required_metadata:
  owners:
    type: array
    items: string
    validation: email
    min_items: 1
    description: "List of team email addresses responsible for repository"
  git_repo_url:
    type: string
    validation: url
    description: "Git repository URL (GitHub, GitLab, etc.)"

optional_metadata: {}

valid_relationships:
  - depends_on:
      target_types: [repository, external_dependency_version]
      description: "Direct dependencies used by this repository"

validation_rules:
  - namespace_matches_owner_domain: true
  - dependency_references_exist: true
```

### Schema Versioning

Each schema file includes version information for migration management.

#### Version Format

```yaml
schema_version: "1.0.0" # Major.Minor.Patch
```

**Version semantics:**

- **Major:** Breaking changes requiring migration
- **Minor:** Backward-compatible additions
- **Patch:** Bug fixes, clarifications

#### Migration Support

**Multiple schema versions during transitions:**

```yaml
# Server supports multiple versions simultaneously
supported_schema_versions: ["1.0.0", "1.1.0"]
default_schema_version: "1.1.0"
migration_deadline: "2025-03-01"
```

**Migration script example:**

```bash
# Automated migration from 1.0.0 to 1.1.0
kg migrate --from 1.0.0 --to 1.1.0 --repo rosa-hcp/rosa-hcp-service
```

## External Dependency Handling

### Auto-Creation Logic

External dependencies are automatically created when first referenced, with smart canonicalization.

#### Creation Flow

1. **Reference Detection:** Server encounters `external://pypi/requests/2.31.0`
2. **Package Check:** Does `external://pypi/requests` exist?
3. **Package Creation:** If not, create package node
4. **Version Check:** Does `external://pypi/requests/2.31.0` exist?
5. **Version Creation:** If not, create version node and link to package
6. **Relationship Creation:** Create `depends_on` edge

#### Ecosystem Detection

**Automatic detection from repository context:**

```python
def detect_ecosystem(dependency_name, repo_files):
    if 'package.json' in repo_files:
        return 'npm'
    elif 'requirements.txt' in repo_files or 'pyproject.toml' in repo_files:
        return 'pypi'
    elif 'go.mod' in repo_files:
        return 'golang.org/x'
    elif 'Cargo.toml' in repo_files:
        return 'crates.io'
    else:
        raise ValidationError(f"Cannot detect ecosystem for {dependency_name}")
```

### Canonicalization Rules

**Package name normalization:**

```yaml
# Input variations all resolve to canonical form
input_variations:
  - "requests"
  - "python-requests"
  - "PyPI::requests"
  - "pypi/requests"

canonical_output: "external://pypi/requests"
```

**Version normalization:**

```yaml
# Version string standardization
input_variations:
  - "v2.31.0"
  - "2.31.0"
  - "==2.31.0"
  - "2.31"

canonical_output: "2.31.0"
```

## Entity Lifecycle Management

### CRUD Operations

#### Create Operation

**Repository submission via GitHub Action:**

```yaml
POST /api/v1/graph/submit
Authorization: Bearer <github-token>
Content-Type: application/yaml

schema_version: "1.0.0"
namespace: rosa-hcp
source_repo: "github.com/openshift/rosa-hcp-service"
source_commit: "abc123def456"

entity:
  repository:
    - rosa-hcp-service:
        metadata:
          owners: ["rosa-team@redhat.com"]
          git_repo_url: "https://github.com/openshift/rosa-hcp-service"
        depends_on:
          - external://pypi/requests/2.31.0
```

**Server processing:**

1. **Schema validation** against rigid v1.0.0 rules
2. **Namespace conflict check** across all repositories
3. **External dependency auto-creation** if needed
4. **Entity creation** with auto-generated metadata
5. **Audit trail creation** with source information

#### Update Operation

**Declarative updates replace entire entity:**

```yaml
# Previous state
entity:
  repository:
    - rosa-hcp-service:
        metadata:
          owners: ["rosa-team@redhat.com"]
          git_repo_url: "https://github.com/openshift/rosa-hcp-service"
        depends_on: [external://pypi/requests/2.30.0]

# New submission replaces completely
entity:
  repository:
    - rosa-hcp-service:
        metadata:
          owners: ["rosa-team@redhat.com"]
          git_repo_url: "https://github.com/openshift/rosa-hcp-service"
        depends_on:
          - external://pypi/requests/2.31.0  # Updated version
          - external://npm/express/4.18.0    # New dependency
```

**Server processing:**

1. **Diff calculation** between current and submitted state
2. **Reference counting updates** for removed dependencies
3. **New dependency creation** if needed
4. **Relationship updates** with audit trail

#### Delete Operation

**Entity removal from YAML:**

```yaml
# Repository removes entity entirely
entity:
  repository: [] # rosa-hcp-service no longer listed
```

**Server processing with reference counting:**

```python
def delete_entity(entity_id):
    # Check for references from other entities
    references = find_references(entity_id)

    if references and entity_type == 'internal':
        raise ConflictError(f"Entity {entity_id} referenced by {references}")

    # Safe to delete internal entity
    if entity_type == 'internal':
        delete_entity_and_relationships(entity_id)

    # External entities: only remove relationships, keep entity
    elif entity_type == 'external':
        remove_relationships_from(entity_id, source_repo)
        # Entity remains for other potential references
```

### Deletion Policies

**Internal entities (strict reference counting):**

- Can only be deleted if no references exist
- Deletion fails with clear error if references found
- All outbound relationships cascade deleted

**External entities (permissive):**

- Never deleted, even when no references remain
- Relationships removed when source repository deletes them
- Orphaned entities preserved for future references

## Conflict Detection

### Namespace Conflicts

**Scenario:** Two repositories claim same namespace

```yaml
# Repo A: github.com/team-a/service-x
namespace: shared-utils

# Repo B: github.com/team-b/service-y
namespace: shared-utils  # CONFLICT if teams different
```

**Resolution:** Allow multiple repos in same namespace only if same owner domain

```python
def validate_namespace_ownership(namespace, owners_list, existing_owners):
    # Check domain consistency within submitted owners
    domains = set()
    for owner_email in owners_list:
        domains.add(owner_email.split('@')[1])

    if len(domains) > 1:
        raise ConflictError(f"All owners must be from same domain, found: {domains}")

    # Check against existing namespace owners
    owner_domain = list(domains)[0]
    for existing_owner in existing_owners:
        existing_domain = existing_owner.split('@')[1]
        if existing_domain != owner_domain:
            raise ConflictError(
                f"Namespace {namespace} owned by {existing_domain}, "
                f"cannot be used by {owner_domain}"
            )
```

### Entity Ownership Conflicts

**Scenario:** Two repositories define same entity

```yaml
# Repo A
entity:
  repository:
    - shared-service:
        owners: ["team-a@redhat.com"]

# Repo B
entity:
  repository:
    - shared-service:  # CONFLICT
        owners: ["team-b@redhat.com"]
```

**Resolution:** First-come-first-served with clear error

```python
def validate_entity_ownership(entity_id, owners_list):
    existing_entity = get_entity(entity_id)

    if existing_entity:
        # Check if any existing owner is in the new owners list
        existing_owners = set(existing_entity.owners)
        new_owners = set(owners_list)

        if not existing_owners.intersection(new_owners):
            raise ConflictError(
                f"Entity {entity_id} already owned by {existing_entity.owners}, "
                f"cannot be claimed by {owners_list}"
            )
```

## API Specification

### REST Endpoints

#### Graph Submission

```http
POST /api/v1/graph/submit
Authorization: Bearer <token>
Content-Type: application/yaml

# Returns 200 OK or 400 Bad Request with validation errors
```

#### Entity Queries

```http
GET /api/v1/entities/repository?namespace=rosa-hcp
GET /api/v1/entities/repository?owner=rosa-team@redhat.com
GET /api/v1/entities/external-dependency?package=requests
GET /api/v1/dependencies?repo=rosa-hcp/rosa-hcp-service
```

#### Schema Information

```http
GET /api/v1/schema/repository/1.0.0
GET /api/v1/schema/versions
GET /api/v1/schema/validate
```

### GraphQL Schema

```graphql
type Query {
  repository(id: String!): Repository
  repositoriesByOwner(owner: String!): [Repository]
  repositoriesByNamespace(namespace: String!): [Repository]
  dependenciesOf(repositoryId: String!): [Dependency]
  repositoriesUsing(packageId: String!): [Repository]
}

type Repository {
  id: String!
  namespace: String!
  owners: [String!]!
  gitRepoUrl: String!
  dependencies: [Dependency]
  createdAt: DateTime!
  updatedAt: DateTime!
}

type Dependency {
  package: ExternalDependencyPackage!
  version: String!
  dependentRepositories: [Repository]
}

type ExternalDependencyPackage {
  id: String!
  ecosystem: String!
  name: String!
  versions: [String]
  repositories: [Repository]
}
```

## GitHub Actions Integration

### Workflow File Template

```yaml
# .github/workflows/knowledge-graph.yml
name: Knowledge Graph Update

on:
  push:
    paths: ["knowledge-graph.yaml"]
  pull_request:
    paths: ["knowledge-graph.yaml"]

jobs:
  validate-and-submit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Validate Knowledge Graph
        uses: redhat/kg-validate-action@v1
        with:
          file: knowledge-graph.yaml
          schema-version: "1.0.0"

      - name: Submit to Graph
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: redhat/kg-submit-action@v1
        with:
          file: knowledge-graph.yaml
          server-url: ${{ secrets.KG_SERVER_URL }}
          auth-token: ${{ secrets.KG_AUTH_TOKEN }}
```

### Validation Action Logic

```python
def validate_yaml_file(file_path, schema_version):
    """Pre-commit validation logic"""

    # 1. Parse YAML with error handling
    try:
        data = yaml.safe_load(open(file_path))
    except yaml.YAMLError as e:
        return ValidationError(f"Invalid YAML: {e}")

    # 2. Schema version check
    if data.get('schema_version') != schema_version:
        return ValidationError(f"Expected schema {schema_version}")

    # 3. Structure validation
    schema = load_schema(schema_version)
    errors = validate_against_schema(data, schema)

    # 4. Reference validation (query server)
    ref_errors = validate_references(data['entity'])

    return errors + ref_errors
```

## Implementation Notes

### Performance Considerations

**Query Optimization:**

- Index on common query patterns (owner, namespace)
- Materialized views for expensive traversals
- Connection pooling for high-throughput scenarios

**Storage Efficiency:**

- Package/version separation reduces duplicate version storage
- Reference counting enables efficient orphan detection
- Audit trail compression for long-running repositories

### Security Model

**Authentication:**

- GitHub App integration for repository-level permissions
- Personal access tokens for development/testing
- Red Hat SSO integration for web interface

**Authorization:**

- Repository owners can only modify their own entities
- Namespace ownership validation prevents squatting
- Admin override capability for conflict resolution

### Monitoring and Observability

**Key Metrics:**

- Ingestion rate (submissions per hour)
- Query response times (p50, p95, p99)
- Validation failure rates by error type
- Reference counting accuracy

**Alerting:**

- Schema validation failures above threshold
- Server response time degradation
- Conflict detection false positives
- External dependency auto-creation failures

### Error Handling

**Graceful Degradation:**

- Read-only mode during server maintenance
- Cached schema validation for network issues
- Retry logic for transient failures
- Clear error messages with remediation steps

This technical specification provides the foundation for implementing a robust, scalable knowledge graph system that can evolve with Red Hat's organizational needs while maintaining data quality and consistency.
