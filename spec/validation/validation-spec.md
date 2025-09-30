# Validation Logic Specification

## Overview

This specification defines the validation logic that ensures YAML files conform to the schema and business rules. Validation is performed at multiple layers: syntax, schema, semantics, and business logic.

## Validation Architecture

### Validation Pipeline

The validation process follows a strict pipeline with early exit on critical failures:

```
1. YAML Syntax Validation
   ↓ (fail fast if invalid YAML)
2. Schema Structure Validation
   ↓ (fail fast if unsupported schema)
3. Field Format Validation
   ↓ (collect all format errors)
4. Business Logic Validation
   ↓ (collect all logic errors)
5. Reference Validation (optional)
   ↓ (validate external references exist)
6. Deprecation Checking
   ↓ (collect deprecation warnings)
7. Final Validation Report
```

### Validation Modes

#### Strict Mode (Default)

- Reject unknown fields at any level
- Enforce all format constraints
- Require all mandatory fields
- Validate all dependency references

#### Permissive Mode (Future)

- Warn on unknown fields but don't fail
- Allow missing optional fields
- Skip reference validation

## Validation Layers

### Layer 1: YAML Syntax Validation

#### Purpose

Ensure the input is valid YAML before processing.

#### Implementation

```python
import yaml
from typing import Any, Optional

class YamlSyntaxValidator:
    """Validates YAML syntax and structure."""

    def validate(self, content: str) -> tuple[bool, Optional[dict[str, Any]], list[ValidationError]]:
        """
        Validate YAML syntax.

        Returns:
            (is_valid, parsed_data, errors)
        """
        try:
            data = yaml.safe_load(content)
            return True, data, []
        except yaml.YAMLError as e:
            error = ValidationError(
                type="yaml_syntax_error",
                message=f"Invalid YAML syntax: {e}",
                line=getattr(e, 'problem_mark', {}).get('line', 0) + 1,
                column=getattr(e, 'problem_mark', {}).get('column', 0) + 1,
                help="Ensure the file contains valid YAML syntax"
            )
            return False, None, [error]
```

#### Error Examples

```yaml
# Invalid YAML - unclosed quote
schema_version: "1.0.0
namespace: test

# Error:
# ValidationError: yaml_syntax_error
# Message: Invalid YAML syntax: found unexpected end of stream
# Line: 2, Column: 16
# Help: Ensure the file contains valid YAML syntax
```

### Layer 2: Schema Structure Validation

#### Purpose

Validate top-level structure and schema version compatibility.

#### Implementation

```python
class SchemaStructureValidator:
    """Validates schema structure and version."""

    SUPPORTED_VERSIONS = ["1.0.0"]
    REQUIRED_FIELDS = ["schema_version", "namespace", "entity"]

    def validate(self, data: dict[str, Any]) -> list[ValidationError]:
        """Validate schema structure."""
        errors = []

        # Check required top-level fields
        for field in self.REQUIRED_FIELDS:
            if field not in data:
                errors.append(ValidationError(
                    type="missing_required_field",
                    field=field,
                    message=f"Missing required top-level field '{field}'",
                    help=f"All knowledge graph files must include '{field}'"
                ))

        # Validate schema version
        if "schema_version" in data:
            version = data["schema_version"]
            if not isinstance(version, str):
                errors.append(ValidationError(
                    type="invalid_field_type",
                    field="schema_version",
                    message="Schema version must be a string",
                    help="Example: schema_version: \"1.0.0\""
                ))
            elif version not in self.SUPPORTED_VERSIONS:
                errors.append(ValidationError(
                    type="unsupported_schema_version",
                    field="schema_version",
                    message=f"Unsupported schema version '{version}'",
                    help=f"Supported versions: {', '.join(self.SUPPORTED_VERSIONS)}"
                ))

        return errors
```

### Layer 3: Field Format Validation

#### Purpose

Validate individual field formats and constraints using Pydantic models.

#### Implementation

```python
from pydantic import ValidationError as PydanticValidationError
from kg.core.models import KnowledgeGraphFile

class FieldFormatValidator:
    """Validates field formats using dynamic schemas."""

    def __init__(self, entity_schemas: Dict[str, EntitySchema]):
        self.entity_schemas = entity_schemas
        self.validator_factory = DynamicValidatorFactory(entity_schemas)

    def validate(self, data: dict[str, Any]) -> tuple[Optional[KnowledgeGraphFile], list[ValidationError]]:
        """
        Validate field formats using dynamic schemas.

        Returns:
            (parsed_model, validation_errors)
        """
        errors = []

        # Validate entities section
        entities = data.get("entity", {})

        for entity_type, entity_list in entities.items():
            if entity_type not in self.entity_schemas:
                errors.append(ValidationError(
                    type="unknown_entity_type",
                    field="entity",
                    message=f"Unknown entity type '{entity_type}'",
                    help=f"Supported entity types: {', '.join(self.entity_schemas.keys())}"
                ))
                continue

            # Validate each entity instance
            entity_validator = self.validator_factory.create_entity_validator(entity_type)

            for entity_data in entity_list:
                for entity_name, entity_fields in entity_data.items():
                    entity_errors = await entity_validator.validate(entity_fields)
                    # Add entity context to errors
                    for error in entity_errors:
                        error.entity = entity_name
                    errors.extend(entity_errors)

        # If no errors, try to create Pydantic model for backwards compatibility
        if not errors:
            try:
                model = KnowledgeGraphFile(**data)
                return model, []
            except PydanticValidationError as e:
                errors = self._convert_pydantic_errors(e)
                return None, errors

        return None, errors

    def _convert_pydantic_errors(self, pydantic_error: PydanticValidationError) -> list[ValidationError]:
        """Convert Pydantic validation errors to our format."""
        errors = []

        for error in pydantic_error.errors():
            location = error["loc"]
            error_type = error["type"]
            message = error["msg"]

            # Map Pydantic error types to our error types
            mapped_type = self._map_error_type(error_type)

            # Extract field and entity context
            field, entity = self._extract_context(location)

            validation_error = ValidationError(
                type=mapped_type,
                field=field,
                entity=entity,
                message=self._format_message(message, location),
                help=self._get_help_text(mapped_type, field)
            )
            errors.append(validation_error)

        return errors

    def _map_error_type(self, pydantic_type: str) -> str:
        """Map Pydantic error types to our validation types."""
        mapping = {
            "missing": "missing_required_field",
            "value_error.email": "invalid_email_format",
            "value_error.url": "invalid_url_format",
            "value_error.list.min_items": "empty_required_array",
            "type_error.str": "invalid_field_type",
            "value_error": "invalid_field_value",
        }
        return mapping.get(pydantic_type, "validation_error")
```

### Layer 4: Business Logic Validation

#### Purpose

Validate business rules and cross-field constraints.

#### Implementation

```python
class BusinessLogicValidator:
    """Validates business rules and constraints."""

    def validate(self, model: KnowledgeGraphFile) -> list[ValidationError]:
        """Validate business logic rules."""
        errors = []

        # Validate namespace consistency
        errors.extend(self._validate_namespace_consistency(model))

        # Validate dependency references
        errors.extend(self._validate_dependency_references(model))

        # Validate owner domain consistency
        errors.extend(self._validate_owner_domains(model))

        # Validate unique repository names
        errors.extend(self._validate_unique_names(model))

        return errors

    def _validate_namespace_consistency(self, model: KnowledgeGraphFile) -> list[ValidationError]:
        """Validate namespace is consistent across entities."""
        errors = []

        for repo in model.repositories:
            # All entities should be in the declared namespace implicitly
            # (This is enforced by the schema structure)
            pass

        return errors

    def _validate_dependency_references(self, model: KnowledgeGraphFile) -> list[ValidationError]:
        """Validate dependency reference formats."""
        errors = []

        for repo in model.repositories:
            for dep_ref in repo.depends_on:
                if dep_ref.startswith("external://"):
                    # Validate external dependency format
                    error = self._validate_external_dependency(dep_ref, repo.name)
                    if error:
                        errors.append(error)
                elif dep_ref.startswith("internal://"):
                    # Validate internal dependency format
                    error = self._validate_internal_dependency(dep_ref, repo.name)
                    if error:
                        errors.append(error)
                else:
                    errors.append(ValidationError(
                        type="invalid_dependency_reference",
                        field="depends_on",
                        entity=repo.name,
                        message=f"Invalid dependency reference '{dep_ref}'",
                        help="Must start with 'external://' or 'internal://'"
                    ))

        return errors

    def _validate_external_dependency(self, dep_ref: str, repo_name: str) -> Optional[ValidationError]:
        """Validate external dependency reference format."""
        # Remove external:// prefix
        ref_parts = dep_ref[11:].split("/")

        if len(ref_parts) < 3:
            return ValidationError(
                type="invalid_external_dependency",
                field="depends_on",
                entity=repo_name,
                message=f"Invalid external dependency format '{dep_ref}'",
                help="Format: external://<ecosystem>/<package>/<version>"
            )

        ecosystem = ref_parts[0]
        package = "/".join(ref_parts[1:-1])
        version = ref_parts[-1]

        # Validate ecosystem
        if ecosystem not in ["pypi", "npm", "golang.org/x", "github.com", "crates.io"]:
            return ValidationError(
                type="unsupported_ecosystem",
                field="depends_on",
                entity=repo_name,
                message=f"Unsupported ecosystem '{ecosystem}' in '{dep_ref}'",
                help="Supported: pypi, npm, golang.org/x, github.com, crates.io"
            )

        # Validate package name is not empty
        if not package:
            return ValidationError(
                type="empty_package_name",
                field="depends_on",
                entity=repo_name,
                message=f"Empty package name in '{dep_ref}'",
                help="Package name cannot be empty"
            )

        # Validate version is not empty
        if not version:
            return ValidationError(
                type="empty_version",
                field="depends_on",
                entity=repo_name,
                message=f"Empty version in '{dep_ref}'",
                help="Version cannot be empty"
            )

        return None

    def _validate_owner_domains(self, model: KnowledgeGraphFile) -> list[ValidationError]:
        """Validate owner email domains are consistent within namespace."""
        errors = []

        # Collect all domains used in this namespace
        domains = set()
        for repo in model.repositories:
            for owner in repo.owners:
                domain = str(owner).split("@")[1]
                domains.add(domain)

        # Warn if multiple domains (organizational policy)
        if len(domains) > 1:
            errors.append(ValidationError(
                type="multiple_owner_domains",
                field="owners",
                message=f"Multiple email domains in namespace '{model.namespace}': {', '.join(domains)}",
                help="Consider using consistent email domain within namespace"
            ))

        return errors
```

### Layer 5: Reference Validation (Optional)

#### Purpose

Validate that referenced entities actually exist in the knowledge graph.

#### Implementation

```python
from typing import Protocol

class StorageInterface(Protocol):
    """Storage interface for reference validation."""

    async def entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists in storage."""
        ...

class ReferenceValidator:
    """Validates that referenced entities exist."""

    def __init__(self, storage: Optional[StorageInterface] = None):
        self.storage = storage

    async def validate(self, model: KnowledgeGraphFile) -> list[ValidationError]:
        """Validate entity references exist."""
        if not self.storage:
            return []  # Skip validation if no storage available

        errors = []

        for repo in model.repositories:
            for dep_ref in repo.depends_on:
                if dep_ref.startswith("internal://"):
                    # Extract entity ID from internal reference
                    entity_id = dep_ref[11:]  # Remove "internal://"

                    if not await self.storage.entity_exists(entity_id):
                        errors.append(ValidationError(
                            type="reference_not_found",
                            field="depends_on",
                            entity=repo.name,
                            message=f"Referenced entity '{entity_id}' not found",
                            help="Ensure the referenced entity exists or will be created"
                        ))

        return errors
```

### Layer 6: Deprecation Checking

#### Purpose

Detect usage of deprecated fields, entity types, and relationships, emitting warnings with migration guidance.

#### Implementation

```python
class DeprecationValidator:
    """Validates and warns about deprecated schema elements."""

    def __init__(self, entity_schemas: dict[str, EntitySchema]):
        self.entity_schemas = entity_schemas

    async def validate(self, data: dict[str, Any]) -> list[ValidationWarning]:
        """Check for usage of deprecated fields and emit warnings."""
        warnings = []

        entities = data.get("entity", {})

        for entity_type, entity_list in entities.items():
            if entity_type not in self.entity_schemas:
                continue

            schema = self.entity_schemas[entity_type]

            # Check if entity type itself is deprecated
            if schema.deprecated:
                warnings.extend(self._create_entity_type_warning(
                    entity_type=entity_type,
                    schema=schema,
                    entity_count=len(entity_list)
                ))

            # Check each entity instance for deprecated fields
            for entity_data in entity_list:
                for entity_name, entity_fields in entity_data.items():
                    warnings.extend(self._check_deprecated_fields(
                        entity_type=entity_type,
                        entity_name=entity_name,
                        entity_fields=entity_fields,
                        schema=schema
                    ))

        return warnings

    def _create_entity_type_warning(
        self,
        entity_type: str,
        schema: EntitySchema,
        entity_count: int
    ) -> list[ValidationWarning]:
        """Create warning for deprecated entity type."""
        warning = ValidationWarning(
            type="deprecated_entity_type",
            message=f"Entity type '{entity_type}' is deprecated (used {entity_count} times)",
            field="entity",
            help=self._format_deprecation_help(schema.deprecation_info)
        )
        return [warning]

    def _check_deprecated_fields(
        self,
        entity_type: str,
        entity_name: str,
        entity_fields: dict[str, Any],
        schema: EntitySchema
    ) -> list[ValidationWarning]:
        """Check entity fields for deprecated usage."""
        warnings = []

        # Check regular fields
        for field_name, field_value in entity_fields.items():
            if field_name == "metadata":
                # Handle metadata fields separately
                warnings.extend(self._check_metadata_deprecations(
                    entity_type=entity_type,
                    entity_name=entity_name,
                    metadata=field_value,
                    schema=schema
                ))
                continue

            field_schema = schema.fields.get(field_name)
            if field_schema and field_schema.deprecated:
                warnings.append(ValidationWarning(
                    type="deprecated_field",
                    field=field_name,
                    entity=entity_name,
                    message=f"Field '{field_name}' is deprecated in {entity_type} '{entity_name}'",
                    help=self._format_deprecation_help(field_schema.deprecation_info)
                ))

        # Check relationships
        for rel_name, rel_targets in entity_fields.items():
            rel_schema = schema.relationships.get(rel_name)
            if rel_schema and rel_schema.deprecated:
                warnings.append(ValidationWarning(
                    type="deprecated_relationship",
                    field=rel_name,
                    entity=entity_name,
                    message=f"Relationship '{rel_name}' is deprecated in {entity_type} '{entity_name}'",
                    help=self._format_deprecation_help(rel_schema.deprecation_info)
                ))

        return warnings

    def _check_metadata_deprecations(
        self,
        entity_type: str,
        entity_name: str,
        metadata: dict[str, Any],
        schema: EntitySchema
    ) -> list[ValidationWarning]:
        """Check metadata fields for deprecations."""
        warnings = []

        for meta_field, meta_value in metadata.items():
            # Check if this metadata field is deprecated in schema
            if hasattr(schema, 'metadata_fields'):
                meta_schema = schema.metadata_fields.get(meta_field)
                if meta_schema and meta_schema.deprecated:
                    warnings.append(ValidationWarning(
                        type="deprecated_metadata_field",
                        field=f"metadata.{meta_field}",
                        entity=entity_name,
                        message=f"Metadata field '{meta_field}' is deprecated in {entity_type} '{entity_name}'",
                        help=self._format_deprecation_help(meta_schema.deprecation_info)
                    ))

        return warnings

    def _format_deprecation_help(self, deprecation_info: DeprecationInfo) -> str:
        """Format deprecation information as help text."""
        help_parts = []

        if deprecation_info.deprecated_since:
            help_parts.append(f"Deprecated since: {deprecation_info.deprecated_since}")

        if deprecation_info.deprecated_reason:
            help_parts.append(f"Reason: {deprecation_info.deprecated_reason}")

        if deprecation_info.removal_planned:
            help_parts.append(f"Removal planned: {deprecation_info.removal_planned}")

        if deprecation_info.migration_guide:
            help_parts.append(f"Migration:\n{deprecation_info.migration_guide}")

        return " | ".join(help_parts) if help_parts else "No migration guidance available"
```

#### Deprecation Info Model

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DeprecationInfo:
    """Deprecation metadata for schema elements."""
    deprecated: bool = False
    deprecated_since: Optional[str] = None
    deprecated_reason: Optional[str] = None
    removal_planned: Optional[str] = None
    migration_guide: Optional[str] = None
```

#### Warning Examples

**Deprecated Field Usage:**

```python
ValidationWarning(
    type="deprecated_field",
    field="legacy_owner",
    entity="test-repo",
    message="Field 'legacy_owner' is deprecated in repository 'test-repo'",
    help="Deprecated since: 1.2.0 | Reason: Use metadata.owners array instead | Removal planned: 2.0.0 | Migration: Replace legacy_owner with metadata.owners array"
)
```

**Deprecated Relationship Usage:**

```python
ValidationWarning(
    type="deprecated_relationship",
    field="legacy_depends_on",
    entity="test-service",
    message="Relationship 'legacy_depends_on' is deprecated in service 'test-service'",
    help="Deprecated since: 1.3.0 | Reason: Use new depends_on with URI format | Removal planned: 2.0.0"
)
```

**Deprecated Entity Type:**

```python
ValidationWarning(
    type="deprecated_entity_type",
    field="entity",
    message="Entity type 'legacy_component' is deprecated (used 3 times)",
    help="Deprecated since: 1.4.0 | Reason: Use 'control_plane_component' instead | Removal planned: 3.0.0"
)
```

## Validation Orchestrator

### Main Validator Class

```python
class KnowledgeGraphValidator:
    """Main validator that orchestrates all validation layers."""

    def __init__(self,
                 entity_schemas: Dict[str, EntitySchema],
                 storage: Optional[StorageInterface] = None,
                 strict_mode: bool = True):
        self.entity_schemas = entity_schemas
        self.storage = storage
        self.strict_mode = strict_mode

        # Initialize validators with dynamic schemas
        self.yaml_validator = YamlSyntaxValidator()
        self.structure_validator = SchemaStructureValidator()
        self.format_validator = FieldFormatValidator(entity_schemas)
        self.business_validator = BusinessLogicValidator(entity_schemas)
        self.reference_validator = ReferenceValidator(storage)
        self.deprecation_validator = DeprecationValidator(entity_schemas)

    async def validate(self, content: str) -> ValidationResult:
        """
        Perform complete validation of YAML content.

        Returns ValidationResult with all errors and warnings.
        """
        errors = []
        warnings = []

        # Layer 1: YAML Syntax
        is_valid_yaml, data, yaml_errors = self.yaml_validator.validate(content)
        if not is_valid_yaml:
            return ValidationResult(
                is_valid=False,
                errors=yaml_errors,
                warnings=warnings
            )

        # Layer 2: Schema Structure
        structure_errors = self.structure_validator.validate(data)
        errors.extend(structure_errors)

        # If critical structure errors, stop here
        if any(e.type in ["missing_required_field", "unsupported_schema_version"]
               for e in structure_errors):
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

        # Layer 3: Field Format
        model, format_errors = self.format_validator.validate(data)
        errors.extend(format_errors)

        # If format errors in strict mode, may continue to collect all errors
        if not model:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

        # Layer 4: Business Logic
        business_errors = self.business_validator.validate(model)
        errors.extend(business_errors)

        # Layer 5: Reference Validation (if storage available)
        if self.storage:
            reference_errors = await self.reference_validator.validate(model)
            errors.extend(reference_errors)

        # Layer 6: Deprecation Checking (always run, emits warnings not errors)
        deprecation_warnings = await self.deprecation_validator.validate(data)
        warnings.extend(deprecation_warnings)

        # Determine final validation result
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            model=model if is_valid else None
        )
```

### Validation Result

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ValidationError:
    """Represents a validation error."""
    type: str
    message: str
    field: Optional[str] = None
    entity: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    help: Optional[str] = None

@dataclass
class ValidationWarning:
    """Represents a validation warning."""
    type: str
    message: str
    field: Optional[str] = None
    entity: Optional[str] = None
    help: Optional[str] = None

@dataclass
class ValidationResult:
    """Complete validation result."""
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    model: Optional[KnowledgeGraphFile] = None

    @property
    def error_count(self) -> int:
        """Number of validation errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Number of validation warnings."""
        return len(self.warnings)
```

## Error Message Standards

### Error Message Format

All error messages MUST follow this format:

- **Type**: Machine-readable error type
- **Message**: Human-readable description
- **Help**: Actionable guidance for fixing the error
- **Context**: Field/entity where error occurred

### Error Message Examples

#### Schema Errors

```python
ValidationError(
    type="missing_required_field",
    field="owners",
    entity="test-repo",
    message="Missing required field 'owners' in repository 'test-repo'",
    help="All repositories must specify at least one owner email address"
)
```

#### Format Errors

```python
ValidationError(
    type="invalid_email_format",
    field="owners",
    entity="test-repo",
    message="Invalid email 'not-an-email' in owners for repository 'test-repo'",
    help="Owner emails must be valid email addresses (user@domain.com)"
)
```

#### Business Logic Errors

```python
ValidationError(
    type="invalid_dependency_reference",
    field="depends_on",
    entity="test-repo",
    message="Invalid dependency reference 'requests' in repository 'test-repo'",
    help="Dependencies must use format: external://<ecosystem>/<package>/<version>"
)
```

## Testing Strategy

### Unit Test Coverage

```python
class TestValidationLayers:
    """Test each validation layer independently."""

    def test_yaml_syntax_validation(self):
        """Test YAML syntax validation."""
        # Valid YAML
        result = YamlSyntaxValidator().validate("key: value")
        assert result[0] is True

        # Invalid YAML
        result = YamlSyntaxValidator().validate("key: [invalid")
        assert result[0] is False
        assert len(result[2]) == 1
        assert result[2][0].type == "yaml_syntax_error"

    def test_field_format_validation(self):
        """Test field format validation."""
        # Valid data
        data = {
            "schema_version": "1.0.0",
            "namespace": "test",
            "entity": {"repository": []}
        }
        model, errors = FieldFormatValidator().validate(data)
        assert model is not None
        assert len(errors) == 0

        # Invalid email
        data["entity"]["repository"] = [{
            "test-repo": {
                "metadata": {"owners": ["invalid-email"]},
                "depends_on": []
            }
        }]
        model, errors = FieldFormatValidator().validate(data)
        assert model is None
        assert any(e.type == "invalid_email_format" for e in errors)

    async def test_deprecation_validation(self):
        """Test deprecation warning generation."""
        # Schema with deprecated field
        schema = EntitySchema(
            entity_type="repository",
            fields={
                "legacy_owner": FieldSchema(
                    type="string",
                    deprecated=True,
                    deprecation_info=DeprecationInfo(
                        deprecated=True,
                        deprecated_since="1.2.0",
                        deprecated_reason="Use metadata.owners instead"
                    )
                )
            }
        )

        # Data using deprecated field
        data = {
            "schema_version": "1.0.0",
            "namespace": "test",
            "entity": {
                "repository": [{
                    "test-repo": {
                        "legacy_owner": "team@redhat.com",
                        "metadata": {"owners": ["team@redhat.com"]},
                        "depends_on": []
                    }
                }]
            }
        }

        validator = DeprecationValidator(entity_schemas={"repository": schema})
        warnings = await validator.validate(data)

        assert len(warnings) == 1
        assert warnings[0].type == "deprecated_field"
        assert warnings[0].field == "legacy_owner"
        assert "1.2.0" in warnings[0].help
```

### Integration Test Coverage

```python
class TestValidationIntegration:
    """Test complete validation pipeline."""

    async def test_complete_validation_success(self):
        """Test successful validation of complete YAML."""
        yaml_content = """
        schema_version: "1.0.0"
        namespace: "test"
        entity:
          repository:
            - test-repo:
                metadata:
                  owners: ["test@redhat.com"]
                  git_repo_url: "https://github.com/test/repo"
                depends_on: ["external://pypi/requests/2.31.0"]
        """

        validator = KnowledgeGraphValidator()
        result = await validator.validate(yaml_content)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.model is not None

    async def test_complete_validation_failure(self):
        """Test validation failure with multiple errors."""
        yaml_content = """
        schema_version: "invalid"
        namespace: "test"
        entity:
          repository:
            - test-repo:
                metadata:
                  owners: []  # Empty owners
                depends_on: ["invalid-reference"]
        """

        validator = KnowledgeGraphValidator()
        result = await validator.validate(yaml_content)

        assert not result.is_valid
        assert len(result.errors) > 1
        error_types = [e.type for e in result.errors]
        assert "unsupported_schema_version" in error_types
        assert "empty_required_array" in error_types

    async def test_validation_with_deprecation_warnings(self):
        """Test validation passes with deprecation warnings."""
        # YAML using deprecated field
        yaml_content = """
        schema_version: "1.0.0"
        namespace: "test"
        entity:
          repository:
            - test-repo:
                legacy_owner: "team@redhat.com"
                metadata:
                  owners: ["team@redhat.com"]
                  git_repo_url: "https://github.com/test/repo"
                depends_on: []
        """

        # Create validator with schema containing deprecated field
        entity_schemas = {
            "repository": EntitySchema(
                entity_type="repository",
                fields={
                    "legacy_owner": FieldSchema(
                        type="string",
                        deprecated=True,
                        deprecation_info=DeprecationInfo(
                            deprecated=True,
                            deprecated_since="1.2.0",
                            deprecated_reason="Use metadata.owners instead",
                            removal_planned="2.0.0"
                        )
                    )
                }
            )
        }

        validator = KnowledgeGraphValidator(entity_schemas=entity_schemas)
        result = await validator.validate(yaml_content)

        # Validation should pass despite deprecation
        assert result.is_valid
        assert len(result.errors) == 0

        # But warnings should be present
        assert len(result.warnings) >= 1
        assert any(w.type == "deprecated_field" for w in result.warnings)
        assert any(w.field == "legacy_owner" for w in result.warnings)
```

This validation specification provides comprehensive validation logic that ensures data quality while providing clear, actionable error messages to users.
