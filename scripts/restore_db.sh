#!/usr/bin/env bash
# whati8 Database Restore Script
# Usage: ./scripts/restore_db.sh <backup_file.sql.gz>
set -euo pipefail

BACKUP_DIR="${WHATI8_BACKUP_DIR:-/var/backups/whati8}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "  (none found in $BACKUP_DIR/)"
    exit 1
fi

BACKUP_FILE="$1"
DB_NAME="${WHATI8_DB_NAME:-whati8}"
DB_USER="${WHATI8_DB_USER:-whati8}"
DB_HOST="${WHATI8_DB_HOST:-localhost}"
DB_PORT="${WHATI8_DB_PORT:-5432}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ File not found: $BACKUP_FILE"
    exit 1
fi

echo "=== whati8 Database Restore ==="
echo "From:     ${BACKUP_FILE}"
echo "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo ""
echo "⚠️  This will OVERWRITE the current database!"
read -p "Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Restoring..."
if gunzip -c "$BACKUP_FILE" | PGPASSWORD="${WHATI8_DB_PASSWORD:-$DB_USER}" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --quiet \
    --single-transaction; then
    echo "✅ Restore complete"
else
    echo "❌ Restore FAILED" >&2
    exit 1
fi
