"""CLI commands for whati8."""
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


# Register command groups
cli.add_command(auth)


if __name__ == "__main__":
    cli()
