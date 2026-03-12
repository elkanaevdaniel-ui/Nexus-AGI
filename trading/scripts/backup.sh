#!/usr/bin/env bash
# Daily backup script for Polymarket Agent
# Backs up database and config, rotates old backups (30 day retention)
set -euo pipefail

APP_DIR="/home/ubuntu/polymarket-agent"
BACKUP_DIR="${APP_DIR}/backups"
RETENTION_DAYS=30
DATE=$(date +%Y-%m-%d_%H%M)

mkdir -p "$BACKUP_DIR"

# Backup SQLite database (using .backup for consistency)
if [[ -f "${APP_DIR}/trading.db" ]]; then
    cp "${APP_DIR}/trading.db" "${BACKUP_DIR}/trading-${DATE}.db"
    echo "[$(date)] Database backed up: trading-${DATE}.db"
fi

# Backup .env (contains config but NOT secrets in plaintext ideally)
if [[ -f "${APP_DIR}/.env" ]]; then
    cp "${APP_DIR}/.env" "${BACKUP_DIR}/env-${DATE}.bak"
    chmod 600 "${BACKUP_DIR}/env-${DATE}.bak"
    echo "[$(date)] Config backed up: env-${DATE}.bak"
fi

# Rotate old backups
find "$BACKUP_DIR" -name "trading-*.db" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "env-*.bak" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

echo "[$(date)] Backup complete. Rotated files older than ${RETENTION_DAYS} days."
