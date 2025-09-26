"""Command-line interface for the knowledge graph."""

import rich_click as click

from .validate import validate_command

# Configure rich-click styling
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.STYLE_OPTION = "bold cyan"
click.rich_click.STYLE_ARGUMENT = "bold yellow"
click.rich_click.STYLE_COMMAND = "bold green"
click.rich_click.STYLE_SWITCH = "bold blue"


@click.group(name="kg")
@click.version_option(version="0.1.0", prog_name="kg")
def main() -> None:
    """🧠 **Red Hat Knowledge Graph** - Modern infrastructure for knowledge management.

    A powerful CLI for validating, managing, and working with knowledge graph data.
    Built with modern Python and designed for enterprise use.
    """
    pass


# Add the validate command to the group
main.add_command(validate_command)


if __name__ == "__main__":
    main()


__all__ = ["main"]
