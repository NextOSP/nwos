#!/usr/bin/env sh
set -eu

mkdir -p backups
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-nwos}" -Fc --no-owner --no-acl "${POSTGRES_DB:-nwos}" \
    > "backups/nwos-${timestamp}.dump"
echo "Wrote backups/nwos-${timestamp}.dump"
