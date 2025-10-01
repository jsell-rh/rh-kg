"""CLI schema command implementation.

This module implements the `kg schema` command group for schema operations,
including JSON Schema export for VSCode autocomplete integration.
"""

import asyncio
import json
from pathlib import Path
import sys

from rich.console import Console
import rich_click as click

from ..core.json_schema_generator import JSONSchemaExporter

# Create console for rich formatting
console = Console()


@click.group(name="schema")
def schema_command() -> None:
    """📋 **Schema operations** - Export and manage schema definitions.

    Commands for working with YAML schema definitions, including exporting
    JSON Schema for IDE integration and validation.
    """
    pass


@schema_command.command(name="export")
@click.option(
    "--format",
    "export_format",  # Use different parameter name to avoid Python keyword
    type=click.Choice(["json-schema"], case_sensitive=False),
    default="json-schema",
    help="Output format (currently only json-schema supported)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=".vscode/kg-schema.json",
    help="Output file path for generated schema",
)
@click.option(
    "--schema-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default="backend/schemas",
    help="Directory containing YAML schema definitions",
)
@click.option(
    "--pretty/--no-pretty",
    default=True,
    help="Pretty-print JSON output with indentation",
)
@click.option(
    "--vscode/--no-vscode",
    default=True,
    help="Update .vscode/settings.json with schema configuration",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress output (only show errors)",
)
def export_command(
    export_format: str,  # noqa: ARG001 - Reserved for future format support
    output: str,
    schema_dir: str,
    pretty: bool,
    vscode: bool,
    quiet: bool,
) -> None:
    """📤 **Export JSON Schema** for IDE autocomplete and validation.

    Generates a JSON Schema file from the YAML schema definitions, enabling
    VSCode autocomplete and inline validation for knowledge-graph.yaml files.

    \b
    Examples:
        # Export to default location (.vscode/kg-schema.json)
        kg schema export

        # Export to custom location
        kg schema export --output docs/kg-schema.json

        # Export without VSCode integration
        kg schema export --no-vscode

        # Compact JSON for production
        kg schema export --no-pretty --output dist/schema.json
    """
    try:
        # Run async export
        asyncio.run(_export_schema(output, schema_dir, pretty, vscode, quiet))

    except KeyboardInterrupt:
        if not quiet:
            console.print("\n⚠️  [yellow]Export cancelled by user[/yellow]")
        sys.exit(130)

    except Exception as e:
        console.print(f"\n❌ [bold red]Export failed:[/bold red] {e}")
        if "--verbose" in sys.argv or "-v" in sys.argv:
            import traceback

            console.print("\n[dim]Traceback:[/dim]")
            console.print(traceback.format_exc())
        sys.exit(1)


async def _export_schema(
    output_path: str,
    schema_dir: str,
    pretty: bool,
    update_vscode: bool,
    quiet: bool,
) -> None:
    """Export JSON Schema asynchronously.

    Args:
        output_path: Path to output JSON file
        schema_dir: Directory containing YAML schemas
        pretty: Whether to pretty-print JSON
        update_vscode: Whether to update VSCode settings
        quiet: Whether to suppress output
    """
    if not quiet:
        console.print("🔄 [cyan]Generating JSON Schema...[/cyan]")

    # Create exporter
    exporter = JSONSchemaExporter(schema_dir)

    # Export schema
    json_schema = await exporter.export(output_path, pretty=pretty)

    # Get statistics
    entity_count = len(
        list(json_schema.get("properties", {}).get("entity", {}).get("properties", {}))
    )
    output_file = Path(output_path)

    if not quiet:
        console.print("✅ [green]Generated JSON Schema successfully[/green]")
        console.print(f"   📁 Output: {output_path}")
        console.print(f"   📊 Entity types: {entity_count}")
        console.print(
            f"   📦 File size: {_format_file_size(output_file.stat().st_size)}"
        )

    # Update VSCode settings if requested
    if update_vscode:
        await _update_vscode_settings(output_path, quiet)

    if not quiet:
        console.print()
        console.print("💡 [bold cyan]Next steps:[/bold cyan]")
        console.print("   1. Reload VSCode to activate the schema")
        console.print("   2. Open a knowledge-graph.yaml file")
        console.print("   3. Enjoy autocomplete and validation! ✨")


async def _update_vscode_settings(schema_path: str, quiet: bool) -> None:
    """Update VSCode settings.json with schema configuration.

    Args:
        schema_path: Path to the generated JSON schema
        quiet: Whether to suppress output
    """
    vscode_settings_path = Path(".vscode/settings.json")

    # Create .vscode directory if it doesn't exist
    vscode_settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Read or create settings
    if vscode_settings_path.exists():
        try:
            existing_settings = json.loads(
                vscode_settings_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            if not quiet:
                console.print(
                    "   ⚠️  [yellow]Warning: Invalid .vscode/settings.json, creating new file[/yellow]"
                )
            existing_settings = {}
    else:
        existing_settings = {}

    # Add/update yaml.schemas configuration
    if "yaml.schemas" not in existing_settings:
        existing_settings["yaml.schemas"] = {}

    existing_settings["yaml.schemas"][schema_path] = [
        "**/knowledge-graph.yaml",
        "tmp/**/knowledge-graph.yaml",
    ]

    # Write updated settings
    vscode_settings_path.write_text(
        json.dumps(existing_settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not quiet:
        console.print(
            "   ⚙️  [cyan]Updated .vscode/settings.json with schema mapping[/cyan]"
        )


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


__all__ = ["schema_command", "export_command"]
