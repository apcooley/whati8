"""CLI commands for whati8."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import click

from whati8.cli.auth import auth


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
    except Exception:
        return False


def kill_process_on_port(port: int) -> bool:
    """Kill any process listening on the specified port."""
    try:
        # Try lsof first (preferred)
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid.strip():
                    try:
                        os.kill(int(pid), 9)
                        click.echo(f"✅ Killed process {pid}")
                        time.sleep(0.5)
                        return True
                    except (ValueError, ProcessLookupError):
                        continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback to fuser
        try:
            result = subprocess.run(
                ['fuser', '-k', f'{port}/tcp'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                time.sleep(0.5)
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    
    return False


@click.group()
def cli():
    """whati8 CLI tools."""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind (0.0.0.0 for LAN access)")
@click.option("--port", default=9428, help="Port to bind")
@click.option("--reload", is_flag=True, help="Auto-reload on changes")
@click.option("--kill-existing", is_flag=True, default=True, help="Kill existing process on port (default: True)")
def serve(host: str, port: int, reload: bool, kill_existing: bool):
    """Start the FastAPI server accessible over LAN."""
    import uvicorn

    # Check if port is already in use
    if is_port_in_use(port):
        if kill_existing:
            click.echo(f"⚠️  Port {port} already in use. Killing existing process...")
            if kill_process_on_port(port):
                # Wait for port to be released with retries
                for attempt in range(1, 6):
                    time.sleep(1)
                    if not is_port_in_use(port):
                        click.echo("✅ Port is now available")
                        break
                    if attempt < 5:
                        click.echo(f"⏳ Waiting for port to be released... ({attempt}s)")
                else:
                    click.echo("⚠️  Port still in use after waiting. Trying anyway...")
            else:
                click.echo("⚠️  Could not kill existing process. Trying anyway...")
        else:
            click.echo(f"❌ Port {port} is already in use.", err=True)
            click.echo("   Use --kill-existing to auto-kill, or:")
            click.echo(f"   pkill -f 'uvicorn.*{port}'")
            sys.exit(1)

    click.echo(f"Starting server on {host}:{port}")
    if host == "0.0.0.0":
        click.echo("Server will be accessible on LAN at:")
        click.echo(f"  - http://192.168.1.11:{port}/docs (Swagger UI)")
        click.echo(f"  - http://192.168.1.11:{port}/redoc (ReDoc)")
        click.echo(f"  - http://localhost:{port}/docs (local)")

    try:
        uvicorn.run(
            "whati8.api:app",
            host=host,
            port=port,
            reload=reload,
        )
    except KeyboardInterrupt:
        click.echo("\n👋 Server stopped.")
        sys.exit(0)


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
