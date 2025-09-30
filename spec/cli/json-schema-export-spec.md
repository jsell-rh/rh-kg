# JSON Schema Export Specification

## Overview

This specification defines the JSON Schema export functionality that enables VSCode autocomplete and validation
for knowledge graph YAML files. The system generates JSON Schema (Draft 2020-12) from the runtime YAML schema
definitions, providing IDE support for developers authoring knowledge graph files.

## Goals

- **Developer Experience**: Enable VSCode autocomplete, inline validation, and documentation
- **Accuracy**: Generated JSON Schema must match runtime validation behavior exactly
- **Maintainability**: Automatically regenerate when YAML schemas change
- **Standards Compliance**: Use JSON Schema Draft 2020-12 for maximum compatibility

## Command Interface

### Basic Usage

```bash
kg schema export [OPTIONS]
```

### Options

#### --format (optional)

- **Type:** String
- **Default:** `json-schema`
- **Allowed values:** `json-schema`
- **Purpose:** Output format (reserved for future formats)

```bash
kg schema export --format json-schema
```

#### --output (optional)

- **Type:** File path
- **Default:** `.vscode/kg-schema.json`
- **Purpose:** Output file path for generated schema

```bash
kg schema export --output custom-path.json
kg schema export -o .vscode/kg-schema.json
```

#### --schema-dir (optional)

- **Type:** Directory path
- **Default:** `backend/schemas`
- **Purpose:** Directory containing YAML schema definitions

```bash
kg schema export --schema-dir /path/to/schemas
```

#### --pretty (optional)

- **Type:** Boolean flag
- **Default:** `true`
- **Purpose:** Pretty-print JSON output with indentation

```bash
kg schema export --pretty
kg schema export --no-pretty
```

### Exit Codes

- **0:** Success - schema exported successfully
- **1:** Error - schema loading failed or output write failed
- **2:** Validation error - generated schema is invalid

### Examples

```bash
# Default behavior
kg schema export

# Custom output location
kg schema export --output docs/kg-schema.json

# Non-pretty output for production
kg schema export --no-pretty --output dist/schema.json
```

## JSON Schema Structure

### Top-Level Schema

The generated JSON Schema MUST define the complete knowledge-graph.yaml structure:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://redhat.com/schemas/knowledge-graph/1.0.0",
  "title": "Red Hat Knowledge Graph Schema",
  "description": "Schema for Red Hat knowledge graph YAML files",
  "type": "object",
  "required": ["schema_version", "namespace", "entity"],
  "additionalProperties": false,
  "properties": {
    "schema_version": { "$ref": "#/$defs/schemaVersion" },
    "namespace": { "$ref": "#/$defs/namespace" },
    "entity": { "$ref": "#/$defs/entity" }
  },
  "$defs": {
    // Reusable definitions
  }
}
```

### Schema Version Definition

```json
"schemaVersion": {
  "type": "string",
  "pattern": "^\\d+\\.\\d+\\.\\d+$",
  "description": "Semantic version of the schema (MAJOR.MINOR.PATCH)",
  "examples": ["1.0.0"],
  "const": "1.0.0"
}
```

### Namespace Definition

```json
"namespace": {
  "type": "string",
  "pattern": "^[a-z][a-z0-9_-]*[a-z0-9]$|^[a-z]$",
  "description": "Namespace for grouping related entities (kebab-case format)",
  "examples": ["rosa-hcp", "shared-utils", "openshift-auth"]
}
```

### Entity Definition

The entity object MUST support all defined entity types (currently only `repository`):

```json
"entity": {
  "type": "object",
  "description": "Entity definitions for the knowledge graph",
  "properties": {
    "repository": {
      "type": "array",
      "description": "Repository entity definitions",
      "items": { "$ref": "#/$defs/repositoryEntity" }
    }
  },
  "additionalProperties": false
}
```

### Repository Entity Definition

```json
"repositoryEntity": {
  "type": "object",
  "description": "A code repository entity",
  "minProperties": 1,
  "maxProperties": 1,
  "additionalProperties": {
    "type": "object",
    "required": ["owners", "git_repo_url"],
    "additionalProperties": false,
    "properties": {
      "owners": {
        "type": "array",
        "description": "List of team email addresses responsible for repository",
        "items": {
          "type": "string",
          "format": "email",
          "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        },
        "minItems": 1,
        "examples": [["team@redhat.com"]]
      },
      "git_repo_url": {
        "type": "string",
        "format": "uri",
        "pattern": "^https?://",
        "description": "Git repository URL (GitHub, GitLab, etc.)",
        "examples": ["https://github.com/openshift/rosa-service"]
      },
      "depends_on": {
        "type": "array",
        "description": "External dependencies used by this repository",
        "items": { "$ref": "#/$defs/externalDependencyReference" },
        "default": [],
        "examples": [["external://pypi/requests/2.31.0"]]
      },
      "internal_depends_on": {
        "type": "array",
        "description": "Internal dependencies (other repositories)",
        "items": { "$ref": "#/$defs/internalDependencyReference" },
        "default": [],
        "examples": [["internal://shared-utils/logging-library"]]
      }
    }
  }
}
```

### Dependency Reference Definitions

```json
"externalDependencyReference": {
  "type": "string",
  "pattern": "^external://[a-zA-Z0-9._-]+/[a-zA-Z0-9@._/-]+/[a-zA-Z0-9._-]+$",
  "description": "External dependency reference: external://<ecosystem>/<package>/<version>",
  "examples": [
    "external://pypi/requests/2.31.0",
    "external://npm/@types/node/18.15.0",
    "external://github.com/stretchr/testify/v1.8.0"
  ]
},
"internalDependencyReference": {
  "type": "string",
  "pattern": "^internal://[a-z][a-z0-9_-]*[a-z0-9]/[a-zA-Z0-9._-]+$",
  "description": "Internal dependency reference: internal://<namespace>/<entity-name>",
  "examples": [
    "internal://shared-utils/logging-library",
    "internal://openshift-auth/auth-service"
  ]
}
```

## Mapping from YAML Schema to JSON Schema

### Field Type Mapping

| YAML Schema Type | JSON Schema Type                            | Additional Constraints     |
| ---------------- | ------------------------------------------- | -------------------------- |
| `string`         | `"type": "string"`                          | -                          |
| `array`          | `"type": "array"`                           | `items` from `items` field |
| `integer`        | `"type": "integer"`                         | -                          |
| `datetime`       | `"type": "string"`, `"format": "date-time"` | -                          |
| `bool`           | `"type": "boolean"`                         | -                          |

### Validation Mapping

| YAML Validation         | JSON Schema Equivalent                           |
| ----------------------- | ------------------------------------------------ |
| `validation: email`     | `"format": "email"`, pattern from EmailValidator |
| `validation: url`       | `"format": "uri"`, pattern `^https?://`          |
| `pattern: <regex>`      | `"pattern": "<regex>"`                           |
| `min_items: N`          | `"minItems": N`                                  |
| `max_items: N`          | `"maxItems": N`                                  |
| `min_length: N`         | `"minLength": N`                                 |
| `max_length: N`         | `"maxLength": N`                                 |
| `allowed_values: [...]` | `"enum": [...]`                                  |

### Required Field Mapping

- Fields in `required_metadata` → `"required": [...]` array
- Fields in `optional_metadata` → optional properties
- Fields in `readonly_metadata` → NOT included (system-managed)

### Relationship Mapping

Relationships defined in YAML schemas map to array properties:

```yaml
# YAML schema
relationships:
  depends_on:
    target_types: [external_dependency_version]
    cardinality: one_to_many
```

```json
// JSON Schema
"depends_on": {
  "type": "array",
  "items": { "$ref": "#/$defs/externalDependencyReference" }
}
```

## VSCode Integration

### Configuration File

The export command SHOULD create/update `.vscode/settings.json`:

```json
{
  "yaml.schemas": {
    ".vscode/kg-schema.json": [
      "**/knowledge-graph.yaml",
      "tmp/**/knowledge-graph.yaml"
    ]
  }
}
```

### User Experience Requirements

When properly configured, VSCode MUST provide:

1. **Autocomplete**: Suggest valid field names and values
2. **Inline Validation**: Show errors for invalid values in real-time
3. **Hover Documentation**: Display field descriptions from schema
4. **Schema Validation**: Highlight unknown fields and missing required fields

## Schema Generation Process

### Algorithm

1. **Load YAML Schemas**: Use `FileSchemaLoader` to load all schema definitions
2. **Resolve Inheritance**: Ensure base schema properties are properly merged
3. **Generate Top-Level Structure**: Create schema_version, namespace, entity structure
4. **Generate Entity Definitions**: For each entity type, create JSON Schema definition
5. **Generate Field Definitions**: Map required/optional fields to JSON Schema properties
6. **Generate Relationship Definitions**: Map relationships to array properties
7. **Generate $defs**: Create reusable definitions for common patterns
8. **Validate Output**: Ensure generated JSON Schema is valid
9. **Write Output**: Write formatted JSON to output file

### Pseudocode

```python
async def generate_json_schema(schema_dir: str) -> dict[str, Any]:
    # Load schemas
    loader = FileSchemaLoader(schema_dir)
    schemas = await loader.load_schemas()

    # Build JSON Schema structure
    json_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://redhat.com/schemas/knowledge-graph/1.0.0",
        "type": "object",
        "required": ["schema_version", "namespace", "entity"],
        "properties": {},
        "$defs": {}
    }

    # Add top-level properties
    json_schema["properties"]["schema_version"] = generate_version_schema()
    json_schema["properties"]["namespace"] = generate_namespace_schema()

    # Generate entity definitions
    entity_schema = {"type": "object", "properties": {}, "additionalProperties": false}
    for entity_type, entity_schema_obj in schemas.items():
        entity_def = generate_entity_definition(entity_schema_obj)
        entity_schema["properties"][entity_type] = entity_def
        json_schema["$defs"][f"{entity_type}Entity"] = entity_def

    json_schema["properties"]["entity"] = entity_schema

    # Generate common definitions
    json_schema["$defs"]["externalDependencyReference"] = generate_external_dep_schema()
    json_schema["$defs"]["internalDependencyReference"] = generate_internal_dep_schema()

    return json_schema
```

## Error Handling

### Schema Loading Errors

If schema loading fails:

```
Error: Failed to load schemas from 'backend/schemas'
Reason: Missing required field 'entity_type' in repository.yaml

Suggestion: Ensure all schema files are valid YAML with required fields
```

### Output Write Errors

If output file cannot be written:

```
Error: Failed to write schema to '.vscode/kg-schema.json'
Reason: Permission denied

Suggestion: Ensure .vscode directory exists and is writable
```

### Validation Errors

If generated schema is invalid:

```
Error: Generated JSON Schema is invalid
Reason: Invalid JSON Schema syntax at $defs.repository

Suggestion: This is a bug in the schema generator. Please report it.
```

## Testing Requirements

### Unit Tests

1. **Schema Generation**: Verify correct JSON Schema structure
2. **Field Mapping**: Ensure all field types map correctly
3. **Validation Mapping**: Verify validation rules translate properly
4. **Relationship Mapping**: Test relationship definitions
5. **Required Fields**: Verify required fields are correctly marked
6. **Pattern Generation**: Test regex patterns are correct

### Integration Tests

1. **VSCode Validation**: Generated schema validates known-good YAML files
2. **Error Detection**: Generated schema rejects known-bad YAML files
3. **Round-Trip**: YAML → validate → should match runtime validation
4. **Schema Updates**: Changing YAML schema regenerates correct JSON Schema

### Test Examples

```python
async def test_generate_repository_entity_schema():
    """Test repository entity JSON Schema generation."""
    schema_loader = FileSchemaLoader("backend/schemas")
    generator = JSONSchemaGenerator(schema_loader)

    json_schema = await generator.generate()

    # Verify structure
    assert "$schema" in json_schema
    assert json_schema["type"] == "object"
    assert "repository" in json_schema["properties"]["entity"]["properties"]

    # Verify repository definition
    repo_def = json_schema["$defs"]["repositoryEntity"]
    assert repo_def["additionalProperties"]["required"] == ["owners", "git_repo_url"]
```

## Future Enhancements

### Phase 2 Additions

When new entity types are added:

- Generator MUST automatically include new entity types
- No code changes required if schema follows standard format
- New entity types appear in autocomplete automatically

### Advanced Features

Potential future enhancements:

1. **Custom Snippets**: Generate VSCode snippet files
2. **JSON Schema $ref Optimization**: Use references to reduce duplication
3. **Multiple Schema Versions**: Support generating schemas for multiple versions
4. **YAML Language Server Integration**: Direct integration with yaml-language-server
5. **Schema Documentation**: Generate human-readable schema documentation

## Compatibility

### JSON Schema Version

- Use JSON Schema Draft 2020-12 for modern features
- Ensure compatibility with VSCode yaml-language-server
- Test with latest YAML extension for VSCode

### VSCode Version Requirements

- Minimum VSCode version: 1.70.0
- Requires: YAML extension by Red Hat (redhat.vscode-yaml)

## Success Criteria

JSON Schema export is successful when:

- [ ] Generated schema validates all valid knowledge-graph.yaml files
- [ ] Generated schema rejects all invalid knowledge-graph.yaml files
- [ ] VSCode provides autocomplete for all fields
- [ ] VSCode shows inline errors for validation failures
- [ ] Hover documentation displays field descriptions
- [ ] Schema regeneration is automated in CI/CD
- [ ] Generated schema matches runtime validation behavior 100%
