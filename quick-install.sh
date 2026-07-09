#!/usr/bin/env bash
#
# quick-install.sh — one-shot NextOSP installer for Ubuntu & Debian.
#
#   Detects the OS, installs prerequisites, collects settings through a small
#   TUI, then deploys NextOSP one of two ways:
#
#     • Docker  — db + web + cron containers, optionally fronted by
#                 Nginx Proxy Manager (GUI reverse proxy + Let's Encrypt TLS).
#     • Native  — PostgreSQL + Python virtualenv + systemd service.
#
#   Afterwards it installs the `nwos` management CLI (backup/restore/update/
#   upgrade/…) and writes /etc/nwos/nwosctl.env so the CLI knows the layout.
#
#   Usage:   sudo ./quick-install.sh
#     curl:  curl -fsSL https://raw.githubusercontent.com/NextOSP/nwos/master/quick-install.sh | sudo bash
#
#   Non-interactive: set any of the NWOS_* env vars below and it won't prompt
#   for those (missing secrets are generated).
#
set -euo pipefail

# Attach a terminal when piped through curl|bash so the TUI/prompts work.
if [ ! -t 0 ] && [ -e /dev/tty ]; then exec </dev/tty; fi

# ---------------------------------------------------------------------------
# Configurable defaults (override via environment)
# ---------------------------------------------------------------------------
NWOS_MODE="${NWOS_MODE:-}"                 # docker | native (asked if empty)
NWOS_DIR="${NWOS_DIR:-/opt/nwos}"
NWOS_IMAGE="${NWOS_IMAGE:-ghcr.io/nextosp/nwos:latest}"
NWOS_REPO="${NWOS_REPO:-https://github.com/NextOSP/nwos.git}"
NWOS_BRANCH="${NWOS_BRANCH:-master}"
NWOS_DB_NAME="${NWOS_DB_NAME:-nwos}"
NWOS_DB_USER="${NWOS_DB_USER:-nwos}"
NWOS_DB_PASSWORD="${NWOS_DB_PASSWORD:-}"
NWOS_ADMIN_PASSWORD="${NWOS_ADMIN_PASSWORD:-}"
NWOS_HTTP_PORT="${NWOS_HTTP_PORT:-}"       # defaults per mode
NWOS_DOMAIN="${NWOS_DOMAIN:-}"             # optional public hostname
NWOS_APPS="${NWOS_APPS:-base}"             # modules to install on first run
NWOS_WORKERS="${NWOS_WORKERS:-2}"
NWOS_WITH_NPM="${NWOS_WITH_NPM:-}"         # docker only: yes/no
NWOS_OS_USER="nwos"
NWOS_DATA_DIR="/var/lib/nwos"
NWOS_STATE_FILE="/etc/nwos/nwosctl.env"
UI_BACKTITLE="NextOSP quick-install"

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo .)"

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  C_RESET='\033[0m'; C_B='\033[0;34m'; C_G='\033[0;32m'; C_Y='\033[0;33m'; C_R='\033[0;31m'; C_BOLD='\033[1m'
else
  C_RESET=''; C_B=''; C_G=''; C_Y=''; C_R=''; C_BOLD=''
fi
info() { printf "${C_B}==>${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_G}✔${C_RESET} %s\n" "$*"; }
warn() { printf "${C_Y}!${C_RESET} %s\n" "$*" >&2; }
die()  { printf "${C_R}error:${C_RESET} %s\n" "$*" >&2; exit 1; }

genpass() {
  { openssl rand -base64 24 2>/dev/null || head -c 64 /dev/urandom | base64; } | tr -dc 'A-Za-z0-9' | head -c 20
}

# ---------------------------------------------------------------------------
# TUI helpers (whiptail when interactive, plain prompts otherwise)
# ---------------------------------------------------------------------------
HAVE_TUI=0
tui_available() { command -v whiptail >/dev/null 2>&1 && [ -t 0 ] && [ -t 1 ]; }

ui_msg()  { if [ "$HAVE_TUI" = 1 ]; then whiptail --backtitle "$UI_BACKTITLE" --msgbox "$1" 14 72; else printf '%b\n' "$1"; fi; }
ui_yesno() {
  local def="${2:-yes}" extra=""
  [ "$def" = no ] && extra="--defaultno"
  if [ "$HAVE_TUI" = 1 ]; then
    whiptail --backtitle "$UI_BACKTITLE" $extra --yesno "$1" 12 72
  else
    local a hint='Y/n'; [ "$def" = no ] && hint='y/N'
    read -r -p "$1 [$hint] " a; a="${a:-$def}"
    [[ "$a" =~ ^([Yy]|yes)$ ]]
  fi
}
ui_input() {  # prompt default -> value on stdout
  local v
  if [ "$HAVE_TUI" = 1 ]; then
    v=$(whiptail --backtitle "$UI_BACKTITLE" --inputbox "$1" 10 72 "$2" 3>&1 1>&2 2>&3) || v="$2"
  else
    read -r -p "$1 [$2]: " v; v="${v:-$2}"
  fi
  printf '%s' "$v"
}
ui_password() {  # prompt -> value on stdout (blank allowed)
  local v
  if [ "$HAVE_TUI" = 1 ]; then
    v=$(whiptail --backtitle "$UI_BACKTITLE" --passwordbox "$1 (blank = auto-generate)" 10 72 3>&1 1>&2 2>&3) || v=""
  else
    read -r -s -p "$1 (blank = auto): " v; printf '\n' >&2
  fi
  printf '%s' "$v"
}
ui_menu() {  # prompt tag1 item1 tag2 item2 ... -> chosen tag on stdout
  local prompt="$1"; shift
  if [ "$HAVE_TUI" = 1 ]; then
    whiptail --backtitle "$UI_BACKTITLE" --menu "$prompt" 16 72 4 "$@" 3>&1 1>&2 2>&3
  else
    printf '%b\n' "$prompt" >&2
    local first="" a
    while [ $# -gt 0 ]; do [ -z "$first" ] && first="$1"; printf '  %s) %s\n' "$1" "$2" >&2; shift 2; done
    read -r -p "choice [$first]: " a; printf '%s' "${a:-$first}"
  fi
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
[ "$(id -u)" -eq 0 ] || die "Please run as root (sudo ./quick-install.sh)."

detect_os() {
  [ -r /etc/os-release ] || die "Cannot read /etc/os-release."
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="$ID"; OS_CODENAME="${VERSION_CODENAME:-}"; OS_NAME="${PRETTY_NAME:-$ID}"
  case "$OS_ID" in
    ubuntu|debian) ok "Detected $OS_NAME" ;;
    *) die "Unsupported OS '$OS_ID'. This installer supports Ubuntu and Debian." ;;
  esac
}

apt_install() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y --no-install-recommends "$@"
}

# ---------------------------------------------------------------------------
# Gather settings
# ---------------------------------------------------------------------------
gather_settings() {
  tui_available && HAVE_TUI=1 || HAVE_TUI=0

  if [ -z "$NWOS_MODE" ]; then
    NWOS_MODE=$(ui_menu "How do you want to run NextOSP?" \
      docker "Docker containers (recommended, easiest to host)" \
      native "Native install (PostgreSQL + systemd)")
  fi
  [ "$NWOS_MODE" = docker ] || [ "$NWOS_MODE" = native ] || die "Invalid mode: $NWOS_MODE"

  if [ -z "$NWOS_HTTP_PORT" ]; then
    [ "$NWOS_MODE" = docker ] && NWOS_HTTP_PORT=7073 || NWOS_HTTP_PORT=8069
  fi

  NWOS_DOMAIN=$(ui_input "Public domain (leave blank for IP-only / no TLS)" "$NWOS_DOMAIN")
  NWOS_APPS=$(ui_input "Modules to install on first run" "$NWOS_APPS")

  if [ -z "$NWOS_DB_PASSWORD" ]; then NWOS_DB_PASSWORD=$(ui_password "PostgreSQL password for role '$NWOS_DB_USER'"); fi
  [ -n "$NWOS_DB_PASSWORD" ] || { NWOS_DB_PASSWORD=$(genpass); info "Generated DB password."; }

  if [ -z "$NWOS_ADMIN_PASSWORD" ]; then NWOS_ADMIN_PASSWORD=$(ui_password "NextOSP master (admin) password"); fi
  [ -n "$NWOS_ADMIN_PASSWORD" ] || { NWOS_ADMIN_PASSWORD=$(genpass); info "Generated master password."; }

  if [ "$NWOS_MODE" = docker ] && [ -z "$NWOS_WITH_NPM" ]; then
    if ui_yesno "Deploy Nginx Proxy Manager (GUI reverse proxy + free TLS)?" yes; then
      NWOS_WITH_NPM=yes; else NWOS_WITH_NPM=no; fi
  fi

  cat <<SUMMARY

$(printf "${C_BOLD}Install summary${C_RESET}")
  Mode:         $NWOS_MODE
  Directory:    $NWOS_DIR
  HTTP port:    $NWOS_HTTP_PORT
  Domain:       ${NWOS_DOMAIN:-<none>}
  Database:     $NWOS_DB_USER / $NWOS_DB_NAME
  Apps:         $NWOS_APPS
  Nginx PM:     ${NWOS_WITH_NPM:-n/a}
SUMMARY
  ui_yesno "Proceed with installation?" yes || die "Aborted."
}

# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------
write_nwos_conf() {  # $1 = target path, $2 = addons_path, $3 = data_dir, $4 = db_host
  local target="$1" addons="$2" data="$3" dbhost="$4"
  mkdir -p "$(dirname "$target")"
  cat > "$target" <<CONF
[options]
addons_path = $addons
data_dir = $data
db_host = $dbhost
db_port = 5432
db_user = $NWOS_DB_USER
db_password = $NWOS_DB_PASSWORD
db_name = $NWOS_DB_NAME
http_interface = 0.0.0.0
http_port = $NWOS_HTTP_PORT
proxy_mode = True
list_db = False
workers = $NWOS_WORKERS
max_cron_threads = 1
admin_passwd = $NWOS_ADMIN_PASSWORD
log_level = info
CONF
}

# ---------------------------------------------------------------------------
# Docker install
# ---------------------------------------------------------------------------
install_docker_engine() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    ok "Docker already installed."; return
  fi
  info "Installing Docker Engine..."
  apt-get update -qq
  apt_install ca-certificates curl
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  ok "Docker installed."
}

deploy_docker() {
  install_docker_engine
  mkdir -p "$NWOS_DIR"
  write_nwos_conf "$NWOS_DIR/nwos.conf" "/opt/nwos/addons,/opt/nwos/nwos/addons" "$NWOS_DATA_DIR" "db"

  local publish_web="    ports: [\"$NWOS_HTTP_PORT:7073\"]"
  [ "$NWOS_WITH_NPM" = yes ] && publish_web="    expose: [\"7073\"]"

  info "Writing $NWOS_DIR/docker-compose.yml"
  cat > "$NWOS_DIR/docker-compose.yml" <<COMPOSE
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: $NWOS_DB_NAME
      POSTGRES_USER: $NWOS_DB_USER
      POSTGRES_PASSWORD: $NWOS_DB_PASSWORD
    volumes: [db-data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $NWOS_DB_USER -d $NWOS_DB_NAME"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  web:
    image: $NWOS_IMAGE
    depends_on:
      db: {condition: service_healthy}
$publish_web
    command: ["server", "-c", "/etc/nwos/nwos.conf", "--max-cron-threads=0"]
    volumes:
      - nwos-data:/var/lib/nwos
      - ./nwos.conf:/etc/nwos/nwos.conf:ro
    restart: unless-stopped

  cron:
    image: $NWOS_IMAGE
    depends_on:
      db: {condition: service_healthy}
    command: ["server", "-c", "/etc/nwos/nwos.conf", "--workers=0", "--max-cron-threads=2"]
    volumes:
      - nwos-data:/var/lib/nwos
      - ./nwos.conf:/etc/nwos/nwos.conf:ro
    restart: unless-stopped
COMPOSE

  if [ "$NWOS_WITH_NPM" = yes ]; then
    cat >> "$NWOS_DIR/docker-compose.yml" <<'COMPOSE'

  npm:
    image: jc21/nginx-proxy-manager:latest
    depends_on: [web]
    ports:
      - "80:80"
      - "443:443"
      - "81:81"
    volumes:
      - npm-data:/data
      - npm-letsencrypt:/etc/letsencrypt
    restart: unless-stopped
COMPOSE
  fi

  cat >> "$NWOS_DIR/docker-compose.yml" <<COMPOSE

volumes:
  db-data:
  nwos-data:
COMPOSE
  [ "$NWOS_WITH_NPM" = yes ] && printf '  npm-data:\n  npm-letsencrypt:\n' >> "$NWOS_DIR/docker-compose.yml"

  info "Pulling images..."
  docker compose -f "$NWOS_DIR/docker-compose.yml" pull
  info "Starting stack..."
  docker compose -f "$NWOS_DIR/docker-compose.yml" up -d
  info "Initializing database (installing: $NWOS_APPS)..."
  docker compose -f "$NWOS_DIR/docker-compose.yml" run --rm web \
    server -c /etc/nwos/nwos.conf -d "$NWOS_DB_NAME" -i "$NWOS_APPS" --stop-after-init
  ok "Docker stack is up."
}

# ---------------------------------------------------------------------------
# Native install
# ---------------------------------------------------------------------------
deploy_native() {
  info "Installing system packages (this can take a few minutes)..."
  apt-get update -qq
  apt_install git curl rsync build-essential python3 python3-dev python3-venv python3-pip \
    libpq-dev libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev libjpeg-dev zlib1g-dev \
    node-less npm postgresql postgresql-client wkhtmltopdf \
    fonts-dejavu-core fonts-font-awesome fonts-roboto-unhinted fonts-inconsolata

  info "Configuring PostgreSQL role '$NWOS_DB_USER'..."
  systemctl enable --now postgresql
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$NWOS_DB_USER'" | grep -q 1; then
    sudo -u postgres createuser --createdb "$NWOS_DB_USER"
  fi
  sudo -u postgres psql -c "ALTER USER \"$NWOS_DB_USER\" WITH PASSWORD '$NWOS_DB_PASSWORD';" >/dev/null

  id "$NWOS_OS_USER" >/dev/null 2>&1 || useradd --system --home "$NWOS_DATA_DIR" --shell /usr/sbin/nologin "$NWOS_OS_USER"
  mkdir -p "$NWOS_DIR" "$NWOS_DATA_DIR" /var/log/nwos /etc/nwos

  # Source: reuse a local checkout if this script sits inside one, else clone.
  if [ -x "$SELF_DIR/nwos-bin" ]; then
    info "Copying source from $SELF_DIR ..."
    rsync -a --delete --exclude venv --exclude data --exclude logs "$SELF_DIR"/ "$NWOS_DIR"/
  elif [ ! -x "$NWOS_DIR/nwos-bin" ]; then
    info "Cloning $NWOS_REPO ($NWOS_BRANCH)..."
    git clone --depth 1 --branch "$NWOS_BRANCH" "$NWOS_REPO" "$NWOS_DIR"
  fi

  info "Creating virtualenv and installing dependencies..."
  python3 -m venv "$NWOS_DIR/venv"
  "$NWOS_DIR/venv/bin/pip" install -q --upgrade pip wheel setuptools
  "$NWOS_DIR/venv/bin/pip" install -q -r "$NWOS_DIR/requirements.txt"

  write_nwos_conf "/etc/nwos/nwos.conf" "$NWOS_DIR/addons,$NWOS_DIR/nwos/addons" "$NWOS_DATA_DIR" "localhost"
  sed -i "s#^logfile.*#logfile = /var/log/nwos/nwos.log#" /etc/nwos/nwos.conf 2>/dev/null || \
    printf 'logfile = /var/log/nwos/nwos.log\n' >> /etc/nwos/nwos.conf

  chown -R "$NWOS_OS_USER:$NWOS_OS_USER" "$NWOS_DIR" "$NWOS_DATA_DIR" /var/log/nwos
  chown "$NWOS_OS_USER:$NWOS_OS_USER" /etc/nwos/nwos.conf && chmod 640 /etc/nwos/nwos.conf

  info "Initializing database (installing: $NWOS_APPS)..."
  sudo -u "$NWOS_OS_USER" "$NWOS_DIR/venv/bin/python" "$NWOS_DIR/nwos-bin" \
    server -c /etc/nwos/nwos.conf -d "$NWOS_DB_NAME" -i "$NWOS_APPS" --stop-after-init

  info "Installing systemd service..."
  cat > /etc/systemd/system/nwos.service <<UNIT
[Unit]
Description=NextOSP (nwos) server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$NWOS_OS_USER
Group=$NWOS_OS_USER
ExecStart=$NWOS_DIR/venv/bin/python $NWOS_DIR/nwos-bin server -c /etc/nwos/nwos.conf
KillMode=mixed
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now nwos.service
  ok "Service nwos.service is running."

  if [ -n "$NWOS_DOMAIN" ]; then
    info "Configuring nginx for $NWOS_DOMAIN ..."
    apt_install nginx
    cat > /etc/nginx/sites-available/nwos <<NGINX
upstream nwos { server 127.0.0.1:$NWOS_HTTP_PORT; }
server {
    listen 80;
    server_name $NWOS_DOMAIN;
    client_max_body_size 100m;
    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    location / { proxy_pass http://nwos; proxy_redirect off; }
    location /websocket {
        proxy_pass http://nwos;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX
    ln -sf /etc/nginx/sites-available/nwos /etc/nginx/sites-enabled/nwos
    nginx -t && systemctl reload nginx
    ok "nginx configured. Add TLS with: certbot --nginx -d $NWOS_DOMAIN"
  fi
}

# ---------------------------------------------------------------------------
# CLI + state
# ---------------------------------------------------------------------------
install_cli() {
  local src="$SELF_DIR/scripts/nwosctl"
  [ -f "$src" ] || src="$NWOS_DIR/scripts/nwosctl"
  if [ -f "$src" ]; then
    install -m 0755 "$src" /usr/local/bin/nwos
    ok "Installed management CLI: nwos"
  else
    warn "scripts/nwosctl not found — 'nwos' CLI not installed."
  fi

  local compose="" config="" venv=""
  if [ "$NWOS_MODE" = docker ]; then
    compose="$NWOS_DIR/docker-compose.yml"
  else
    config="/etc/nwos/nwos.conf"; venv="$NWOS_DIR/venv"
  fi

  cat > "$NWOS_STATE_FILE" <<STATE
# Written by quick-install.sh — used by the 'nwos' CLI
NWOS_MODE=$NWOS_MODE
NWOS_DIR=$NWOS_DIR
NWOS_COMPOSE=$compose
NWOS_CONFIG=${config:-$NWOS_DIR/nwos.conf}
NWOS_VENV=${venv:-$NWOS_DIR/venv}
NWOS_SERVICE=nwos.service
NWOS_OS_USER=$NWOS_OS_USER
NWOS_DB_NAME=$NWOS_DB_NAME
NWOS_DB_USER=$NWOS_DB_USER
NWOS_DB_HOST=localhost
NWOS_DB_PORT=5432
NWOS_DB_PASSWORD=$NWOS_DB_PASSWORD
NWOS_DATA_DIR=$NWOS_DATA_DIR
NWOS_BACKUP_DIR=/var/backups/nwos
STATE
  chmod 600 "$NWOS_STATE_FILE"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
final_summary() {
  local ip; ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; ip="${ip:-localhost}"
  local url="http://$ip:$NWOS_HTTP_PORT"
  [ -n "$NWOS_DOMAIN" ] && url="http://$NWOS_DOMAIN"

  printf "\n${C_G}${C_BOLD}NextOSP is installed.${C_RESET}\n\n"
  if [ "$NWOS_MODE" = docker ] && [ "$NWOS_WITH_NPM" = yes ]; then
    printf "  Nginx Proxy Manager:  ${C_BOLD}http://%s:81${C_RESET}  (login admin@example.com / changeme)\n" "$ip"
    printf "    → add a Proxy Host forwarding to hostname ${C_BOLD}web${C_RESET} port ${C_BOLD}7073${C_RESET},\n"
    printf "      enable Websockets Support, then request a Let's Encrypt cert.\n\n"
    [ -n "$NWOS_DOMAIN" ] && printf "  App (after proxy host + DNS):  ${C_BOLD}https://%s${C_RESET}\n" "$NWOS_DOMAIN"
  else
    printf "  Web:      ${C_BOLD}%s${C_RESET}   (login: admin / admin on first run)\n" "$url"
  fi
  printf "  Master password:  %s\n" "$NWOS_ADMIN_PASSWORD"
  printf "  DB password:      %s\n\n" "$NWOS_DB_PASSWORD"
  printf "  Manage it with the ${C_BOLD}nwos${C_RESET} CLI:\n"
  printf "    nwos status | logs -f | backup | restore <dump> | update | upgrade\n\n"
  warn "Save the passwords above — they are also stored in $NWOS_STATE_FILE (root only)."
}

# ---------------------------------------------------------------------------
main() {
  info "NextOSP quick-install starting..."
  detect_os
  tui_available && HAVE_TUI=1 || HAVE_TUI=0
  command -v whiptail >/dev/null 2>&1 || { apt-get update -qq && apt_install whiptail >/dev/null 2>&1 || true; }
  tui_available && HAVE_TUI=1 || HAVE_TUI=0

  gather_settings
  if [ "$NWOS_MODE" = docker ]; then deploy_docker; else deploy_native; fi
  install_cli
  final_summary
}

main "$@"
