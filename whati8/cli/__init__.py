"""CLI commands for whati8."""
import click
from whati8.cli.auth import auth


@click.group()
def cli():
    """whati8 CLI tools."""
    pass


# Register command groups
cli.add_command(auth)


if __name__ == "__main__":
    cli()
