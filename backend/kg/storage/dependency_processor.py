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
    EntitySchema,
    RelationshipTypes,
    get_logger,
    is_external_dependency,
    parse_external_dependency,
)
from .interface import StorageInterface
from .relationship_processor import RelationshipProcessorFactory

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
    """Processes external dependencies into graph entities and relationships.

    This processor now uses generic relationship management based on schema
    definitions instead of hard-coded relationship types.
    """

    def __init__(self, storage: StorageInterface, schemas: dict[str, EntitySchema]):
        """Initialize dependency processor.

        Args:
            storage: Storage backend to use for entity/relationship creation
            schemas: Entity schemas for relationship definitions
        """
        self.storage = storage
        self.schemas = schemas
        self.relationship_processor = RelationshipProcessorFactory.create_processor(
            storage, schemas
        )

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

            return {
                "package_id": package_id,
                "version_id": version_id,
            }

        except Exception as e:
            logger.error(
                f"Failed to create dependency entities for {dependency_uri}: {e}"
            )
            return None

    async def process_entity_relationships(  # noqa: PLR0912
        self, entity_type: str, entity_id: str, yaml_relationships: dict[str, list[str]]
    ) -> bool:
        """Process all relationships for an entity with special handling for depends_on.

        Args:
            entity_type: Type of the entity (e.g., "repository")
            entity_id: Entity ID to update relationships for
            yaml_relationships: Relationships from YAML (relationship_name -> target_ids)

        Returns:
            True if all relationships processed successfully
        """
        logger.info(
            f"Processing relationships for {entity_type}/{entity_id}: {list(yaml_relationships.keys())}"
        )

        try:
            # Special handling for depends_on relationships
            depends_on_targets = yaml_relationships.get(
                RelationshipTypes.DEPENDS_ON, []
            )
            if depends_on_targets:
                logger.debug(
                    f"Processing {len(depends_on_targets)} {RelationshipTypes.DEPENDS_ON} relationships with entity creation"
                )

                # Create external dependency entities and has_version relationships
                for target_id in depends_on_targets:
                    if is_external_dependency(target_id):
                        result = await self.create_dependency_entities(target_id)
                        if result:
                            # Create has_version relationship between package and version
                            await self.storage.create_relationship(
                                source_entity_type="external_dependency_package",
                                source_entity_id=result["package_id"],
                                relationship_type=RelationshipTypes.HAS_VERSION,
                                target_entity_type="external_dependency_version",
                                target_entity_id=result["version_id"],
                            )
                            logger.debug(
                                f"Created {RelationshipTypes.HAS_VERSION} relationship: {result['package_id']} -> {result['version_id']}"
                            )
                        else:
                            logger.warning(
                                f"Failed to create dependency entities for {target_id}"
                            )

            # Handle other external dependency relationships (non-depends_on)
            for relationship_name, target_ids in yaml_relationships.items():
                if (
                    relationship_name != RelationshipTypes.DEPENDS_ON
                ):  # Skip depends_on, handled above
                    for target_id in target_ids:
                        if is_external_dependency(target_id):
                            result = await self.create_dependency_entities(target_id)
                            if not result:
                                logger.warning(
                                    f"Failed to create dependency entities for {target_id}"
                                )

            # Use generic relationship processor to replace all relationships
            success = await self.relationship_processor.replace_entity_relationships(
                entity_type, entity_id, yaml_relationships
            )

            if success:
                logger.info(f"Successfully processed all relationships for {entity_id}")
            else:
                logger.warning(
                    f"Partial success processing relationships for {entity_id}"
                )

            return success

        except Exception as e:
            logger.error(f"Failed to process relationships for {entity_id}: {e}")
            return False
