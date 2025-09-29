"""Health check router for the Knowledge Graph API.

This module provides HTTP endpoints for health checking, monitoring,
and system status reporting.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from ...storage import HealthCheckResult, HealthStatus, SystemMetrics
from .dependencies import HealthServiceDep

router = APIRouter()


@router.get("/health", response_model=HealthCheckResult)
async def health_check(health_service: HealthServiceDep) -> HealthCheckResult:
    """Health check endpoint for monitoring and Docker health checks.

    Returns detailed health information including:
    - API server status
    - Storage backend connectivity
    - Response times
    - System metrics
    """
    try:
        # Get storage health through service layer
        health = await health_service.get_health()
        return health

    except Exception as e:
        # Return unhealthy status with error details
        return HealthCheckResult(
            status=HealthStatus.ERROR,
            response_time_ms=0.0,
            backend_version=None,
            additional_info={
                "error": str(e),
                "api_status": "running",
                "storage_status": "error",
            },
        )


@router.get("/metrics", response_model=SystemMetrics)
async def system_metrics(health_service: HealthServiceDep) -> SystemMetrics:
    """Get system-wide metrics for monitoring and analytics.

    Returns:
        SystemMetrics: Comprehensive system metrics including entity counts,
                      storage usage, and performance statistics.
    """
    try:
        metrics = await health_service.get_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve system metrics: {e!s}"
        ) from e


@router.get("/status")
async def detailed_status(health_service: HealthServiceDep) -> dict[str, Any]:
    """Detailed status endpoint for debugging and development.

    Provides comprehensive information about:
    - API server configuration
    - Storage backend details
    - Environment information
    - Performance metrics
    """
    try:
        status = await health_service.get_detailed_status()
        return status
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve detailed status: {e!r}"
        ) from e
