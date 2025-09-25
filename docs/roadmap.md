# Knowledge Graph MVP Roadmap

## Overview
This roadmap focuses on proving core value through a highly constrained, rigid schema that solves 2-3 specific high-value problems perfectly. The approach prioritizes demonstrating clear value and achieving adoption threshold (50+ repositories) before adding any complexity or flexibility. Schema versioning infrastructure is built from day one to enable planned migration phases once value is proven.

## Phase 1: Rigid Schema Foundation (6-8 weeks)

### Goals
- Prove minimal viable schema delivers clear value for dependency mapping and ownership tracking
- Establish strict validation that ensures consistent, high-quality data
- Build schema versioning infrastructure for future planned migrations
- Achieve initial adoption and demonstrate ROI

### Deliverables

**Week 1-2: Minimal Schema Infrastructure**
- Dgraph deployment (local + staging)
- **Rigid schema system:** Only `repository` and `external_dependency` entity types
- **Strict validation:** Rejects all unknown fields with clear error messages
- **Schema versioning infrastructure:** Built from day one for future migrations
- **Minimal required fields:**
  ```yaml
  entity:
    repository:
      - name:
          owner: "team@redhat.com"        # REQUIRED
          depends_on: [list_of_entities]  # REQUIRED
  ```

**Week 3-4: Core Value Demonstration**
- Manual data entry for 10-15 diverse repositories
- Focus on **2 specific high-value questions:**
  - "Which repositories does team X own?"
  - "Which repositories depend on external package Y?"
- Implement package/version separation for external dependencies
- Build simple query interface for these specific use cases

**Week 5-6: Automation Foundation**
- Basic GitHub Action for YAML validation and submission
- Conflict detection for namespace and entity ownership
- Automated external entity creation with canonicalization
- Pre-commit validation CLI tool

**Week 7-8: Adoption Push**
- Document setup process (<5 minutes for new repository)
- Create templates and examples for common repository types
- Onboard 20+ repositories with real teams
- Measure actual usage patterns and value delivered

### Success Criteria
- [ ] **25+ repositories documented** with high-quality, consistent data
- [ ] **Teams regularly using graph** for dependency and ownership questions (tracked usage)
- [ ] **Zero schema exceptions** - all data fits rigid schema without escape hatches
- [ ] **<5 minute setup time** for new repositories
- [ ] **Query response time <200ms** for target use cases
- [ ] **Strict validation working** - unknown fields rejected with helpful errors

### Key Risks & Mitigation
- **Risk:** Rigid schema too constraining for real Red Hat diversity
- **Mitigation:** Choose initial repositories carefully, document rejected use cases for future phases
- **Risk:** Teams don't see enough value to adopt
- **Mitigation:** Focus on specific pain points, measure actual usage, pivot if necessary
- **Risk:** Schema versioning adds unnecessary complexity to MVP
- **Mitigation:** Keep versioning simple but functional, test with mock migrations

## Phase 2: Scale to Adoption Threshold (4-5 weeks)

### Goals
- Scale automation to handle 50+ repositories reliably
- Improve developer experience and reduce friction
- Establish monitoring and quality metrics
- Reach adoption threshold for expansion decision

### Deliverables

**Week 1-2: Production-Ready Automation**
- Enhanced GitHub Action with proper authentication and error handling
- Reference counting for entity deletion (internal vs external policies)
- Comprehensive audit trail (source repo, commit, timestamp)
- Production monitoring and alerting

**Week 3-4: Developer Experience Polish**
- Advanced CLI tool with entity discovery (`kg search`, `kg list`)
- JSON Schema generation for VSCode autocomplete
- Comprehensive documentation and troubleshooting guides
- Template repository for easy onboarding

**Week 4-5: Adoption Campaign**
- Systematic onboarding of diverse teams and repository types
- Usage analytics to track value delivery
- Feedback collection and pain point identification
- Performance optimization for scale

### Success Criteria
- [ ] **50+ repositories documented** across diverse teams
- [ ] **Demonstrable value:** Teams making decisions based on graph data weekly
- [ ] **High data quality:** <2% incorrect/stale data based on spot checks
- [ ] **Reliable automation:** <1% CI failure rate due to knowledge graph issues
- [ ] **Fast queries:** <200ms response time for all supported use cases
- [ ] **Self-service onboarding:** New repositories setup without assistance

### Key Risks & Mitigation
- **Risk:** Cannot reach 50 repository threshold due to adoption resistance
- **Mitigation:** Focus on teams with strongest pain points, consider pivoting use cases
- **Risk:** Performance issues at scale
- **Mitigation:** Load testing, query optimization, consider infrastructure scaling
- **Risk:** Data quality degrades as adoption scales
- **Mitigation:** Automated quality checks, spot auditing, team feedback loops

## Phase 3: Expansion Decision Point (2-3 weeks)

### Goals
- Evaluate whether adoption threshold and value demonstration justify schema expansion
- Analyze collected pain points and usage patterns
- Design next schema evolution phase based on evidence
- Prepare expansion infrastructure if justified

### Deliverables

**Week 1: Evidence Analysis**
- **Adoption metrics review:** Confirm 50+ repositories, regular usage patterns
- **Value assessment:** Document specific decisions teams are making based on graph data
- **Pain point analysis:** Catalog rejected use cases and team requests for additional functionality
- **Query pattern analysis:** Identify most common unsupported query types

**Week 2: Expansion Planning**
- **RFC process setup:** Community input mechanism for schema changes
- **Next phase design:** Based on highest-value pain points identified
- **Migration planning:** Detailed plan for schema evolution with rollback capability
- **Pilot program selection:** 5-10 repositories for testing expanded schema

**Week 3: Go/No-Go Decision**
- **Stakeholder review:** Present evidence and expansion recommendations
- **Decision criteria evaluation:** Clear thresholds for proceeding with expansion
- **Alternative strategies:** If expansion not justified, plan for different approach
- **Resource allocation:** Confirm resources for next phase if proceeding

### Success Criteria
- [ ] **Clear evidence-based recommendation** for schema expansion based on usage data
- [ ] **RFC process established** for community input on schema changes
- [ ] **Specific expansion plan** targeting highest-value pain points
- [ ] **Go/no-go decision made** with clear rationale and stakeholder buy-in

### Key Risks & Mitigation
- **Risk:** Insufficient adoption to justify expansion
- **Mitigation:** Alternative value delivery strategies, different target use cases
- **Risk:** Conflicting priorities from different teams
- **Mitigation:** Clear prioritization criteria based on usage data and organizational impact
- **Risk:** Technical debt from rapid MVP development
- **Mitigation:** Refactoring plan as part of expansion preparation

## Phase 4: Web Interface & Query Tools (3-4 weeks)

### Goals
- Enable self-service querying for non-technical users
- Provide visual exploration of the proven high-value use cases
- Establish comprehensive monitoring and health metrics

### Deliverables

**Week 1-2: Simple Query Interface**
- **Form-based queries** for the 2 proven use cases (ownership, dependencies)
- **GraphQL playground** for power users
- **Export capabilities** (CSV, JSON) for further analysis
- **Authentication integration** with Red Hat SSO

**Week 3-4: Visualization & Analytics**
- **Targeted graph visualization** focused on dependency and ownership relationships
- **Usage analytics dashboard** to track adoption and value delivery
- **System health monitoring** (ingestion rate, query performance, data quality)
- **Feedback collection mechanism** for continuous improvement

### Success Criteria
- [ ] **Non-developers can answer** the 2 core questions via web UI
- [ ] **Visual exploration useful** for understanding repository relationships
- [ ] **Comprehensive monitoring** identifies issues before users complain
- [ ] **Usage data collection** informs future development priorities

## Post-MVP: Planned Schema Evolution (Contingent on Phase 3 Decision)

### Phase 5: First Expansion (6-8 weeks) - IF JUSTIFIED
**Prerequisite:** Phase 3 decision to proceed based on evidence

**Potential expansions based on anticipated pain points:**
- **Service-level entities:** Add `service`, `operator` entity types
- **Operational metadata:** SLA tiers, deployment information, incident contacts
- **Relationship precision:** Distinguish runtime vs build-time dependencies

**Approach:**
- **RFC process:** Community input on specific schema additions
- **Pilot program:** 10-15 repositories testing expanded schema
- **Migration script:** Automated transition from v1.0 to v2.0 schema
- **Parallel operation:** Support both schema versions during 4-week transition
- **Rollback capability:** Ability to revert if adoption fails

### Phase 6: Second Expansion (6-8 weeks) - IF JUSTIFIED
**Prerequisite:** Successful Phase 5 adoption (75+ repositories using expanded schema)

**Potential additional complexity:**
- **Custom metadata fields:** Governed free-form fields for team-specific needs
- **Cross-service relationships:** API integrations, data flow mappings
- **Temporal modeling:** Version compatibility, deployment synchronization

### Long-term Evolution Strategy
- **Evidence-driven decisions:** Each expansion requires demonstrated value from previous phase
- **Community governance:** RFC process for all schema changes
- **Migration tooling:** Automated scripts and rollback capabilities for all changes
- **Usage analytics:** Data-driven prioritization of new features

## Success Metrics

### Phase 1-2: Foundation Success (MVP Threshold)
**Adoption Metrics:**
- **50+ repositories documented** with consistent data quality
- **Teams using graph weekly** for dependency and ownership decisions (tracked usage)
- **<5 minute setup time** for new repositories
- **Self-service onboarding** without manual assistance

**Technical Metrics:**
- **Query response time <200ms** for the 2 core use cases
- **99% uptime** for central server
- **<1% CI failure rate** due to knowledge graph issues
- **Zero schema exceptions** - all data fits rigid schema

**Quality Metrics:**
- **<2% incorrect data** (based on spot checks and team feedback)
- **Strict validation working** - unknown fields properly rejected
- **Consistent data formats** across all repositories

### Phase 3: Expansion Decision Criteria
**Evidence Required for Schema Expansion:**
- **Demonstrable value:** Specific examples of teams making better decisions based on graph data
- **Pain point documentation:** Clear catalog of use cases rejected by current schema
- **Usage patterns:** Query analytics showing demand for unsupported functionality
- **Community support:** RFC process engagement and consensus for expansion

### Phase 5+: Evolution Success (If Applicable)
**Migration Metrics:**
- **<4 week migration time** from old to new schema versions
- **Zero data loss** during schema transitions
- **Rollback capability tested** and functional
- **Community participation** in RFC process for schema changes

**Long-term Health:**
- **Continuous value delivery:** Teams regularly discovering new insights from expanded graph
- **Sustainable maintenance:** Schema evolution without breaking existing integrations
- **Quality preservation:** Data consistency maintained across complexity increases

## Critical Questions for Success

### Immediate (Phase 1-2)
1. **Value demonstration:** Which specific Red Hat teams have the strongest pain points around dependency/ownership tracking?
2. **Repository selection:** Which 50 repositories best represent Red Hat's diversity while fitting the minimal schema?
3. **Success measurement:** How do we track whether teams are actually making better decisions based on graph data?
4. **Quality assurance:** What processes ensure data accuracy as we scale from 25 to 50+ repositories?

### Expansion Decision (Phase 3)
1. **Evidence thresholds:** What specific usage patterns and value demonstrations justify schema complexity?
2. **Community governance:** Who participates in RFC processes for schema evolution decisions?
3. **Migration strategy:** How do we ensure schema changes don't disrupt existing users?
4. **Alternative value:** If 50+ repository threshold isn't reached, what other value delivery strategies should we pursue?

### Long-term Evolution (Phase 5+)
1. **Sustainability:** How do we prevent feature creep while accommodating Red Hat's organizational complexity?
2. **Integration strategy:** How does this knowledge graph integrate with existing Red Hat tooling and documentation?
3. **Support model:** Who provides ongoing support for teams as the system grows in complexity?
4. **Success definition:** What does "success" look like for a Red Hat-wide knowledge graph?

**Key Insight:** The rigid-first approach means many organizational questions can be deferred until we prove the core concept delivers value. Focus on adoption and value demonstration first, organizational complexity second.