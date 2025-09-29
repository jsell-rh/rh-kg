"""Dependency type definitions and URI handling.

This module defines the supported dependency types and provides utilities
for parsing, validating, and working with dependency URIs in a consistent way.
"""

from enum import Enum
import re
from typing import Any


class DependencyType(Enum):
    """Supported dependency types with their URI patterns and parsing logic."""

    EXTERNAL = "external"
    INTERNAL = "internal"

    @property
    def uri_prefix(self) -> str:
        """Get the URI prefix for this dependency type."""
        return f"{self.value}://"

    @property
    def uri_pattern(self) -> str:
        """Get the regex pattern for validating URIs of this type."""
        if self == DependencyType.EXTERNAL:
            # external://ecosystem/package/version
            return r"^external://([^/]+)/(.+)/([^/]+)$"
        elif self == DependencyType.INTERNAL:
            # internal://namespace/entity-id (can have multiple path segments)
            return r"^internal://(.+)$"
        else:
            raise ValueError(f"Unknown dependency type: {self}")

    def matches_uri(self, uri: str) -> bool:
        """Check if a URI matches this dependency type.

        Args:
            uri: Dependency URI to check

        Returns:
            True if URI matches this dependency type
        """
        if not uri or not isinstance(uri, str):
            return False
        return uri.startswith(self.uri_prefix)

    def parse_uri(self, uri: str) -> dict[str, Any] | None:
        """Parse a dependency URI into its components.

        Args:
            uri: Dependency URI to parse

        Returns:
            Dictionary with parsed components or None if invalid
        """
        if not self.matches_uri(uri):
            return None

        match = re.match(self.uri_pattern, uri)
        if not match:
            return None

        return self._parse_matched_groups(match, uri)

    def _parse_matched_groups(
        self, match: re.Match[str], uri: str
    ) -> dict[str, Any] | None:
        """Parse regex match groups based on dependency type."""
        if self == DependencyType.EXTERNAL:
            return self._parse_external_groups(match, uri)
        elif self == DependencyType.INTERNAL:
            return self._parse_internal_groups(match, uri)
        return None

    def _parse_external_groups(
        self, match: re.Match[str], uri: str
    ) -> dict[str, Any] | None:
        """Parse external dependency match groups."""
        ecosystem, package_name, version = match.groups()
        if not all([ecosystem, package_name, version]):
            return None

        return {
            "type": self,
            "ecosystem": ecosystem,
            "package_name": package_name,
            "version": version,
            "package_id": f"{self.uri_prefix}{ecosystem}/{package_name}",
            "version_id": uri,
            "uri": uri,
        }

    def _parse_internal_groups(
        self, match: re.Match[str], uri: str
    ) -> dict[str, Any] | None:
        """Parse internal dependency match groups."""
        reference_path = match.groups()[0]
        if not reference_path:
            return None

        path_parts = reference_path.split("/")
        if len(path_parts) < 2:
            return None

        return {
            "type": self,
            "reference_path": reference_path,
            "namespace": path_parts[0],
            "entity_id": "/".join(path_parts),  # Full path as entity ID
            "uri": uri,
        }

    @classmethod
    def identify_dependency_type(cls, uri: str) -> "DependencyType | None":
        """Identify the dependency type from a URI.

        Args:
            uri: Dependency URI to identify

        Returns:
            DependencyType if identified, None otherwise
        """
        for dep_type in cls:
            if dep_type.matches_uri(uri):
                return dep_type
        return None

    @classmethod
    def parse_any_dependency_uri(cls, uri: str) -> dict[str, Any] | None:
        """Parse any supported dependency URI type.

        Args:
            uri: Dependency URI to parse

        Returns:
            Dictionary with parsed components or None if invalid
        """
        dep_type = cls.identify_dependency_type(uri)
        if dep_type:
            return dep_type.parse_uri(uri)
        return None


class DependencyUriBuilder:
    """Builder for constructing dependency URIs in a type-safe way."""

    @staticmethod
    def external(ecosystem: str, package_name: str, version: str) -> str:
        """Build an external dependency URI.

        Args:
            ecosystem: Package ecosystem (pypi, npm, etc.)
            package_name: Package name
            version: Package version

        Returns:
            External dependency URI
        """
        return (
            f"{DependencyType.EXTERNAL.uri_prefix}{ecosystem}/{package_name}/{version}"
        )

    @staticmethod
    def internal(namespace: str, entity_id: str) -> str:
        """Build an internal dependency URI.

        Args:
            namespace: Entity namespace
            entity_id: Entity identifier

        Returns:
            Internal dependency URI
        """
        # If entity_id already includes namespace, use as-is
        if "/" in entity_id and entity_id.startswith(f"{namespace}/"):
            return f"{DependencyType.INTERNAL.uri_prefix}{entity_id}"
        else:
            return f"{DependencyType.INTERNAL.uri_prefix}{namespace}/{entity_id}"


# Convenience functions for common operations
def is_external_dependency(uri: str) -> bool:
    """Check if URI is an external dependency."""
    return DependencyType.EXTERNAL.matches_uri(uri)


def is_internal_dependency(uri: str) -> bool:
    """Check if URI is an internal dependency."""
    return DependencyType.INTERNAL.matches_uri(uri)


def parse_external_dependency(uri: str) -> dict[str, Any] | None:
    """Parse external dependency URI."""
    return DependencyType.EXTERNAL.parse_uri(uri)


def parse_internal_dependency(uri: str) -> dict[str, Any] | None:
    """Parse internal dependency URI."""
    return DependencyType.INTERNAL.parse_uri(uri)


def get_dependency_type(uri: str) -> DependencyType | None:
    """Get the dependency type for a URI."""
    return DependencyType.identify_dependency_type(uri)


def parse_dependency_uri(uri: str) -> dict[str, Any] | None:
    """Parse any dependency URI."""
    return DependencyType.parse_any_dependency_uri(uri)
