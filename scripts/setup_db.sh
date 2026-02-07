#!/bin/bash
# Database setup script for whati8

set -e  # Exit on error

echo "=== whati8 Database Setup ==="
echo

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed."
    echo "Install with: sudo apt-get install postgresql postgresql-contrib"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready &> /dev/null; then
    echo "❌ PostgreSQL is not running."
    echo "Start with: sudo systemctl start postgresql"
    exit 1
fi

echo "✓ PostgreSQL is installed and running"
echo

# Database credentials from .env
DB_NAME="whati8"
DB_USER="whati8"
DB_PASS="whati8"

echo "Creating database and user..."

# Create user if not exists
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

# Create database if not exists
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Grant privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# Enable pg_trgm extension
sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

echo "✓ Database '$DB_NAME' created"
echo "✓ User '$DB_USER' created"
echo "✓ Extension 'pg_trgm' enabled"
echo

echo "Running Alembic migrations..."
uv run alembic upgrade head

echo
echo "Seeding standard data (nutrients and meals)..."
uv run python scripts/seed_standard_data.py

echo
echo "✓ Database setup complete!"
echo
echo "Connection string: postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"
