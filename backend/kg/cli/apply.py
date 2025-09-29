"""CLI apply command implementation.

This module implements the `kg apply` command according to cli/apply-spec.md,
providing full validation pipeline (Layers 1-5) including reference validation,
storage operations, dry-run functionality, and comprehensive error handling.
"""

import asyncio
import contextlib
import json
from pathlib import Path
import sys
import time
import traceback
from typing import Any

from rich.console import Console
from rich.table import Table
import rich_click as click
import yaml

from ..api.config import config
from ..core import FileSchemaLoader
from ..storage import (
    DryRunResult,
    create_storage,
)
from ..validation import KnowledgeGraphValidator

# Create console for rich formatting
console = Console()


def _should_use_rich_formatting(force_colors: bool = False) -> bool:
    """Determine if we should use rich formatting based on environment."""
    return force_colors or console.is_terminal


def _format_time_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    SECONDS_PER_MINUTE = 60

    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < SECONDS_PER_MINUTE:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // SECONDS_PER_MINUTE)
        remaining_seconds = seconds % SECONDS_PER_MINUTE
        return f"{minutes}m {remaining_seconds:.1f}s"


def _extract_entities_from_yaml(parsed_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract entities from parsed YAML data for storage operations.

    Separates entity metadata from relationships to maintain architectural
    consistency with the schema definitions.
    """
    entities = []
    namespace = parsed_data.get("namespace", "")

    entity_section = parsed_data.get("entity", {})
    for entity_type, entity_list in entity_section.items():
        if isinstance(entity_list, list):
            for entity_dict in entity_list:
                if isinstance(entity_dict, dict):
                    for entity_name, entity_data in entity_dict.items():
                        if isinstance(entity_data, dict):
                            # Create entity ID in format: namespace/entity-name
                            entity_id = (
                                f"{namespace}/{entity_name}"
                                if namespace
                                else entity_name
                            )

                            # Separate metadata from relationships
                            metadata = {}
                            relationships = {}

                            for key, value in entity_data.items():
                                if key == "relationships":
                                    # Handle nested relationships structure
                                    if isinstance(value, dict):
                                        relationships.update(value)
                                else:
                                    # Regular metadata field
                                    metadata[key] = value

                            # For backward compatibility, also flatten relationship data
                            # into metadata so existing dependency processing works
                            if relationships:
                                metadata.update(relationships)

                            entities.append(
                                {
                                    "entity_type": entity_type,
                                    "entity_id": entity_id,
                                    "metadata": metadata,
                                    "relationships": relationships,
                                    "system_metadata": {
                                        "namespace": namespace,
                                        "source_name": entity_name,
                                    },
                                }
                            )

    return entities


def _output_dry_run_table_format(  # noqa: PLR0912, PLR0915
    dry_run_result: DryRunResult,
    file_path: str,
    verbose: bool,
    validation_time_ms: float,
    force_colors: bool = False,
) -> None:
    """Output dry-run results in table format."""
    if _should_use_rich_formatting(force_colors):
        console.print("🔍 [bold blue]Dry-run results[/bold blue]")
        console.print()

        # File info
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_row("[bold]File:[/bold]", f"[cyan]{file_path}[/cyan]")
        info_table.add_row(
            "[bold]Mode:[/bold]", "[yellow]Dry-run (no changes made)[/yellow]"
        )

        if verbose:
            info_table.add_row(
                "[bold]Validation time:[/bold]",
                f"[dim]{validation_time_ms:.1f}ms[/dim]",
            )

        console.print(info_table)
        console.print()

        # Operations summary
        if dry_run_result.would_create:
            console.print("[bold green]Would create:[/bold green]")
            for op in dry_run_result.would_create:
                console.print(
                    f"  📁 [green]{op.entity_type}[/green]: [cyan]{op.entity_id}[/cyan]"
                )
            console.print()

        if dry_run_result.would_update:
            console.print("[bold yellow]Would update:[/bold yellow]")
            for op in dry_run_result.would_update:
                console.print(
                    f"  📝 [yellow]{op.entity_type}[/yellow]: "
                    f"[cyan]{op.entity_id}[/cyan]"
                )
                if verbose and op.changes:
                    for field, value in op.changes.items():
                        console.print(
                            f"     - [dim]{field}[/dim]: [green]{value}[/green]"
                        )
            console.print()

        if dry_run_result.would_delete:
            console.print("[bold red]Would delete:[/bold red]")
            for op in dry_run_result.would_delete:
                console.print(
                    f"  🗑️ [red]{op.entity_type}[/red]: [cyan]{op.entity_id}[/cyan]"
                )
            console.print()

        # Validation issues
        if dry_run_result.validation_issues:
            errors = [
                issue
                for issue in dry_run_result.validation_issues
                if issue.severity == "error"
            ]
            warnings = [
                issue
                for issue in dry_run_result.validation_issues
                if issue.severity == "warning"
            ]

            if errors:
                console.print("[bold red]Errors found:[/bold red]")
                for issue in errors:
                    console.print(f"  ❌ [red]{issue.message}[/red]")
                    if issue.suggestion:
                        console.print(f"     💡 [italic]{issue.suggestion}[/italic]")
                console.print()

            if warnings:
                console.print("[bold yellow]Warnings:[/bold yellow]")
                for issue in warnings:
                    console.print(f"  ⚠️ [yellow]{issue.message}[/yellow]")
                    if issue.suggestion:
                        console.print(f"     💡 [italic]{issue.suggestion}[/italic]")
                console.print()

        # Summary
        summary = dry_run_result.summary
        create_count = summary.get("create_count", 0)
        update_count = summary.get("update_count", 0)
        delete_count = summary.get("delete_count", 0)

        console.print(
            f"[bold]Summary:[/bold] {create_count} create, "
            f"{update_count} update, {delete_count} delete"
        )

    else:
        # Plain text output for CI/non-interactive
        click.echo("🔍 Dry-run results")
        click.echo()
        click.echo(f"File: {file_path}")
        click.echo("Mode: Dry-run (no changes made)")
        click.echo()

        if dry_run_result.would_create:
            click.echo("Would create:")
            for op in dry_run_result.would_create:
                click.echo(f"  📁 {op.entity_type}: {op.entity_id}")

        if dry_run_result.would_update:
            click.echo("Would update:")
            for op in dry_run_result.would_update:
                click.echo(f"  📝 {op.entity_type}: {op.entity_id}")

        if dry_run_result.would_delete:
            click.echo("Would delete:")
            for op in dry_run_result.would_delete:
                click.echo(f"  🗑️ {op.entity_type}: {op.entity_id}")

        if dry_run_result.validation_issues:
            click.echo("Issues:")
            for issue in dry_run_result.validation_issues:
                click.echo(f"  {issue.severity.upper()}: {issue.message}")

        summary = dry_run_result.summary
        create_count = summary.get("create_count", 0)
        update_count = summary.get("update_count", 0)
        delete_count = summary.get("delete_count", 0)
        click.echo(
            f"Summary: {create_count} create, {update_count} update, "
            f"{delete_count} delete"
        )


def _output_apply_success_table_format(
    file_path: str,
    entities_created: int,
    entities_updated: int,
    entities_applied: int,
    validation_time_ms: float,
    storage_time_ms: float,
    verbose: bool,
    force_colors: bool = False,
) -> None:
    """Output successful apply results in table format."""
    total_time_ms = validation_time_ms + storage_time_ms

    if _should_use_rich_formatting(force_colors):
        console.print("✅ [bold green]Apply successful[/bold green]")
        console.print()

        # File and operation info
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_row("[bold]File:[/bold]", f"[cyan]{file_path}[/cyan]")
        info_table.add_row("[bold]Server:[/bold]", "[yellow]local storage[/yellow]")
        info_table.add_row(
            "[bold]Applied:[/bold]",
            f"[green]{entities_applied} entities "
            f"({entities_created} created, {entities_updated} updated)[/green]",
        )

        if verbose:
            info_table.add_row(
                "[bold]Validation time:[/bold]",
                f"[dim]{validation_time_ms:.1f}ms[/dim]",
            )
            info_table.add_row(
                "[bold]Storage time:[/bold]", f"[dim]{storage_time_ms:.1f}ms[/dim]"
            )
            info_table.add_row(
                "[bold]Total time:[/bold]",
                f"[dim]{_format_time_duration(total_time_ms / 1000)}[/dim]",
            )

        console.print(info_table)
        console.print()

        # Summary
        console.print("[bold]Summary:[/bold]")
        console.print("  ✅ Schema validation passed")
        console.print("  ✅ Reference validation passed")
        if entities_created > 0:
            console.print(f"  ✅ {entities_created} entities created")
        if entities_updated > 0:
            console.print(f"  ✅ {entities_updated} entities updated")

    else:
        # Plain text for CI
        click.echo("✅ Apply successful")
        click.echo()
        click.echo(f"File: {file_path}")
        click.echo("Server: local storage")
        click.echo(
            f"Applied: {entities_applied} entities "
            f"({entities_created} created, {entities_updated} updated)"
        )

        if verbose:
            click.echo(f"Time: {_format_time_duration(total_time_ms / 1000)}")


def _output_json_format(result_data: dict[str, Any]) -> None:
    """Output results in JSON format."""
    click.echo(json.dumps(result_data, indent=2))


def _output_compact_format(status: str, file_path: str, **kwargs: Any) -> None:
    """Output results in compact format."""
    if status == "applied":
        entities_applied = kwargs.get("entities_applied", 0)
        entities_created = kwargs.get("entities_created", 0)
        entities_updated = kwargs.get("entities_updated", 0)
        total_time_ms = kwargs.get("total_time_ms", 0)

        click.echo(
            f"✅ {file_path}: APPLIED (entities={entities_applied}, "
            f"created={entities_created}, updated={entities_updated}, "
            f"time={_format_time_duration(total_time_ms / 1000)})"
        )

    elif status == "dry_run":
        create_count = kwargs.get("create_count", 0)
        update_count = kwargs.get("update_count", 0)
        delete_count = kwargs.get("delete_count", 0)

        click.echo(
            f"🔍 {file_path}: DRY-RUN (create={create_count}, "
            f"update={update_count}, delete={delete_count})"
        )

    elif status == "failed":
        error_count = kwargs.get("error_count", 0)
        click.echo(f"❌ {file_path}: FAILED (errors={error_count})")


async def _apply_implementation(  # noqa: PLR0912, PLR0915
    file: str,
    server: str | None,
    dry_run: bool,
    force: bool,
    timeout: int,
    format: str,
    verbose: bool,
    force_colors: bool = False,
) -> None:
    """Implementation of the apply command."""
    file_path = Path(file)
    start_time = time.time()

    try:
        # Check if file exists
        if not file_path.exists():
            error_data = {
                "status": "error",
                "error_type": "file_not_found",
                "message": f"File not found: {file}",
                "file": str(file_path),
            }

            if format == "json":
                _output_json_format(error_data)
            else:
                click.echo(f"❌ File not found: {file}")
                if verbose:
                    click.echo(f"Checked path: {file_path.absolute()}")
            sys.exit(2)

        # Read file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            error_data = {
                "status": "error",
                "error_type": "file_read_error",
                "message": f"Cannot read file: {e}",
                "file": str(file_path),
            }

            if format == "json":
                _output_json_format(error_data)
            else:
                click.echo(f"❌ Cannot read file: {e}")
            sys.exit(2)

        # Parse YAML for entity extraction
        try:
            parsed_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            error_data = {
                "status": "error",
                "error_type": "yaml_parse_error",
                "message": f"Invalid YAML: {e}",
                "file": str(file_path),
            }

            if format == "json":
                _output_json_format(error_data)
            else:
                click.echo(f"❌ Invalid YAML: {e}")
            sys.exit(1)

        # Load schemas
        try:
            backend_dir = Path(__file__).parent.parent.parent
            schema_dir = backend_dir / "schemas"

            if not schema_dir.exists():
                raise FileNotFoundError(f"Schema directory not found: {schema_dir}")

            schema_loader = FileSchemaLoader(str(schema_dir))
            schemas = await schema_loader.load_schemas()
        except Exception as e:
            error_data = {
                "status": "error",
                "error_type": "schema_load_error",
                "message": f"Cannot load schemas: {e}",
                "file": str(file_path),
            }

            if format == "json":
                _output_json_format(error_data)
            else:
                click.echo(f"❌ Cannot load schemas: {e}")
            sys.exit(4)

        # Create and connect to storage (local or remote)
        try:
            if server:
                # TODO: Implement remote server mode
                raise NotImplementedError("Remote server mode not yet implemented")
            else:
                # Local storage mode
                storage = create_storage(config.storage)
                if storage is None:
                    raise RuntimeError("Failed to create storage backend")

                await storage.connect()

                # Load schemas into storage if not already loaded
                with contextlib.suppress(Exception):
                    await storage.load_schemas(str(schema_dir))

        except Exception as e:
            error_data = {
                "status": "error",
                "error_type": "storage_connection_error",
                "message": f"Storage connection failed: {e}",
                "file": str(file_path),
            }

            if format == "json":
                _output_json_format(error_data)
            else:
                click.echo(f"❌ Storage connection failed: {e}")
                if verbose:
                    click.echo("Suggestions:")
                    click.echo("  • Check if storage backend is running")
                    click.echo("  • For local storage: run 'docker compose up -d'")
            sys.exit(3)

        # Run full validation pipeline (Layers 1-5)
        validation_start = time.time()
        try:
            # Create validator with storage for reference validation (Layer 5)
            validator = KnowledgeGraphValidator(schemas, storage=storage)
            validation_result = await validator.validate(content)

            if not validation_result.is_valid:
                validation_time_ms = (time.time() - validation_start) * 1000

                validation_error_data = {
                    "status": "failed",
                    "error_type": "validation_failed",
                    "file": str(file_path),
                    "error_count": validation_result.error_count,
                    "warning_count": validation_result.warning_count,
                    "errors": [
                        {
                            "type": error.type,
                            "message": error.message,
                            "field": error.field,
                            "entity": error.entity,
                            "line": error.line,
                            "column": error.column,
                            "help": error.help,
                        }
                        for error in validation_result.errors
                    ],
                    "validation_time_ms": round(validation_time_ms, 1),
                }

                if format == "json":
                    _output_json_format(validation_error_data)
                else:
                    click.echo("❌ Apply failed - validation errors")
                    click.echo()
                    click.echo(f"File: {file_path}")
                    click.echo(f"Errors found: {validation_result.error_count}")
                    click.echo()

                    for _i, error in enumerate(validation_result.errors, 1):
                        if error.entity and error.field:
                            click.echo(
                                f"❌ {error.type} in '{error.entity}.{error.field}': "
                                f"{error.message}"
                            )
                        elif error.entity:
                            click.echo(
                                f"❌ {error.type} in '{error.entity}': {error.message}"
                            )
                        else:
                            click.echo(f"❌ {error.type}: {error.message}")

                        if error.help:
                            click.echo(f"   💡 Help: {error.help}")

                        if error.line is not None:
                            click.echo(
                                f"   📍 Line {error.line}, Column {error.column or 1}"
                            )

                    click.echo()
                    click.echo("No changes were made to storage.")

                sys.exit(1)

        except Exception as e:
            error_data = {
                "status": "error",
                "error_type": "validation_error",
                "message": f"Validation failed: {e}",
                "file": str(file_path),
            }

            if format == "json":
                _output_json_format(error_data)
            else:
                click.echo(f"❌ Validation failed: {e}")
            sys.exit(4)

        validation_time_ms = (time.time() - validation_start) * 1000

        # Extract entities for storage operations
        entities = _extract_entities_from_yaml(parsed_data)

        if dry_run:
            # Dry-run mode: simulate operations
            try:
                dry_run_result = await storage.dry_run_apply(entities)

                if format == "json":
                    result_data = {
                        "status": "dry_run",
                        "file": str(file_path),
                        "would_create": [
                            {
                                "entity_type": op.entity_type,
                                "entity_id": op.entity_id,
                                "changes": op.changes,
                            }
                            for op in dry_run_result.would_create
                        ],
                        "would_update": [
                            {
                                "entity_type": op.entity_type,
                                "entity_id": op.entity_id,
                                "changes": op.changes,
                            }
                            for op in dry_run_result.would_update
                        ],
                        "would_delete": [
                            {
                                "entity_type": op.entity_type,
                                "entity_id": op.entity_id,
                            }
                            for op in dry_run_result.would_delete
                        ],
                        "validation_issues": [
                            {
                                "severity": issue.severity,
                                "entity_type": issue.entity_type,
                                "entity_id": issue.entity_id,
                                "message": issue.message,
                                "suggestion": issue.suggestion,
                            }
                            for issue in dry_run_result.validation_issues
                        ],
                        "summary": dry_run_result.summary,
                        "validation_time_ms": round(validation_time_ms, 1),
                    }
                    _output_json_format(result_data)

                elif format == "compact":
                    _output_compact_format(
                        "dry_run",
                        str(file_path),
                        create_count=dry_run_result.summary.get("create_count", 0),
                        update_count=dry_run_result.summary.get("update_count", 0),
                        delete_count=dry_run_result.summary.get("delete_count", 0),
                    )

                else:
                    _output_dry_run_table_format(
                        dry_run_result,
                        str(file_path),
                        verbose,
                        validation_time_ms,
                        force_colors,
                    )

                # Check if dry-run found errors
                if dry_run_result.has_errors:
                    sys.exit(1)
                else:
                    sys.exit(0)

            except Exception as e:
                error_data = {
                    "status": "error",
                    "error_type": "dry_run_error",
                    "message": f"Dry-run simulation failed: {e}",
                    "file": str(file_path),
                }

                if format == "json":
                    _output_json_format(error_data)
                else:
                    click.echo(f"❌ Dry-run simulation failed: {e}")
                sys.exit(3)

        else:
            # Actual apply mode: store entities
            storage_start = time.time()
            entities_created = 0
            entities_updated = 0

            try:
                for entity in entities:
                    entity_type = entity["entity_type"]
                    entity_id = entity["entity_id"]
                    metadata = entity["metadata"]
                    system_metadata = entity["system_metadata"]

                    # Check if entity exists to determine create vs update
                    existing_entity = await storage.get_entity(entity_type, entity_id)

                    # Store entity
                    await storage.store_entity(
                        entity_type, entity_id, metadata, system_metadata
                    )

                    if existing_entity:
                        entities_updated += 1
                    else:
                        entities_created += 1

                storage_time_ms = (time.time() - storage_start) * 1000
                entities_applied = entities_created + entities_updated
                total_time_ms = validation_time_ms + storage_time_ms

                if format == "json":
                    result_data = {
                        "status": "applied",
                        "file": str(file_path),
                        "server": "local",
                        "summary": {
                            "entities_applied": entities_applied,
                            "entities_created": entities_created,
                            "entities_updated": entities_updated,
                            "entities_deleted": 0,
                            "validation_time_ms": round(validation_time_ms, 1),
                            "storage_time_ms": round(storage_time_ms, 1),
                        },
                        "operations": [
                            {
                                "entity_type": entity["entity_type"],
                                "entity_id": entity["entity_id"],
                                "operation": "created"
                                if i < entities_created
                                else "updated",
                            }
                            for i, entity in enumerate(entities)
                        ],
                    }
                    _output_json_format(result_data)

                elif format == "compact":
                    _output_compact_format(
                        "applied",
                        str(file_path),
                        entities_applied=entities_applied,
                        entities_created=entities_created,
                        entities_updated=entities_updated,
                        total_time_ms=total_time_ms,
                    )

                else:
                    _output_apply_success_table_format(
                        str(file_path),
                        entities_created,
                        entities_updated,
                        entities_applied,
                        validation_time_ms,
                        storage_time_ms,
                        verbose,
                        force_colors,
                    )

                sys.exit(0)

            except Exception as e:
                error_data = {
                    "status": "error",
                    "error_type": "storage_operation_error",
                    "message": f"Storage operation failed: {e}",
                    "file": str(file_path),
                }

                if format == "json":
                    _output_json_format(error_data)
                else:
                    click.echo(f"❌ Storage operation failed: {e}")
                sys.exit(3)

    except KeyboardInterrupt:
        error_data = {
            "status": "error",
            "error_type": "interrupted",
            "message": "Apply operation interrupted by user",
            "file": str(file_path) if "file_path" in locals() else file,
        }

        if format == "json":
            _output_json_format(error_data)
        else:
            click.echo("\n❌ Apply operation interrupted")
        sys.exit(4)

    except Exception as e:
        error_data = {
            "status": "error",
            "error_type": "internal_error",
            "message": f"Internal error: {e}",
            "file": str(file_path) if "file_path" in locals() else file,
        }

        if format == "json":
            _output_json_format(error_data)
        else:
            click.echo(f"❌ Internal error: {e}")
            if verbose:
                click.echo("\nFull traceback:")
                click.echo(traceback.format_exc())
        sys.exit(4)


@click.command("apply")
@click.argument(
    "file",
    type=click.Path(exists=False),
    required=False,
    default="knowledge-graph.yaml",
    help="**Path to YAML file to apply** (default: knowledge-graph.yaml)",
)
@click.option(
    "--server",
    type=str,
    help="🌐 **Apply to remote server** - HTTP/HTTPS URL to server API endpoint",
    metavar="URL",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="🔍 **Simulate operations** without making changes - shows what would be "
    "applied",
)
@click.option(
    "--force",
    is_flag=True,
    help="⚡ **Skip confirmations** - apply changes without interactive prompts",
)
@click.option(
    "--timeout",
    type=click.IntRange(1, 300),
    default=30,
    help="⏱️ **Timeout for operations** (1-300 seconds)",
    show_default=True,
)
@click.option(
    "--format",
    type=click.Choice(["table", "compact", "json", "yaml"]),
    default="table",
    help="📋 **Output format** for apply results",
    show_default=True,
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="🔍 **Show detailed information** - timing, storage details, operation "
    "progress",
)
@click.option(
    "--force-colors",
    is_flag=True,
    help="🎨 **Force colored output** - useful for testing rich formatting",
    hidden=True,
)
def apply_command(
    file: str,
    server: str | None,
    dry_run: bool,
    force: bool,
    timeout: int,
    format: str,
    verbose: bool,
    force_colors: bool,
) -> None:
    """🚀 **Apply knowledge graph YAML file to storage**

    Applies your knowledge graph file to storage backend with full validation.
    Performs complete 5-layer validation including reference checking.

    **Examples:**

    ```bash
    kg apply                                    # Apply knowledge-graph.yaml to local
                                            # storage
    kg apply my-graph.yaml                      # Apply specific file
    kg apply --dry-run                          # Show what would be applied
    kg apply --server=http://localhost:8000     # Apply to remote server
    kg apply --format json                      # JSON output
    kg apply --verbose                          # Detailed information
    ```

    **Exit Codes:**
    - `0`: Apply successful ✅
    - `1`: Validation failed ❌
    - `2`: File not found or invalid arguments 📁⚠️
    - `3`: Storage connection/operation failed 💾⚠️
    - `4`: Internal error 💥
    """
    asyncio.run(
        _apply_implementation(
            file, server, dry_run, force, timeout, format, verbose, force_colors
        )
    )
