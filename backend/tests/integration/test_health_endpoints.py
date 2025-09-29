"""Integration tests for health-related API endpoints.

This module tests the /health, /metrics, and /status endpoints to ensure
they properly handle various storage backend states and return expected
data structures.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
import pytest
import pytest_asyncio

from kg.api.dependencies import set_storage
from kg.storage import (
    HealthCheckResult,
    HealthStatus,
    StorageInterface,
    SystemMetrics,
)
from kg.storage.models import EntityCounts


@pytest.fixture
def mock_storage():
    """Create a mock storage interface for testing."""
    storage = Mock(spec=StorageInterface)
    return storage


@pytest.fixture
def app_with_mock_storage(mock_storage):
    """Create FastAPI app with mock storage dependency."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from kg.api.health.router import router as health_router

    # Create a minimal test app without the problematic lifespan
    app = FastAPI(
        title="Test Knowledge Graph API",
        version="0.1.0",
        # Don't use the lifespan that creates real storage
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router, tags=["health"])

    # Set the mock storage for dependency injection
    set_storage(mock_storage)

    return app


@pytest.fixture
def client(app_with_mock_storage):
    """Create test client with mock storage."""
    return TestClient(app_with_mock_storage)


@pytest_asyncio.fixture
async def async_client(app_with_mock_storage):
    """Create async test client with mock storage."""
    from fastapi.testclient import TestClient

    # For async testing with FastAPI, we'll use a regular TestClient
    # since the endpoints we're testing don't have async dependencies
    # that require true async client behavior
    with TestClient(app_with_mock_storage) as client:
        yield client


class TestHealthEndpoint:
    """Test the /health endpoint."""

    def test_health_check_healthy_storage(self, client, mock_storage):
        """Test health check when storage is healthy."""
        # Setup mock storage response
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=15.5,
                backend_version="v23.1.0",
                additional_info={
                    "endpoint": "dgraph-alpha:9080",
                    "schemas_loaded": 3,
                    "query_response": {"health": [{"count": 100}]},
                },
            )
        )

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["response_time_ms"] == 15.5
        assert data["backend_version"] == "v23.1.0"
        assert data["additional_info"]["endpoint"] == "dgraph-alpha:9080"
        assert data["additional_info"]["schemas_loaded"] == 3

        mock_storage.health_check.assert_called_once()

    def test_health_check_degraded_storage(self, client, mock_storage):
        """Test health check when storage is degraded."""
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.DEGRADED,
                response_time_ms=250.0,
                backend_version="v23.1.0",
                additional_info={
                    "error": "Slow response from backend",
                    "endpoint": "dgraph-alpha:9080",
                },
            )
        )

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["response_time_ms"] == 250.0
        assert "Slow response from backend" in data["additional_info"]["error"]

    def test_health_check_disconnected_storage(self, client, mock_storage):
        """Test health check when storage is disconnected."""
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.DISCONNECTED,
                response_time_ms=0.0,
                backend_version="unknown",
                additional_info={"error": "Not connected to Dgraph"},
            )
        )

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "disconnected"
        assert data["response_time_ms"] == 0.0
        assert data["backend_version"] == "unknown"
        assert "Not connected to Dgraph" in data["additional_info"]["error"]

    def test_health_check_storage_exception(self, client, mock_storage):
        """Test health check when storage raises an exception."""
        mock_storage.health_check = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "error"
        assert data["response_time_ms"] == 0.0
        assert data["backend_version"] is None
        assert "Database connection failed" in data["additional_info"]["error"]
        assert data["additional_info"]["api_status"] == "running"
        assert data["additional_info"]["storage_status"] == "error"

    @pytest.mark.asyncio
    async def test_health_check_async(self, async_client, mock_storage):
        """Test health check with async client."""
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=12.3,
                backend_version="v23.1.0",
                additional_info={"test": "async"},
            )
        )

        response = async_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["additional_info"]["test"] == "async"


class TestMetricsEndpoint:
    """Test the /metrics endpoint."""

    def test_metrics_successful_response(self, client, mock_storage):
        """Test metrics endpoint with successful storage response."""
        # Setup mock metrics response
        entity_counts = EntityCounts(
            repository=15,
            external_dependency_package=250,
            external_dependency_version=1500,
        )

        mock_storage.get_system_metrics = AsyncMock(
            return_value=SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=750,
                storage_size_mb=45.2,
                last_updated=datetime(2024, 1, 15, 10, 30, 0),
                backend_specific={
                    "dgraph_version": "v23.1.0",
                    "endpoint": "dgraph-alpha:9080",
                },
            )
        )

        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()

        assert data["entity_counts"]["repository"] == 15
        assert data["entity_counts"]["external_dependency_package"] == 250
        assert data["entity_counts"]["external_dependency_version"] == 1500
        assert data["entity_counts"]["total"] == 1765  # Sum calculated automatically
        assert data["total_relationships"] == 750
        assert data["storage_size_mb"] == 45.2
        assert data["last_updated"] == "2024-01-15T10:30:00"
        assert data["backend_specific"]["dgraph_version"] == "v23.1.0"

        mock_storage.get_system_metrics.assert_called_once()

    def test_metrics_storage_exception(self, client, mock_storage):
        """Test metrics endpoint when storage raises an exception."""
        mock_storage.get_system_metrics = AsyncMock(
            side_effect=Exception("Metrics collection failed")
        )

        response = client.get("/metrics")

        assert response.status_code == 500
        data = response.json()

        assert "Failed to retrieve system metrics" in data["detail"]
        assert "Metrics collection failed" in data["detail"]

    def test_metrics_zero_counts(self, client, mock_storage):
        """Test metrics endpoint with zero entity counts."""
        entity_counts = EntityCounts(
            repository=0,
            external_dependency_package=0,
            external_dependency_version=0,
        )

        mock_storage.get_system_metrics = AsyncMock(
            return_value=SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=0,
                storage_size_mb=0.1,
                last_updated=datetime(2024, 1, 15, 10, 30, 0),
                backend_specific={},
            )
        )

        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()

        assert data["entity_counts"]["total"] == 0
        assert data["total_relationships"] == 0
        assert data["storage_size_mb"] == 0.1

    @pytest.mark.asyncio
    async def test_metrics_async(self, async_client, mock_storage):
        """Test metrics endpoint with async client."""
        entity_counts = EntityCounts(
            repository=1, external_dependency_package=2, external_dependency_version=3
        )

        mock_storage.get_system_metrics = AsyncMock(
            return_value=SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=5,
                storage_size_mb=1.0,
                last_updated=datetime(2024, 1, 15, 10, 30, 0),
                backend_specific={"test": "async"},
            )
        )

        response = async_client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["backend_specific"]["test"] == "async"


class TestStatusEndpoint:
    """Test the /status endpoint."""

    def test_status_successful_response(self, client, mock_storage):
        """Test status endpoint with successful storage responses."""
        # Setup mock health response
        health_result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            response_time_ms=20.5,
            backend_version="v23.1.0",
            additional_info={
                "endpoint": "dgraph-alpha:9080",
                "schemas_loaded": 3,
            },
        )

        # Setup mock metrics response
        entity_counts = EntityCounts(
            repository=10,
            external_dependency_package=100,
            external_dependency_version=500,
        )
        metrics_result = SystemMetrics(
            entity_counts=entity_counts,
            total_relationships=250,
            storage_size_mb=25.5,
            last_updated=datetime(2024, 1, 15, 12, 0, 0),
            backend_specific={"dgraph_version": "v23.1.0"},
        )

        # Mock the health service methods
        mock_storage.health_check = AsyncMock(return_value=health_result)
        mock_storage.get_system_metrics = AsyncMock(return_value=metrics_result)

        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()

        # Check API section
        assert data["api"]["name"] == "Knowledge Graph API"
        assert data["api"]["version"] == "0.1.0"
        assert data["api"]["status"] == "healthy"
        assert "response_time_ms" in data["api"]

        # Check storage section
        assert (
            "DgraphStorage" in data["storage"]["type"]
            or "Mock" in data["storage"]["type"]
        )
        assert data["storage"]["status"] == "healthy"
        assert data["storage"]["response_time_ms"] == 20.5
        assert data["storage"]["backend_version"] == "v23.1.0"
        assert data["storage"]["additional_info"]["endpoint"] == "dgraph-alpha:9080"

        # Check metrics section
        assert data["metrics"]["total_entities"] == 610  # Sum of all entity counts
        assert data["metrics"]["entity_breakdown"]["repositories"] == 10
        assert data["metrics"]["entity_breakdown"]["external_packages"] == 100
        assert data["metrics"]["entity_breakdown"]["external_versions"] == 500
        assert data["metrics"]["total_relationships"] == 250
        assert data["metrics"]["storage_size_mb"] == 25.5
        assert data["metrics"]["last_updated"] == "2024-01-15T12:00:00"

        # Check environment section
        assert "timestamp" in data["environment"]
        assert "uptime_seconds" in data["environment"]

        # Verify both service methods were called
        mock_storage.health_check.assert_called_once()
        mock_storage.get_system_metrics.assert_called_once()

    def test_status_health_exception(self, client, mock_storage):
        """Test status endpoint when health check fails but metrics succeeds."""
        mock_storage.health_check = AsyncMock(
            side_effect=Exception("Health check failed")
        )

        # Metrics should still succeed
        entity_counts = EntityCounts(
            repository=5, external_dependency_package=10, external_dependency_version=15
        )
        mock_storage.get_system_metrics = AsyncMock(
            return_value=SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=20,
                storage_size_mb=5.0,
                last_updated=datetime(2024, 1, 15, 12, 0, 0),
                backend_specific={},
            )
        )

        response = client.get("/status")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve detailed status" in data["detail"]
        assert "Health check failed" in data["detail"]

    def test_status_metrics_exception(self, client, mock_storage):
        """Test status endpoint when metrics fails but health succeeds."""
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=15.0,
                backend_version="v23.1.0",
                additional_info={},
            )
        )

        mock_storage.get_system_metrics = AsyncMock(
            side_effect=Exception("Metrics collection failed")
        )

        response = client.get("/status")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve detailed status" in data["detail"]
        assert "Metrics collection failed" in data["detail"]

    def test_status_both_exceptions(self, client, mock_storage):
        """Test status endpoint when both health and metrics fail."""
        mock_storage.health_check = AsyncMock(
            side_effect=Exception("Health check failed")
        )
        mock_storage.get_system_metrics = AsyncMock(
            side_effect=Exception("Metrics failed")
        )

        response = client.get("/status")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve detailed status" in data["detail"]

    @pytest.mark.asyncio
    async def test_status_async(self, async_client, mock_storage):
        """Test status endpoint with async client."""
        # Setup basic working responses
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=10.0,
                backend_version="v23.1.0",
                additional_info={"test": "async"},
            )
        )

        entity_counts = EntityCounts(
            repository=1, external_dependency_package=2, external_dependency_version=3
        )
        mock_storage.get_system_metrics = AsyncMock(
            return_value=SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=5,
                storage_size_mb=1.0,
                last_updated=datetime(2024, 1, 15, 12, 0, 0),
                backend_specific={"test": "async"},
            )
        )

        response = async_client.get("/status")

        assert response.status_code == 200
        data = response.json()
        assert data["storage"]["additional_info"]["test"] == "async"


class TestEndpointDataTypes:
    """Test that endpoints return correct data types and structures."""

    def test_health_response_model_compliance(self, client, mock_storage):
        """Test that health endpoint response matches HealthCheckResult model."""
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=15.5,
                backend_version="v23.1.0",
                additional_info={"key": "value"},
            )
        )

        response = client.get("/health")
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "status",
            "response_time_ms",
            "backend_version",
            "additional_info",
        ]
        for field in required_fields:
            assert field in data

        # Verify types
        assert isinstance(data["status"], str)
        assert isinstance(data["response_time_ms"], int | float)
        assert isinstance(data["additional_info"], dict)

    def test_metrics_response_model_compliance(self, client, mock_storage):
        """Test that metrics endpoint response matches SystemMetrics model."""
        entity_counts = EntityCounts(
            repository=1, external_dependency_package=2, external_dependency_version=3
        )
        mock_storage.get_system_metrics = AsyncMock(
            return_value=SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=5,
                storage_size_mb=1.0,
                last_updated=datetime(2024, 1, 15, 12, 0, 0),
                backend_specific={"key": "value"},
            )
        )

        response = client.get("/metrics")
        data = response.json()

        # Verify required fields
        required_fields = [
            "entity_counts",
            "total_relationships",
            "storage_size_mb",
            "last_updated",
            "backend_specific",
        ]
        for field in required_fields:
            assert field in data

        # Verify entity_counts structure
        entity_count_fields = [
            "repository",
            "external_dependency_package",
            "external_dependency_version",
            "total",
        ]
        for field in entity_count_fields:
            assert field in data["entity_counts"]
            assert isinstance(data["entity_counts"][field], int)

        # Verify types
        assert isinstance(data["total_relationships"], int)
        assert isinstance(data["storage_size_mb"], int | float)
        assert isinstance(data["last_updated"], str)  # ISO format
        assert isinstance(data["backend_specific"], dict)

    def test_status_response_structure(self, client, mock_storage):
        """Test that status endpoint returns expected structure."""
        # Setup working responses
        mock_storage.health_check = AsyncMock(
            return_value=HealthCheckResult(
                status=HealthStatus.HEALTHY,
                response_time_ms=10.0,
                backend_version="v23.1.0",
                additional_info={},
            )
        )

        entity_counts = EntityCounts(
            repository=1, external_dependency_package=2, external_dependency_version=3
        )
        mock_storage.get_system_metrics = AsyncMock(
            return_value=SystemMetrics(
                entity_counts=entity_counts,
                total_relationships=5,
                storage_size_mb=1.0,
                last_updated=datetime(2024, 1, 15, 12, 0, 0),
                backend_specific={},
            )
        )

        response = client.get("/status")
        data = response.json()

        # Verify top-level sections
        required_sections = ["api", "storage", "metrics", "environment"]
        for section in required_sections:
            assert section in data
            assert isinstance(data[section], dict)

        # Verify API section structure
        api_fields = ["name", "version", "status", "response_time_ms"]
        for field in api_fields:
            assert field in data["api"]

        # Verify storage section structure
        storage_fields = [
            "type",
            "status",
            "response_time_ms",
            "backend_version",
            "additional_info",
        ]
        for field in storage_fields:
            assert field in data["storage"]

        # Verify metrics section structure
        metrics_fields = [
            "total_entities",
            "entity_breakdown",
            "total_relationships",
            "storage_size_mb",
            "last_updated",
        ]
        for field in metrics_fields:
            assert field in data["metrics"]

        # Verify entity_breakdown structure
        breakdown_fields = ["repositories", "external_packages", "external_versions"]
        for field in breakdown_fields:
            assert field in data["metrics"]["entity_breakdown"]
            assert isinstance(data["metrics"]["entity_breakdown"][field], int)

        # Verify environment section structure
        env_fields = ["timestamp", "uptime_seconds", "started_at"]
        for field in env_fields:
            assert field in data["environment"]

        # Verify uptime is reasonable (positive and not tiny)
        assert data["environment"]["uptime_seconds"] >= 0
        assert isinstance(data["environment"]["uptime_seconds"], int | float)

        # Verify started_at is a valid ISO format string
        assert isinstance(data["environment"]["started_at"], str)
        assert (
            len(data["environment"]["started_at"]) == 19
        )  # YYYY-MM-DDTHH:MM:SS format
