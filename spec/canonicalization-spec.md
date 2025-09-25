# External Dependency Canonicalization Specification

## Overview

This specification defines how external dependency references are normalized and canonicalized to prevent duplicates and ensure consistent naming across the knowledge graph.

## Canonicalization Process

### Input Processing
External dependencies can be referenced in multiple formats in YAML files, but they MUST be canonicalized to a standard format before storage.

### Canonical Format
```
external://<ecosystem>/<package>/<version>
```

### Processing Pipeline
1. **Parse dependency reference** from YAML
2. **Detect ecosystem** (auto-detection or explicit)
3. **Normalize package name** according to ecosystem rules
4. **Normalize version** according to ecosystem rules
5. **Generate canonical ID**
6. **Validate canonical ID format**

## Required Format

### Explicit Format Only
All external dependencies MUST use the complete URI format with explicit ecosystem specification:

**Required format:**
```yaml
depends_on:
  - "external://pypi/requests/2.31.0"      # ✅ Correct format
  - "external://npm/express/4.18.0"        # ✅ Correct format
  - "external://golang.org/x/client-go/v0.28.4"  # ✅ Correct format
```

**Invalid formats:**
```yaml
depends_on:
  - "requests/2.31.0"                      # ❌ Missing ecosystem
  - "pypi:requests/2.31.0"                 # ❌ Wrong format
  - "requests"                             # ❌ Missing version
```

### Format Validation
```python
def validate_external_dependency_format(dep_ref: str) -> bool:
    """Validate external dependency follows required format."""
    if not dep_ref.startswith("external://"):
        return False

    parts = dep_ref[11:].split("/")  # Remove "external://"
    if len(parts) < 3:
        return False

    ecosystem, package, version = parts[0], "/".join(parts[1:-1]), parts[-1]
    return all([ecosystem, package, version])
```

## Package Name Normalization

### Python (PyPI) Ecosystem

#### Normalization Rules
- Convert to lowercase
- Replace underscores with hyphens
- Remove redundant prefixes

**Examples:**
```
Input: "Python-Requests" → Output: "requests"
Input: "python_requests" → Output: "requests"
Input: "PyQt5" → Output: "pyqt5"
Input: "beautifulsoup4" → Output: "beautifulsoup4"
```

#### Known Aliases
```python
PYPI_ALIASES = {
    "python-requests": "requests",
    "python_requests": "requests",
    "py-requests": "requests",
    "PyYAML": "pyyaml",
    "Pillow": "pillow",
}
```

### Node.js (NPM) Ecosystem

#### Normalization Rules
- Preserve exact case for scoped packages
- Convert unscoped packages to lowercase
- Preserve scope prefixes

**Examples:**
```
Input: "@Types/Node" → Output: "@types/node"
Input: "@types/NODE" → Output: "@types/node"
Input: "Express" → Output: "express"
Input: "@angular/core" → Output: "@angular/core"
```

#### Scoped Package Handling
```python
def normalize_npm_package(name: str) -> str:
    """Normalize NPM package name."""
    if name.startswith('@'):
        # Scoped package: @scope/package
        scope, package = name.split('/', 1)
        return f"{scope.lower()}/{package.lower()}"
    else:
        # Unscoped package
        return name.lower()
```

### Go Modules Ecosystem

#### Normalization Rules
- Preserve exact case for domain names
- Preserve exact case for repository paths
- Normalize protocol prefixes

**Examples:**
```
Input: "GITHUB.COM/stretchr/testify" → Output: "github.com/stretchr/testify"
Input: "k8s.io/CLIENT-GO" → Output: "k8s.io/client-go"
Input: "golang.org/x/crypto" → Output: "golang.org/x/crypto"
```

#### Domain-Based Routing
```python
GO_MODULE_ECOSYSTEMS = {
    "github.com": "github.com",
    "gitlab.com": "gitlab.com",
    "golang.org/x": "golang.org/x",
    "k8s.io": "golang.org/x",  # Kubernetes packages use golang.org/x ecosystem
    "sigs.k8s.io": "golang.org/x",
}

def normalize_go_module(name: str) -> tuple[str, str]:
    """Normalize Go module name and determine ecosystem."""
    # Normalize domain to lowercase
    parts = name.split('/')
    if len(parts) >= 2:
        domain = parts[0].lower()
        path = '/'.join(parts[1:])

        # Determine ecosystem
        ecosystem = GO_MODULE_ECOSYSTEMS.get(domain, "golang.org/x")

        return ecosystem, f"{domain}/{path}"

    raise ValueError(f"Invalid Go module format: {name}")
```

## Version Normalization

### Semantic Versioning (SemVer)

#### Standard Format
```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

#### Normalization Rules
- Remove leading 'v' prefix
- Ensure three-part version (add .0 if needed)
- Preserve prerelease and build metadata

**Examples:**
```
Input: "v2.31.0" → Output: "2.31.0"
Input: "2.31" → Output: "2.31.0"
Input: "1.0.0-alpha.1" → Output: "1.0.0-alpha.1"
Input: "2.0.0+build.123" → Output: "2.0.0+build.123"
```

### Python Version Normalization

#### PEP 440 Compliance
- Convert to canonical form
- Handle epoch, prerelease, and local versions

**Examples:**
```
Input: "2.31.0" → Output: "2.31.0"
Input: "2.31.0a1" → Output: "2.31.0a1"
Input: "2.31.0.post1" → Output: "2.31.0.post1"
Input: "1!2.31.0" → Output: "1!2.31.0"
```

### NPM Version Normalization

#### Follow Node.js SemVer
- Same as standard SemVer
- Handle npm-specific prerelease tags

**Examples:**
```
Input: "^18.15.0" → Error: "Version ranges not supported, use exact versions"
Input: "18.15.0-next.1" → Output: "18.15.0-next.1"
Input: "latest" → Error: "Tag versions not supported, use exact versions"
```

### Go Module Version Normalization

#### Handle Go-specific versioning
- Preserve 'v' prefix for Go modules
- Handle pseudo-versions
- Support +incompatible suffix

**Examples:**
```
Input: "v0.28.4" → Output: "v0.28.4"
Input: "v1.8.0+incompatible" → Output: "v1.8.0+incompatible"
Input: "v0.0.0-20230101120000-abcdef123456" → Output: "v0.0.0-20230101120000-abcdef123456"
```

## Canonical ID Generation

### Generation Algorithm
```python
def generate_canonical_id(
    ecosystem: str,
    package_name: str,
    version: str
) -> str:
    """Generate canonical external dependency ID."""

    # Validate inputs
    validate_ecosystem(ecosystem)
    validate_package_name(package_name, ecosystem)
    validate_version(version, ecosystem)

    # Generate canonical ID
    return f"external://{ecosystem}/{package_name}/{version}"
```

### Validation Rules

#### Ecosystem Validation
```python
SUPPORTED_ECOSYSTEMS = {
    "pypi",
    "npm",
    "golang.org/x",
    "github.com",
    "crates.io",
    "maven",  # Future support
    "nuget",  # Future support
}

def validate_ecosystem(ecosystem: str) -> None:
    """Validate ecosystem is supported."""
    if ecosystem not in SUPPORTED_ECOSYSTEMS:
        raise UnsupportedEcosystemError(
            f"Unsupported ecosystem: {ecosystem}. "
            f"Supported: {', '.join(SUPPORTED_ECOSYSTEMS)}"
        )
```

#### Package Name Validation
```python
def validate_package_name(package_name: str, ecosystem: str) -> None:
    """Validate package name format for ecosystem."""

    if ecosystem == "pypi":
        # Python package names: letters, numbers, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9._-]+$", package_name):
            raise InvalidPackageNameError(
                f"Invalid PyPI package name: {package_name}"
            )

    elif ecosystem == "npm":
        # NPM package names: support scoped packages
        if package_name.startswith('@'):
            if not re.match(r"^@[a-z0-9-~][a-z0-9-._~]*/[a-z0-9-~][a-z0-9-._~]*$", package_name):
                raise InvalidPackageNameError(
                    f"Invalid NPM scoped package name: {package_name}"
                )
        else:
            if not re.match(r"^[a-z0-9-~][a-z0-9-._~]*$", package_name):
                raise InvalidPackageNameError(
                    f"Invalid NPM package name: {package_name}"
                )

    elif ecosystem in ["golang.org/x", "github.com"]:
        # Go module paths: domain/path format
        if not re.match(r"^[a-z0-9.-]+/[a-zA-Z0-9._/-]+$", package_name):
            raise InvalidPackageNameError(
                f"Invalid Go module name: {package_name}"
            )
```

## Canonicalization Examples

### Input/Output Examples

#### Python Dependencies
```
Input: "requests"
Context: requirements.txt present
Output: "external://pypi/requests/2.31.0"

Input: "PyYAML/6.0.1"
Context: pyproject.toml present
Output: "external://pypi/pyyaml/6.0.1"

Input: "python-requests/2.31.0"
Context: setup.py present
Output: "external://pypi/requests/2.31.0"
```

#### Node.js Dependencies
```
Input: "@types/node"
Context: package.json present
Output: "external://npm/@types/node/18.15.0"

Input: "Express/4.18.0"
Context: package.json present
Output: "external://npm/express/4.18.0"

Input: "npm:@angular/core/15.2.0"
Context: Explicit ecosystem
Output: "external://npm/@angular/core/15.2.0"
```

#### Go Dependencies
```
Input: "github.com/stretchr/testify/v1.8.0"
Context: go.mod present
Output: "external://github.com/stretchr/testify/v1.8.0"

Input: "k8s.io/client-go/v0.28.4"
Context: go.mod present
Output: "external://golang.org/x/k8s.io/client-go/v0.28.4"

Input: "golang.org/x/crypto/v0.10.0"
Context: go.mod present
Output: "external://golang.org/x/golang.org/x/crypto/v0.10.0"
```

## Error Handling

### Canonicalization Errors

#### Missing Ecosystem
```
Error: MissingEcosystemError
Message: Dependency reference missing ecosystem: 'requests/2.31.0'
Help: Use complete external dependency format
Example: external://pypi/requests/2.31.0
```

#### Invalid Package Name
```
Error: InvalidPackageNameError
Message: Invalid NPM package name 'Invalid@Package'
Help: NPM package names must be lowercase and follow naming rules
Valid: external://npm/valid-package/1.0.0
```

#### Unsupported Ecosystem
```
Error: UnsupportedEcosystemError
Message: Unsupported ecosystem 'unsupported'
Help: Supported ecosystems: pypi, npm, golang.org/x, github.com, crates.io
```

#### Version Format Error
```
Error: InvalidVersionError
Message: Invalid version format '^1.0.0' for NPM package 'express'
Help: Use exact versions, not version ranges
Valid: external://npm/express/4.18.0
```

## Future Extensions

### Phase 2 Enhancements
- **Auto-detection from repository context:** Scan package.json, requirements.txt, etc. to suggest dependencies
- **Version range support:** Handle semantic version ranges
- **Tag resolution:** Resolve 'latest', 'stable' tags to specific versions
- **Custom ecosystems:** Support for internal package repositories

### Integration Features
- **Real-time validation:** Check package existence during canonicalization
- **Version availability:** Verify specified versions exist in ecosystem
- **Security scanning:** Integration with vulnerability databases
- **Dependency discovery:** Automated scanning of repository files to generate dependency suggestions
