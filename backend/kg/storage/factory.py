"""Storage backend factory for creating storage instances.

This module provides a factory function to create storage backends
based on configuration, supporting different backend types.
"""

import logging
from typing import TYPE_CHECKING

from .dgraph import DgraphStorage
from .exceptions import StorageConfigurationError
from .interface import StorageInterface
from .mock import MockStorage
from .models import StorageConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def create_storage(config: StorageConfig) -> StorageInterface:
    """Create a storage backend instance based on configuration.

    Args:
        config: Storage configuration specifying backend type and settings

    Returns:
        StorageInterface: Configured storage backend instance

    Raises:
        StorageConfigurationError: If backend type is unsupported or config is invalid
    """
    backend_type = config.backend_type.lower()

    logger.info(f"Creating storage backend: {backend_type}")

    if backend_type == "mock":
        return MockStorage()

    elif backend_type == "dgraph":
        return DgraphStorage(config)

    else:
        supported_backends = ["mock", "dgraph"]
        raise StorageConfigurationError(
            f"Unsupported storage backend: {backend_type}. "
            f"Supported backends: {', '.join(supported_backends)}"
        )


def validate_storage_config(config: StorageConfig) -> None:
    """Validate storage configuration.

    Args:
        config: Storage configuration to validate

    Raises:
        StorageConfigurationError: If configuration is invalid
    """
    # Basic validation
    if not config.backend_type:
        raise StorageConfigurationError("Storage backend type is required")

    if not config.endpoint:
        raise StorageConfigurationError("Storage endpoint is required")

    # Backend-specific validation
    if config.backend_type.lower() == "dgraph":
        if config.timeout_seconds <= 0:
            raise StorageConfigurationError("Timeout must be positive")

        if config.max_retries < 0:
            raise StorageConfigurationError("Max retries cannot be negative")

        # Validate endpoint format (should be host:port)
        if ":" not in config.endpoint:
            raise StorageConfigurationError(
                "Dgraph endpoint must be in format host:port"
            )

    logger.debug(f"Storage configuration validated for backend: {config.backend_type}")


async def test_storage_connection(storage: StorageInterface) -> bool:
    """Test storage connection and basic functionality.

    Args:
        storage: Storage instance to test

    Returns:
        bool: True if connection test passes, False otherwise
    """
    try:
        # Test connection
        await storage.connect()

        # Test health check
        health = await storage.health_check()

        if health.status.value in ["healthy", "degraded"]:
            logger.info(f"Storage connection test passed: {health.status}")
            return True
        else:
            logger.warning(f"Storage connection test failed: {health.status}")
            return False

    except Exception as e:
        logger.error(f"Storage connection test failed: {e}")
        return False

    finally:
        try:
            await storage.disconnect()
        except Exception as e:
            logger.warning(f"Error during test cleanup: {e}")
