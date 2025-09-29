"""Health check service layer.

This module contains the business logic for health checks and system status,
separated from the HTTP routing layer for better testability.
"""

import time
from typing import Any

from ...storage import HealthCheckResult, StorageInterface, SystemMetrics

# Global application start time
_app_start_time: float = time.time()


class HealthService:
    """Service class for health check operations."""

    def __init__(self, storage: StorageInterface):
        """Initialize health service with storage backend."""
        self.storage = storage

    async def get_health(self) -> HealthCheckResult:
        """Get basic health status from storage backend.

        Returns:
            HealthCheckResult: Typed health status from storage
        """
        return await self.storage.health_check()

    async def get_metrics(self) -> SystemMetrics:
        """Get system-wide metrics for monitoring.

        Returns:
            SystemMetrics: Comprehensive system metrics
        """
        return await self.storage.get_system_metrics()

    async def get_detailed_status(self) -> dict[str, Any]:
        """Get detailed status for debugging and monitoring.

        Returns:
            Comprehensive status including API, storage, and metrics information
        """
        start_time = time.time()

        # Get storage health and metrics
        health = await self.get_health()
        metrics = await self.get_metrics()

        response_time = (time.time() - start_time) * 1000

        # Calculate actual uptime since application start
        current_time = time.time()
        uptime_seconds = current_time - _app_start_time

        return {
            "api": {
                "name": "Knowledge Graph API",
                "version": "0.1.0",
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
            },
            "storage": {
                "type": type(self.storage).__name__,
                "status": health.status,
                "response_time_ms": health.response_time_ms,
                "backend_version": health.backend_version,
                "additional_info": health.additional_info,
            },
            "metrics": {
                "total_entities": metrics.entity_counts.total,
                "entity_breakdown": {
                    "repositories": metrics.entity_counts.repository,
                    "external_packages": metrics.entity_counts.external_dependency_package,
                    "external_versions": metrics.entity_counts.external_dependency_version,
                },
                "total_relationships": metrics.total_relationships,
                "storage_size_mb": metrics.storage_size_mb,
                "last_updated": metrics.last_updated.isoformat(),
            },
            "environment": {
                "timestamp": current_time,
                "uptime_seconds": round(uptime_seconds, 2),
                "started_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(_app_start_time)
                ),
            },
        }
