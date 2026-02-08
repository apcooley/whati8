"""CLI commands for authentication."""

import asyncio
import click
from datetime import datetime, timedelta

from whati8.database import AsyncSessionLocal
from whati8.services.auth import AuthService
from whati8.schemas.auth import UserCreate, UserResponse
from whati8.config import settings


@click.group()
def auth():
    """Authentication commands."""
    pass


async def register_async(username: str, email: str, password: str):
    """Register a new user (async implementation)."""
    async with AsyncSessionLocal() as db:
        try:
            # Validate with schema
            user_data = UserCreate(username=username, email=email, password=password)

            # Create user
            user = await AuthService.create_user(db, user_data)

            # Display result
            user_response = UserResponse.model_validate(user)
            click.echo("\n✓ User created successfully!")
            click.echo(f"  ID: {user_response.id}")
            click.echo(f"  Username: {user_response.username}")
            click.echo(f"  Email: {user_response.email}")
            click.echo(f"  Created: {user_response.created_at}")

        except Exception as e:
            click.echo(f"\n✗ Error: {e}", err=True)
            raise click.Abort()


async def login_async(login: str, password: str):
    """Login and get JWT token (async implementation)."""
    async with AsyncSessionLocal() as db:
        # Authenticate
        user = await AuthService.authenticate_user(db, login, password)

        if not user:
            click.echo("\n✗ Invalid username/email or password", err=True)
            raise click.Abort()

        # Generate token
        token = AuthService.create_access_token(user.id)
        expires_at = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

        # Display result
        click.echo("\n✓ Login successful!")
        click.echo(f"  User: {user.username}")
        click.echo(f"  Token: {token}")
        click.echo(f"  Expires: {expires_at} UTC")
        click.echo("\n  Use this token for authenticated requests:")
        click.echo(f"  Authorization: Bearer {token}")


async def whoami_async(token: str):
    """Decode a JWT token and show user info (async implementation)."""
    async with AsyncSessionLocal() as db:
        try:
            # Decode token
            payload = AuthService.decode_token(token)

            # Get user
            user = await AuthService.get_user_by_id(db, payload.sub)

            if not user:
                click.echo("\n✗ User not found", err=True)
                raise click.Abort()

            # Display result
            user_response = UserResponse.model_validate(user)
            expires_at = datetime.fromtimestamp(payload.exp)

            click.echo("\n✓ Token valid!")
            click.echo(f"  User ID: {user_response.id}")
            click.echo(f"  Username: {user_response.username}")
            click.echo(f"  Email: {user_response.email}")
            click.echo(f"  Token expires: {expires_at} UTC")

        except Exception as e:
            click.echo(f"\n✗ Invalid or expired token: {e}", err=True)
            raise click.Abort()


@auth.command()
@click.option("--username", prompt=True, help="Username (3-50 chars)")
@click.option("--email", prompt=True, help="Email address")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
def register(username: str, email: str, password: str):
    """Register a new user."""
    asyncio.run(register_async(username, email, password))


@auth.command()
@click.option("--login", prompt=True, help="Username or email")
@click.option("--password", prompt=True, hide_input=True)
def login(login: str, password: str):
    """Login and get JWT token."""
    asyncio.run(login_async(login, password))


@auth.command()
@click.argument("token")
def whoami(token: str):
    """Decode a JWT token and show user info."""
    asyncio.run(whoami_async(token))
