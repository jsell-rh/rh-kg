"""Pydantic models for storage interface return types.

These models provide strongly-typed, validated data structures for
all storage operations, ensuring type safety and clear contracts.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Storage backend health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class HealthCheckResult(BaseModel):
    """Result of storage backend health check."""

    status: HealthStatus
    response_time_ms: float = Field(ge=0, description="Response time in milliseconds")
    backend_version: str | None = Field(None, description="Backend version info")
    additional_info: dict[str, Any] = Field(
        default_factory=dict, description="Backend-specific health metrics"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class EntityData(BaseModel):
    """Standardized entity data structure."""

    id: str = Field(description="Unique entity identifier")
    entity_type: str = Field(description="Type of entity (e.g., 'repository')")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Entity field data"
    )
    relationships: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict, description="Entity relationships grouped by type"
    )
    system_metadata: dict[str, Any] = Field(
        default_factory=dict, description="System-managed metadata"
    )


class RelationshipData(BaseModel):
    """Data structure for entity relationships."""

    relationship_name: str = Field(description="Name of the relationship")
    target_entities: list[EntityData] = Field(
        description="Entities that are targets of this relationship"
    )
    relationship_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional relationship metadata"
    )


class EntityCounts(BaseModel):
    """Entity counts by type."""

    repository: int = 0
    external_dependency_package: int = 0
    external_dependency_version: int = 0
    total: int = Field(description="Total entities across all types")

    def __init__(self, **data: Any):
        """Calculate total automatically."""
        super().__init__(**data)
        self.total = (
            self.repository
            + self.external_dependency_package
            + self.external_dependency_version
        )


class SystemMetrics(BaseModel):
    """System-wide storage metrics."""

    entity_counts: EntityCounts
    total_relationships: int = Field(ge=0, description="Total relationship count")
    storage_size_mb: float = Field(ge=0, description="Storage size in megabytes")
    last_updated: datetime = Field(description="When metrics were last calculated")
    backend_specific: dict[str, Any] = Field(
        default_factory=dict, description="Backend-specific metrics"
    )


class EntityOperation(BaseModel):
    """Represents an entity operation for dry-run results."""

    entity_type: str
    entity_id: str
    operation_type: str = Field(description="create, update, or delete")
    changes: dict[str, Any] = Field(
        default_factory=dict, description="What would change"
    )


class ValidationIssue(BaseModel):
    """Validation error or warning for dry-run results."""

    severity: str = Field(description="error or warning")
    entity_type: str | None = None
    entity_id: str | None = None
    message: str
    suggestion: str | None = None


class DryRunResult(BaseModel):
    """Result of dry-run apply operation."""

    would_create: list[EntityOperation] = Field(
        default_factory=list, description="Entities that would be created"
    )
    would_update: list[EntityOperation] = Field(
        default_factory=list, description="Entities that would be updated"
    )
    would_delete: list[EntityOperation] = Field(
        default_factory=list, description="Entities that would be deleted"
    )
    validation_issues: list[ValidationIssue] = Field(
        default_factory=list, description="Validation errors and warnings"
    )
    summary: dict[str, Any] = Field(
        default_factory=dict, description="Summary of changes"
    )

    @property
    def has_errors(self) -> bool:
        """Check if there are any validation errors."""
        return any(issue.severity == "error" for issue in self.validation_issues)

    @property
    def error_count(self) -> int:
        """Count of validation errors."""
        return sum(1 for issue in self.validation_issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of validation warnings."""
        return sum(1 for issue in self.validation_issues if issue.severity == "warning")


class QueryResult(BaseModel):
    """Result of raw query execution."""

    success: bool
    data: dict[str, Any] = Field(default_factory=dict, description="Query result data")
    execution_time_ms: float = Field(ge=0, description="Query execution time")
    backend_specific: dict[str, Any] = Field(
        default_factory=dict, description="Backend-specific result metadata"
    )
    error_message: str | None = Field(
        default=None, description="Error message if failed"
    )


class ConnectionInfo(BaseModel):
    """Storage connection information."""

    backend_type: str = Field(description="Type of storage backend (e.g., 'dgraph')")
    endpoint: str = Field(description="Connection endpoint")
    connected: bool = Field(description="Whether currently connected")
    connection_time: datetime | None = Field(
        None, description="When connection was established"
    )
    schema_version: str | None = Field(None, description="Loaded schema version")


class StorageConfig(BaseModel):
    """Storage configuration settings."""

    backend_type: str
    endpoint: str
    timeout_seconds: int = Field(30, ge=1, le=300)
    max_retries: int = Field(3, ge=0, le=10)
    retry_delay_seconds: float = Field(1.0, ge=0.1, le=10.0)

    # Authentication
    username: str | None = None
    password: str | None = None

    # TLS settings
    use_tls: bool = False
    ca_cert_path: str | None = None
    client_cert_path: str | None = None
    client_key_path: str | None = None

    class Config:
        """Pydantic configuration."""

        env_prefix = "STORAGE_"
