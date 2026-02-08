"""CLI commands for whati8."""

import subprocess
import sys
from pathlib import Path

import click

from whati8.cli.auth import auth


@click.group()
def cli():
    """whati8 CLI tools."""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind (0.0.0.0 for LAN access)")
@click.option("--port", default=8000, help="Port to bind")
@click.option("--reload", is_flag=True, help="Auto-reload on changes")
def serve(host: str, port: int, reload: bool):
    """Start the FastAPI server accessible over LAN."""
    import uvicorn

    click.echo(f"Starting server on {host}:{port}")
    if host == "0.0.0.0":
        click.echo("Server will be accessible on LAN at:")
        click.echo(f"  - http://192.168.1.11:{port}/docs (Swagger UI)")
        click.echo(f"  - http://192.168.1.11:{port}/redoc (ReDoc)")
        click.echo(f"  - http://localhost:{port}/docs (local)")

    uvicorn.run(
        "whati8.api:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.command(name="import-usda")
@click.option(
    "--limit",
    "-l",
    type=int,
    help="Limit number of foods to import per dataset (for testing)",
)
def import_usda(limit: int | None):
    """Import USDA Food Data Central bulk data into database.

    Downloads bulk JSON files from USDA FDC and imports ~9,000 foods with nutrients.
    Includes Foundation Foods (~1,000) and SR Legacy (~8,000) datasets.

    Examples:
        uv run python -m whati8 import-usda           # Full import
        uv run python -m whati8 import-usda --limit 100  # Test with 100 foods
    """
    script_path = (
        Path(__file__).parent.parent.parent / "scripts" / "import_usda_data.py"
    )

    cmd = [sys.executable, str(script_path)]
    if limit:
        cmd.extend(["--limit", str(limit)])

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


# Register command groups
cli.add_command(auth)


if __name__ == "__main__":
    cli()
