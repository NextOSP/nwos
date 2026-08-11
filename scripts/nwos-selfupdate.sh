#!/usr/bin/env sh
# Pull the latest CI-published image and roll it out, if and only if the
# published digest differs from what is running. Safe to run on a timer.
#
#   NWOS_DIR   directory holding docker-compose.yml (default: script's parent)
#   NWOS_IMAGE image to track (default: read from .env, else ghcr.io/nextosp/nwos:latest)
#
# Exits 0 when already up to date so a systemd timer stays green.
set -eu

NWOS_DIR="${NWOS_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
cd "$NWOS_DIR"

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

IMAGE="${NWOS_IMAGE:-ghcr.io/nextosp/nwos:latest}"
DB="${NWOS_DB_NAME:-nwos}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

digest() {
    docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGE" 2>/dev/null || echo none
}

before="$(digest)"
log "running digest: ${before}"

log "pulling ${IMAGE}"
docker compose pull --quiet

after="$(digest)"

if [ "$before" = "$after" ]; then
    log "already up to date, nothing to do"
    exit 0
fi

log "new image: ${after}"

# Pick up compose/config changes that ship alongside the image. Skipped when the
# working tree is dirty so local edits are never clobbered - keep server-specific
# config in .env and docker/nwos.local.conf (both untracked) instead.
if [ -d .git ]; then
    if [ -z "$(git status --porcelain)" ]; then
        log "updating checkout"
        git fetch --prune origin
        git reset --hard "origin/$(git rev-parse --abbrev-ref HEAD)"
    else
        log "WARNING: working tree is dirty, skipping git update"
    fi
fi

log "backing up ${DB}"
sh scripts/backup-compose.sh

# Stop app containers before upgrading so no worker serves new code against the
# old schema. db keeps running - the upgrade needs it.
log "stopping web and cron"
docker compose stop web cron

log "upgrading modules"
docker compose run --rm web server -c /etc/nwos/nwos.conf \
    -d "$DB" -u all --stop-after-init

log "starting stack"
docker compose up -d --no-build --remove-orphans

docker image prune -f >/dev/null 2>&1 || true

log "deployed ${after}"
