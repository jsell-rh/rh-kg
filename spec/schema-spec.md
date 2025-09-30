# YAML Schema Specification

## Overview

This specification defines the exact format and validation rules for knowledge graph YAML files.
The schema follows a rigid approach for Phase 1 MVP, with planned evolution points.

## Schema Version 1.0.0

### File Structure

A knowledge graph YAML file MUST have this exact structure:

```yaml
schema_version: "1.0.0"
namespace: <namespace-name>
entity:
  repository:
    - <repository-name>:
        metadata:
          owners: [<email-list>]
          git_repo_url: <url>
        depends_on: [<dependency-list>]
```

### Global Fields

#### schema_version (REQUIRED)

- **Type:** String
- **Format:** Semantic version (MAJOR.MINOR.PATCH)
- **Pattern:** `^\d+\.\d+\.\d+$`
- **Current value:** `"1.0.0"`

**Examples:**

```yaml
# Valid
schema_version: "1.0.0"

# Invalid
schema_version: "1.0"      # Missing patch version
schema_version: "v1.0.0"   # Unexpected prefix
schema_version: 1.0.0      # Must be string
```

#### namespace (REQUIRED)

- **Type:** String
- **Format:** Kebab-case identifier
- **Pattern:** `^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$`
- **Purpose:** Groups related entities, prevents naming conflicts

**Examples:**

```yaml
# Valid
namespace: "rosa-hcp"
namespace: "team-auth"
namespace: "a"
namespace: "service_name"

# Invalid
namespace: "Rosa-HCP"      # Uppercase letters
namespace: "rosa.hcp"      # Dots not allowed
namespace: "rosa hcp"      # Spaces not allowed
namespace: "-rosa"         # Cannot start with dash
namespace: "rosa-"         # Cannot end with dash
namespace: ""              # Cannot be empty
```

### Entity Structure

#### entity (REQUIRED)

- **Type:** Object
- **Purpose:** Contains all entity definitions
- **Current entity types:** `repository` only
- **Future entity types:** `service`, `control_plane_component`, `etc` (planned)

#### entity.repository (OPTIONAL)

- **Type:** Array of repository objects
- **Purpose:** Define repository entities
- **Can be empty:** Yes

### Repository Entity

Each repository entity has this structure:

```yaml
entity:
  repository:
    - <repository-name>:
        metadata:
          owners: [<email-addresses>]
          git_repo_url: <repository-url>
        depends_on: [<dependency-references>]
```

#### Repository Name (Key)

- **Type:** String (object key)
- **Format:** Free-form string
- **Constraints:** Must be unique within namespace
- **Purpose:** Human-readable repository identifier

#### metadata (REQUIRED)

- **Type:** Object
- **Purpose:** Repository metadata
- **Required fields:** `owners`, `git_repo_url`

#### metadata.owners (REQUIRED)

- **Type:** Array of strings
- **Format:** Email addresses
- **Validation:** Each string MUST be valid email format
- **Constraints:** Minimum 1 item, maximum unlimited
- **Purpose:** Team ownership information

**Examples:**

```yaml
# Valid
owners: ["team@redhat.com"]
owners: ["team@redhat.com", "lead@redhat.com", "architect@redhat.com"]

# Invalid
owners: []                           # Must have at least one owner
owners: ["invalid-email"]           # Must be valid email format
owners: "team@redhat.com"           # Must be array, not string
owners: ["team@redhat.com", ""]     # Empty email not allowed
```

#### metadata.git_repo_url (REQUIRED)

- **Type:** String
- **Format:** Valid HTTP/HTTPS URL
- **Purpose:** Link to source repository
- **Constraints:** Must be accessible URL format

**Examples:**

```yaml
# Valid
git_repo_url: "https://github.com/openshift/rosa-hcp-service"
git_repo_url: "https://gitlab.com/redhat/internal-tool"
git_repo_url: "https://git.corp.redhat.com/team/project"

# Invalid
git_repo_url: "not-a-url"           # Must be valid URL
git_repo_url: "file:///local/path"  # Must be HTTP/HTTPS
git_repo_url: ""                    # Cannot be empty
```

### Field Deprecation Support

Any schema field can be marked as deprecated using deprecation metadata. Deprecated fields remain functional but emit warnings during validation.

#### Deprecation Metadata Fields

All deprecation fields are OPTIONAL and apply to entity type fields, relationship definitions, and metadata fields:

- `deprecated` (boolean): Marks field as deprecated
- `deprecated_since` (string): Schema version when deprecation began (semantic version)
- `deprecated_reason` (string): Human-readable explanation of why field is deprecated
- `removal_planned` (string): Schema version when field may be removed (semantic version)
- `migration_guide` (string): Instructions for migrating away from deprecated field

#### Deprecated Field Example

```yaml
# In schema definition YAML (backend/schemas/repository.yaml)
fields:
  legacy_owner:
    type: string
    required: false
    deprecated: true
    deprecated_since: "1.2.0"
    deprecated_reason: "Use metadata.owners array instead for multi-owner support"
    removal_planned: "2.0.0"
    migration_guide: |
      Replace:
        legacy_owner: "team@redhat.com"
      With:
        metadata:
          owners: ["team@redhat.com"]
```

#### Deprecation Validation Behavior

- **Deprecated fields ARE still validated** - type and format rules still apply
- **Warnings are emitted** when deprecated fields are used
- **Validation does NOT fail** due to deprecation alone
- **Migration guidance is included** in warning messages

#### depends_on (REQUIRED)

- **Type:** Array of strings
- **Format:** Dependency reference URIs
- **Can be empty:** Yes
- **Purpose:** Declare dependencies on other entities

**Dependency Reference Format:**

- **External dependencies:** `external://<ecosystem>/<package>/<version>`
- **Internal dependencies:** `internal://<namespace>/<entity-name>`

**Examples:**

```yaml
# Valid
depends_on: []
depends_on: ["external://pypi/requests/2.31.0"]
depends_on:
  - "external://pypi/requests/2.31.0"
  - "external://npm/@types/node/18.15.0"
  - "internal://shared-utils/logging-library"

# Invalid
depends_on: "external://pypi/requests/2.31.0"  # Must be array
depends_on: ["requests"]                        # Must use full URI format
depends_on: ["external://pypi/requests"]        # Must include version
depends_on: ["internal://invalid space/lib"]    # Invalid namespace format
```

## Validation Rules

### Strict Validation Policy

The schema follows a **strict validation policy** for Phase 1:

1. **Unknown fields MUST be rejected** with clear error messages
2. **Missing required fields MUST cause validation failure**
3. **Invalid formats MUST be caught with specific error messages**
4. **All dependency references MUST be well-formed URIs**

### External Dependency Format

External dependencies MUST follow this exact format:

```
external://<ecosystem>/<package>/<version>
```

**Supported ecosystems:**

- `pypi` - Python packages
- `npm` - Node.js packages
- `golang.org/x` - Go modules
- `github.com/<org>` - Go modules from GitHub
- `maven` - Java packages (future)
- `nuget` - .NET packages (future)

**Examples:**

```yaml
# Python
- "external://pypi/requests/2.31.0"
- "external://pypi/django/4.2.1"

# Node.js
- "external://npm/express/4.18.0"
- "external://npm/@types/node/18.15.0"

# Go
- "external://golang.org/x/client-go/v0.28.4"
- "external://github.com/stretchr/testify/v1.8.0"
```

### Internal Dependency Format

Internal dependencies MUST follow this exact format:

```
internal://<namespace>/<entity-name>
```

**Examples:**

```yaml
# Valid
- "internal://shared-utils/logging-library"
- "internal://openshift-auth/auth-service"
- "internal://rosa-hcp/rosa-operator"

# Invalid
- "internal://SharedUtils/LoggingLibrary" # Namespace must be kebab-case
- "internal://shared-utils" # Must include entity name
- "internal:///logging-library" # Namespace cannot be empty
```

## Complete Example

```yaml
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
          - "external://npm/@types/node/18.15.0"
          - "internal://shared-utils/logging-library"
          - "internal://openshift-auth/auth-service"

    - rosa-operator:
        metadata:
          owners: ["rosa-team@redhat.com"]
          git_repo_url: "https://github.com/openshift/rosa-operator"
        depends_on:
          - "external://golang.org/x/client-go/v0.28.4"
          - "internal://rosa-hcp/rosa-hcp-service"

    - documentation-site:
        metadata:
          owners: ["docs-team@redhat.com"]
          git_repo_url: "https://github.com/openshift/rosa-docs"
        depends_on: []
```

## Error Messages

Validation errors MUST provide clear, actionable feedback:

### Unknown Field Error

```
ValidationError: Unknown field 'custom_field' in repository 'test-repo'
  Allowed fields: metadata, depends_on
  Help: Phase 1 schema only supports specific fields. Custom fields will be supported in Phase 2.
```

### Missing Required Field Error

```
ValidationError: Missing required field 'owners' in repository 'test-repo'
  Required fields: owners, git_repo_url
  Help: All repositories must specify at least one owner email address.
```

### Invalid Dependency Reference Error

```
ValidationError: Invalid dependency reference 'requests' in repository 'test-repo'
  Expected format: external://<ecosystem>/<package>/<version> or internal://<namespace>/<entity>
  Example: external://pypi/requests/2.31.0
  Help: All dependencies must use the full URI format.
```

### Invalid Email Format Error

```
ValidationError: Invalid email 'not-an-email' in owners for repository 'test-repo'
  Expected format: user@domain.com
  Help: All owners must be valid email addresses.
```

### Deprecation Warning

```
DeprecationWarning: Field 'legacy_owner' is deprecated in repository 'test-repo'
  Deprecated since: 1.2.0
  Reason: Use metadata.owners array instead for multi-owner support
  Removal planned: 2.0.0
  Migration guide:
    Replace:
      legacy_owner: "team@redhat.com"
    With:
      metadata:
        owners: ["team@redhat.com"]
```

## Future Evolution

### Phase 2 Planned Changes

- Add `service` and other entity type
- Add operational metadata fields
- Support for custom metadata with governance

### Phase 3 Planned Changes

- Add relationship precision (runtime vs build dependencies)
- Support for temporal modeling
- Cross-service relationship types

### Migration Strategy

- Schema version field enables migration tooling
- Multiple version support during transition periods
- Automated migration scripts for breaking changes
- Rollback capability for failed migrations

## Backwards Compatibility

### Version 1.x Compatibility Promise

- Patch versions (1.0.x): No breaking changes
- Minor versions (1.x.0): Additive changes only
- Major versions (x.0.0): Breaking changes allowed with migration path

### Deprecation Policy

- Features marked deprecated for at least one minor version
- Clear migration guidance provided
- Automated migration tools when possible
