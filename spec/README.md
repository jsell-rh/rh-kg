# Knowledge Graph System Specification

This directory contains comprehensive specifications for the Red Hat Knowledge Graph system,
following a specification-driven development approach.

## Specification Structure

### Core Specifications

- `schema-spec.md` - YAML schema format and validation rules
- `data-model-spec.md` - Dgraph data model and relationships
- `canonicalization-spec.md` - External dependency naming and ID generation

### Interface Specifications

- `cli/` - Command-line interface specifications
- `api/` - REST/GraphQL API specifications
- `storage/` - Dgraph storage interface specifications
- `validation/` - Validation logic and error handling specifications

## Specification-Driven Development Process

1. **Define the specification** - Clear behavior contracts with examples
2. **Write tests from spec** - Test cases that verify specification compliance
3. **Implement to pass tests** - Code that satisfies the specification
4. **Iterate on spec** - Refine based on implementation learnings

## Reading Order

For new contributors, read specifications in this order:

1. `schema-spec.md` - Understand the YAML format
2. `data-model-spec.md` - Understand how data is stored
3. `cli/validation-spec.md` - Understand the primary use case
4. `api/rest-spec.md` - Understand the server interface
5. `storage/dgraph-spec.md` - Understand storage implementation

## Specification Conventions

- **MUST/SHOULD/MAY** - RFC 2119 keywords for requirement levels
- **Examples** - Every specification includes working examples
- **Error cases** - Explicit error conditions and messages
- **Edge cases** - Boundary conditions and corner cases
- **Backwards compatibility** - Version compatibility requirements
