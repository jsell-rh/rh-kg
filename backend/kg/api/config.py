"""Configuration management for the Knowledge Graph API.

This module handles environment-based configuration using Pydantic Settings,
supporting both config files and environment variables.
"""

from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings

from ..storage import StorageConfig


class APIConfig(BaseSettings):
    """FastAPI application configuration."""

    # Environment
    environment: Literal["development", "testing", "production"] = Field(
        default="development", description="Application environment"
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")
    reload: bool = Field(
        default=False, description="Enable auto-reload for development"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    json_logs: bool = Field(default=False, description="Enable JSON formatted logs")
    log_requests: bool = Field(
        default=True, description="Enable request logging middleware"
    )

    # Schema configuration
    schema_dir: str = Field(
        default="/app/spec/schemas",
        description="Directory containing entity schema YAML files",
    )

    # CORS settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )

    # Storage configuration fields (flattened)
    storage_backend_type: str = Field(default="dgraph", alias="STORAGE_BACKEND_TYPE")
    storage_endpoint: str = Field(default="localhost:9080", alias="STORAGE_ENDPOINT")
    storage_timeout_seconds: int = Field(default=30, alias="STORAGE_TIMEOUT_SECONDS")
    storage_max_retries: int = Field(default=3, alias="STORAGE_MAX_RETRIES")
    storage_use_tls: bool = Field(default=False, alias="STORAGE_USE_TLS")

    class Config:
        """Pydantic configuration."""

        env_prefix = ""
        case_sensitive = False

    @computed_field  # type: ignore
    @property
    def storage(self) -> StorageConfig:
        """Create storage configuration from individual fields."""
        return StorageConfig(
            backend_type=self.storage_backend_type,
            endpoint=self.storage_endpoint,
            timeout_seconds=self.storage_timeout_seconds,
            max_retries=self.storage_max_retries,
            use_tls=self.storage_use_tls,
            retry_delay_seconds=1.0,
        )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


# Global configuration instance
config = APIConfig()
