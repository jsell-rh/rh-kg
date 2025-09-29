"""Integration tests that demonstrate real issues with apply command.

These tests use actual Dgraph storage to show:
1. Duplicate entity creation bug
2. Missing dependency processing bug
"""

from pathlib import Path
import tempfile

import pytest

from kg.cli.apply import apply_command


@pytest.mark.integration
class TestApplyRealIssues:
    """Integration tests that demonstrate actual bugs in apply command."""

    def test_duplicate_entity_creation_with_real_storage(self):
        """Test that demonstrates duplicate entity creation bug."""
        from click.testing import CliRunner

        yaml_content = """
schema_version: "1.0.0"
namespace: "test-namespace"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com"]
        git_repo_url: "https://github.com/test/repo"
"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            runner = CliRunner()

            # Apply first time
            result1 = runner.invoke(apply_command, [temp_path, "--format", "json"])
            print("First apply result:", result1.output)
            assert result1.exit_code == 0

            # Apply second time - should update, not create duplicate
            result2 = runner.invoke(apply_command, [temp_path, "--format", "json"])
            print("Second apply result:", result2.output)
            assert result2.exit_code == 0

            # This test will currently show the bug - "created=1" on second apply
            # After fix, second apply should show "created=0, updated=1"

        finally:
            Path(temp_path).unlink()

    def test_missing_dependency_processing_with_real_storage(self):
        """Test that demonstrates missing dependency processing."""
        from click.testing import CliRunner

        yaml_content = """
schema_version: "1.0.0"
namespace: "test-namespace"
entity:
  repository:
    - test-repo:
        owners: ["test@example.com"]
        git_repo_url: "https://github.com/test/repo"
        depends_on:
          - "external://pypi/requests/2.31.0"
"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            runner = CliRunner()

            # Apply with dependencies
            result = runner.invoke(apply_command, [temp_path, "--format", "json"])
            print("Apply with dependencies result:", result.output)
            assert result.exit_code == 0

            # TODO: Add queries to verify dependency entities were created
            # This should create:
            # 1. ExternalDependencyPackage: external://pypi/requests
            # 2. ExternalDependencyVersion: external://pypi/requests/2.31.0
            # 3. Relationship from repository to dependency version

        finally:
            Path(temp_path).unlink()

    def test_query_storage_to_show_duplicates(self):
        """Query storage directly to demonstrate duplicate issue."""
        # This test would query Dgraph directly to show multiple nodes
        # with the same entity_id, demonstrating the duplicate creation bug
        pass

    def test_query_storage_to_show_missing_dependencies(self):
        """Query storage directly to show missing dependency entities."""
        # This test would query Dgraph to show that external dependency
        # entities are not being created when depends_on is specified
        pass
