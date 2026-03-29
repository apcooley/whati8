#!/usr/bin/env bash
# whati8 Database Backup Script
# Usage: ./scripts/backup_db.sh [backup_dir]
# Cron:  0 3 * * * /path/to/whati8/scripts/backup_db.sh
set -euo pipefail

# Configuration
DB_NAME="${WHATI8_DB_NAME:-whati8}"
DB_USER="${WHATI8_DB_USER:-whati8}"
DB_HOST="${WHATI8_DB_HOST:-localhost}"
DB_PORT="${WHATI8_DB_PORT:-5432}"
BACKUP_DIR="${1:-/var/backups/whati8}"
RETENTION_DAYS="${WHATI8_BACKUP_RETENTION:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "=== whati8 Database Backup ==="
echo "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "Backup:   ${BACKUP_FILE}"
echo "Retention: ${RETENTION_DAYS} days"

# Run backup (plain SQL format, compressed with gzip)
if PGPASSWORD="${WHATI8_DB_PASSWORD:-$DB_USER}" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    | gzip > "$BACKUP_FILE"; then
    
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup complete: ${BACKUP_FILE} (${SIZE})"
else
    echo "❌ Backup FAILED" >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Cleanup old backups
DELETED=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "🗑️  Cleaned up ${DELETED} backup(s) older than ${RETENTION_DAYS} days"
fi

# Summary
TOTAL=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" | wc -l)
echo "📦 Total backups: ${TOTAL}"
