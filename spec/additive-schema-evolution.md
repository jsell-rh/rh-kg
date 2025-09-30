# Additive Schema Evolution Specification

## 1. Overview

This specification defines the Red Hat Knowledge Graph's approach to schema evolution through **additive-only migrations**. This design philosophy prioritizes safety, simplicity, and alignment with Dgraph's native capabilities while enabling continuous system evolution.

### 1.1 Philosophy

> "Schema evolution should be invisible to existing consumers and safe by design."

- **Safety First**: No changes can break existing data or queries
- **Zero Downtime**: All schema changes must be deployable without system interruption
- **Gradual Adoption**: New features can be adopted incrementally
- **Dgraph Native**: Work with Dgraph's additive schema nature, not against it

### 1.2 Key Benefits

- **Elimination of Migration Complexity**: No data transformation pipelines needed
- **Zero Risk of Data Loss**: Additive changes cannot corrupt existing data
- **Instant Rollback**: Simply stop using new features to "roll back"
- **Continuous Deployment**: Schema changes become routine, low-risk operations

## 2. Core Principles

### 2.1 Additive-Only Rule

**RULE**: All schema changes MUST be additive. Removing, renaming, or changing types of existing schema elements is FORBIDDEN.

**Rationale**:

- Dgraph's schema system is naturally additive
- Prevents data corruption and query breakage
- Enables zero-downtime deployments
- Aligns with API versioning best practices

### 2.2 Deprecation Over Deletion

**RULE**: When schema elements become obsolete, they MUST be deprecated, not removed.

**Implementation**:

```yaml
# Instead of removing a field, deprecate it
old_field_name:
  type: string
  deprecated: true
  deprecated_since: "1.2.0"
  deprecated_reason: "Use new_field_name instead"
  removal_planned: "2.0.0" # Major version boundary
```

### 2.3 Versioning Strategy

**Schema Version Format**: `MAJOR.MINOR.PATCH`

- **MAJOR**: Reserved for rare breaking changes (requires special approval)
- **MINOR**: Additive features (new fields, relationships, entity types)
- **PATCH**: Non-functional changes (documentation, metadata)

## 3. Allowed Changes

### 3.1 Adding New Entity Types

**✅ ALLOWED**: Introducing entirely new entity types

```yaml
# NEW in version 1.1.0
deployment:
  entity_type: deployment
  schema_version: "1.1.0"
  description: "Kubernetes deployment information"
  required_metadata:
    cluster_name:
      type: string
      description: "Target cluster name"
```

### 3.2 Adding New Fields

**✅ ALLOWED**: Adding new optional or readonly fields to existing entities

```yaml
repository:
  schema_version: "1.2.0" # Incremented
  optional_metadata:
    # Existing fields remain unchanged
    description:
      type: string

    # NEW FIELD in 1.2.0
    primary_language:
      type: string
      description: "Primary programming language"
      indexed: true
```

**RESTRICTION**: New required fields are FORBIDDEN as they would break existing entities.

### 3.3 Adding New Relationships

**✅ ALLOWED**: Adding new relationship types

```yaml
repository:
  relationships:
    # Existing relationships unchanged
    depends_on:
      target_types: [external_dependency_version]

    # NEW RELATIONSHIP in 1.2.0
    deployed_to:
      description: "Clusters where this repository is deployed"
      target_types: [deployment]
      cardinality: one_to_many
      direction: outbound
```

### 3.4 Adding Indexes

**✅ ALLOWED**: Adding indexes to existing fields for performance

```yaml
existing_field:
  type: string
  indexed: true # NEW in 1.1.0
  description: "Now indexed for faster queries"
```

### 3.5 Extending Relationships

**✅ ALLOWED**: Adding new target types to existing relationships

```yaml
depends_on:
  target_types:
    - external_dependency_version # Existing
    - internal_service # NEW in 1.2.0
```

## 4. Forbidden Changes

### 4.1 Removing Schema Elements

**❌ FORBIDDEN**: Deleting fields, relationships, or entity types

```yaml
# WRONG - This would break existing data
repository:
  required_metadata:
    # owners: [string]  # NEVER remove existing fields
```

**Correct Approach**: Use deprecation

```yaml
repository:
  required_metadata:
    owners:
      type: array
      items: string
      deprecated: true
      deprecated_since: "1.3.0"
      deprecated_reason: "Use maintainers field instead"
```

### 4.2 Type Changes

**❌ FORBIDDEN**: Changing field types

```yaml
# WRONG - This could corrupt data
version_number:
  type: string # Was: integer
```

**Correct Approach**: Add new field with correct type

```yaml
version_number:
  type: integer
  deprecated: true
  deprecated_reason: "Use semantic_version instead"

semantic_version:
  type: string
  validation: semver
  description: "Semantic version string (e.g., 1.2.3)"
```

### 4.3 Making Optional Fields Required

**❌ FORBIDDEN**: Converting optional to required fields

```yaml
# WRONG - Existing entities might not have this field
description:
  type: string
  required: true # Was: optional
```

### 4.4 Removing Relationship Target Types

**❌ FORBIDDEN**: Reducing relationship target types

```yaml
# WRONG - Existing relationships might use removed types
depends_on:
  target_types: [external_dependency_version] # Removed: repository
```

## 5. Implementation Architecture

### 5.1 Schema Change Detection

```python
class AdditiveChangeDetector:
    """Detects and validates additive-only schema changes."""

    def detect_changes(self, old_schemas: dict, new_schemas: dict) -> ChangeSet:
        """Identify all changes between schema versions."""

    def validate_additive_only(self, changes: ChangeSet) -> ValidationResult:
        """Ensure all changes follow additive-only rules."""

    def generate_migration_plan(self, changes: ChangeSet) -> MigrationPlan:
        """Create simple additive migration plan."""
```

### 5.2 Change Types

```python
@dataclass
class AdditiveChange:
    """Represents a valid additive schema change."""
    change_type: Literal["add_field", "add_relationship", "add_entity_type", "add_index"]
    entity_type: str
    element_name: str
    definition: dict[str, Any]
    schema_version: str

@dataclass
class ForbiddenChange:
    """Represents an invalid non-additive change."""
    change_type: Literal["remove", "modify", "require_optional"]
    entity_type: str
    element_name: str
    reason: str
    suggestion: str
```

### 5.3 Migration Execution

```python
class AdditiveMigrationExecutor:
    """Executes additive-only schema migrations."""

    async def apply_additive_changes(self, migration_plan: MigrationPlan) -> MigrationResult:
        """Apply only additive changes to Dgraph schema."""
        # 1. Validate changes are additive
        # 2. Generate new Dgraph schema predicates
        # 3. Apply schema updates (additive only)
        # 4. Update schema version metadata
        # No data migration needed!
```

## 6. Deprecation Management

### 6.1 Deprecation Lifecycle

1. **Active**: Field is used and maintained
2. **Deprecated**: Field marked deprecated, still functional
3. **Legacy**: Field maintained for compatibility only
4. **Removal Eligible**: Can be removed in next major version

### 6.2 Deprecation Metadata

```yaml
deprecated_field:
  type: string
  deprecated: true
  deprecated_since: "1.2.0"
  deprecated_reason: "Use new_field_name for improved functionality"
  removal_planned: "2.0.0"
  migration_guide: |
    Replace usage of deprecated_field with new_field_name.
    Example: deprecated_field: "value" → new_field_name: "value"
```

### 6.3 Automated Deprecation Warnings

```python
class DeprecationWarningSystem:
    """Provides deprecation warnings for schema usage."""

    def check_entity_for_deprecated_fields(self, entity_data: dict) -> list[DeprecationWarning]:
        """Warn when deprecated fields are used."""

    def generate_migration_suggestions(self, warnings: list[DeprecationWarning]) -> str:
        """Provide actionable migration guidance."""
```

## 7. Version Management

### 7.1 Schema Version Tracking

```python
@dataclass
class SchemaVersionInfo:
    """Tracks schema version metadata."""
    version: str
    timestamp: datetime
    changes: list[AdditiveChange]
    deprecated_elements: list[str]
    previous_version: str | None
```

### 7.2 Compatibility Matrix

| Current Schema | Supported Client Versions | Notes                               |
| -------------- | ------------------------- | ----------------------------------- |
| 1.0.0          | 1.0.x                     | Initial version                     |
| 1.1.0          | 1.0.x, 1.1.x              | Additive changes only               |
| 1.2.0          | 1.0.x, 1.1.x, 1.2.x       | Full backward compatibility         |
| 2.0.0          | 1.2.x, 2.0.x              | Major version may remove deprecated |

## 8. Operational Procedures

### 8.1 Schema Change Deployment

1. **Pre-deployment Validation**

   ```bash
   kg schema validate --additive-only schemas/
   kg schema plan --from=production --to=schemas/
   ```

2. **Deployment Process**

   ```bash
   kg schema apply --additive-only schemas/
   # Zero downtime - just adds new predicates
   ```

3. **Post-deployment Verification**
   ```bash
   kg schema verify --version=1.2.0
   kg health check --schema-compatibility
   ```

### 8.2 Rollback Strategy

**Immediate Rollback**: Stop using new features

- No schema changes needed
- Applications continue with old fields
- New features simply unused

**Full Rollback**: Revert to previous application version

- Schema remains compatible
- No data loss or corruption risk

## 9. Developer Guidelines

### 9.1 Adding New Features

```yaml
# ✅ DO: Add new optional fields
user:
  optional_metadata:
    profile_picture_url: # NEW FIELD
      type: string
      validation: url

# ✅ DO: Add new relationships
repository:
  relationships:
    tested_by: # NEW RELATIONSHIP
      target_types: [test_suite]

# ✅ DO: Create new entity types
test_suite: # NEW ENTITY TYPE
  entity_type: test_suite
  required_metadata:
    name:
      type: string
```

### 9.2 Handling Obsolete Features

```yaml
# ✅ DO: Deprecate instead of removing
repository:
  optional_metadata:
    legacy_build_config:
      type: string
      deprecated: true
      deprecated_since: "1.3.0"
      deprecated_reason: "Use build_pipeline relationship instead"

    # Provide replacement
  relationships:
    build_pipeline:
      target_types: [ci_pipeline]
```

### 9.3 Error Prevention

**Automated Validation**:

```python
# Pre-commit hook
if not schema_validator.is_additive_only(old_schema, new_schema):
    raise SchemaValidationError("Non-additive changes detected")
```

**Review Checklist**:

- [ ] All changes are additive only
- [ ] No required fields added to existing entities
- [ ] Deprecated fields properly documented
- [ ] Schema version incremented correctly
- [ ] Migration guide provided for breaking patterns

## 10. Monitoring and Observability

### 10.1 Schema Metrics

- **Schema Version**: Current deployed version
- **Deprecated Field Usage**: Track usage of deprecated elements
- **Migration Readiness**: Entities ready for next major version
- **Schema Size Growth**: Monitor predicate count over time

### 10.2 Alerts

- **Deprecated Field Usage Spike**: Unusual increase in deprecated field usage
- **Schema Validation Failure**: Attempt to deploy non-additive changes
- **Version Compatibility Issues**: Client using unsupported schema features

## 11. Future Considerations

### 11.1 Major Version Boundaries

**When Major Versions Are Needed**:

- Fundamental architectural changes
- Removal of extensively deprecated features
- Performance-critical schema restructuring

**Major Version Process**:

1. Extensive deprecation period (minimum 6 months)
2. Migration tooling provided
3. Parallel version support during transition
4. Formal approval process required

### 11.2 Emergency Procedures

**Critical Security Issues**:

- Temporary bypass of additive-only rule
- Requires emergency change approval
- Immediate communication to all consumers
- Automated rollback plan required

## 12. Examples

### 12.1 Evolution Timeline

**Version 1.0.0 - Initial Schema**

```yaml
repository:
  required_metadata:
    owners: [string]
    git_repo_url: string
  relationships:
    depends_on: [external_dependency_version]
```

**Version 1.1.0 - Add Optional Fields**

```yaml
repository:
  required_metadata:
    owners: [string]
    git_repo_url: string
  optional_metadata:
    description: string # NEW
    primary_language: string # NEW
  relationships:
    depends_on: [external_dependency_version]
```

**Version 1.2.0 - Add New Relationships**

```yaml
repository:
  required_metadata:
    owners: [string]
    git_repo_url: string
  optional_metadata:
    description: string
    primary_language: string
  relationships:
    depends_on: [external_dependency_version]
    deployed_to: [deployment] # NEW
    tested_by: [test_suite] # NEW
```

**Version 1.3.0 - Deprecation Example**

```yaml
repository:
  required_metadata:
    owners: [string]
    git_repo_url: string
    maintainers: [string] # NEW - replacement for owners
  optional_metadata:
    description: string
    primary_language: string
  relationships:
    depends_on: [external_dependency_version]
    deployed_to: [deployment]
    tested_by: [test_suite]

# Deprecation tracking
deprecations:
  - field: owners
    deprecated_since: "1.3.0"
    reason: "Use maintainers field for improved team management"
    removal_planned: "2.0.0"
```

### 12.2 Common Anti-Patterns

**❌ Anti-Pattern: Immediate Removal**

```yaml
# WRONG - Breaks existing entities
repository:
  required_metadata:
    # owners: [string]  # Removed without deprecation
    maintainers: [string]
```

**✅ Correct Pattern: Gradual Migration**

```yaml
# RIGHT - Gradual transition
repository:
  required_metadata:
    owners:
      type: array
      items: string
      deprecated: true
      deprecated_reason: "Use maintainers field"
    maintainers: [string] # New preferred field
```

## 13. Conclusion

The additive-only schema evolution approach provides:

- **Safety**: Impossible to break existing data
- **Simplicity**: No complex migration pipelines
- **Speed**: Zero-downtime deployments
- **Flexibility**: Continuous evolution capability

This design philosophy aligns with modern API versioning practices and Dgraph's native capabilities, creating a robust foundation for long-term system evolution.

---

**Document Status**: DRAFT - Pending team review and approval
**Next Review**: 2025-10-15
**Approvers**: Architecture Team, Platform Team, Security Team
