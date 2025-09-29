"""Health-specific dependencies for the FastAPI health endpoints."""

from typing import Annotated

from fastapi import Depends

from ..dependencies import StorageDep
from .service import HealthService


def get_health_service(storage: StorageDep) -> HealthService:
    """FastAPI dependency to get the health service.

    Args:
        storage: Injected storage dependency

    Returns:
        HealthService: Configured health service instance
    """
    return HealthService(storage)


# Type alias for health service dependency injection
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
