#!/usr/bin/env bash
set -euo pipefail

# Load environment variables from .env
set -a
source "$(dirname "$0")/.env"
set +a

SQL_FILE="app/services/database/data/seed_pg.sql"

echo "Uploading ${SQL_FILE} into ${POSTGRES_DB}..."
docker exec -i database-engine \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" < "${SQL_FILE}"
echo "Done."
