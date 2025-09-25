<instructions>
- You are a professional.
- You are to always respond after thinking deeply and bringing a critical lens to the user's request.
- Do not be sycophantic, or praise the user. Instead, assume that they may have missed something, and never suggest something is the best without ensuring the user's intent, etc.
</instructions>

## Development Standards

### Technology Stack
1. **FastAPI/Python** for all components (CLI, server, shared libraries)
2. **Alembic** for SQL migrations
3. **SQLAlchemy** for all SQL interactions
4. **Pydantic** for all data structures and validation
5. **Pydantic Settings** for configuration (supports both config files and environment variables)
6. **Python 3.12** with modern typing conventions

### Code Quality Standards
- **Always use type hints** - avoid `Any` type
- **Use Python 3.12 typing conventions**: `dict[str, list]` instead of `Dict[str, List]`
- **Google search for latest library versions** before adding dependencies
- **Strict typing** throughout the codebase

### Development Environment
- **UV** for Python package and environment management
- **Monorepo structure** - all components in single repository
- **Pre-commit hooks** must pass before any commit
- **Conventional commits** for all commit messages (feat:, fix:, docs:, etc.)
- **Atomic commits** - each commit represents a single logical change
- **Frequent commits** - commit early and often to maintain clear development history
- **Test-Driven Development (TDD)** - write tests first, then implement functionality
- **Specification-Driven Development** - spec/ directory contains authoritative design documents that MUST be referenced before writing any code
