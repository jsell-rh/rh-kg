# Red Hat Knowledge Graph

A centrally-managed knowledge graph for discovering who owns services, what dependencies exist across repositories, and how systems connect across Red Hat engineering teams.

## Why This Exists

Critical information about our software systems lives in people's heads. New engineers ask "what's the CI/CD pipeline for this service?" or "where's the monitoring dashboard?" Existing engineers ask "who do I contact about the auth library?" or "which repositories will break if I update this dependency?"

The answers exist somewhere, but finding them means interrupting someone who knows or digging through outdated wikis.

This system captures that knowledge in a simple YAML file committed alongside your code. The benefits:

- **Onboarding**: New engineers find build systems, deployment docs, and ownership without asking
- **Incident response**: Quickly identify who owns a service and what depends on it
- **Dependency management**: See which repositories use a specific library version across the organization
- **AI readiness**: Structured knowledge enables better AI agent performance
- **Reduced interruptions**: Teams spend less time answering "where is X?" questions

## How It Works (For Repository Owners)

Add a `knowledge-graph.yaml` file to your repository:

```yaml
# yaml-language-server: $schema=.vscode/kg-schema.json
namespace: "my-team"

entity:
  repository:
    - my-service:
        owners: ["team@redhat.com"]
        git_repo_url: "https://github.com/redhat/my-service"
        depends_on:
          - "external://pypi/requests/2.31.0"
        internal_depends_on:
          - "internal://auth-team/auth-service"
```

That's it. The system handles the rest:

- External dependencies are automatically tracked across all Red Hat repositories
- You can reference other teams' services using `internal://<namespace>/<service>`
- When you update the file, the central graph updates automatically
- Your declarations won't break when the system evolves

**Time investment:** ~5 minutes initial setup, minimal ongoing maintenance.

### IDE Autocomplete

Enable autocomplete and inline validation for your YAML files:

```bash
kg schema export
```

This generates `.vscode/kg-schema.json` and configures VSCode to provide field autocomplete, type validation, and inline documentation.

**Recommended:** Add this comment at the top of your `knowledge-graph.yaml` file for editor integration:

```yaml
# yaml-language-server: $schema=.vscode/kg-schema.json
```

This works with most YAML-aware editors, not just VSCode.

## What You Can Query

Once repositories are documented, you can answer questions like:

**For onboarding:**

- "What's the git URL for the rosa-operator repository?"
- "Who owns the authentication service?"
- "What repositories does the platform team maintain?"

**For development:**

- "Which repositories depend on requests 2.31.0?"
- "What are all the dependencies of rosa-operator?"
- "Which teams use our logging-library?"

**For incident response:**

- "If the auth-service goes down, what else breaks?"
- "Who should I contact about the payment processing service?"
- "What services does this repository depend on?"

The goal is to make organizational knowledge searchable rather than requiring you to know who to ask.

## YAML Format Reference

**Required fields:**

- `namespace`: Your team's namespace (e.g., "rosa-team", "platform-services")
- `owners`: Array of team email addresses
- `git_repo_url`: Repository URL
- `depends_on`: Array of external package dependencies (can be empty)
- `internal_depends_on`: Array of internal service dependencies (can be empty)

**Dependency formats:**

- External packages in `depends_on`: `external://<ecosystem>/<package>/<version>`
  - Examples: `external://pypi/django/4.2.1`, `external://npm/react/18.0.0`
- Internal services in `internal_depends_on`: `internal://<namespace>/<repository>`
  - Example: `internal://platform/logging-service`

**What's intentionally minimal:**

The Phase 1 schema supports only repository entities with essential metadata. This isn't a limitation but a deliberate choice to prove value before adding complexity. Future phases may add service-level entities, operational metadata, or custom fields based on actual usage patterns.

## Development Setup (For Contributors)

If you're contributing to the knowledge graph system itself (not just using it):

**Prerequisites:** Python 3.12, Docker Compose, uv package manager

```bash
# Install dependencies
cd backend
uv sync
uv run pre-commit install

# Start local Dgraph backend
docker compose up -d

# Run tests
uv run pytest

# Validate a YAML file
uv run kg validate ../test-apply.yaml
```

**Important:** Always use `uv run` prefix for Python commands.

**Development workflow:**

1. Read specifications in `spec/` directory (they're authoritative)
2. Write tests based on specifications
3. Implement to pass tests
4. Ensure pre-commit hooks pass (includes ruff, mypy, pytest)

**Technology stack:**

- Python 3.12 with strict typing
- FastAPI for REST API
- Dgraph for graph storage
- Pydantic for validation
- Test-driven development required

## Project Structure

```
backend/
├── kg/               # Core system code
│   ├── cli/          # Command-line tools
│   ├── storage/      # Dgraph integration
│   ├── validation/   # YAML validation
│   └── migrations/   # Schema evolution
├── schemas/          # Entity type definitions
└── tests/            # Test suite

spec/                 # Authoritative design specs
docs/                 # Roadmap and architecture
```

## Current Status

Phase 1 MVP focused on proving core value:

**Working:**

- YAML validation and schema enforcement
- CLI tools (validate, apply)
- Dgraph storage backend
- Query capabilities for ownership and dependencies

**Not yet available:**

- Web UI for queries (use CLI currently)
- GitHub Actions automation
- REST API (skeleton exists)

The immediate goal is 50+ repositories using the system to validate the approach before expanding features.

## For New Contributors

**Start here:**

1. `spec/README.md` - How specification-driven development works
2. `spec/schema-spec.md` - YAML validation rules
3. `spec/data-model-spec.md` - Graph storage model
4. `backend/kg/cli/validate.py` - Entry point to understand code flow

**Key architectural decisions:**

- Additive-only schema evolution (your YAML files never break)
- Strict validation (catches errors early, ensures data quality)
- Separate governance for internal vs. external entities
- Package/version separation for dependency tracking

See `ADR-001-knowledge-graph-architecture.md` for detailed rationale.

## License

MIT
