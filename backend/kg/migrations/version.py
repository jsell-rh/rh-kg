"""Schema version management and compatibility tracking.

This module handles semantic versioning for schemas and compatibility checking.
"""

from dataclasses import dataclass


@dataclass
class CompatibilityMatrix:
    """Represents version compatibility information."""

    versions: list[str]
    _compatibility_map: dict[tuple[str, str], bool] | None = None

    def is_compatible(self, version1: str, version2: str) -> bool:
        """Check if two versions are compatible.

        Compatible means they share the same major version for additive-only changes.

        Args:
            version1: First version to compare
            version2: Second version to compare

        Returns:
            True if versions are compatible
        """
        major1 = self._get_major_version(version1)
        major2 = self._get_major_version(version2)

        # Same major version = compatible (additive-only changes)
        return major1 == major2

    def _get_major_version(self, version: str) -> int:
        """Extract major version number from semantic version string."""
        return int(version.split(".")[0])


class SchemaVersionManager:
    """Manages schema version increments and compatibility."""

    def is_valid_version_increment(
        self, old_version: str, new_version: str, additive_only: bool
    ) -> bool:
        """Check if version increment is valid for the type of changes.

        Args:
            old_version: Previous version (e.g., "1.0.0")
            new_version: New version (e.g., "1.1.0")
            additive_only: True if only additive changes were made

        Returns:
            True if version increment is appropriate
        """
        old_parts = self._parse_version(old_version)
        new_parts = self._parse_version(new_version)

        old_major, old_minor, old_patch = old_parts
        new_major, new_minor, new_patch = new_parts

        # Major version increment
        if new_major > old_major:
            # Major version changes are only allowed for breaking changes
            return not additive_only

        # Same major version
        elif new_major == old_major:
            # Minor version increment - allowed for additive changes
            if new_minor > old_minor:
                return additive_only

            # Patch version increment - allowed for non-functional changes
            # No increment or decrement - invalid
            return new_minor == old_minor and new_patch > old_patch

        # Version went backwards - invalid
        else:
            return False

    def generate_compatibility_matrix(self, versions: list[str]) -> CompatibilityMatrix:
        """Generate compatibility matrix for list of versions.

        Args:
            versions: List of semantic version strings

        Returns:
            CompatibilityMatrix object
        """
        return CompatibilityMatrix(versions=versions)

    def _parse_version(self, version: str) -> tuple[int, int, int]:
        """Parse semantic version string into (major, minor, patch) tuple."""
        parts = version.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid semantic version: {version}")

        return (int(parts[0]), int(parts[1]), int(parts[2]))
