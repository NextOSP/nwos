#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 backups/nwos-YYYYMMDDTHHMMSSZ.dump" >&2
    exit 2
fi

backup_file="$1"
docker compose exec -T db pg_restore --clean --if-exists --no-owner --no-acl \
    -U "${POSTGRES_USER:-nwos}" -d "${POSTGRES_DB:-nwos}" < "${backup_file}"
