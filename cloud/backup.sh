#!/bin/bash
# ================================================================
# NEXUS AGI — Auto Backup (Unified System)
# Backs up all databases and critical data files
# ================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NEXUS_DIR="$PROJECT_DIR/nexus-agi"
BACKUP_DIR="$NEXUS_DIR/data/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting NEXUS unified backup..."

# Back up all SQLite databases
for db in \
    "$PROJECT_DIR/linkedin-bot/data/posts.db" \
    "$PROJECT_DIR/cost-optimizer/data/cost_tracker.db" \
    "$NEXUS_DIR/data/cortex.db" \
    "$NEXUS_DIR/command-center/backend/command_center.db" \
    "$NEXUS_DIR/command-center/backend/sentinel.db" \
    "$NEXUS_DIR/divisions/tier3-intelligence/sigma/data/sigma.db" \
    "$NEXUS_DIR/divisions/tier4-protect/shield/shield.db" \
    "$NEXUS_DIR/divisions/tier2-build/oracle/oracle.db"
do
    if [ -f "$db" ]; then
        dbname=$(basename "$db")
        cp "$db" "$BACKUP_DIR/${TIMESTAMP}_${dbname}"
        echo "  Backed up: $dbname"
    fi
done

# Back up Redis dump
REDIS_DUMP="/var/lib/redis/dump.rdb"
if [ -f "$REDIS_DUMP" ]; then
    cp "$REDIS_DUMP" "$BACKUP_DIR/${TIMESTAMP}_redis_dump.rdb"
    echo "  Backed up: redis_dump.rdb"
fi

# Clean old backups (keep last 7 days)
find "$BACKUP_DIR" -name "20*" -mtime +7 -delete 2>/dev/null || true

echo "[$(date)] Backup complete. Files in: $BACKUP_DIR"
