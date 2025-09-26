"""CLI validation command implementation.

This module implements the `kg validate` command according to cli/validation-spec.md,
providing comprehensive YAML validation with multiple output formats and detailed
error reporting.
"""

import asyncio
from dataclasses import replace
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

from ..core import FileSchemaLoader
from ..validation import KnowledgeGraphValidator
from ..validation.errors import ValidationError

# Create console for rich formatting - auto-detects if we're in interactive environment
console = Console()


def _should_use_rich_formatting(force_colors: bool = False) -> bool:
    """Determine if we should use rich formatting based on environment."""
    return force_colors or console.is_terminal


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _count_dependencies(data: dict[str, Any]) -> int:
    """Count total dependencies in the YAML data."""
    count = 0
    entities = data.get("entity", {})

    for _entity_type, entity_list in entities.items():
        if isinstance(entity_list, list):
            for entity_dict in entity_list:
                if isinstance(entity_dict, dict):
                    for _entity_name, entity_data in entity_dict.items():
                        if isinstance(entity_data, dict):
                            depends_on = entity_data.get("depends_on", [])
                            if isinstance(depends_on, list):
                                count += len(depends_on)

    return count


def _output_table_format(  # noqa: PLR0912, PLR0915
    result: Any,
    file_path: str,
    verbose: bool,
    parse_time_ms: float,
    file_size: int,
    dependency_count: int,
    schema_version: str | None,
    namespace: str | None,
    force_colors: bool = False,
) -> None:
    """Output validation result in table format."""
    if result.is_valid:
        # Success output with rich formatting for interactive terminals
        if _should_use_rich_formatting(force_colors):
            console.print("✅ [bold green]Validation successful[/bold green]")
            console.print()

            # Create info table for better readability
            info_table = Table(show_header=False, box=None, padding=(0, 1))
            info_table.add_row("[bold]File:[/bold]", f"[cyan]{file_path}[/cyan]")
            info_table.add_row(
                "[bold]Schema version:[/bold]",
                f"[yellow]{schema_version or 'Unknown'}[/yellow]",
            )
            info_table.add_row(
                "[bold]Namespace:[/bold]",
                f"[magenta]{namespace or 'Unknown'}[/magenta]",
            )

            if verbose:
                info_table.add_row(
                    "[bold]File size:[/bold]",
                    f"[dim]{_format_file_size(file_size)}[/dim]",
                )
                info_table.add_row(
                    "[bold]Parse time:[/bold]", f"[dim]{parse_time_ms:.1f}ms[/dim]"
                )
                info_table.add_row(
                    "[bold]Dependencies:[/bold]", f"[dim]{dependency_count}[/dim]"
                )

            console.print(info_table)
        else:
            # Plain text for non-interactive (CI)
            click.echo("✅ Validation successful")
            click.echo()
            click.echo(f"File: {file_path}")
            click.echo(f"Schema version: {schema_version or 'Unknown'}")
            click.echo(f"Namespace: {namespace or 'Unknown'}")
            if verbose:
                click.echo(f"File size: {_format_file_size(file_size)}")
                click.echo(f"Parsed in: {parse_time_ms:.1f}ms")
                click.echo(f"Dependencies: {dependency_count}")
    elif _should_use_rich_formatting(force_colors):
        console.print("❌ [bold red]Validation failed[/bold red]")
        console.print()

        # File info
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_row("[bold]File:[/bold]", f"[cyan]{file_path}[/cyan]")
        info_table.add_row(
            "[bold red]Errors found:[/bold red]", f"[red]{result.error_count}[/red]"
        )
        console.print(info_table)
        console.print()

        # Error details with enhanced formatting
        for i, error in enumerate(result.errors, 1):
            # Create error panel for each error
            error_content = []

            if error.entity and error.field:
                error_content.append(
                    f"[bold red]Error {i}:[/bold red] [red]{error.type}[/red] in [bold yellow]{error.entity}[/bold yellow].[bold blue]{error.field}[/bold blue]"
                )
            elif error.entity:
                error_content.append(
                    f"[bold red]Error {i}:[/bold red] [red]{error.type}[/red] in [bold yellow]{error.entity}[/bold yellow]"
                )
            else:
                error_content.append(
                    f"[bold red]Error {i}:[/bold red] [red]{error.type}[/red]"
                )

            error_content.append(f"[dim]{error.message}[/dim]")

            if error.help:
                error_content.append(f"💡 [italic green]{error.help}[/italic green]")

            if error.line is not None:
                error_content.append(
                    f"📍 [dim]Line {error.line}, Column {error.column or 1}[/dim]"
                )

            console.print("\n".join(error_content))
            if i < len(result.errors):
                console.print()

        if verbose:
            console.print()
            console.print("[bold]Detailed error analysis:[/bold]")
            console.print(f"• [red]Total errors: {result.error_count}[/red]")
            console.print(f"• [yellow]Total warnings: {result.warning_count}[/yellow]")
    else:
        # Plain text for non-interactive (CI)
        click.echo("❌ Validation failed")
        click.echo()
        click.echo(f"File: {file_path}")
        click.echo(f"Errors found: {result.error_count}")
        click.echo()

        for error in result.errors:
            if error.entity:
                click.echo(
                    f"❌ {error.type} in '{error.entity}.{error.field}': {error.message}"
                )
            else:
                click.echo(f"❌ {error.type}: {error.message}")

            if error.help:
                click.echo(f"   💡 Help: {error.help}")

            if error.line is not None:
                click.echo(f"   📍 Line {error.line}, Column {error.column or 1}")

        if verbose:
            click.echo()
            click.echo("Detailed error analysis:")
            click.echo(f"- Total errors: {result.error_count}")
            click.echo(f"- Total warnings: {result.warning_count}")


def _output_compact_format(  # noqa: PLR0912
    result: Any,
    file_path: str,
    verbose: bool,
    parse_time_ms: float,
    file_size: int,
    dependency_count: int,
    schema_version: str | None,
    namespace: str | None,
    force_colors: bool = False,
) -> None:
    """Output validation result in compact format."""
    if result.is_valid:
        if _should_use_rich_formatting(force_colors):
            # Rich compact format for success
            parts = [
                "[bold green]✅ VALID[/bold green]",
                f"[bold]file[/bold]=[cyan]{file_path}[/cyan]",
                f"[bold]schema[/bold]=[yellow]{schema_version or 'unknown'}[/yellow]",
                f"[bold]namespace[/bold]=[magenta]{namespace or 'unknown'}[/magenta]",
            ]

            if verbose:
                parts.extend(
                    [
                        f"[bold]size[/bold]=[dim]{_format_file_size(file_size)}[/dim]",
                        f"[bold]parsed[/bold]=[dim]{parse_time_ms:.1f}ms[/dim]",
                        f"[bold]deps[/bold]=[dim]{dependency_count}[/dim]",
                    ]
                )

            console.print(" ".join(parts))
        else:
            # Plain compact format for CI
            status_parts = [
                "✅ VALID",
                f"file={file_path}",
                f"schema={schema_version or 'unknown'}",
                f"namespace={namespace or 'unknown'}",
            ]

            if verbose:
                status_parts.extend(
                    [
                        f"size={_format_file_size(file_size)}",
                        f"parsed={parse_time_ms:.1f}ms",
                        f"deps={dependency_count}",
                    ]
                )

            click.echo(" ".join(status_parts))
    elif _should_use_rich_formatting(force_colors):
        # Rich compact format for errors
        parts = [
            "[bold red]❌ INVALID[/bold red]",
            f"[bold]file[/bold]=[cyan]{file_path}[/cyan]",
            f"[bold]errors[/bold]=[red]{result.error_count}[/red]",
        ]

        if result.warning_count > 0:
            parts.append(
                f"[bold]warnings[/bold]=[yellow]{result.warning_count}[/yellow]"
            )

        console.print(" ".join(parts))

        # Show first few errors in compact format with rich formatting
        for _i, error in enumerate(result.errors[:3], 1):
            if error.entity and error.field:
                console.print(
                    f"  [red]❌[/red] [bold yellow]{error.entity}[/bold yellow].[bold blue]{error.field}[/bold blue]: [dim]{error.message}[/dim]"
                )
            elif error.entity:
                console.print(
                    f"  [red]❌[/red] [bold yellow]{error.entity}[/bold yellow]: [dim]{error.message}[/dim]"
                )
            else:
                console.print(f"  [red]❌[/red] [dim]{error.message}[/dim]")
    else:
        # Plain compact format for CI
        status_parts = [
            "❌ INVALID",
            f"file={file_path}",
            f"errors={result.error_count}",
        ]

        if result.warning_count > 0:
            status_parts.append(f"warnings={result.warning_count}")

        click.echo(" ".join(status_parts))

        # Show first few errors in compact format
        for error in result.errors[:3]:
            if error.entity:
                click.echo(f"  ❌ {error.entity}.{error.field}: {error.message}")
            else:
                click.echo(f"  ❌ {error.message}")


def _output_json_format(
    result: Any,
    file_path: str,
    verbose: bool,
    parse_time_ms: float,
    file_size: int,
    dependency_count: int,
    schema_version: str | None,
    namespace: str | None,
) -> None:
    """Output validation result in JSON format."""
    output: dict[str, Any] = {
        "status": "valid" if result.is_valid else "invalid",
        "file": file_path,
        "schema_version": schema_version,
        "namespace": namespace,
    }

    if not result.is_valid:
        output["error_count"] = result.error_count
        output["warning_count"] = result.warning_count
        output["errors"] = []

        for error in result.errors:
            error_dict: dict[str, Any] = {
                "type": error.type,
                "message": error.message,
            }

            if error.field:
                error_dict["field"] = error.field
            if error.entity:
                error_dict["entity"] = error.entity
            if error.line is not None:
                error_dict["line"] = error.line
            if error.column is not None:
                error_dict["column"] = error.column
            if error.help:
                error_dict["help"] = error.help

            output["errors"].append(error_dict)

    if verbose:
        output["file_size"] = file_size
        output["parse_time_ms"] = round(parse_time_ms, 1)
        output["dependency_count"] = dependency_count

    click.echo(json.dumps(output, indent=2))


def _output_yaml_format(
    result: Any,
    file_path: str,
    verbose: bool,
    parse_time_ms: float,
    file_size: int,
    dependency_count: int,
    schema_version: str | None,
    namespace: str | None,
) -> None:
    """Output validation result in YAML format."""
    output: dict[str, Any] = {
        "status": "valid" if result.is_valid else "invalid",
        "file": file_path,
        "schema_version": schema_version,
        "namespace": namespace,
    }

    if not result.is_valid:
        output["error_count"] = result.error_count
        output["warning_count"] = result.warning_count
        output["errors"] = []

        for error in result.errors:
            error_dict: dict[str, Any] = {
                "type": error.type,
                "message": error.message,
            }

            if error.field:
                error_dict["field"] = error.field
            if error.entity:
                error_dict["entity"] = error.entity
            if error.line is not None:
                error_dict["line"] = error.line
            if error.column is not None:
                error_dict["column"] = error.column
            if error.help:
                error_dict["help"] = error.help

            output["errors"].append(error_dict)

    if verbose:
        output["file_size"] = file_size
        output["parse_time_ms"] = round(parse_time_ms, 1)
        output["dependency_count"] = dependency_count

    click.echo(yaml.dump(output, default_flow_style=False, sort_keys=False))


def _validate_implementation(  # noqa: PLR0912, PLR0915
    file: str,
    schema_version: str | None,
    strict: bool,
    format: str,
    verbose: bool,
    force_colors: bool,
) -> None:
    """🔍 **Validate a knowledge graph YAML file**

    Validates your knowledge graph file against the schema specification.
    Provides detailed error reporting with helpful suggestions.

    **Examples:**

    ```bash
    kg validate                          # Validate knowledge-graph.yaml
    kg validate my-graph.yaml            # Validate specific file
    kg validate --format json            # JSON output
    kg validate --verbose                # Detailed information
    kg validate --strict                 # Strict mode (warnings as errors)
    ```

    **Exit Codes:**
    - `0`: Validation successful ✅
    - `1`: Validation failed ❌
    - `2`: File not found, not readable, or invalid command line arguments 📁⚠️
    - `4`: Internal error 💥
    """
    # Convert file path to Path object
    file_path = Path(file)

    try:
        # Check if file exists
        if not file_path.exists():
            if format == "json":
                error_output = {
                    "status": "error",
                    "error_type": "file_not_found",
                    "message": f"File not found: {file}",
                    "file": str(file_path),
                }
                click.echo(json.dumps(error_output, indent=2))
            else:
                click.echo(f"❌ File not found: {file}")
                if verbose:
                    click.echo(f"Checked path: {file_path.absolute()}")
            sys.exit(2)

        # Record file size and start time
        file_size = file_path.stat().st_size
        start_time = time.time()

        # Read file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            if format == "json":
                error_output = {
                    "status": "error",
                    "error_type": "file_read_error",
                    "message": f"Cannot read file: {e}",
                    "file": str(file_path),
                }
                click.echo(json.dumps(error_output, indent=2))
            else:
                click.echo(f"❌ Cannot read file: {e}")
            sys.exit(2)

        # Load schemas from spec/schemas directory
        try:
            # Get schema directory relative to this file's location
            backend_dir = Path(__file__).parent.parent.parent
            schema_dir = backend_dir.parent / "spec" / "schemas"

            if not schema_dir.exists():
                raise FileNotFoundError(f"Schema directory not found: {schema_dir}")

            schema_loader = FileSchemaLoader(str(schema_dir))
            schemas = asyncio.run(schema_loader.load_schemas())
        except Exception as e:
            if format == "json":
                error_output = {
                    "status": "error",
                    "error_type": "schema_load_error",
                    "message": f"Cannot load schemas: {e}",
                    "file": str(file_path),
                }
                click.echo(json.dumps(error_output, indent=2))
            else:
                click.echo(f"❌ Cannot load schemas: {e}")
            sys.exit(4)

        # Create validator
        validator = KnowledgeGraphValidator(schemas)

        # Parse YAML for additional metrics
        try:
            parsed_data = yaml.safe_load(content)
        except yaml.YAMLError:
            parsed_data = {}

        # Run validation
        try:
            result = asyncio.run(validator.validate(content))
        except Exception as e:
            if format == "json":
                error_output = {
                    "status": "error",
                    "error_type": "validation_error",
                    "message": f"Validation failed: {e}",
                    "file": str(file_path),
                }
                click.echo(json.dumps(error_output, indent=2))
            else:
                click.echo(f"❌ Validation failed: {e}")
            sys.exit(4)

        # Calculate parse time and metrics
        parse_time_ms = (time.time() - start_time) * 1000
        dependency_count = _count_dependencies(parsed_data)

        # Extract schema info from parsed data
        schema_version_actual = (
            parsed_data.get("schema_version") if parsed_data else None
        )
        namespace_actual = parsed_data.get("namespace") if parsed_data else None

        # Validate expected schema version if provided
        if schema_version and schema_version_actual != schema_version:
            if format == "json":
                version_error_output: dict[str, Any] = {
                    "status": "invalid",
                    "error_type": "schema_version_mismatch",
                    "message": f"Expected schema version '{schema_version}', got '{schema_version_actual}'",
                    "file": str(file_path),
                    "expected_version": schema_version,
                    "actual_version": schema_version_actual,
                }
                click.echo(json.dumps(version_error_output, indent=2))
            else:
                click.echo(
                    f"❌ Schema version mismatch: expected '{schema_version}', got '{schema_version_actual}'"
                )
            sys.exit(1)

        # Apply strict mode (convert warnings to errors)
        final_result = result
        if strict and result.warning_count > 0:
            # Create a new result object with warnings converted to errors
            all_errors = result.errors + [
                ValidationError(
                    type=warning.type,
                    message=warning.message,
                    field=warning.field,
                    entity=warning.entity,
                    help=warning.help,
                )
                for warning in result.warnings
            ]
            final_result = replace(
                result,
                is_valid=False,
                errors=all_errors,
                warnings=[],
            )

        # Output results based on format
        if format == "table":
            _output_table_format(
                final_result,
                str(file_path),
                verbose,
                parse_time_ms,
                file_size,
                dependency_count,
                schema_version_actual,
                namespace_actual,
                force_colors,
            )
        elif format == "compact":
            _output_compact_format(
                final_result,
                str(file_path),
                verbose,
                parse_time_ms,
                file_size,
                dependency_count,
                schema_version_actual,
                namespace_actual,
                force_colors,
            )
        elif format == "json":
            _output_json_format(
                final_result,
                str(file_path),
                verbose,
                parse_time_ms,
                file_size,
                dependency_count,
                schema_version_actual,
                namespace_actual,
            )
        elif format == "yaml":
            _output_yaml_format(
                final_result,
                str(file_path),
                verbose,
                parse_time_ms,
                file_size,
                dependency_count,
                schema_version_actual,
                namespace_actual,
            )

        # Exit with appropriate code
        sys.exit(0 if final_result.is_valid else 1)

    except KeyboardInterrupt:
        if format == "json":
            error_output = {
                "status": "error",
                "error_type": "interrupted",
                "message": "Validation interrupted by user",
                "file": str(file_path) if "file_path" in locals() else file,
            }
            click.echo(json.dumps(error_output, indent=2))
        else:
            click.echo("\n❌ Validation interrupted")
        sys.exit(4)
    except Exception as e:
        # Handle unexpected errors
        if format == "json":
            error_output = {
                "status": "error",
                "error_type": "internal_error",
                "message": f"Internal error: {e}",
                "file": str(file_path) if "file_path" in locals() else file,
            }
            click.echo(json.dumps(error_output, indent=2))
        else:
            click.echo(f"❌ Internal error: {e}")
            if verbose:
                click.echo("\nFull traceback:")
                click.echo(traceback.format_exc())
        sys.exit(4)


@click.command("validate")
@click.argument(
    "file",
    type=click.Path(exists=False),
    required=False,
    default="knowledge-graph.yaml",
    help="**Path to YAML file to validate** (default: knowledge-graph.yaml)",
)
@click.option(
    "--schema-version",
    type=str,
    help="🔢 **Expected schema version** to validate against",
    metavar="VERSION",
)
@click.option(
    "--strict",
    is_flag=True,
    help="⚡ **Enable strict mode** - warnings become errors",
)
@click.option(
    "--format",
    type=click.Choice(["table", "compact", "json", "yaml"]),
    default="table",
    help="📋 **Output format** for validation results",
    show_default=True,
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="🔍 **Show detailed information** - file size, parse time, dependency count",
)
@click.option(
    "--force-colors",
    is_flag=True,
    help="🎨 **Force colored output** - useful for testing rich formatting",
    hidden=True,  # Hide from main help but available for testing
)
def validate_command(
    file: str,
    schema_version: str | None,
    strict: bool,
    format: str,
    verbose: bool,
    force_colors: bool,
) -> None:
    """🔍 **Validate a knowledge graph YAML file**

    Validates your knowledge graph file against the schema specification.
    Provides detailed error reporting with helpful suggestions.

    **Examples:**

    ```bash
    kg validate                          # Validate knowledge-graph.yaml
    kg validate my-graph.yaml            # Validate specific file
    kg validate --format json            # JSON output
    kg validate --verbose                # Detailed information
    kg validate --strict                 # Strict mode (warnings as errors)
    ```

    **Exit Codes:**
    - `0`: Validation successful ✅
    - `1`: Validation failed ❌
    - `2`: File not found, not readable, or invalid command line arguments 📁⚠️
    - `4`: Internal error 💥
    """
    _validate_implementation(
        file, schema_version, strict, format, verbose, force_colors
    )
