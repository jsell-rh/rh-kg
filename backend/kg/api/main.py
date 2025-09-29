"""FastAPI application entry point for the Knowledge Graph API.

This module creates and configures the FastAPI application with proper
dependency injection, middleware, and router registration using structured logging.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core import StructlogMiddleware, configure_logging, get_logger
from ..storage import StorageInterface, create_storage, validate_storage_config
from .config import config
from .dependencies import set_storage
from .health.router import router as health_router

# Configure structured logging
configure_logging(
    environment=config.environment,
    log_level=config.log_level,
    json_logs=config.json_logs or config.is_production,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan - startup and shutdown."""
    # Startup: Initialize storage
    try:
        logger.info(
            "Starting Knowledge Graph API...",
            environment=config.environment,
            log_level=config.log_level,
        )

        # Validate storage configuration
        validate_storage_config(config.storage)
        logger.info(
            "Storage configuration validated",
            backend_type=config.storage.backend_type,
            endpoint=config.storage.endpoint,
        )

        # Create and initialize storage backend
        storage: StorageInterface | None = create_storage(config.storage)

        if storage is None:
            logger.critical("Failed to create storage.")
            raise RuntimeError("Failed to create storage.")

        await storage.connect()

        # Set storage for dependency injection
        set_storage(storage)

        # Load schemas if available
        try:
            await storage.load_schemas(config.schema_dir)
            logger.info("Schemas loaded successfully", schema_dir=config.schema_dir)
        except Exception as e:
            logger.warning(
                "Could not load schemas", schema_dir=config.schema_dir, error=str(e)
            )

        logger.info(
            "Knowledge Graph API started successfully",
            storage_backend=config.storage.backend_type,
            environment=config.environment,
        )

    except Exception as e:
        logger.error("Failed to initialize storage", error=str(e))
        raise

    yield

    # Shutdown: Clean up storage
    try:
        logger.info("Shutting down Knowledge Graph API...")
        # Get storage from dependency injection
        from .dependencies import get_storage_unsafe

        storage = get_storage_unsafe()
        if storage:
            await storage.disconnect()
            logger.info("Storage disconnected cleanly")
    except Exception as e:
        logger.warning("Error during storage cleanup", error=str(e))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Red Hat Knowledge Graph API",
        description="""
        Modern knowledge graph API for managing repositories, dependencies, and relationships.

        **Features:**
        - Schema-driven entity management
        - Multi-layer validation pipeline
        - Strongly-typed API responses
        - Docker-native deployment

        **Environments:**
        - Development: Hot reload, debug logging
        - Production: Optimized performance, clustering
        """,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add structured logging middleware for request tracing
    if config.log_requests:
        app.add_middleware(StructlogMiddleware)

    # Add CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router, tags=["health"])
    # Future routers will be added here as they are implemented

    return app


# Create the app instance
app = create_app()


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": "Red Hat Knowledge Graph API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
