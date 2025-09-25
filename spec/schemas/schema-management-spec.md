# Schema Management Specification

## Overview

This specification defines how entity schemas are dynamically loaded, validated, and hot-reloaded in the knowledge graph system. Schemas are defined in YAML files and can be updated without server restarts.

## Schema File Structure

### File Organization

```
schemas/
├── base_internal.yaml              # Base schema for internal entities
├── base_external.yaml              # Base schema for external entities
├── repository.yaml                 # Repository entity schema
├── external_dependency_package.yaml # External package schema
├── external_dependency_version.yaml # External version schema
└── service.yaml                    # Future: service entity schema
```

### Schema File Format

#### Base Schema Structure

```yaml
schema_type: base_internal|base_external|entity
schema_version: "1.0.0"
extends: null|base_internal|base_external # For entity schemas
governance: strict|permissive # For base schemas only

# Entity-specific fields (for entity schemas)
entity_type: string # Unique entity type name
description: string # Human-readable description

# Metadata field definitions
required_metadata:
  field_name:
    type: string|array|integer|float|boolean|datetime
    validation: email|url|enum|regex|custom
    description: string
    indexed: boolean
    # Additional constraints based on type

optional_metadata:
  # Same structure as required_metadata

readonly_metadata:
  # System-managed fields, same structure

# Relationship definitions
relationships:
  relationship_name:
    description: string
    target_types: [entity_type, ...]
    cardinality: one_to_one|one_to_many|many_to_one|many_to_many
    direction: inbound|outbound|bidirectional

# Dgraph schema generation
dgraph_type: string # Dgraph type name
dgraph_predicates:
  predicate_name:
    type: string|"[string]"|uid|"[uid]"|int|float|bool|datetime
    index: [exact, term, fulltext, trigram, hash]
    reverse: boolean
    description: string

# Validation and business rules
validation_rules:
  rule_name: boolean|string|object

# Auto-creation rules (for external entities)
auto_creation:
  enabled: boolean
  trigger: string
  id_format: string
```

## Schema Loading and Management

### Schema Loader Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class FieldDefinition:
    """Definition of a metadata field."""
    name: str
    type: str
    required: bool
    validation: Optional[str] = None
    indexed: bool = False
    description: str = ""
    # Type-specific constraints
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    allowed_values: Optional[List[str]] = None
    pattern: Optional[str] = None

@dataclass
class RelationshipDefinition:
    """Definition of an entity relationship."""
    name: str
    description: str
    target_types: List[str]
    cardinality: str
    direction: str

@dataclass
class EntitySchema:
    """Complete entity schema definition."""
    entity_type: str
    schema_version: str
    description: str
    extends: Optional[str]
    required_fields: List[FieldDefinition]
    optional_fields: List[FieldDefinition]
    readonly_fields: List[FieldDefinition]
    relationships: List[RelationshipDefinition]
    validation_rules: Dict[str, any]
    dgraph_type: str
    dgraph_predicates: Dict[str, any]

class SchemaLoader(ABC):
    """Interface for loading and managing schemas."""

    @abstractmethod
    async def load_schemas(self, schema_dir: str) -> Dict[str, EntitySchema]:
        """Load all schemas from directory."""
        pass

    @abstractmethod
    async def reload_schemas(self) -> Dict[str, EntitySchema]:
        """Reload schemas from disk."""
        pass

    @abstractmethod
    async def validate_schema_consistency(self, schemas: Dict[str, EntitySchema]) -> List[str]:
        """Validate schema consistency and return errors."""
        pass

    @abstractmethod
    async def get_entity_schema(self, entity_type: str) -> Optional[EntitySchema]:
        """Get schema for specific entity type."""
        pass
```

### File-Based Schema Loader

```python
import yaml
import os
from pathlib import Path

class FileSchemaLoader(SchemaLoader):
    """File-based schema loader implementation."""

    def __init__(self, schema_dir: str):
        self.schema_dir = Path(schema_dir)
        self.schemas: Dict[str, EntitySchema] = {}
        self.last_loaded: Optional[datetime] = None

    async def load_schemas(self, schema_dir: str = None) -> Dict[str, EntitySchema]:
        """Load all schema files from directory."""
        schema_path = Path(schema_dir) if schema_dir else self.schema_dir

        # Load base schemas first
        base_schemas = await self._load_base_schemas(schema_path)

        # Load entity schemas
        entity_schemas = await self._load_entity_schemas(schema_path, base_schemas)

        # Validate consistency
        errors = await self.validate_schema_consistency(entity_schemas)
        if errors:
            raise SchemaValidationError(f"Schema validation failed: {errors}")

        self.schemas = entity_schemas
        self.last_loaded = datetime.utcnow()

        return self.schemas

    async def _load_base_schemas(self, schema_path: Path) -> Dict[str, Dict]:
        """Load base schema definitions."""
        base_schemas = {}

        for base_file in ["base_internal.yaml", "base_external.yaml"]:
            file_path = schema_path / base_file
            if file_path.exists():
                with open(file_path, 'r') as f:
                    base_schemas[base_file.replace('.yaml', '')] = yaml.safe_load(f)

        return base_schemas

    async def _load_entity_schemas(self, schema_path: Path, base_schemas: Dict) -> Dict[str, EntitySchema]:
        """Load entity schema files and resolve inheritance."""
        schemas = {}

        for schema_file in schema_path.glob("*.yaml"):
            if schema_file.name.startswith("base_"):
                continue  # Skip base schemas

            with open(schema_file, 'r') as f:
                schema_data = yaml.safe_load(f)

            # Skip if not an entity schema
            if schema_data.get('schema_type') != 'entity':
                continue

            # Resolve inheritance
            resolved_schema = await self._resolve_inheritance(schema_data, base_schemas)

            # Convert to EntitySchema object
            entity_schema = await self._parse_entity_schema(resolved_schema)
            schemas[entity_schema.entity_type] = entity_schema

        return schemas

    async def _resolve_inheritance(self, schema_data: Dict, base_schemas: Dict) -> Dict:
        """Resolve schema inheritance from base schemas."""
        extends = schema_data.get('extends')
        if not extends or extends not in base_schemas:
            return schema_data

        base_schema = base_schemas[extends].copy()

        # Merge readonly metadata
        readonly_metadata = base_schema.get('readonly_metadata', {})
        schema_readonly = schema_data.get('readonly_metadata', {})
        readonly_metadata.update(schema_readonly)

        # Apply inheritance
        resolved = schema_data.copy()
        resolved['readonly_metadata'] = readonly_metadata
        resolved['validation_rules'] = {
            **base_schema.get('validation_rules', {}),
            **schema_data.get('validation_rules', {})
        }
        resolved['deletion_policy'] = base_schema.get('deletion_policy', {})

        return resolved
```

## Dynamic Dgraph Schema Generation

### Schema Generator

```python
class DgraphSchemaGenerator:
    """Generates Dgraph schema from entity schemas."""

    def __init__(self, schemas: Dict[str, EntitySchema]):
        self.schemas = schemas

    async def generate_schema(self) -> str:
        """Generate complete Dgraph schema string."""
        schema_parts = []

        # Generate type definitions
        for entity_schema in self.schemas.values():
            type_def = await self._generate_type_definition(entity_schema)
            schema_parts.append(type_def)

        # Generate predicate definitions
        predicates = await self._generate_predicate_definitions()
        schema_parts.extend(predicates)

        return "\n\n".join(schema_parts)

    async def _generate_type_definition(self, schema: EntitySchema) -> str:
        """Generate Dgraph type definition for entity."""
        type_name = schema.dgraph_type

        # Collect all predicates for this type
        predicates = []

        # Add metadata predicates
        for field in schema.required_fields + schema.optional_fields + schema.readonly_fields:
            predicates.append(field.name)

        # Add relationship predicates
        for relationship in schema.relationships:
            predicates.append(relationship.name)

        # Add system predicates
        predicates.extend(schema.dgraph_predicates.keys())

        predicate_list = "\n    ".join(predicates)

        return f"""type {type_name} {{
    {predicate_list}
}}"""

    async def _generate_predicate_definitions(self) -> List[str]:
        """Generate predicate definitions with indexes."""
        predicates = []
        seen_predicates = set()

        for entity_schema in self.schemas.values():
            for predicate_name, predicate_def in entity_schema.dgraph_predicates.items():
                if predicate_name in seen_predicates:
                    continue

                seen_predicates.add(predicate_name)

                # Build predicate definition
                predicate_type = predicate_def.get('type', 'string')
                indexes = predicate_def.get('index', [])
                reverse = predicate_def.get('reverse', False)

                definition = f"{predicate_name}: {predicate_type}"

                if indexes:
                    index_str = ", ".join(indexes)
                    definition += f" @index({index_str})"

                if reverse:
                    definition += " @reverse"

                definition += " ."
                predicates.append(definition)

        return predicates
```

## Hot Reload API

### Schema Reload Endpoint

```python
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/admin")

@router.post("/reload-schemas")
async def reload_schemas() -> Dict[str, Any]:
    """Reload schemas from disk and update Dgraph schema."""
    try:
        # Reload schemas
        new_schemas = await schema_loader.reload_schemas()

        # Validate backwards compatibility
        compatibility_errors = await validate_backwards_compatibility(
            current_schemas=current_schemas,
            new_schemas=new_schemas
        )

        if compatibility_errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "backwards_compatibility_violation",
                    "message": "New schemas break backwards compatibility",
                    "errors": compatibility_errors
                }
            )

        # Generate new Dgraph schema
        schema_generator = DgraphSchemaGenerator(new_schemas)
        dgraph_schema = await schema_generator.generate_schema()

        # Apply schema to Dgraph
        await storage.update_schema(dgraph_schema)

        # Update global schema reference
        global current_schemas
        current_schemas = new_schemas

        return {
            "status": "success",
            "message": "Schemas reloaded successfully",
            "schema_count": len(new_schemas),
            "reloaded_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "schema_reload_failed",
                "message": str(e)
            }
        )

async def validate_backwards_compatibility(
    current_schemas: Dict[str, EntitySchema],
    new_schemas: Dict[str, EntitySchema]
) -> List[str]:
    """Validate that new schemas don't break backwards compatibility."""
    errors = []

    for entity_type, current_schema in current_schemas.items():
        if entity_type not in new_schemas:
            errors.append(f"Entity type '{entity_type}' was removed")
            continue

        new_schema = new_schemas[entity_type]

        # Check for removed required fields
        current_required = {f.name for f in current_schema.required_fields}
        new_required = {f.name for f in new_schema.required_fields}

        removed_required = current_required - new_required
        if removed_required:
            errors.append(
                f"Required fields removed from {entity_type}: {removed_required}"
            )

        # Check for type changes
        for current_field in current_schema.required_fields + current_schema.optional_fields:
            new_field = next(
                (f for f in new_schema.required_fields + new_schema.optional_fields
                 if f.name == current_field.name),
                None
            )
            if new_field and new_field.type != current_field.type:
                errors.append(
                    f"Field type changed in {entity_type}.{current_field.name}: "
                    f"{current_field.type} -> {new_field.type}"
                )

    return errors
```

## Schema Validation Integration

### Dynamic Validator Factory

```python
class DynamicValidatorFactory:
    """Creates validators based on loaded schemas."""

    def __init__(self, schemas: Dict[str, EntitySchema]):
        self.schemas = schemas

    def create_entity_validator(self, entity_type: str) -> EntityValidator:
        """Create validator for specific entity type."""
        if entity_type not in self.schemas:
            raise ValueError(f"Unknown entity type: {entity_type}")

        schema = self.schemas[entity_type]
        return EntityValidator(schema)

class EntityValidator:
    """Validates entity data against schema."""

    def __init__(self, schema: EntitySchema):
        self.schema = schema

    async def validate(self, entity_data: Dict[str, Any]) -> List[ValidationError]:
        """Validate entity against schema."""
        errors = []

        # Check required fields
        for field in self.schema.required_fields:
            if field.name not in entity_data:
                errors.append(ValidationError(
                    type="missing_required_field",
                    field=field.name,
                    message=f"Missing required field '{field.name}'",
                    help=field.description
                ))

        # Validate field types and constraints
        for field_name, field_value in entity_data.items():
            field_def = self._find_field_definition(field_name)
            if field_def:
                field_errors = await self._validate_field(field_def, field_value)
                errors.extend(field_errors)

        return errors

    def _find_field_definition(self, field_name: str) -> Optional[FieldDefinition]:
        """Find field definition in schema."""
        all_fields = (
            self.schema.required_fields +
            self.schema.optional_fields +
            self.schema.readonly_fields
        )
        return next((f for f in all_fields if f.name == field_name), None)
```

This schema management system provides complete flexibility for defining entity types while maintaining backwards compatibility and enabling hot reloads without server restarts.
