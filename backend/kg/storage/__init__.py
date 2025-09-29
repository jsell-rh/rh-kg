"""Storage and persistence layer for the knowledge graph."""

from .dgraph import DgraphStorage
from .exceptions import (
    StorageConfigurationError,
    StorageConnectionError,
    StorageError,
    StorageOperationError,
    StorageQueryError,
    StorageValidationError,
)
from .factory import create_storage, test_storage_connection, validate_storage_config
from .interface import StorageInterface
from .mock import MockStorage
from .models import (
    DryRunResult,
    EntityData,
    EntityOperation,
    HealthCheckResult,
    HealthStatus,
    QueryResult,
    RelationshipData,
    StorageConfig,
    SystemMetrics,
    ValidationIssue,
)

__all__ = [
    # Core interface
    "StorageInterface",
    # Implementations
    "DgraphStorage",
    "MockStorage",
    # Factory functions
    "create_storage",
    "test_storage_connection",
    "validate_storage_config",
    # Models
    "DryRunResult",
    "EntityData",
    "EntityOperation",
    "HealthCheckResult",
    "HealthStatus",
    "QueryResult",
    "RelationshipData",
    "StorageConfig",
    "SystemMetrics",
    "ValidationIssue",
    # Exceptions
    "StorageError",
    "StorageConfigurationError",
    "StorageConnectionError",
    "StorageOperationError",
    "StorageQueryError",
    "StorageValidationError",
]
