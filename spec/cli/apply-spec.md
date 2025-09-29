# CLI Apply Command Specification

## Overview

The `kg apply` command applies knowledge graph YAML files to storage backends, performing full validation (Layers 1-5) and storage operations. It supports both local storage and remote server deployment scenarios.

## Command Purpose

The `apply` command is designed for **storage operations** - taking validated YAML data and persisting it to the knowledge graph. This is distinct from the `validate` command which only performs schema validation.

## Command Line Interface

### Basic Syntax

```bash
kg apply [FILE] [OPTIONS]
```

### Arguments

#### FILE (optional)

- **Type:** Path
- **Default:** knowledge-graph.yaml
- **Purpose:** Path to YAML file to apply to storage
- **Validation:** File must exist and be readable

```bash
kg apply                          # Apply knowledge-graph.yaml
kg apply my-graph.yaml           # Apply specific file
kg apply /path/to/graph.yaml     # Apply with absolute path
```

### Options

#### --server (optional)

- **Type:** URL
- **Default:** None (use local storage)
- **Purpose:** Apply to remote knowledge graph server
- **Format:** HTTP/HTTPS URL to server API endpoint

```bash
kg apply --server=http://localhost:8000 graph.yaml
kg apply --server=https://kg.company.com graph.yaml
```

#### --dry-run (optional)

- **Type:** Boolean flag
- **Default:** false
- **Purpose:** Simulate storage operations without making changes
- **Behavior:** Shows what would be created, updated, or deleted

```bash
kg apply --dry-run graph.yaml                         # Local dry-run
kg apply --server=http://localhost:8000 --dry-run graph.yaml  # Remote dry-run
```

#### --force (optional)

- **Type:** Boolean flag
- **Default:** false
- **Purpose:** Skip confirmation prompts
- **Behavior:** Apply changes without interactive confirmation

```bash
kg apply --force graph.yaml                          # No prompts
kg apply --server=https://kg.company.com --force graph.yaml  # Force remote apply
```

#### --timeout (optional)

- **Type:** Integer (seconds)
- **Default:** 30
- **Purpose:** Timeout for storage operations
- **Range:** 1-300 seconds

```bash
kg apply --timeout=60 graph.yaml                     # 60-second timeout
kg apply --server=remote --timeout=120 graph.yaml    # 2-minute timeout for remote
```

#### --format (optional)

- **Type:** Enum: table, compact, json, yaml
- **Default:** table
- **Purpose:** Output format for apply results

```bash
kg apply --format=json graph.yaml                    # JSON output
kg apply --dry-run --format=compact graph.yaml       # Compact dry-run output
```

#### --verbose, -v (optional)

- **Type:** Boolean flag
- **Default:** false
- **Purpose:** Show detailed apply information and progress

```bash
kg apply -v graph.yaml                               # Verbose output
kg apply --verbose --dry-run graph.yaml              # Detailed dry-run info
```

## Operation Modes

### Local Storage Mode (Default)

- **Trigger:** No `--server` option provided
- **Behavior:** Apply to local storage backend (Dgraph via Docker Compose)
- **Requirements:** Local storage must be running

```bash
kg apply graph.yaml                                  # Apply to local storage
kg apply --dry-run graph.yaml                        # Local dry-run
```

### Remote Server Mode

- **Trigger:** `--server` URL provided
- **Behavior:** Apply to remote knowledge graph server via API
- **Authentication:** Uses standard HTTP headers/cookies

```bash
kg apply --server=https://kg.company.com graph.yaml  # Remote apply
kg apply --server=http://localhost:8000 graph.yaml   # Local server apply
```

## Validation Pipeline

The `apply` command performs the complete 5-layer validation pipeline:

### Layer 1-4: Schema Validation

- YAML syntax validation
- Schema structure validation
- Field format validation
- Business logic validation

### Layer 5: Reference Validation

- **Storage Queries:** Checks if referenced entities exist
- **Dependency Validation:** Validates external and internal references
- **Relationship Integrity:** Ensures relationship targets are valid

### Storage Operations

- **Entity Creation:** Create new entities not in storage
- **Entity Updates:** Update existing entities with new data
- **Relationship Management:** Create/update entity relationships
- **Atomic Operations:** All changes succeed or all fail

## Exit Codes

The command MUST use these exact exit codes:

- **0:** Apply successful, all entities stored
- **1:** Validation failed, no changes made
- **2:** File not found, not readable, or invalid command line arguments
- **3:** Storage connection failed or storage operation failed
- **4:** Internal error (unexpected failures)

## Output Formats

### Success Output (Exit Code 0)

#### Default Format (table)

```
✅ Apply successful

File: knowledge-graph.yaml
Server: local storage
Applied: 3 entities (2 created, 1 updated)
Relationships: 8 created

Summary:
  ✅ Schema validation passed
  ✅ Reference validation passed
  ✅ 2 repositories created
  ✅ 1 repository updated
  ✅ 5 external dependencies auto-created
  ✅ 8 relationships established

Time: 1.2s
```

#### Compact Format

```
✅ knowledge-graph.yaml: APPLIED (entities=3, created=2, updated=1, time=1.2s)
```

#### JSON Format

```json
{
  "status": "applied",
  "file": "knowledge-graph.yaml",
  "server": "local",
  "summary": {
    "entities_applied": 3,
    "entities_created": 2,
    "entities_updated": 1,
    "entities_deleted": 0,
    "relationships_created": 8,
    "validation_time_ms": 450,
    "storage_time_ms": 750
  },
  "operations": [
    {
      "entity_type": "repository",
      "entity_id": "myorg/myrepo",
      "operation": "created"
    }
  ]
}
```

### Dry-Run Output

#### Table Format

```
🔍 Dry-run results for knowledge-graph.yaml

Would create:
  📁 repository: myorg/new-repo
  📁 repository: myorg/another-repo

Would update:
  📝 repository: myorg/existing-repo
     - owners: ["old@company.com"] → ["new@company.com"]
     - depends_on: +2 dependencies

Would auto-create:
  📦 external_dependency_version: external://pypi/requests/2.31.0
  📦 external_dependency_version: external://npm/react/18.0.0

Summary: 2 create, 1 update, 2 auto-create, 0 warnings
```

#### JSON Dry-Run Format

```json
{
  "status": "dry_run",
  "file": "knowledge-graph.yaml",
  "would_create": [
    {
      "entity_type": "repository",
      "entity_id": "myorg/new-repo",
      "changes": {
        "owners": ["team@company.com"],
        "git_repo_url": "https://github.com/myorg/new-repo"
      }
    }
  ],
  "would_update": [
    {
      "entity_type": "repository",
      "entity_id": "myorg/existing-repo",
      "changes": {
        "owners": ["new@company.com"]
      }
    }
  ],
  "would_auto_create": [
    {
      "entity_type": "external_dependency_version",
      "entity_id": "external://pypi/requests/2.31.0"
    }
  ],
  "validation_issues": [],
  "summary": {
    "total_operations": 5,
    "create_count": 2,
    "update_count": 1,
    "auto_create_count": 2
  }
}
```

### Error Output (Exit Code 1)

#### Validation Errors

```
❌ Apply failed - validation errors

File: knowledge-graph.yaml
Errors found: 2

❌ missing_required_field in 'new-repo.owners': Field 'owners' is required
   💡 Help: Add owners field with at least one email address

❌ invalid_reference in 'new-repo.depends_on': Referenced entity 'nonexistent/repo' not found
   💡 Help: Ensure referenced entity exists or remove the reference

No changes were made to storage.
```

#### Storage Connection Errors (Exit Code 3)

```
❌ Storage connection failed

Server: http://localhost:8000
Error: Connection refused

Suggestions:
  • Check if storage backend is running
  • Verify server URL is correct
  • Check network connectivity
  • For local storage: run 'docker compose up -d'
```

## Security Considerations

### Remote Server Authentication

```bash
# Environment variables for authentication
export KG_API_TOKEN="your-token-here"
kg apply --server=https://kg.company.com graph.yaml

# Or use config file authentication
kg apply --server=https://kg.company.com --auth-config=~/.kg/auth graph.yaml
```

### Safe Apply Practices

1. **Always dry-run first:** `kg apply --dry-run graph.yaml`
2. **Validate locally:** `kg validate graph.yaml` before apply
3. **Use version control:** Commit YAML files before applying
4. **Staged deployment:** Apply to staging before production

## Integration with Storage Interface

The `apply` command uses the strongly-typed storage interface:

```python
from kg.storage import StorageInterface, DryRunResult, EntityData

async def apply_file(storage: StorageInterface, file_path: str, dry_run: bool) -> None:
    # Load and validate file (Layers 1-4)
    entities = await load_and_validate_file(file_path)

    if dry_run:
        # Get typed dry-run results
        result: DryRunResult = await storage.dry_run_apply(entities)
        display_dry_run_results(result)
    else:
        # Apply entities to storage
        for entity in entities:
            entity_id = await storage.store_entity(
                entity["entity_type"],
                entity["entity_id"],
                entity["metadata"],
                {"source_file": file_path}
            )
```

## Performance Considerations

### Batch Operations

Large files are processed in batches to avoid memory issues:

```bash
kg apply --batch-size=100 large-graph.yaml        # Process 100 entities at a time
```

### Progress Reporting

For large applies, show progress:

```
Applying knowledge-graph.yaml...
✅ Validated 1000 entities (2.1s)
🔄 Storing entities: 342/1000 (34%) [████▋     ] ETA: 8s
```

### Parallel Processing

Multiple entities can be processed in parallel where safe:

```bash
kg apply --parallel=4 graph.yaml                  # Use 4 parallel workers
```

This specification ensures the `apply` command provides a complete, production-ready workflow for applying knowledge graph data to storage backends.
