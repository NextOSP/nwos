#!/usr/bin/env sh
set -eu

if [ "${NWOS_WAIT_FOR_DB:-1}" = "1" ]; then
    echo "Waiting for PostgreSQL at ${NWOS_DB_HOST:-db}:${NWOS_DB_PORT:-5432}..."
    until pg_isready -h "${NWOS_DB_HOST:-db}" -p "${NWOS_DB_PORT:-5432}" -U "${NWOS_DB_USER:-nwos}" >/dev/null 2>&1; do
        sleep 2
    done
fi

exec /opt/nwos/nwos-bin "$@"
