"""External dependency processing for knowledge graph entities.

This module handles the processing of external dependencies specified in entity
metadata into proper graph entities and relationships according to the data model
specification.

External dependency URIs follow the format defined by DependencyType.EXTERNAL:
    external://ecosystem/package_name/version

For example:
    external://pypi/requests/2.31.0
    external://npm/@types/node/18.15.0

This creates:
1. ExternalDependencyPackage entity: external://ecosystem/package_name
2. ExternalDependencyVersion entity: external://ecosystem/package_name/version
3. has_version relationship: package -> version
4. depends_on relationship: source_entity -> version
"""

from typing import Any

from ..core import (
    get_logger,
    is_external_dependency,
    parse_external_dependency,
)
from .interface import StorageInterface

logger = get_logger(__name__)


def parse_external_dependency_uri(uri: str) -> dict[str, str] | None:
    """Parse external dependency URI into components.

    Args:
        uri: External dependency URI (e.g., "external://pypi/requests/2.31.0")

    Returns:
        Dictionary with parsed components or None if invalid:
        - ecosystem: The ecosystem (pypi, npm, etc.)
        - package_name: The package name
        - version: The version string
        - package_id: Full package identifier
        - version_id: Full version identifier

    Note:
        This function is deprecated. Use parse_external_dependency from core instead.
    """
    # Use the new enum-based parser
    result = parse_external_dependency(uri)
    if not result:
        return None

    # Convert to legacy format for compatibility
    return {
        "ecosystem": result["ecosystem"],
        "package_name": result["package_name"],
        "version": result["version"],
        "package_id": result["package_id"],
        "version_id": result["version_id"],
    }


class DependencyProcessor:
    """Processes external dependencies into graph entities and relationships."""

    def __init__(self, storage: StorageInterface):
        """Initialize dependency processor.

        Args:
            storage: Storage backend to use for entity/relationship creation
        """
        self.storage = storage

    async def parse_and_validate_dependency(
        self, dependency_uri: str
    ) -> dict[str, Any] | None:
        """Parse and validate external dependency URI.

        Args:
            dependency_uri: External dependency URI to parse

        Returns:
            Parsed dependency info or None if invalid
        """
        if not is_external_dependency(dependency_uri):
            logger.debug(f"Not an external dependency: {dependency_uri}")
            return None

        parsed = parse_external_dependency(dependency_uri)
        if not parsed:
            logger.warning(f"Invalid external dependency URI: {dependency_uri}")
            return None

        return parsed

    async def create_external_dependency_package(
        self, package_info: dict[str, Any]
    ) -> str:
        """Create ExternalDependencyPackage entity.

        Args:
            package_info: Parsed package information from dependency parser

        Returns:
            Package entity ID
        """
        entity_type = "external_dependency_package"
        entity_id = package_info["package_id"]

        entity_data = {
            "ecosystem": package_info["ecosystem"],
            "package_name": package_info["package_name"],
        }

        metadata = {
            "auto_created": "true",
            "source": "dependency_processing",
        }

        logger.debug(f"Creating external dependency package: {entity_id}")

        return await self.storage.store_entity(
            entity_type, entity_id, entity_data, metadata
        )

    async def create_external_dependency_version(
        self, version_info: dict[str, Any]
    ) -> str:
        """Create ExternalDependencyVersion entity.

        Args:
            version_info: Parsed version information from dependency parser

        Returns:
            Version entity ID
        """
        entity_type = "external_dependency_version"
        entity_id = version_info["version_id"]

        entity_data = {
            "ecosystem": version_info["ecosystem"],
            "package_name": version_info["package_name"],
            "version": version_info["version"],
        }

        metadata = {
            "auto_created": "true",
            "source": "dependency_processing",
        }

        logger.debug(f"Creating external dependency version: {entity_id}")

        return await self.storage.store_entity(
            entity_type, entity_id, entity_data, metadata
        )

    async def create_has_version_relationship(
        self, package_id: str, version_id: str
    ) -> bool:
        """Create has_version relationship between package and version.

        Args:
            package_id: Package entity ID
            version_id: Version entity ID

        Returns:
            True if successful
        """
        logger.debug(f"Creating has_version relationship: {package_id} -> {version_id}")

        return await self.storage.create_relationship(
            source_entity_type="external_dependency_package",
            source_entity_id=package_id,
            relationship_type="has_version",
            target_entity_type="external_dependency_version",
            target_entity_id=version_id,
        )

    async def create_depends_on_relationship(
        self, source_entity_id: str, version_id: str
    ) -> bool:
        """Create depends_on relationship between entity and dependency version.

        Args:
            source_entity_id: Source entity ID (e.g., repository)
            version_id: Dependency version entity ID

        Returns:
            True if successful
        """
        logger.debug(
            f"Creating depends_on relationship: {source_entity_id} -> {version_id}"
        )

        return await self.storage.create_relationship(
            source_entity_type="repository",  # TODO: Make this configurable
            source_entity_id=source_entity_id,
            relationship_type="depends_on",
            target_entity_type="external_dependency_version",
            target_entity_id=version_id,
        )

    async def create_dependency_entities(
        self, dependency_uri: str
    ) -> dict[str, str] | None:
        """Create both package and version entities for a dependency.

        Args:
            dependency_uri: External dependency URI

        Returns:
            Dictionary with package_id and version_id, or None if failed
        """
        parsed = await self.parse_and_validate_dependency(dependency_uri)
        if not parsed:
            return None

        try:
            # Create package entity (if it doesn't exist)
            package_id = await self.create_external_dependency_package(parsed)

            # Create version entity (if it doesn't exist)
            version_id = await self.create_external_dependency_version(parsed)

            # Create has_version relationship
            await self.create_has_version_relationship(package_id, version_id)

            return {
                "package_id": package_id,
                "version_id": version_id,
            }

        except Exception as e:
            logger.error(
                f"Failed to create dependency entities for {dependency_uri}: {e}"
            )
            return None

    async def process_dependencies(
        self, source_entity_id: str, dependencies: list[str]
    ) -> bool:
        """Process all dependencies for an entity.

        Args:
            source_entity_id: Entity ID that has the dependencies
            dependencies: List of dependency URIs

        Returns:
            True if all dependencies processed successfully
        """
        if not dependencies:
            return True

        logger.info(
            f"Processing {len(dependencies)} dependencies for {source_entity_id}"
        )

        # Filter to only external dependencies
        external_dependencies = [
            dep for dep in dependencies if is_external_dependency(dep)
        ]

        if len(external_dependencies) != len(dependencies):
            skipped_count = len(dependencies) - len(external_dependencies)
            logger.debug(f"Skipping {skipped_count} non-external dependencies")

        success_count = 0

        for dependency_uri in external_dependencies:
            try:
                # Create dependency entities and relationships
                result = await self.create_dependency_entities(dependency_uri)
                if result:
                    # Create depends_on relationship
                    await self.create_depends_on_relationship(
                        source_entity_id, result["version_id"]
                    )
                    success_count += 1
                    logger.debug(f"Successfully processed dependency: {dependency_uri}")
                else:
                    logger.warning(f"Failed to process dependency: {dependency_uri}")

            except Exception as e:
                logger.error(f"Error processing dependency {dependency_uri}: {e}")

        logger.info(
            f"Processed {success_count}/{len(external_dependencies)} external dependencies successfully"
        )
        return success_count == len(external_dependencies)
