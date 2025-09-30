"""Generic relationship processor for managing entity relationships based on schema definitions.

This module provides a schema-driven approach to relationship management that:
1. Reads relationship definitions from entity schemas
2. Replaces existing relationships with new ones from YAML
3. Removes relationships not present in YAML
4. Works with any entity type and relationship defined in schema
"""

from ..core import EntitySchema, RelationshipDefinition, get_logger
from .interface import StorageInterface

logger = get_logger(__name__)


class GenericRelationshipProcessor:
    """Generic processor for managing entity relationships based on schema definitions.

    This processor replaces the hard-coded dependency-specific logic with a
    dynamic system that works with any entity type and relationship configuration.
    """

    def __init__(self, storage: StorageInterface, schemas: dict[str, EntitySchema]):
        """Initialize the processor with storage and schema definitions.

        Args:
            storage: Storage backend interface
            schemas: Dictionary mapping entity types to their schemas
        """
        self.storage = storage
        self.schemas = schemas

    async def replace_entity_relationships(
        self, entity_type: str, entity_id: str, yaml_relationships: dict[str, list[str]]
    ) -> bool:
        """Replace all relationships for an entity based on YAML definition.

        This method implements proper relationship replacement:
        1. For each relationship type defined in schema:
           - Remove all existing relationships of that type
           - Add new relationships from YAML (if any)
        2. This ensures relationships not in YAML are removed
        3. This ensures relationships in YAML are added

        Args:
            entity_type: Type of the entity (e.g., "repository")
            entity_id: ID of the entity
            yaml_relationships: Relationships from YAML (relationship_name -> target_ids)

        Returns:
            True if successful

        Raises:
            ValueError: If no schema found for entity type
        """
        schema = self.schemas.get(entity_type)
        if not schema:
            raise ValueError(f"No schema found for entity type: {entity_type}")

        logger.debug(f"Replacing relationships for {entity_type}/{entity_id}")

        success = True

        # Process each relationship type defined in the schema
        for relationship in schema.relationships:
            relationship_name = relationship.name
            yaml_targets = yaml_relationships.get(relationship_name, [])

            logger.debug(
                f"Processing {relationship_name} relationship: "
                f"{len(yaml_targets)} targets in YAML"
            )

            try:
                # Step 1: Remove all existing relationships of this type
                removed_count = await self.storage.remove_relationships_by_type(
                    source_entity_type=entity_type,
                    source_entity_id=entity_id,
                    relationship_type=relationship_name,
                )

                if removed_count > 0:
                    logger.debug(
                        f"Removed {removed_count} existing {relationship_name} relationships"
                    )

                # Step 2: Add new relationships from YAML
                created_count = 0
                for target_id in yaml_targets:
                    target_entity_type = self._determine_target_entity_type(
                        relationship, target_id
                    )

                    relationship_success = await self.storage.create_relationship(
                        source_entity_type=entity_type,
                        source_entity_id=entity_id,
                        relationship_type=relationship_name,
                        target_entity_type=target_entity_type,
                        target_entity_id=target_id,
                    )

                    if relationship_success:
                        created_count += 1
                        logger.debug(
                            f"Created {relationship_name} relationship: "
                            f"{entity_id} -> {target_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to create {relationship_name} relationship: "
                            f"{entity_id} -> {target_id}"
                        )
                        success = False

                if created_count > 0:
                    logger.debug(
                        f"Created {created_count} new {relationship_name} relationships"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to process {relationship_name} relationships for {entity_id}: {e}"
                )
                success = False

        if success:
            logger.info(f"Successfully replaced all relationships for {entity_id}")
        else:
            logger.warning(f"Partial success replacing relationships for {entity_id}")

        return success

    def _determine_target_entity_type(
        self, relationship: RelationshipDefinition, target_id: str
    ) -> str:
        """Determine target entity type based on relationship definition and target ID.

        This method uses heuristics to determine the correct target entity type:
        1. For external dependencies: parse URI to determine if it's package or version
        2. For internal dependencies: use the relationship's target types
        3. For other relationships: use first target type from schema

        Args:
            relationship: Relationship definition from schema
            target_id: Target entity ID

        Returns:
            Target entity type string
        """
        # Handle external dependency URIs
        if target_id.startswith("external://"):
            return self._determine_external_dependency_type(target_id)

        # Handle internal dependency URIs
        if target_id.startswith("internal://"):
            return self._determine_internal_dependency_type(target_id, relationship)

        # For other relationships, use the first target type from schema
        if relationship.target_types:
            return relationship.target_types[0]

        # Fallback
        logger.warning(
            f"Could not determine target type for {target_id}, using 'unknown'"
        )
        return "unknown"

    def _determine_external_dependency_type(self, target_id: str) -> str:
        """Determine if external dependency is package or version.

        Args:
            target_id: External dependency URI

        Returns:
            Either "external_dependency_package" or "external_dependency_version"
        """
        # Count the number of path segments after external://
        # external://ecosystem/package = 2 segments (package)
        # external://ecosystem/package/version = 3 segments (version)

        uri_path = target_id[11:]  # Remove "external://"
        segments = uri_path.split("/")

        if len(segments) >= 3:
            return "external_dependency_version"
        else:
            return "external_dependency_package"

    def _determine_internal_dependency_type(
        self,
        target_id: str,  # noqa: ARG002
        relationship: RelationshipDefinition,
    ) -> str:
        """Determine target type for internal dependency.

        Args:
            target_id: Internal dependency URI
            relationship: Relationship definition

        Returns:
            Target entity type
        """
        # For internal dependencies, use the first target type that makes sense
        # Most internal dependencies point to repositories

        if "repository" in relationship.target_types:
            return "repository"
        elif relationship.target_types:
            return relationship.target_types[0]
        else:
            return "repository"  # Default assumption


class RelationshipProcessorFactory:
    """Factory for creating relationship processors with loaded schemas."""

    @staticmethod
    def create_processor(
        storage: StorageInterface, schemas: dict[str, EntitySchema]
    ) -> GenericRelationshipProcessor:
        """Create a relationship processor with the given storage and schemas.

        Args:
            storage: Storage backend interface
            schemas: Entity schemas dictionary

        Returns:
            Configured GenericRelationshipProcessor
        """
        return GenericRelationshipProcessor(storage, schemas)
