"""Command-line interface for the knowledge graph."""

import click


@click.command()
@click.version_option()
def main() -> None:
    """Red Hat Knowledge Graph CLI."""
    click.echo("Welcome to Red Hat Knowledge Graph!")
    click.echo("Use --help to see available commands.")


if __name__ == "__main__":
    main()


__all__ = ["main"]
