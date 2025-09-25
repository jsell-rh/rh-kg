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

### Complexity Management: Rigid First, Flexible Later
**Chosen:** Start with highly constrained schema focused on specific high-value problems, plan explicit migration points for flexibility
**Implementation Strategy:**

**1. Minimal Viable Schema (MVP Phase):**
```yaml
# Phase 1: Only essential fields allowed, strict validation
entity:
  repository:
    - name:
        owner: "team@redhat.com"           # REQUIRED
        depends_on: [list_of_entities]     # REQUIRED
        # No other fields accepted
```
- **Reject unknown fields** with clear error messages
- **Consistent data quality** enables reliable analytics
- **Focus on 2-3 critical use cases** (dependency mapping, ownership tracking)
- **Demonstrate clear value** before adding complexity

**2. Planned Flexibility Phases:**
- **Phase 2 (6 months):** Add service-level entities and operational metadata
- **Phase 3 (12 months):** Add relationship precision (runtime vs build dependencies)
- **Phase 4 (18 months):** Add custom metadata fields with governance

**3. Schema Versioning for Migration Points:**
- Each schema file includes version: `schema_version: "1.0.0"`
- **Explicit migration events** between phases (not organic evolution)
- **Migration scripts** and communication for breaking changes
- **Multiple schema versions supported** only during planned transition periods (4-6 weeks max)

**4. Value-Driven Expansion Criteria:**
Before adding complexity, require evidence of:
- **Adoption threshold:** 50+ repositories using current schema
- **Value demonstration:** Teams regularly using graph for their decisions
- **Specific pain points:** Clear problems that current schema cannot solve
- **Usage analysis:** Query patterns showing need for additional complexity

**5. Expansion Process:**
- **RFC process** for schema changes with clear problem statements
- **Pilot programs** with 5-10 repositories testing proposed changes
- **Migration timeline** with rollback plans if adoption fails
- **Documentation updates** and tooling changes before schema deployment

**Rationale:**
- **Adoption first:** Rigid schema ensures consistent data quality that demonstrates clear value
- **Planned complexity:** Explicit decision points prevent feature creep and maintain simplicity
- **Migration safety:** Versioning enables controlled evolution without breaking existing users
- **Flexibility eventually:** System designed to accommodate Red Hat's diversity, but only after proving core value

## Consequences

### Positive
- **Scalable governance:** Different rules for internal vs external entities
- **Developer friendly:** Familiar YAML syntax, VSCode autocomplete via JSON Schema
- **Consistent data:** CI-blocking prevents graph corruption + rigid schema ensures quality
- **Flexible queries:** Package and version level queries supported
- **Low maintenance:** Auto-creation of external entities reduces manual work
- **Clear value demonstration:** Focused schema solves specific problems well
- **Predictable evolution:** Planned migration points prevent surprise breaking changes
- **High data quality:** Strict validation ensures reliable analytics and AI consumption

### Negative
- **Complexity:** Multi-tier entity model requires careful implementation
- **Storage overhead:** Package/version separation increases node count
- **Schema proliferation:** Each entity type needs explicit schema definition
- **CI dependency:** Graph updates coupled to CI pipeline availability
- **Initial inflexibility:** Teams with edge cases may be frustrated by rigid schema
- **Migration overhead:** Planned schema evolution requires coordination and communication
- **Delayed flexibility:** Complex use cases must wait for later phases

### Risks
- **Schema evolution:** Migration points may be disruptive if not well-managed
- **Performance:** Reference counting for deletion may impact large graph updates
- **Adoption:** Teams may resist additional YAML maintenance burden
- **Conflict resolution:** Pre-commit blocking may slow development velocity
- **Value threshold:** May never reach adoption levels needed to justify flexibility phases
- **Migration complexity:** Schema versioning infrastructure adds significant implementation burden

## Implementation Notes

### Phase 1 (MVP): Rigid Schema Foundation
1. **Minimal entity types:** Start with only `repository` and `external_dependency`
2. **Strict validation:** Reject all unknown fields with clear error messages
3. **Focus on value:** Target 2-3 specific high-value questions (dependency mapping, ownership)
4. **Simple tooling:** Basic GitHub Action, CLI validator, minimal web UI
5. **Success metrics:** 50+ repositories, regular usage for decision-making

### Phase 2+: Planned Expansion
1. **Evidence-based decisions:** Require clear problem statements before adding complexity
2. **RFC process:** Community input on schema changes with pilot programs
3. **Migration tooling:** Automated scripts and clear communication for breaking changes
4. **Rollback capability:** Ability to revert schema changes if adoption fails

### Technical Implementation
1. **Schema versioning infrastructure:** Built from day one to support future migrations
2. **JSON Schema generation:** Automatic VSCode autocomplete from rigid YAML schemas
3. **Conflict detection:** Separate validation step before graph updates
4. **Monitoring:** Track adoption metrics and query patterns to inform expansion decisions

## Alternatives Considered

### Graph Database Alternatives
- **Neo4j:** Rejected due to licensing costs at scale
- **Amazon Neptune:** Rejected due to vendor lock-in concerns
- **ArangoDB:** Rejected due to smaller ecosystem

### Schema Approaches
- **Prefix-based rules:** Rejected for external entities due to poor tooling support
- **Monolithic schema:** Rejected due to governance complexity
- **Progressive refinement:** Rejected due to data quality concerns and adoption risks

### Complexity Management Approaches
- **Progressive schema refinement:** Rejected - allows organic evolution but leads to inconsistent data quality and complex analytics infrastructure
- **Fully flexible from start:** Rejected - too complex for initial adoption, no clear value demonstration
- **Rigid forever:** Rejected - doesn't accommodate Red Hat's long-term diversity needs

### Conflict Resolution
- **Human override:** Rejected due to complexity of approval workflows
- **Last-writer-wins:** Rejected due to data corruption risk
- **Dual-state storage:** Rejected due to query complexity

---
*This ADR documents the foundational architecture decisions for the Red Hat Knowledge Graph system.*