# CLI Validation Specification

## Overview

This specification defines the behavior of the `kg validate` command, which is the primary entry point for teams
to validate their knowledge graph YAML files.

## Command Interface

### Basic Usage

```bash
kg validate [FILE] [OPTIONS]
```

### Arguments

#### FILE (optional)

- **Type:** File path
- **Default:** `knowledge-graph.yaml` in current directory
- **Purpose:** Path to knowledge graph YAML file to validate
- **Behavior:** If file doesn't exist, command MUST fail with clear error

**Examples:**

```bash
kg validate                           # Validates ./knowledge-graph.yaml
kg validate my-graph.yaml            # Validates ./my-graph.yaml
kg validate /path/to/graph.yaml      # Validates absolute path
kg validate ../other/graph.yaml      # Validates relative path
```

### Options

#### --schema-version (optional)

- **Type:** String
- **Default:** Auto-detect from file, fallback to "1.0.0"
- **Purpose:** Specify schema version for validation
- **Format:** Semantic version (e.g., "1.0.0")

```bash
kg validate --schema-version 1.0.0 graph.yaml
```

#### --strict (optional)

- **Type:** Boolean flag
- **Default:** true (Phase 1 behavior)
- **Purpose:** Enable strict validation mode
- **Behavior:** Reject unknown fields, enforce all constraints

```bash
kg validate --strict graph.yaml      # Explicit strict mode
kg validate --no-strict graph.yaml   # Future: permissive mode
```

#### --format (optional)

- **Type:** Enum: json, yaml, table, compact
- **Default:** table
- **Purpose:** Output format for validation results

```bash
kg validate --format json graph.yaml
kg validate --format compact graph.yaml
```

#### --verbose, -v (optional)

- **Type:** Boolean flag
- **Default:** false
- **Purpose:** Show detailed validation information

```bash
kg validate -v graph.yaml
kg validate --verbose graph.yaml
```

## Exit Codes

The command MUST use these exact exit codes:

- **0:** Validation successful, no errors
- **1:** Validation failed, errors found
- **2:** File not found or not readable
- **3:** Invalid command line arguments
- **4:** Internal error (unexpected failures)

## Output Format

### Success Output (Exit Code 0)

#### Default Format (table)

```
✅ Validation successful

File: knowledge-graph.yaml
Schema version: 1.0.0
Namespace: rosa-hcp
Entities: 3 repositories
Dependencies: 8 external, 2 internal

Summary:
  ✅ Schema format valid
  ✅ All required fields present
  ✅ All dependency references well-formed
  ✅ All email addresses valid
  ✅ All URLs accessible format
```

#### Compact Format

```
✅ knowledge-graph.yaml: VALID (schema=1.0.0, entities=3, deps=10)
```

#### JSON Format

```json
{
  "status": "valid",
  "file": "knowledge-graph.yaml",
  "schema_version": "1.0.0",
  "namespace": "rosa-hcp",
  "summary": {
    "repositories": 3,
    "external_dependencies": 8,
    "internal_dependencies": 2
  },
  "checks": [
    { "name": "schema_format", "status": "pass" },
    { "name": "required_fields", "status": "pass" },
    { "name": "dependency_references", "status": "pass" },
    { "name": "email_validation", "status": "pass" },
    { "name": "url_validation", "status": "pass" }
  ]
}
```

### Error Output (Exit Code 1)

#### Default Format (table)

```
❌ Validation failed

File: knowledge-graph.yaml
Errors found: 3

❌ Schema Format Error (line 15)
   Unknown field 'custom_field' in repository 'test-repo'
   Allowed fields: metadata, depends_on
   Help: Phase 1 schema only supports specific fields.

❌ Missing Required Field (line 8)
   Missing required field 'owners' in repository 'broken-repo'
   Required fields: owners, git_repo_url
   Help: All repositories must specify at least one owner.

❌ Invalid Dependency Reference (line 22)
   Invalid dependency reference 'requests' in repository 'test-repo'
   Expected: external://<ecosystem>/<package>/<version>
   Example: external://pypi/requests/2.31.0

Summary:
  ❌ 3 errors found
  ⚠️  Validation failed - fix errors and try again
```

#### Compact Format

```
❌ knowledge-graph.yaml: INVALID (3 errors)
```

#### JSON Format

```json
{
  "status": "invalid",
  "file": "knowledge-graph.yaml",
  "error_count": 3,
  "errors": [
    {
      "type": "unknown_field",
      "line": 15,
      "field": "custom_field",
      "entity": "test-repo",
      "message": "Unknown field 'custom_field' in repository 'test-repo'",
      "help": "Phase 1 schema only supports specific fields.",
      "allowed_fields": ["metadata", "depends_on"]
    },
    {
      "type": "missing_required_field",
      "line": 8,
      "field": "owners",
      "entity": "broken-repo",
      "message": "Missing required field 'owners' in repository 'broken-repo'",
      "help": "All repositories must specify at least one owner.",
      "required_fields": ["owners", "git_repo_url"]
    },
    {
      "type": "invalid_dependency_reference",
      "line": 22,
      "field": "depends_on",
      "entity": "test-repo",
      "value": "requests",
      "message": "Invalid dependency reference 'requests' in repository 'test-repo'",
      "help": "Expected: external://<ecosystem>/<package>/<version>",
      "example": "external://pypi/requests/2.31.0"
    }
  ]
}
```

### File Not Found (Exit Code 2)

```
❌ File not found: knowledge-graph.yaml

Searched in: /current/working/directory
Help: Create a knowledge-graph.yaml file or specify a different path
Example: kg validate /path/to/your/graph.yaml
```

### Invalid Arguments (Exit Code 3)

```
❌ Invalid arguments

Error: Unknown option --invalid-option
Usage: kg validate [FILE] [OPTIONS]

Run 'kg validate --help' for more information.
```

## Validation Behavior

### Schema Validation

1. **Parse YAML:** Validate YAML syntax is correct
2. **Schema version:** Verify schema_version field format and support
3. **Structure validation:** Ensure all required top-level fields present
4. **Entity validation:** Validate each entity against its schema
5. **Reference validation:** Check all dependency references are well-formed

### Error Collection

- **Continue on error:** Collect ALL errors, don't stop at first failure
- **Line numbers:** Report exact line numbers for YAML parsing errors
- **Context:** Provide entity/field context for each error
- **Helpful messages:** Suggest corrections, not just error descriptions

### Validation Order

1. **YAML parsing** (stop if fails)
2. **Schema version validation** (stop if unsupported)
3. **Global structure validation**
4. **Per-entity validation** (collect all errors)
5. **Cross-entity reference validation** (future: check internal references exist)

## Error Types and Messages

### Schema Format Errors

#### Unknown Field

```
Type: unknown_field
Message: Unknown field '{field}' in {entity_type} '{entity_name}'
Help: Phase 1 schema only supports specific fields. Custom fields will be supported in Phase 2.
Context: Allowed fields: {allowed_fields}
```

#### Invalid Schema Version

```
Type: invalid_schema_version
Message: Invalid schema version '{version}'
Help: Must follow semantic versioning (MAJOR.MINOR.PATCH)
Example: "1.0.0"
```

#### Unsupported Schema Version

```
Type: unsupported_schema_version
Message: Unsupported schema version '{version}'
Help: This validator supports versions: {supported_versions}
Context: Latest supported: {latest_version}
```

### Required Field Errors

#### Missing Required Field

```
Type: missing_required_field
Message: Missing required field '{field}' in {entity_type} '{entity_name}'
Help: All {entity_type} entities must specify {field}
Context: Required fields: {required_fields}
```

#### Empty Required Array

```
Type: empty_required_array
Message: Field '{field}' cannot be empty in {entity_type} '{entity_name}'
Help: Must specify at least one {field_description}
Example: {example_value}
```

### Format Validation Errors

#### Invalid Email Format

```
Type: invalid_email
Message: Invalid email '{email}' in owners for {entity_type} '{entity_name}'
Help: Must be valid email address format
Example: user@redhat.com
```

#### Invalid URL Format

```
Type: invalid_url
Message: Invalid URL '{url}' in {field} for {entity_type} '{entity_name}'
Help: Must be valid HTTP/HTTPS URL
Example: https://github.com/org/repo
```

#### Invalid Dependency Reference

```
Type: invalid_dependency_reference
Message: Invalid dependency reference '{reference}' in {entity_type} '{entity_name}'
Help: Must use full URI format
Format: external://<ecosystem>/<package>/<version> or internal://<namespace>/<entity>
Example: external://pypi/requests/2.31.0
```

## Verbose Mode

When `--verbose` flag is used, show additional information:

### Successful Validation

```
✅ Validation successful

File: knowledge-graph.yaml (1,247 bytes)
Schema version: 1.0.0
Parsed in: 0.023s
Validated in: 0.015s

Namespace: rosa-hcp
  └─ Repositories: 3
     ├─ rosa-hcp-service (2 owners, 4 dependencies)
     ├─ rosa-operator (1 owner, 2 dependencies)
     └─ documentation-site (1 owner, 0 dependencies)

Dependency Analysis:
  External dependencies: 8 unique packages
  ├─ pypi: 3 packages
  ├─ npm: 2 packages
  └─ golang.org/x: 3 packages

  Internal dependencies: 2 references
  ├─ shared-utils namespace: 1 reference
  └─ openshift-auth namespace: 1 reference

All checks passed ✅
```

### Failed Validation

```
❌ Validation failed

File: knowledge-graph.yaml (1,247 bytes)
Schema version: 1.0.0
Parsed in: 0.023s
Validation stopped with errors.

Detailed error analysis:
  └─ Repository: test-repo
     ├─ ❌ Unknown field: custom_field (line 15, column 7)
     │   Expected at this level: metadata, depends_on
     │
     └─ ❌ Invalid dependency: requests (line 22, column 9)
         Expected format: external://<ecosystem>/<package>/<version>
         Common ecosystems: pypi, npm, golang.org/x
         Did you mean: external://pypi/requests/2.31.0?

Fix these errors and run validation again.
```

## Integration with CI/CD

### GitHub Actions Integration

The validator MUST work seamlessly in CI environments:

```yaml
- name: Validate Knowledge Graph
  run: kg validate knowledge-graph.yaml --format json
  continue-on-error: false
```

### CI-Specific Behavior

- **Exit codes** must be reliable for CI decision making
- **JSON output** format must be stable for automated processing
- **Error messages** must be actionable for developers
- **Performance** should validate typical files in <1 second

## Future Extensions

### Phase 2 Planned Features

- **Cross-reference validation:** Check internal dependencies exist
- **Schema suggestion:** Suggest fixes for common errors
- **Batch validation:** Validate multiple files at once
- **Watch mode:** Continuous validation during development

### External Integration

- **Pre-commit hooks:** Fast validation for git workflows
- **IDE integration:** Real-time validation in editors
- **Web validation:** API endpoint for web-based validation
