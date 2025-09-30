# Dgraph Data Model Specification

## Overview

This specification defines how knowledge graph data is stored in Dgraph, including node types, relationships, and query patterns.
The model follows the package/version separation approach for external dependencies.

## Node Types

### Repository Node

Represents a code repository entity from the YAML files.

#### Dgraph Type Definition

```graphql
type Repository {
  id: string @id              # Fully qualified ID: <namespace>/<repository-name>
  namespace: string @index(exact)
  name: string @index(exact)
  owners: [string] @index(exact)
  git_repo_url: string @index(exact)

  # Relationships
  depends_on: [ExternalDependencyVersion] @reverse
  internal_depends_on: [Repository] @reverse

  # System metadata (read-only)
  created_at: datetime
  updated_at: datetime
  source_repo: string         # Which repository submitted this data
  source_commit: string       # Git commit hash of submission

  # Deprecation metadata (optional)
  deprecated: bool            # Flag indicating if this entity is deprecated
  deprecated_since: string    # Schema version when deprecation was introduced
  deprecated_reason: string   # Explanation for deprecation
  removal_planned: string     # Schema version when removal is planned (optional)

  # Type identifier
  dgraph.type: Repository
}
```

#### Node ID Format

```
<namespace>/<repository-name>
```

**Examples:**

- `rosa-hcp/rosa-hcp-service`
- `shared-utils/logging-library`
- `openshift-auth/auth-service`

#### Field Specifications

**id (required)**

- Unique identifier combining namespace and repository name
- Format: `<namespace>/<repository-name>`
- Must be URL-safe characters only

**namespace (required)**

- Repository namespace from YAML file
- Indexed for efficient namespace-based queries
- Must follow kebab-case convention

**name (required)**

- Repository name from YAML file
- Indexed for efficient name-based lookups
- Combined with namespace to form unique ID

**owners (required)**

- Array of email addresses from YAML metadata
- Each email indexed separately for owner-based queries
- Minimum 1 item, no maximum limit

**git_repo_url (required)**

- Repository URL from YAML metadata
- Indexed for reverse lookups
- Must be valid HTTP/HTTPS URL

### External Dependency Package Node

Represents a package from an external ecosystem (pypi, npm, etc.).

#### Dgraph Type Definition

```graphql
type ExternalDependencyPackage {
  id: string @id              # Format: external://<ecosystem>/<package>
  ecosystem: string @index(exact)
  package_name: string @index(exact)

  # Relationships
  has_version: [ExternalDependencyVersion] @reverse

  # System metadata
  created_at: datetime
  first_referenced_by: string # Repository ID that first referenced this package

  # Deprecation metadata (optional)
  deprecated: bool            # Flag indicating if this package is deprecated
  deprecated_since: string    # Schema version when deprecation was introduced
  deprecated_reason: string   # Explanation for deprecation
  removal_planned: string     # Schema version when removal is planned (optional)

  # Type identifier
  dgraph.type: ExternalDependencyPackage
}
```

#### Node ID Format

```
external://<ecosystem>/<package>
```

**Examples:**

- `external://pypi/requests`
- `external://npm/@types/node`
- `external://golang.org/x/client-go`

### External Dependency Version Node

Represents a specific version of an external package.

#### Dgraph Type Definition

```graphql
type ExternalDependencyVersion {
  id: string @id              # Format: external://<ecosystem>/<package>/<version>
  ecosystem: string @index(exact)
  package_name: string @index(exact)
  version: string @index(exact)

  # Relationships
  package: ExternalDependencyPackage @reverse
  referenced_by: [Repository] @reverse

  # System metadata
  created_at: datetime
  first_referenced_by: string
  reference_count: int @index(int)

  # Deprecation metadata (optional)
  deprecated: bool            # Flag indicating if this version is deprecated
  deprecated_since: string    # Schema version when deprecation was introduced
  deprecated_reason: string   # Explanation for deprecation
  removal_planned: string     # Schema version when removal is planned (optional)

  # Type identifier
  dgraph.type: ExternalDependencyVersion
}
```

#### Node ID Format

```
external://<ecosystem>/<package>/<version>
```

**Examples:**

- `external://pypi/requests/2.31.0`
- `external://npm/@types/node/18.15.0`
- `external://golang.org/x/client-go/v0.28.4`

## Relationships

### Repository Dependencies

#### External Dependencies

- **Predicate:** `depends_on`
- **From:** Repository
- **To:** ExternalDependencyVersion
- **Direction:** Unidirectional (Repository → ExternalDependencyVersion)
- **Cardinality:** One-to-many

#### Internal Dependencies

- **Predicate:** `internal_depends_on`
- **From:** Repository (dependent)
- **To:** Repository (dependency)
- **Direction:** Unidirectional
- **Cardinality:** One-to-many

### Package-Version Relationships

#### Package Versions

- **Predicate:** `has_version`
- **From:** ExternalDependencyPackage
- **To:** ExternalDependencyVersion
- **Direction:** Unidirectional
- **Cardinality:** One-to-many

## Data Ingestion Process

### Repository Creation/Update

When a repository YAML file is submitted:

1. **Parse and validate** YAML file
2. **Create or update Repository node** with metadata
3. **Process external dependencies:**
   - For each external dependency reference:
     - Create ExternalDependencyPackage node (if not exists)
     - Create ExternalDependencyVersion node (if not exists)
     - Create `has_version` relationship (if not exists)
     - Create `depends_on` relationship (replace existing)
4. **Process internal dependencies:**
   - Create `internal_depends_on` relationships (replace existing)
5. **Update system metadata** (updated_at, source_commit)

### Dependency Auto-Creation

External dependencies are automatically created when first referenced:

```
Input: external://pypi/requests/2.31.0

1. Check if ExternalDependencyPackage exists: external://pypi/requests
   - If not, create with ecosystem="pypi", package_name="requests"

2. Check if ExternalDependencyVersion exists: external://pypi/requests/2.31.0
   - If not, create with version="2.31.0"
   - Link to package with has_version relationship

3. Create depends_on relationship from Repository to ExternalDependencyVersion
```

### Entity Deletion

#### Repository Deletion

When a repository is removed from YAML:

1. **Check internal references:** If other repositories depend on this one, fail with error
2. **Remove repository node** and all its outbound relationships
3. **Update external dependency reference counts**
4. **Keep external dependency nodes** (never delete external entities)

#### External Dependency Cleanup

External dependencies are never deleted, even when no longer referenced:

- Orphaned ExternalDependencyVersion nodes remain
- Orphaned ExternalDependencyPackage nodes remain
- Reference counts may reach zero but nodes persist

## Query Patterns

### Common Queries

#### Find Repositories by Owner

```graphql
query($owner: string) {
  repositories(func: eq(owners, $owner)) {
    id
    name
    namespace
    git_repo_url
  }
}
```

#### Find Repositories Using External Package

```graphql
query($package_id: string) {
  package(func: eq(id, $package_id)) {
    has_version {
      ~depends_on {
        id
        name
        namespace
        owners
      }
    }
  }
}
```

**Example:**

```graphql
# Find all repositories using any version of requests
query {
  package(func: eq(id, "external://pypi/requests")) {
    has_version {
      ~depends_on {
        id
        name
        namespace
        owners
      }
    }
  }
}
```

#### Find Repositories Using Specific Version

```graphql
query($version_id: string) {
  version(func: eq(id, $version_id)) {
    ~depends_on {
      id
      name
      namespace
      owners
    }
  }
}
```

#### Find Dependencies of Repository

```graphql
query($repo_id: string) {
  repository(func: eq(id, $repo_id)) {
    depends_on {
      id
      package_name
      version
      ecosystem
    }
    internal_depends_on {
      id
      name
      namespace
    }
  }
}
```

#### Find Repositories in Namespace

```graphql
query($namespace: string) {
  repositories(func: eq(namespace, $namespace)) {
    id
    name
    owners
    git_repo_url
    depends_on {
      id
      package_name
      version
    }
  }
}
```

### Analytics Queries

#### Dependency Usage Statistics

```graphql
query {
  packages(func: type(ExternalDependencyPackage)) {
    id
    ecosystem
    package_name
    has_version {
      version
      reference_count
    }
  }
}
```

#### Most Popular External Dependencies

```graphql
query {
  versions(func: type(ExternalDependencyVersion), orderdesc: reference_count, first: 10) {
    id
    package_name
    version
    reference_count
    ~depends_on {
      id
      namespace
    }
  }
}
```

#### Repository Dependency Counts

```graphql
query {
  repositories(func: type(Repository)) {
    id
    name
    namespace
    external_dep_count: count(depends_on)
    internal_dep_count: count(internal_depends_on)
  }
}
```

## Deprecation Management

### Deprecation Metadata

All node types support deprecation metadata to enable safe schema evolution without breaking changes.

#### Deprecation Fields

**deprecated (optional)**

- Type: boolean
- Default: false
- Marks entity as deprecated when true

**deprecated_since (optional)**

- Type: string
- Format: semantic version (e.g., "1.2.0")
- Schema version when deprecation was introduced

**deprecated_reason (optional)**

- Type: string
- Human-readable explanation for deprecation
- Should include guidance on replacement

**removal_planned (optional)**

- Type: string
- Format: semantic version (e.g., "2.0.0")
- Schema version when removal is planned

#### Example Deprecated Repository

```json
{
  "uid": "0x1",
  "dgraph.type": ["Repository"],
  "id": "legacy-namespace/old-service",
  "name": "old-service",
  "namespace": "legacy-namespace",
  "owners": ["legacy-team@redhat.com"],
  "git_repo_url": "https://github.com/legacy/old-service",
  "deprecated": true,
  "deprecated_since": "1.3.0",
  "deprecated_reason": "Replaced by new-namespace/modern-service for improved architecture",
  "removal_planned": "2.0.0"
}
```

### Deprecation Lifecycle

1. **Active** - Normal entity, no deprecation metadata
2. **Deprecated** - Entity marked deprecated but functional
3. **Legacy** - Deprecated entity with planned removal version
4. **Removal Eligible** - Entity can be removed in major version update

### Deprecation Queries

#### Find All Deprecated Entities

```graphql
query {
  deprecated_repositories(func: eq(deprecated, true)) @filter(type(Repository)) {
    id
    name
    namespace
    deprecated_since
    deprecated_reason
    removal_planned
  }

  deprecated_packages(func: eq(deprecated, true)) @filter(type(ExternalDependencyPackage)) {
    id
    package_name
    ecosystem
    deprecated_since
    deprecated_reason
  }
}
```

#### Find Entities Eligible for Removal

```graphql
query($target_version: string) {
  eligible_for_removal(func: eq(removal_planned, $target_version)) {
    expand(_all_) {
      expand(_all_)
    }
  }
}
```

#### Check Repository Dependencies on Deprecated Entities

```graphql
query($repo_id: string) {
  repository(func: eq(id, $repo_id)) {
    depends_on @filter(eq(deprecated, true)) {
      id
      package_name
      version
      deprecated_reason
      removal_planned
    }
    internal_depends_on @filter(eq(deprecated, true)) {
      id
      name
      namespace
      deprecated_reason
      removal_planned
    }
  }
}
```

## Schema Evolution

### Version 1.0.0 Schema

Current minimal schema with Repository and ExternalDependency types only.

### Additive-Only Evolution Strategy

Following the additive-only evolution approach:

#### Allowed Changes (Minor Version Increments)

- Add new node types
- Add new optional fields to existing nodes
- Add new relationships
- Add indexes to existing fields
- Deprecate existing elements

#### Forbidden Changes

- Remove fields or relationships
- Change field types
- Make optional fields required
- Remove relationship target types

### Migration Strategy

#### Additive Changes Only

- Add new node types without affecting existing data
- Add new predicates without removing old ones
- Extend existing types with new optional fields
- Use deprecation instead of removal

#### Major Version Boundaries

Reserved for rare cases requiring breaking changes:

- Removal of extensively deprecated elements
- Fundamental architectural changes
- Performance-critical restructuring

Major versions require:

- Extensive deprecation period (minimum 6 months)
- Migration tooling provided
- Formal approval process

## Performance Considerations

### Indexing Strategy

- **Exact indexes** on frequently queried fields (namespace, owners, ecosystem)
- **Integer indexes** on numeric fields (reference_count)
- **Full-text indexes** on searchable content (future enhancement)

### Query Optimization

- Use specific predicates instead of broad traversals
- Limit result sets with `first:` parameter
- Use pagination for large result sets
- Cache common query results

### Storage Efficiency

- Package/version separation reduces duplicate version storage
- Reference counting enables efficient orphan detection
- Namespace grouping improves query locality

## Data Integrity

### Constraints

- Repository IDs must be unique across all namespaces
- External dependency IDs must follow canonical format
- All email addresses must be valid format
- All URLs must be valid HTTP/HTTPS format

### Validation Rules

- Reference counts must match actual relationship counts
- Package-version relationships must be consistent
- System metadata fields must be properly maintained

### Consistency Checks

- Periodic validation of reference counts
- Orphan node detection and reporting
- Cross-reference validation between related entities

## Example Data Structure

### Complete Repository with Dependencies

```json
{
  "uid": "0x1",
  "dgraph.type": ["Repository"],
  "id": "rosa-hcp/rosa-hcp-service",
  "namespace": "rosa-hcp",
  "name": "rosa-hcp-service",
  "owners": ["rosa-team@redhat.com", "rosa-leads@redhat.com"],
  "git_repo_url": "https://github.com/openshift/rosa-hcp-service",
  "depends_on": [
    {
      "uid": "0x10",
      "id": "external://pypi/requests/2.31.0"
    },
    {
      "uid": "0x11",
      "id": "external://pypi/pydantic/2.5.0"
    }
  ],
  "internal_depends_on": [
    {
      "uid": "0x2",
      "id": "shared-utils/logging-library"
    }
  ],
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T14:22:00Z",
  "source_repo": "github.com/openshift/rosa-hcp-service",
  "source_commit": "abc123def456"
}
```

### External Dependency Structure

```json
{
  "uid": "0x20",
  "dgraph.type": ["ExternalDependencyPackage"],
  "id": "external://pypi/requests",
  "ecosystem": "pypi",
  "package_name": "requests",
  "has_version": [
    {
      "uid": "0x10",
      "id": "external://pypi/requests/2.31.0",
      "version": "2.31.0",
      "reference_count": 5
    },
    {
      "uid": "0x21",
      "id": "external://pypi/requests/2.30.0",
      "version": "2.30.0",
      "reference_count": 2
    }
  ],
  "created_at": "2025-01-10T09:15:00Z",
  "first_referenced_by": "rosa-hcp/rosa-hcp-service"
}
```
