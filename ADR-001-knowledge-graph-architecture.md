# ADR-001: Knowledge Graph Architecture for Red Hat Engineering

## Status
Proposed

## Context
Red Hat engineering teams need a centralized knowledge graph to track relationships between code repositories, services, operators, and external dependencies. The graph must serve both human exploration and AI agent queries while maintaining consistency across organizational boundaries.

Key requirements:
- Multi-resolution structure (code → repo → service → org levels)
- Low friction for contributor adoption
- Formalized definitions with conflict detection
- Staleness tracking and versioning
- AI-queryable with human visual exploration capabilities

## Decision

### Graph Database: Dgraph
**Chosen:** Dgraph with GraphQL native support
**Rationale:** Horizontal scaling, open source, GraphQL interface natural for both AI agents and web UIs

### Data Model: Package/Version Separation
**Chosen:** Three-node model for external dependencies
```
external://pypi/requests (package node)
├── external://pypi/requests/2.31.0 (version node)
├── external://pypi/requests/2.30.0 (version node)
└── has_version edges connecting package to versions
```
**Rationale:** Enables both package-level queries ("who uses requests") and precise version tracking for conflict detection

### Schema Architecture: Inheritance-Based
**Chosen:** Base schemas with inheritance for internal vs external entities
```
schemas/
├── base_internal.yaml    (strict governance)
├── base_external.yaml    (permissive governance)
├── repository.yaml       (extends base_internal)
├── operator.yaml         (extends base_internal)
└── external_dependency.yaml (extends base_external)
```
**Rationale:** Explicit governance model, better VSCode autocomplete, clear maintenance boundaries

### Metadata Model: Hybrid with Read-Only Fields
**Chosen:** Three metadata categories per entity type:
- **Required metadata:** User must provide (e.g., maintainer, sla_tier)
- **Optional metadata:** User may provide (e.g., technology_stack)
- **Read-only metadata:** System managed (e.g., staleness_score, created_at)
- **Custom fields:** Free-form user additions allowed

**Rationale:** Balances governance with flexibility, prevents corruption of system metadata

### Declarative Syntax: Embedded Relationships
**Chosen:** Relationships defined within entity blocks
```yaml
namespace: rosa-hcp
entity:
  repository:
    - rosa-hcp-service:
        metadata:
          maintainer: "rosa-team@redhat.com"
          sla_tier: "critical"
        depends_on:
          - external://pypi/requests/2.31.0
          - internal://openshift-auth/auth-service
```
**Rationale:** Co-location improves clarity, simplifies deletion logic, natural mental model

### Namespace Model: Explicit Declaration with Conflict Detection
**Chosen:** Namespaces explicitly declared in files, multiple repos can contribute to same namespace
**Rationale:** Enables team-based organization while preventing accidental naming conflicts

### Entity Lifecycle: Reference Counting with Governance Tiers
**Chosen:** Two-tier deletion policy:
- **Internal entities:** Can only be deleted if no references exist (strict)
- **External entities:** Never deleted, only relationships removed (permissive)
**Rationale:** Prevents breaking changes while allowing external entity accumulation

### Conflict Resolution: Pre-commit Detection with CI Blocking
**Chosen:** GitHub Actions validate declarations and fail CI on conflicts
**Rationale:** Maintains graph consistency, prevents conflicted states in production

### Data Ingestion: GitHub Actions to Central Server
**Chosen:** Distributed declarations in repositories, GitHub Actions submit to central Dgraph server
**Rationale:** Low friction for teams, version controlled with repos, central consistency enforcement

### External Dependency Handling: Auto-Creation with Canonicalization
**Chosen:** External entities auto-created on first reference with smart naming
- Format: `external://ecosystem/package/version`
- Ecosystem detection from context (package.json → npm)
- Canonical naming prevents duplicates
**Rationale:** Removes maintenance burden while ensuring consistency

### Schema Evolution: Hot-Reloadable Configuration
**Chosen:** Schema files in server repository with API reload endpoint
**Rationale:** Enables schema updates without server restarts, maintains backwards compatibility

## Consequences

### Positive
- **Scalable governance:** Different rules for internal vs external entities
- **Developer friendly:** Familiar YAML syntax, VSCode autocomplete via JSON Schema
- **Consistent data:** CI-blocking prevents graph corruption
- **Flexible queries:** Package and version level queries supported
- **Low maintenance:** Auto-creation of external entities reduces manual work

### Negative
- **Complexity:** Multi-tier entity model requires careful implementation
- **Storage overhead:** Package/version separation increases node count
- **Schema proliferation:** Each entity type needs explicit schema definition
- **CI dependency:** Graph updates coupled to CI pipeline availability

### Risks
- **Schema evolution:** Backwards compatibility constraints may limit future changes
- **Performance:** Reference counting for deletion may impact large graph updates
- **Adoption:** Teams may resist additional YAML maintenance burden
- **Conflict resolution:** Pre-commit blocking may slow development velocity

## Implementation Notes
1. Start with repository and external_dependency entity types for MVP
2. Build GitHub Action template for easy repo adoption
3. Generate JSON Schema automatically from YAML schemas for VSCode
4. Implement conflict detection as separate validation step before graph updates
5. Create web UI for graph exploration and conflict resolution workflow

## Alternatives Considered

### Graph Database Alternatives
- **Neo4j:** Rejected due to licensing costs at scale
- **Amazon Neptune:** Rejected due to vendor lock-in concerns
- **ArangoDB:** Rejected due to smaller ecosystem

### Schema Approaches
- **Prefix-based rules:** Rejected for external entities due to poor tooling support
- **Monolithic schema:** Rejected due to governance complexity

### Conflict Resolution
- **Human override:** Rejected due to complexity of approval workflows
- **Last-writer-wins:** Rejected due to data corruption risk
- **Dual-state storage:** Rejected due to query complexity

---
*This ADR documents the foundational architecture decisions for the Red Hat Knowledge Graph system.*