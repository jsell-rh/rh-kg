"""FastAPI dependency injection for the Knowledge Graph API.

This module provides dependency injection functions for FastAPI endpoints,
including storage backend access, authentication, and configuration.
"""

from typing import Annotated

from fastapi import Depends, HTTPException

from ..storage import StorageInterface

# Global storage instance (will be set by the main application)
_storage: StorageInterface | None = None


def set_storage(storage: StorageInterface) -> None:
    """Set the global storage instance.

    This is called during application startup to inject the storage backend.
    """
    global _storage  # noqa: PLW0603
    _storage = storage


def get_storage() -> StorageInterface:
    """FastAPI dependency to get the current storage backend.

    Returns:
        StorageInterface: The configured storage backend

    Raises:
        HTTPException: If storage is not initialized
    """
    if _storage is None:
        raise HTTPException(
            status_code=500,
            detail="Storage backend not initialized. Check server configuration.",
        )
    return _storage


def get_storage_unsafe() -> StorageInterface | None:
    """Get storage without raising HTTP exceptions.

    Used for internal operations like shutdown cleanup.
    """
    return _storage


# Type alias for storage dependency injection
StorageDep = Annotated[StorageInterface, Depends(get_storage)]
