"""Comprehensive unit tests for the CLI apply command.

This module tests the `kg apply` command according to cli/apply-spec.md,
ensuring full validation pipeline, storage operations, dry-run functionality,
and proper error handling following TDD principles.
"""

from datetime import datetime
import json
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from kg.cli.apply import apply_command
from kg.storage import (
    DryRunResult,
    HealthCheckResult,
    HealthStatus,
    StorageInterface,
    SystemMetrics,
)
from kg.storage.models import (
    EntityCounts,
    EntityOperation,
    StorageConfig,
    ValidationIssue,
)


@pytest.fixture
def mock_apply_environment(mock_storage):
    """Set up complete mock environment for apply command testing."""
    with (
        patch("kg.cli.apply.create_storage") as mock_create_storage,
        patch("kg.cli.apply.FileSchemaLoader") as mock_schema_loader,
        patch("kg.api.config.config") as mock_config,
    ):
        # Setup config mock
        mock_config.storage = StorageConfig(
            backend_type="mock",
            endpoint="localhost:9080",
            timeout_seconds=30,
            max_retries=3,
            use_tls=False,
            retry_delay_seconds=1.0,
        )

        # Setup storage mocks
        mock_create_storage.return_value = mock_storage

        # Setup schema loader mocks
        from kg.core.schema import EntitySchema, FieldDefinition

        mock_repository_schema = EntitySchema(
            entity_type="repository",
            schema_version="1.0.0",
            description="A repository schema for testing",
            extends=None,
            required_fields=[
                FieldDefinition(
                    name="owners",
                    type="array",
                    required=True,
                    description="Repository owners",
                )
            ],
            optional_fields=[
                FieldDefinition(
                    name="git_repo_url",
                    type="string",
                    required=False,
                    description="Git repository URL",
                ),
                FieldDefinition(
                    name="depends_on",
                    type="array",
                    required=False,
                    description="Entity dependencies",
                ),
            ],
            readonly_fields=[],
            relationships=[],
            validation_rules={},
            dgraph_type="repository",
            dgraph_predicates={},
        )

        mock_schema_loader_instance = Mock()
        mock_schema_loader.return_value = mock_schema_loader_instance
        mock_schema_loader_instance.load_schemas = AsyncMock(
            return_value={"repository": mock_repository_schema}
        )

        yield {
            "mock_create_storage": mock_create_storage,
            "mock_schema_loader": mock_schema_loader,
            "mock_config": mock_config,
            "mock_storage": mock_storage,
        }


@pytest.fixture
def mock_storage():
    """Create a mock storage interface for testing."""
    storage = Mock(spec=StorageInterface)

    # Default successful health check
    storage.health_check = AsyncMock(
        return_value=HealthCheckResult(
            status=HealthStatus.HEALTHY,
            response_time_ms=10.0,
            backend_version="v23.1.0",
            additional_info={"test": "mock"},
        )
    )

    # Default successful metrics
    storage.get_system_metrics = AsyncMock(
        return_value=SystemMetrics(
            entity_counts=EntityCounts(
                repository=0,
                external_dependency_package=0,
                external_dependency_version=0,
            ),
            total_relationships=0,
            storage_size_mb=0.0,
            last_updated=datetime.now(),
            backend_specific={},
        )
    )

    # Default entity existence checks
    storage.entity_exists = AsyncMock(return_value=True)

    # Default storage operations
    storage.store_entity = AsyncMock(return_value="test-id")

    return storage


@pytest.fixture
def sample_valid_yaml():
    """Sample valid YAML content for testing."""
    return """
namespace: "test-namespace"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com"]
        git_repo_url: "https://github.com/test/repo"
"""


@pytest.fixture
def sample_invalid_yaml():
    """Sample invalid YAML content for testing."""
    return """
namespace: "test-namespace"
entity:
  repository:
    - test-repo:
        # Missing required 'owners' field
        git_repo_url: "https://github.com/test/repo"
"""


@pytest.fixture
def sample_complex_yaml():
    """Sample complex YAML with multiple entities and dependencies."""
    return """
namespace: "test-namespace"
entity:
  repository:
    - repo1:
        owners: ["team1@example.com"]
        git_repo_url: "https://github.com/test/repo1"
        depends_on: ["external://pypi/requests/2.31.0"]
    - repo2:
        owners: ["team2@example.com"]
        git_repo_url: "https://github.com/test/repo2"
        depends_on: ["internal://test-namespace/repo1"]
"""


class TestApplyCommandBasics:
    """Test basic apply command functionality."""

    def test_apply_command_exists(self):
        """Test that apply command can be imported."""
        from kg.cli.apply import apply_command

        assert apply_command is not None
        assert callable(apply_command)

    @patch("kg.cli.apply._apply_implementation")
    def test_apply_command_default_args(self, mock_impl):
        """Test apply command with default arguments."""
        from click.testing import CliRunner

        runner = CliRunner()
        runner.invoke(apply_command, [])

        # Should call implementation with default values
        mock_impl.assert_called_once()
        call_args = mock_impl.call_args[0]

        # Check default file argument
        assert call_args[0] == "knowledge-graph.yaml"

        # Check default options
        assert call_args[1] is None  # server
        assert call_args[2] is False  # dry_run
        assert call_args[3] is False  # force
        assert call_args[4] == 30  # timeout
        assert call_args[5] == "table"  # format
        assert call_args[6] is False  # verbose

    @patch("kg.cli.apply._apply_implementation")
    def test_apply_command_all_options(self, mock_impl):
        """Test apply command with all options specified."""
        from click.testing import CliRunner

        runner = CliRunner()
        runner.invoke(
            apply_command,
            [
                "custom-file.yaml",
                "--server",
                "http://localhost:8000",
                "--dry-run",
                "--force",
                "--timeout",
                "60",
                "--format",
                "json",
                "--verbose",
            ],
        )

        mock_impl.assert_called_once()
        call_args = mock_impl.call_args[0]

        assert call_args[0] == "custom-file.yaml"
        assert call_args[1] == "http://localhost:8000"
        assert call_args[2] is True  # dry_run
        assert call_args[3] is True  # force
        assert call_args[4] == 60  # timeout
        assert call_args[5] == "json"  # format
        assert call_args[6] is True  # verbose


class TestApplyValidation:
    """Test apply command validation functionality."""

    def test_apply_with_validation_success(
        self, mock_apply_environment, sample_valid_yaml
    ):
        """Test successful apply with valid YAML."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            # Should succeed (exit code 0)
            assert result.exit_code == 0
            assert "Apply successful" in result.output or "APPLIED" in result.output

        finally:
            Path(temp_path).unlink()

    def test_apply_with_validation_failure(
        self, mock_apply_environment, sample_invalid_yaml
    ):
        """Test apply failure with invalid YAML."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_invalid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            # Should fail with validation error (exit code 1)
            assert result.exit_code == 1
            assert (
                "validation" in result.output.lower()
                or "error" in result.output.lower()
            )

        finally:
            Path(temp_path).unlink()

    def test_apply_file_not_found(self):
        """Test apply with non-existent file."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(apply_command, ["nonexistent-file.yaml"])

        # Should fail with file not found (exit code 2)
        assert result.exit_code == 2
        assert "not found" in result.output.lower()


class TestApplyDryRun:
    """Test apply command dry-run functionality."""

    def test_dry_run_basic(self, mock_apply_environment, sample_valid_yaml):
        """Test basic dry-run functionality."""
        from click.testing import CliRunner

        # Get mocks from fixture
        mock_storage = mock_apply_environment["mock_storage"]

        # Mock dry-run result
        mock_storage.dry_run_apply = AsyncMock(
            return_value=DryRunResult(
                would_create=[
                    EntityOperation(
                        entity_type="repository",
                        entity_id="test-namespace/test-repo",
                        operation_type="create",
                        changes={"owners": ["test@example.com"]},
                    )
                ],
                would_update=[],
                would_delete=[],
                validation_issues=[],
                summary={"create_count": 1, "update_count": 0, "delete_count": 0},
            )
        )

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path, "--dry-run"])

            # Should succeed with dry-run output
            assert result.exit_code == 0
            assert (
                "dry-run" in result.output.lower()
                or "would create" in result.output.lower()
            )

            # Verify dry_run_apply was called but store_entity was not
            mock_storage.dry_run_apply.assert_called_once()
            mock_storage.store_entity.assert_not_called()

        finally:
            Path(temp_path).unlink()

    def test_dry_run_with_validation_issues(
        self, mock_apply_environment, sample_valid_yaml
    ):
        """Test dry-run with validation issues."""
        from click.testing import CliRunner

        # Get mocks from fixture
        mock_storage = mock_apply_environment["mock_storage"]

        # Mock dry-run result with validation issues
        mock_storage.dry_run_apply = AsyncMock(
            return_value=DryRunResult(
                would_create=[],
                would_update=[],
                would_delete=[],
                validation_issues=[
                    ValidationIssue(
                        severity="warning",
                        entity_type="repository",
                        entity_id="test-repo",
                        message="Repository already exists",
                        suggestion="Use different name or update existing",
                    )
                ],
                summary={"warning_count": 1},
            )
        )

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path, "--dry-run"])

            # Should succeed but show warnings
            assert result.exit_code == 0
            assert "warning" in result.output.lower()

        finally:
            Path(temp_path).unlink()


class TestApplyOutputFormats:
    """Test apply command output formats."""

    def test_apply_json_format_success(self, mock_apply_environment, sample_valid_yaml):
        """Test apply with JSON output format on success."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path, "--format", "json"])

            # Should succeed with valid JSON output
            assert result.exit_code == 0

            # Parse JSON output
            output_data = json.loads(result.output)
            assert output_data["status"] == "applied"
            assert "file" in output_data
            assert "summary" in output_data

        finally:
            Path(temp_path).unlink()

    def test_apply_json_format_error(self, mock_apply_environment, sample_invalid_yaml):
        """Test apply with JSON output format on validation error."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_invalid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path, "--format", "json"])

            # Should fail with valid JSON error output
            assert result.exit_code == 1

            # Parse JSON output
            output_data = json.loads(result.output)
            assert output_data["status"] == "failed"
            assert "errors" in output_data

        finally:
            Path(temp_path).unlink()

    def test_apply_compact_format(self, mock_apply_environment, sample_valid_yaml):
        """Test apply with compact output format."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path, "--format", "compact"])

            # Should succeed with compact output (single line)
            assert result.exit_code == 0
            lines = result.output.strip().split("\n")
            assert len(lines) == 1  # Compact should be single line
            assert "APPLIED" in result.output

        finally:
            Path(temp_path).unlink()


class TestApplyStorageIntegration:
    """Test apply command storage backend integration."""

    @patch("kg.cli.apply.create_storage")
    @patch("kg.cli.apply.FileSchemaLoader")
    def test_apply_storage_connection_failure(
        self, mock_schema_loader, mock_create_storage, sample_valid_yaml
    ):
        """Test apply when storage connection fails."""
        from click.testing import CliRunner

        # Setup mocks - storage creation fails
        mock_create_storage.side_effect = Exception("Connection failed")
        mock_schema_loader_instance = Mock()
        mock_schema_loader.return_value = mock_schema_loader_instance
        mock_schema_loader_instance.load_schemas = AsyncMock(
            return_value={"repository": Mock()}
        )

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            # Should fail with storage connection error (exit code 3)
            assert result.exit_code == 3
            assert (
                "storage" in result.output.lower()
                or "connection" in result.output.lower()
            )

        finally:
            Path(temp_path).unlink()

    def test_apply_storage_operation_failure(
        self, mock_apply_environment, sample_valid_yaml
    ):
        """Test apply when storage operations fail."""
        from click.testing import CliRunner

        # Get mocks from fixture
        mock_storage = mock_apply_environment["mock_storage"]

        # Make storage operations fail
        mock_storage.store_entity = AsyncMock(
            side_effect=Exception("Storage operation failed")
        )

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            # Should fail with storage operation error (exit code 3)
            assert result.exit_code == 3

        finally:
            Path(temp_path).unlink()


class TestApplyReferenceValidation:
    """Test apply command reference validation (Layer 5)."""

    def test_apply_with_valid_references(
        self, mock_apply_environment, sample_complex_yaml
    ):
        """Test apply with valid internal references."""
        from click.testing import CliRunner

        # Get mocks from fixture
        mock_storage = mock_apply_environment["mock_storage"]

        # Mock that referenced entities exist
        mock_storage.entity_exists = AsyncMock(return_value=True)

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_complex_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            # Should succeed
            assert result.exit_code == 0

            # Verify reference validation was called
            mock_storage.entity_exists.assert_called()

        finally:
            Path(temp_path).unlink()

    def test_apply_with_invalid_references(
        self, mock_apply_environment, sample_complex_yaml
    ):
        """Test apply with invalid internal references."""
        from click.testing import CliRunner

        # Get mocks from fixture
        mock_storage = mock_apply_environment["mock_storage"]

        # Mock that referenced entities don't exist
        mock_storage.entity_exists = AsyncMock(return_value=False)

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_complex_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            # Should fail with validation error (exit code 1)
            assert result.exit_code == 1
            assert (
                "reference" in result.output.lower()
                or "not found" in result.output.lower()
            )

        finally:
            Path(temp_path).unlink()


class TestApplyExitCodes:
    """Test apply command exit codes per specification."""

    def test_exit_code_file_not_found(self):
        """Test exit code 2 for file not found."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(apply_command, ["nonexistent.yaml"])

        assert result.exit_code == 2

    def test_exit_code_validation_failed(
        self, mock_apply_environment, sample_invalid_yaml
    ):
        """Test exit code 1 for validation failure."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_invalid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            assert result.exit_code == 1

        finally:
            Path(temp_path).unlink()

    @patch("kg.cli.apply.create_storage")
    def test_exit_code_storage_failed(self, mock_create_storage, sample_valid_yaml):
        """Test exit code 3 for storage failure."""
        from click.testing import CliRunner

        # Setup storage creation failure
        mock_create_storage.side_effect = Exception("Storage failed")

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            assert result.exit_code == 3

        finally:
            Path(temp_path).unlink()

    def test_exit_code_success(self, mock_apply_environment, sample_valid_yaml):
        """Test exit code 0 for success."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(apply_command, [temp_path])

            assert result.exit_code == 0

        finally:
            Path(temp_path).unlink()


class TestApplyTimeout:
    """Test apply command timeout functionality."""

    def test_timeout_option_validation(self):
        """Test timeout option accepts valid values."""
        from click.testing import CliRunner

        runner = CliRunner()

        # Valid timeout values
        for timeout in [1, 30, 300]:
            result = runner.invoke(apply_command, ["--timeout", str(timeout), "--help"])
            assert result.exit_code == 0

        # Invalid timeout values should be rejected by click
        result = runner.invoke(apply_command, ["--timeout", "0"])
        assert result.exit_code != 0

        result = runner.invoke(apply_command, ["--timeout", "400"])
        assert result.exit_code != 0


class TestApplyVerboseMode:
    """Test apply command verbose mode."""

    def test_verbose_output(self, mock_apply_environment, sample_valid_yaml):
        """Test verbose mode provides additional details."""
        from click.testing import CliRunner

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_valid_yaml)
            temp_path = f.name

        try:
            runner = CliRunner()
            result_normal = runner.invoke(apply_command, [temp_path])
            result_verbose = runner.invoke(apply_command, [temp_path, "--verbose"])

            # Both should succeed
            assert result_normal.exit_code == 0
            assert result_verbose.exit_code == 0

            # Verbose should have more output
            assert len(result_verbose.output) >= len(result_normal.output)

        finally:
            Path(temp_path).unlink()
