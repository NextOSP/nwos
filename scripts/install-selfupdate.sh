#!/usr/bin/env sh
# Install the self-update systemd timer, pointed at wherever this checkout lives
# and whichever user runs it. Run from the repository root:
#
#   sudo sh scripts/install-selfupdate.sh
#
# Re-run it any time to repoint the unit (e.g. after moving the checkout).
set -eu

REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

# The user that owns the checkout - not necessarily whoever invoked sudo.
RUN_USER="${SUDO_USER:-$(id -un)}"
if [ -z "${RUN_USER}" ] || [ "${RUN_USER}" = "root" ]; then
    RUN_USER="$(stat -c '%U' "${REPO_DIR}" 2>/dev/null || echo root)"
fi

if [ ! -f "${REPO_DIR}/docker-compose.yml" ]; then
    echo "error: no docker-compose.yml in ${REPO_DIR}" >&2
    exit 1
fi

if ! id "${RUN_USER}" >/dev/null 2>&1; then
    echo "error: user ${RUN_USER} does not exist" >&2
    exit 1
fi

if [ ! -r "${REPO_DIR}/.env" ]; then
    echo "warning: ${REPO_DIR}/.env not found - copy .env.example first" >&2
fi

echo "installing timer for ${REPO_DIR} running as ${RUN_USER}"

cat > /etc/systemd/system/nwos-selfupdate.service <<EOF
[Unit]
Description=Pull and deploy the latest NWOS image
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
User=${RUN_USER}
WorkingDirectory=${REPO_DIR}
Environment=NWOS_DIR=${REPO_DIR}
ExecStart=/bin/sh ${REPO_DIR}/scripts/nwos-selfupdate.sh
TimeoutStartSec=1800
StandardOutput=journal
StandardError=journal
EOF

cp "${REPO_DIR}/scripts/systemd/nwos-selfupdate.timer" \
   /etc/systemd/system/nwos-selfupdate.timer

systemctl daemon-reload
systemctl enable --now nwos-selfupdate.timer

echo
echo "installed. next steps:"
echo "  systemctl list-timers nwos-selfupdate"
echo "  systemctl start nwos-selfupdate      # force a check now"
echo "  journalctl -u nwos-selfupdate -f     # watch it"
