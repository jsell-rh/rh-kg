"""Comprehensive tests for the CLI validation command.

This module tests the `kg validate` command according to cli/validation-spec.md,
covering all command-line arguments, output formats, exit codes, and error scenarios.
"""

import json
from pathlib import Path
import tempfile

from click.testing import CliRunner
import pytest

from kg.cli.validate import validate_command


# Global fixtures for all test classes
@pytest.fixture
def runner():
    """Create CLI runner for tests."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def valid_yaml_content():
    """Valid YAML content for testing."""
    return """
schema_version: "1.0.0"
namespace: "test-project"
entity:
  repository:
    - test-repo:
        owners: ["team@company.com"]
        git_repo_url: "https://github.com/company/test-repo"
        depends_on:
          - "external://pypi/requests/2.31.0"
"""


@pytest.fixture
def invalid_yaml_content():
    """Invalid YAML content for testing."""
    return """
schema_version: "2.0.0"  # Unsupported version
namespace: "test-project"
entity:
  repository:
    - test-repo:
        owners: []  # Empty array
        git_repo_url: "not-a-url"  # Invalid URL
"""


class TestCLIValidateBasics:
    """Test basic CLI validation command functionality."""

    def test_validate_command_exists(self):
        """Test that the validate command can be imported."""
        assert validate_command is not None
        assert callable(validate_command)

    def test_cli_runner_setup(self):
        """Test that CLI runner works."""
        runner = CliRunner()
        assert runner is not None


class TestCLIArgumentParsing:
    """Test command line argument parsing."""

    def test_validate_with_no_arguments_uses_default_file(self, runner):
        """Test that validate with no args looks for knowledge-graph.yaml."""
        # This should fail with file not found (exit code 2)
        result = runner.invoke(validate_command, [])
        assert result.exit_code == 2
        assert "knowledge-graph.yaml" in result.output
        assert "File not found" in result.output or "not found" in result.output

    def test_validate_with_file_argument(self, runner, temp_dir, valid_yaml_content):
        """Test validate with explicit file argument."""
        test_file = temp_dir / "test-graph.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file)])
        assert result.exit_code in [0, 1]  # Should parse and validate

    def test_validate_with_schema_version_option(
        self, runner, temp_dir, valid_yaml_content
    ):
        """Test --schema-version option."""
        test_file = temp_dir / "test.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(
            validate_command, [str(test_file), "--schema-version", "1.0.0"]
        )
        assert result.exit_code in [0, 1]

    def test_validate_with_strict_option(self, runner, temp_dir, valid_yaml_content):
        """Test --strict option."""
        test_file = temp_dir / "test.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file), "--strict"])
        assert result.exit_code in [0, 1]

    def test_validate_with_format_options(self, runner, temp_dir, valid_yaml_content):
        """Test all --format options."""
        test_file = temp_dir / "test.yaml"
        test_file.write_text(valid_yaml_content)

        formats = ["table", "compact", "json", "yaml"]
        for fmt in formats:
            result = runner.invoke(validate_command, [str(test_file), "--format", fmt])
            assert result.exit_code in [0, 1]

    def test_validate_with_verbose_option(self, runner, temp_dir, valid_yaml_content):
        """Test --verbose option."""
        test_file = temp_dir / "test.yaml"
        test_file.write_text(valid_yaml_content)

        # Test both short and long form
        for verbose_flag in ["-v", "--verbose"]:
            result = runner.invoke(validate_command, [str(test_file), verbose_flag])
            assert result.exit_code in [0, 1]

    def test_invalid_format_option_fails(self, runner):
        """Test that invalid format option fails with exit code 2."""
        result = runner.invoke(
            validate_command, ["nonexistent.yaml", "--format", "invalid"]
        )
        assert result.exit_code == 2
        assert "Invalid" in result.output or "invalid" in result.output


class TestCLIExitCodes:
    """Test CLI exit codes match specification."""

    def test_exit_code_0_on_valid_file(self, runner, temp_dir, valid_yaml_content):
        """Test exit code 0 for successful validation."""
        test_file = temp_dir / "valid.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file)])
        assert result.exit_code == 0

    def test_exit_code_1_on_invalid_file(self, runner, temp_dir, invalid_yaml_content):
        """Test exit code 1 for validation failures."""
        test_file = temp_dir / "invalid.yaml"
        test_file.write_text(invalid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file)])
        assert result.exit_code == 1

    def test_exit_code_2_on_file_not_found(self, runner):
        """Test exit code 2 for file not found."""
        result = runner.invoke(validate_command, ["nonexistent.yaml"])
        assert result.exit_code == 2

    def test_exit_code_2_on_invalid_arguments(self, runner):
        """Test exit code 2 for invalid arguments."""
        result = runner.invoke(validate_command, ["--invalid-option"])
        assert result.exit_code == 2


class TestCLIOutputFormats:
    """Test different CLI output formats."""

    def test_table_format_success(self, runner, temp_dir, valid_yaml_content):
        """Test table format for successful validation."""
        test_file = temp_dir / "valid.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file), "--format", "table"])
        assert result.exit_code == 0
        assert "✅" in result.output
        assert "Validation successful" in result.output
        assert "Schema version:" in result.output
        assert "Namespace:" in result.output

    def test_compact_format_success(self, runner, temp_dir, valid_yaml_content):
        """Test compact format for successful validation."""
        test_file = temp_dir / "valid.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(
            validate_command, [str(test_file), "--format", "compact"]
        )
        assert result.exit_code == 0
        assert "✅" in result.output
        assert "VALID" in result.output
        assert "schema=" in result.output

    def test_json_format_success(self, runner, temp_dir, valid_yaml_content):
        """Test JSON format for successful validation."""
        test_file = temp_dir / "valid.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file), "--format", "json"])
        assert result.exit_code == 0

        # Parse JSON output
        output_json = json.loads(result.output)
        assert output_json["status"] == "valid"
        assert "file" in output_json
        assert "schema_version" in output_json
        assert "namespace" in output_json

    def test_table_format_failure(self, runner, temp_dir, invalid_yaml_content):
        """Test table format for validation failures."""
        test_file = temp_dir / "invalid.yaml"
        test_file.write_text(invalid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file), "--format", "table"])
        assert result.exit_code == 1
        assert "❌" in result.output
        assert "Validation failed" in result.output
        assert "Errors found:" in result.output

    def test_json_format_failure(self, runner, temp_dir, invalid_yaml_content):
        """Test JSON format for validation failures."""
        test_file = temp_dir / "invalid.yaml"
        test_file.write_text(invalid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file), "--format", "json"])
        assert result.exit_code == 1

        # Parse JSON output
        output_json = json.loads(result.output)
        assert output_json["status"] == "invalid"
        assert "error_count" in output_json
        assert "errors" in output_json
        assert len(output_json["errors"]) > 0


class TestCLIVerboseMode:
    """Test verbose mode functionality."""

    def test_verbose_mode_success_shows_details(
        self, runner, temp_dir, valid_yaml_content
    ):
        """Test verbose mode shows detailed information for success."""
        test_file = temp_dir / "valid.yaml"
        test_file.write_text(valid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file), "--verbose"])
        assert result.exit_code == 0
        assert "bytes" in result.output
        assert "Parsed in:" in result.output or "ms" in result.output
        assert "Dependencies:" in result.output or "Dependency" in result.output

    def test_verbose_mode_failure_shows_analysis(
        self, runner, temp_dir, invalid_yaml_content
    ):
        """Test verbose mode shows detailed error analysis."""
        test_file = temp_dir / "invalid.yaml"
        test_file.write_text(invalid_yaml_content)

        result = runner.invoke(validate_command, [str(test_file), "--verbose"])
        assert result.exit_code == 1
        assert (
            "Detailed error analysis:" in result.output or "Analysis:" in result.output
        )


class TestCLIErrorMessages:
    """Test error message formatting and helpfulness."""

    def test_file_not_found_error_message(self, runner):
        """Test file not found error provides helpful message."""
        result = runner.invoke(validate_command, ["nonexistent.yaml"])
        assert result.exit_code == 2
        assert "File not found" in result.output or "not found" in result.output
        assert "nonexistent.yaml" in result.output

    def test_yaml_syntax_error_shows_line_numbers(self, runner, temp_dir):
        """Test YAML syntax errors show line numbers."""
        invalid_yaml = """
schema_version: "1.0.0"
namespace: "test"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com"  # Missing closing bracket
"""
        test_file = temp_dir / "syntax-error.yaml"
        test_file.write_text(invalid_yaml)

        result = runner.invoke(validate_command, [str(test_file)])
        assert result.exit_code == 1
        # Should show line information
        assert "line" in result.output.lower()

    def test_validation_errors_show_helpful_context(self, runner, temp_dir):
        """Test validation errors include helpful context and suggestions."""
        invalid_yaml = """
schema_version: "1.0.0"
namespace: "test"
entity:
  repository:
    - test-repo:
        owners: []  # Empty array
        git_repo_url: "not-a-url"
        depends_on:
          - "invalid-dependency"
"""
        test_file = temp_dir / "validation-errors.yaml"
        test_file.write_text(invalid_yaml)

        result = runner.invoke(validate_command, [str(test_file)])
        assert result.exit_code == 1
        # Should show helpful error messages
        assert "Help:" in result.output or "help" in result.output.lower()


class TestCLIIntegrationWithValidationEngine:
    """Test CLI integration with the existing validation engine."""

    def test_cli_uses_real_schemas(self, runner, temp_dir):
        """Test CLI loads and uses real schemas from spec directory."""
        # Create a YAML file with real repository structure
        yaml_content = """
schema_version: "1.0.0"
namespace: "test-project"
entity:
  repository:
    - test-repo:
        owners: ["team@company.com"]
        git_repo_url: "https://github.com/company/test-repo"
"""
        test_file = temp_dir / "real-schema-test.yaml"
        test_file.write_text(yaml_content)

        result = runner.invoke(validate_command, [str(test_file)])
        # Should work with real schemas
        assert result.exit_code in [0, 1]

    def test_cli_validates_repository_fields(self, runner, temp_dir):
        """Test CLI validates repository fields according to schemas."""
        # Missing required field
        yaml_content = """
schema_version: "1.0.0"
namespace: "test-project"
entity:
  repository:
    - test-repo:
        git_repo_url: "https://github.com/company/test-repo"
        # Missing owners field
"""
        test_file = temp_dir / "missing-field.yaml"
        test_file.write_text(yaml_content)

        result = runner.invoke(validate_command, [str(test_file)])
        assert result.exit_code == 1
        assert "owners" in result.output


class TestCLIPerformance:
    """Test CLI performance requirements."""

    def test_validation_completes_quickly(self, runner, temp_dir, valid_yaml_content):
        """Test validation completes in reasonable time."""
        test_file = temp_dir / "performance-test.yaml"
        test_file.write_text(valid_yaml_content)

        import time

        start_time = time.time()
        result = runner.invoke(validate_command, [str(test_file)])
        end_time = time.time()

        # Should complete within 5 seconds (generous for CI)
        assert (end_time - start_time) < 5.0
        assert result.exit_code in [0, 1]
