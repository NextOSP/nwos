# Installing NextOSP

This guide installs **NextOSP** (`nwos`, v4.0) from source on **Ubuntu** and
**Debian**, for both a **local development** setup and a **production**
deployment following best practices (dedicated system user, virtualenv, systemd
service, nginx reverse proxy, hardened configuration).

It also covers **Docker**, **Kubernetes** (production), **reverse proxying with
Nginx Proxy Manager**, and **backup & restore**.

> NextOSP is an open-source ERP/CRM platform built on a Python server and
> PostgreSQL. See the [README](README.md) for a feature overview, and
> [`docs/deployment.md`](docs/deployment.md) for deeper container/Kubernetes
> reference material.

## Contents

- [Requirements](#requirements)
- [Quick install (automated)](#quick-install-automated)
- [1. Install system packages](#1-install-system-packages)
- [2. Set up PostgreSQL](#2-set-up-postgresql)
- [3. Get the source & create a virtualenv](#3-get-the-source--create-a-virtualenv)
- [4. Configure NextOSP](#4-configure-nextosp)
- [Path A — Local development](#path-a--local-development)
- [Path B — Production (native)](#path-b--production-native)
- [Path C — Docker](#path-c--docker)
- [Path D — Kubernetes (production)](#path-d--kubernetes-production)
- [Reverse proxy with Nginx Proxy Manager](#reverse-proxy-with-nginx-proxy-manager)
- [Backup & restore](#backup--restore)
- [Managing NextOSP (the nwos CLI)](#managing-nextosp-the-nwos-cli)
- [Verify the installation](#verify-the-installation)
- [Troubleshooting](#troubleshooting)

## Requirements

| Component | Supported | Notes |
| --- | --- | --- |
| OS | Ubuntu 22.04 / 24.04 · Debian 11 / 12 / Trixie | Officially targeted by `requirements.txt` |
| Python | 3.10 – 3.14 | `python_requires >= 3.10` |
| PostgreSQL | 13 or newer | Minimum enforced by the server |
| Node / less | `node-less` (+ `npm`) | For CSS/asset compilation |
| wkhtmltopdf | 0.12.x | Required for PDF reports |

**Choose your path** — the native paths share steps 1–4:

- **[Path A — Local development](#path-a--local-development):** run from the
  checkout with auto-reload.
- **[Path B — Production (native)](#path-b--production-native):** dedicated
  user, systemd, nginx + TLS.
- **[Path C — Docker](#path-c--docker):** Compose stack (`db` + `web` + `cron`).
- **[Path D — Kubernetes (production)](#path-d--kubernetes-production):** web/cron
  Deployments, PostgreSQL, Ingress, and backup Jobs.

Put any deployment behind TLS with a [reverse proxy](#reverse-proxy-with-nginx-proxy-manager)
(Nginx Proxy Manager or plain nginx), and set up
[Backup & restore](#backup--restore) for production.

---

## Quick install (automated)

On a fresh Ubuntu/Debian host, the bundled **[`quick-install.sh`](quick-install.sh)**
does everything: detects the OS, installs prerequisites, asks a few questions in
a text (whiptail) menu, and deploys **either** a Docker stack — optionally
fronted by **Nginx Proxy Manager** for GUI-managed TLS — **or** a native systemd
service. It finishes by installing the [`nwos` CLI](#managing-nextosp-the-nwos-cli).

```bash
# From a checkout
sudo ./quick-install.sh

# Or straight from GitHub
curl -fsSL https://raw.githubusercontent.com/NextOSP/nwos/master/quick-install.sh | sudo bash
```

It's interactive by default. To run unattended, preset any `NWOS_*` variables
(secrets are auto-generated when omitted):

```bash
sudo NWOS_MODE=docker NWOS_WITH_NPM=yes NWOS_DOMAIN=erp.example.com \
     NWOS_APPS=sale,stock,account ./quick-install.sh
```

Want to understand or customize each step instead? Follow the manual paths below.

---

## 1. Install system packages

These packages provide the compilers and headers needed to build the Python
dependencies, plus PostgreSQL, Node/less, fonts, and wkhtmltopdf.

<details open>
<summary><strong>Ubuntu (22.04 / 24.04)</strong></summary>

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  git curl build-essential \
  python3 python3-dev python3-venv python3-pip \
  libpq-dev libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev \
  libjpeg-dev zlib1g-dev \
  node-less npm \
  postgresql postgresql-client \
  wkhtmltopdf \
  fonts-dejavu-core fonts-font-awesome fonts-roboto-unhinted fonts-inconsolata
```

</details>

<details>
<summary><strong>Debian (11 / 12 / Trixie)</strong></summary>

Run as `root` or with `sudo`. The package set is identical to Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  git curl build-essential \
  python3 python3-dev python3-venv python3-pip \
  libpq-dev libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev \
  libjpeg-dev zlib1g-dev \
  node-less npm \
  postgresql postgresql-client \
  wkhtmltopdf \
  fonts-dejavu-core fonts-font-awesome fonts-roboto-unhinted fonts-inconsolata
```

> **wkhtmltopdf on Debian:** the Debian-shipped build produces PDF reports with
> missing headers/footers (see [`debian/README.Debian`](debian/README.Debian)).
> For pixel-perfect reports, install the patched-Qt build from the
> [wkhtmltopdf releases](https://github.com/wkhtmltopdf/wkhtmltopdf/releases)
> matching your distro.

</details>

<details>
<summary><strong>Alternative: install runtime deps as distro packages</strong></summary>

If you prefer system-managed Python packages over a pip virtualenv, the repo
ships a helper that installs the exact runtime dependencies listed in
[`debian/control`](debian/control):

```bash
./setup/debinstall.sh --list   # preview the package set
sudo ./setup/debinstall.sh     # install them
```

This covers the `python3-*` runtime libraries only — you still need
`build-essential`, the `*-dev` headers, `wkhtmltopdf`, `node-less`, and
`postgresql` from the list above.

</details>

## 2. Set up PostgreSQL

NextOSP connects as its **own** database role (not `postgres`) that is allowed
to create databases.

```bash
# Start and enable the service
sudo systemctl enable --now postgresql

# Create a login role named "nwos" with CREATEDB privilege (prompts for a password)
sudo -u postgres createuser --createdb --pwprompt nwos
```

Remember the password you set — it goes into `db_password` in the config
(step 4). The database itself is created automatically by NextOSP on first run.

## 3. Get the source & create a virtualenv

```bash
git clone https://github.com/NextOSP/nwos.git
cd nwos

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

> Already have the checkout? Just `cd` into it and create the `venv` there. The
> bundled [`start.sh`](start.sh) expects the virtualenv at `./venv`.

## 4. Configure NextOSP

The server reads its config from `-c <file>`, or falls back to `~/.nwosrc` (and
the legacy `~/.nwos_serverrc`). The repo ships a working template at
[`nwos.conf`](nwos.conf). Copy and adapt it:

```bash
cp nwos.conf my.conf
```

```ini
[options]
; Where addons live (core + bundled apps)
addons_path = /path/to/nwos/addons,/path/to/nwos/nwos/addons
data_dir    = /path/to/nwos/data       ; filestore + sessions

; Database
db_host     = localhost
db_port     = 5432
db_user     = nwos
db_password = <the password from step 2>
db_name     = False                    ; False = allow selecting/creating DBs

; HTTP
http_port   = 8069                     ; built-in default is 7073; containers use 7073
logfile     = /path/to/nwos/logs/nwos.log
log_level   = info

; Master password for the database manager (set a strong one!)
admin_passwd = <strong-master-password>
```

Set a strong hashed `admin_passwd` instead of storing it in plaintext:

```bash
python3 -c "from passlib.context import CryptContext; \
print(CryptContext(['pbkdf2_sha512']).hash('choose-a-strong-password'))"
```

Paste the resulting `$pbkdf2-sha512$...` string as the `admin_passwd` value.

---

## Path A — Local development

With the virtualenv active and `nwos.conf` in place, the simplest launch is the
bundled script:

```bash
./start.sh          # activates ./venv and runs: nwos-bin -c nwos.conf
```

Or run the binary directly with extra flags:

```bash
# First run: create and initialize the database
./nwos-bin server -c nwos.conf -d nwos --init base --stop-after-init

# Day-to-day dev with auto-reload of Python/QWeb/XML
./nwos-bin server -c nwos.conf -d nwos --dev=reload,qweb,xml
```

Open **http://localhost:8069** and log in (default `admin` / `admin` on a fresh
database).

Useful commands:

```bash
./nwos-bin server -c nwos.conf -d nwos -i sale,stock,purchase   # install apps
./nwos-bin server -c nwos.conf -d nwos -u sale                  # upgrade a module
./nwos-bin shell  -c nwos.conf -d nwos                          # interactive shell
```

---

## Path B — Production (native)

Best-practice native deployment: dedicated user, code under `/opt/nwos`, data
under `/var/lib/nwos`, managed by systemd and fronted by nginx + TLS.

### B.1 Create a dedicated system user and directories

```bash
sudo useradd --system --home /var/lib/nwos --shell /usr/sbin/nologin nwos
sudo mkdir -p /opt/nwos /var/lib/nwos /var/log/nwos /etc/nwos

# Deploy the code (clone or rsync your checkout into /opt/nwos)
sudo git clone https://github.com/NextOSP/nwos.git /opt/nwos

# Virtualenv owned by the service user
sudo python3 -m venv /opt/nwos/venv
sudo /opt/nwos/venv/bin/pip install --upgrade pip wheel setuptools
sudo /opt/nwos/venv/bin/pip install -r /opt/nwos/requirements.txt

sudo chown -R nwos:nwos /opt/nwos /var/lib/nwos /var/log/nwos
```

### B.2 Production config

Create `/etc/nwos/nwos.conf` (owned by `nwos`, mode `640`):

```ini
[options]
addons_path      = /opt/nwos/addons,/opt/nwos/nwos/addons
data_dir         = /var/lib/nwos
logfile          = /var/log/nwos/nwos.log
log_level        = info

db_host          = localhost
db_port          = 5432
db_user          = nwos
db_password      = <db-password>
db_name          = nwos
db_maxconn       = 32

; Bind to localhost — nginx is the only thing that talks to the app
http_interface   = 127.0.0.1
http_port        = 8069
proxy_mode       = True

; Hardening
list_db          = False                 ; hide the database manager
admin_passwd     = <hashed-master-password>

; Multiprocessing (see the sizing table in docs/deployment.md)
workers          = 4
max_cron_threads = 2
```

```bash
sudo chown nwos:nwos /etc/nwos/nwos.conf && sudo chmod 640 /etc/nwos/nwos.conf
```

Initialize the database once (as the service user):

```bash
sudo -u nwos /opt/nwos/venv/bin/python /opt/nwos/nwos-bin \
  server -c /etc/nwos/nwos.conf -d nwos -i base --stop-after-init
```

> See the **Worker Sizing** and **Production Topology** tables in
> [`docs/deployment.md`](docs/deployment.md) for tuning `workers`,
> `max_cron_threads`, and `db_maxconn`.

### B.3 systemd service

Create `/etc/systemd/system/nwos.service`:

```ini
[Unit]
Description=NextOSP (nwos) server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=nwos
Group=nwos
ExecStart=/opt/nwos/venv/bin/python /opt/nwos/nwos-bin server -c /etc/nwos/nwos.conf
KillMode=mixed
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nwos.service
sudo systemctl status nwos.service
journalctl -u nwos.service -f          # follow logs
```

> The repo also ships a legacy LSB init script at [`debian/init`](debian/init);
> the systemd unit above is the recommended path on modern Ubuntu/Debian.

### B.4 nginx reverse proxy + TLS

Create `/etc/nginx/sites-available/nwos` and enable it. `proxy_mode = True`
(set above) makes NextOSP trust the forwarded headers below.

```nginx
upstream nwos {
    server 127.0.0.1:8069;
}

server {
    listen 80;
    server_name erp.example.com;

    # Long timeouts for reports/imports; large body for uploads
    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    client_max_body_size 100m;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    location / {
        proxy_pass http://nwos;
        proxy_redirect off;
    }

    # WebSocket / longpolling (live chat, notifications)
    location /websocket {
        proxy_pass http://nwos;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Cache static assets
    location ~* /web/static/ {
        proxy_pass http://nwos;
        proxy_cache_valid 200 90m;
        expires 864000;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/nwos /etc/nginx/sites-enabled/nwos
sudo nginx -t && sudo systemctl reload nginx

# Add TLS with Let's Encrypt (rewrites the server block to listen on 443)
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d erp.example.com
```

### B.5 Production hardening checklist

- Firewall so only nginx (80/443) is exposed; keep `8069` bound to `127.0.0.1`.
- Keep `list_db = False` and a strong hashed `admin_passwd` to lock the
  database manager.
- Store secrets outside git (config file mode `640`, owned by `nwos`).
- Schedule regular PostgreSQL **and** filestore (`/var/lib/nwos`) backups — see
  [`docs/deployment.md`](docs/deployment.md) and
  [`scripts/backup-compose.sh`](scripts/backup-compose.sh).
- Run module upgrades with `--stop-after-init` during maintenance windows, then
  restart the service.
- Keep staging and production databases separate.

---

## Path C — Docker

The stack is three services — `db` (PostgreSQL) + `web` (HTTP workers) + `cron`
(scheduler) — and the container defaults to port **7073**. You can run a
**prebuilt image** from the registry (no source checkout needed) or **build from
source**.

### C.1 Run the published image (no clone)

CI publishes the image to the **GitHub Container Registry (GHCR)** on every push
to `master`:

- `ghcr.io/nextosp/nwos:latest`
- `ghcr.io/nextosp/nwos:<commit-sha>` — pin this in production

The image is self-contained (code, addons, and a default `/etc/nwos/nwos.conf`
are baked in), so you only need a Compose file — no repository clone. Save this
as `docker-compose.yml` in an empty directory:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: nwos
      POSTGRES_USER: nwos
      POSTGRES_PASSWORD: nwos
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nwos -d nwos"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  web:
    image: ghcr.io/nextosp/nwos:latest      # or pin :<commit-sha>
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "7073:7073"
    command: ["server", "-c", "/etc/nwos/nwos.conf", "--max-cron-threads=0"]
    volumes:
      - nwos-data:/var/lib/nwos
    restart: unless-stopped

  cron:
    image: ghcr.io/nextosp/nwos:latest
    depends_on:
      db:
        condition: service_healthy
    command: ["server", "-c", "/etc/nwos/nwos.conf", "--workers=0", "--max-cron-threads=2"]
    volumes:
      - nwos-data:/var/lib/nwos
    restart: unless-stopped

volumes:
  db-data:
  nwos-data:
```

The `db` service is named `db` because the baked config uses `db_host = db` —
keep that name and the `web`/`cron` services resolve the database automatically
(no bind mounts required). Pull and start:

```bash
docker compose pull          # fetch the images from GHCR
docker compose up -d
docker compose run --rm web server -c /etc/nwos/nwos.conf -d nwos -i base --stop-after-init
```

<details>
<summary><strong>Authenticating to GHCR (private packages only)</strong></summary>

Public packages need no login. If the package is private, sign in with a
Personal Access Token that has the `read:packages` scope:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <github-username> --password-stdin
```

</details>

Open **http://localhost:7073**.

### C.2 Build from source

If you have the repository checked out, the bundled
[`docker-compose.yml`](docker-compose.yml) both **builds** the image and tags it
as `ghcr.io/nextosp/nwos:latest`, mounting [`docker/nwos.conf`](docker/nwos.conf)
so you can tweak config without rebuilding:

```bash
docker compose up --build -d
docker compose run --rm web server -c /etc/nwos/nwos.conf -d nwos -i base --stop-after-init
```

Override the image tag (e.g. to pull a pinned build instead of rebuilding) with
the `NWOS_IMAGE` variable:

```bash
NWOS_IMAGE=ghcr.io/nextosp/nwos:<commit-sha> docker compose up -d
```

> For the image internals and the web/cron service split, see
> [`docs/deployment.md`](docs/deployment.md).

---

## Path D — Kubernetes (production)

The [`k8s/`](k8s/) directory contains a production-oriented starter stack: a
`web` Deployment (HTTP workers, cron disabled), a `cron` Deployment (scheduler,
HTTP off), PostgreSQL, backup/restore Jobs, and an Ingress. Splitting web and
cron lets HTTP scale horizontally while exactly one scheduler runs.

### D.1 Build and push the image

```bash
docker build -t ghcr.io/nextosp/nwos:latest .
docker push  ghcr.io/nextosp/nwos:latest
```

Update the image reference, Ingress host (`nextosp.example.com`), and storage
classes in the manifests before applying — the defaults use `ReadWriteOnce`
volumes and an example hostname.

### D.2 Create the namespace and secrets

Keep secrets out of git — create them imperatively:

```bash
kubectl apply -f k8s/namespace.yaml

kubectl -n nextosp create secret generic nextosp-secret \
  --from-literal=db-user=nwos \
  --from-literal=db-password='change-me' \
  --from-literal=db-name=nwos \
  --from-literal=admin-password='change-me' \
  --dry-run=client -o yaml | kubectl apply -f -
```

### D.3 Apply the stack and initialize

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/web.yaml
kubectl apply -f k8s/cron.yaml
kubectl apply -f k8s/ingress.yaml

# Initialize the database once
kubectl -n nextosp exec deploy/nextosp-web -- \
  /opt/nwos/nwos-bin server -c /etc/nwos/nwos.conf -d nwos -i base --stop-after-init

# Watch the rollout
kubectl -n nextosp rollout status deploy/nextosp-web
kubectl -n nextosp get pods,svc,ingress
```

> **Multiple web replicas** must share the filestore (`/var/lib/nwos`) via a
> `ReadWriteMany` volume (NFS/EFS/CephFS) or object storage. With only
> `ReadWriteOnce`, keep `nextosp-web` at one replica.

For worker sizing, `db_maxconn` planning, TLS, and upgrade jobs, see the
**Production Topology**, **Worker Sizing**, and **Upgrades** sections of
[`docs/deployment.md`](docs/deployment.md).

---

## Reverse proxy with Nginx Proxy Manager

[Nginx Proxy Manager](https://nginxproxymanager.com/) (NPM) is a Docker-based
reverse proxy with a web UI and one-click Let's Encrypt certificates. It's a
good alternative to the hand-written nginx config in [Path B.4](#b4-nginx-reverse-proxy--tls)
when you'd rather manage TLS and hosts from a dashboard. It works the same way
for a native install (Path B) or a Docker install (Path C) — only the *forward
host and port* differ.

### 1. Run Nginx Proxy Manager

Skip this if you already run NPM. Otherwise, a minimal stack:

```yaml
# npm-compose.yml
services:
  npm:
    image: jc21/nginx-proxy-manager:latest
    restart: unless-stopped
    ports:
      - "80:80"       # HTTP (ACME challenges)
      - "443:443"     # HTTPS
      - "81:81"       # Admin UI
    volumes:
      - ./npm-data:/data
      - ./npm-letsencrypt:/etc/letsencrypt
    networks: [proxy]

networks:
  proxy:
    external: true
```

```bash
docker network create proxy          # shared network (once)
docker compose -f npm-compose.yml up -d
```

Open the admin UI at `http://<server>:81` and log in with the default
`admin@example.com` / `changeme` (you'll be forced to change it).

### 2. Make NextOSP reachable from NPM

NPM must be able to reach the NextOSP HTTP port. Pick the row that matches your
deployment:

| NextOSP runs as | Forward Hostname / IP | Forward Port |
| --- | --- | --- |
| Docker Compose (same `proxy` network) | `web` (the compose service name) | `7073` |
| Native on the same host as NPM | `host.docker.internal` (or the host LAN IP) | `8069` |
| Native on another server | that server's IP/hostname | `8069` |

<details>
<summary><strong>Docker Compose: join NextOSP to the shared network</strong></summary>

Add the external `proxy` network to the `web` service in `docker-compose.yml` so
NPM can resolve `web`. Keep the app port internal — you no longer need to publish
`7073` on the host:

```yaml
services:
  web:
    # ...existing config...
    networks: [default, proxy]

networks:
  proxy:
    external: true
```

Then `docker compose up -d`.

</details>

### 3. Set `proxy_mode` on NextOSP

Because NPM terminates TLS and forwards plain HTTP, NextOSP must trust the
forwarded headers. In `nwos.conf` (or `docker/nwos.conf`):

```ini
proxy_mode = True
```

Restart NextOSP after changing it.

### 4. Create the Proxy Host

In NPM: **Hosts → Proxy Hosts → Add Proxy Host**.

**Details tab**

- **Domain Names:** `erp.example.com`
- **Scheme:** `http`
- **Forward Hostname / IP** and **Forward Port:** from the table in step 2
- **Cache Assets:** optional
- **Block Common Exploits:** on
- **Websockets Support:** **on** (required — live chat, notifications, and the
  bus use the `/websocket` endpoint)

**Advanced tab** — paste custom config for large uploads/imports and long
report/backup requests (NPM already sends `Host`, `X-Forwarded-For`,
`X-Real-IP`, and `X-Forwarded-Proto`, which `proxy_mode` consumes):

```nginx
client_max_body_size 100m;
proxy_read_timeout 720s;
proxy_connect_timeout 720s;
proxy_send_timeout 720s;
```

**SSL tab**

- **SSL Certificate:** *Request a new SSL Certificate* (Let's Encrypt)
- **Force SSL:** on · **HTTP/2 Support:** on · **HSTS:** optional
- Enter your email and agree to the Let's Encrypt terms, then **Save**

Port 80 must be reachable from the internet for the certificate challenge to
succeed. Once saved, browse to `https://erp.example.com`.

### Other reverse proxies

- **Plain nginx** (native): see [Path B.4](#b4-nginx-reverse-proxy--tls) for a
  full server block.
- **Traefik / Caddy / Cloudflare Tunnel:** any proxy works — forward to the
  NextOSP HTTP port, enable WebSocket upgrades for `/websocket`, raise the body
  size and timeouts as above, and keep `proxy_mode = True`.

---

## Backup & restore

A complete backup is **both** the PostgreSQL database **and** the filestore
under `data_dir` (`/var/lib/nwos` in production). Take them close together so no
attachments are missed.

### Native (source install)

```bash
# Database — compressed custom-format dump
pg_dump -Fc --no-owner --no-acl -U nwos nwos > nwos-$(date -u +%Y%m%dT%H%M%SZ).dump

# Restore into a clean database (stop the service first)
sudo systemctl stop nwos.service
pg_restore --clean --if-exists --no-owner --no-acl -U nwos -d nwos nwos-<timestamp>.dump
sudo systemctl start nwos.service

# Filestore — snapshot or copy the data directory alongside the DB dump
sudo tar czf nwos-filestore-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /var/lib/nwos .
```

### Docker Compose

Helper scripts wrap `pg_dump`/`pg_restore` against the `db` service:

```bash
./scripts/backup-compose.sh                                  # writes backups/nwos-<timestamp>.dump

docker compose stop web
./scripts/restore-compose.sh backups/nwos-<timestamp>.dump
docker compose up -d web
```

### Kubernetes

A nightly `CronJob` and an on-demand restore `Job` are included:

```bash
kubectl apply -f k8s/backup-cronjob.yaml            # nightly pg_dump to a PVC

# Run a backup immediately
kubectl -n nextosp create job --from=cronjob/nextosp-postgres-backup backup-manual
kubectl -n nextosp logs job/backup-manual

# Restore: set BACKUP_FILE in k8s/restore-job.yaml, scale down, restore, scale up
kubectl -n nextosp scale deploy/nextosp-web  --replicas=0
kubectl -n nextosp scale deploy/nextosp-cron --replicas=0
kubectl apply -f k8s/restore-job.yaml
kubectl -n nextosp scale deploy/nextosp-web  --replicas=2
kubectl -n nextosp scale deploy/nextosp-cron --replicas=1
```

Back up the filestore with your storage provider's volume snapshots (or Velero /
restic). See [`docs/deployment.md`](docs/deployment.md) for the full backup,
restore, and upgrade procedures.

---

## Managing NextOSP (the `nwos` CLI)

`quick-install.sh` installs a **`nwos`** management command — in the spirit of
Frappe's `bench` — that wraps day-to-day operations for **both** Docker and
native deployments. It reads `/etc/nwos/nwosctl.env` (written by the installer)
to discover your layout, so the same commands work either way. Without the
installer, run it from a checkout as [`./scripts/nwosctl`](scripts/nwosctl).

| Command | What it does |
| --- | --- |
| `nwos start` · `stop` · `restart` | Control the server (systemd or compose) |
| `nwos status` | Service / container status |
| `nwos logs [-f]` | Show or follow logs |
| `nwos backup [dir]` | Dump database **and** filestore (default `/var/backups/nwos`) |
| `nwos restore <dump> [fs.tgz]` | Restore a database dump and optional filestore |
| `nwos update` | Pull new code/image + dependencies, then restart |
| `nwos upgrade [modules\|all]` | Apply module/schema upgrades (like `bench migrate`) |
| `nwos install-app <mods>` | Install modules, e.g. `sale,stock,account` |
| `nwos initdb` | Initialize a fresh database with `base` |
| `nwos shell` · `psql` | NextOSP Python shell · database shell |
| `nwos config` | Edit the deployment config file |
| `nwos version` | Show deployment info and version |

Examples:

```bash
nwos backup                        # → /var/backups/nwos/nwos-db-*.dump (+ filestore .tgz)
nwos update && nwos upgrade all    # pull latest, then migrate all modules
nwos install-app crm,project
nwos logs -f
```

---

## Verify the installation

1. **Service is up** (production): `systemctl status nwos.service` shows
   `active (running)`.
2. **Port is listening:** `curl -I http://localhost:8069/web/login` (or `7073`
   for Docker) returns `200`/`303`.
3. **Web login:** open the URL in a browser and log in.
4. **PDF reports work** (confirms wkhtmltopdf): open any record and print a
   report to PDF, e.g. a sales order.
5. **Logs are clean:** `tail -f /var/log/nwos/nwos.log` (or
   `journalctl -u nwos.service -f`) shows no tracebacks.

## Troubleshooting

<details>
<summary><strong>PDF reports are blank or missing headers/footers</strong></summary>

wkhtmltopdf must be installed and on `PATH`. On Debian the shipped build has a
known header/footer bug — install the patched-Qt release (see
[`debian/README.Debian`](debian/README.Debian)). Verify with
`wkhtmltopdf --version` (should mention `(with patched qt)`).

</details>

<details>
<summary><strong>PostgreSQL: "peer authentication failed" / "role does not exist"</strong></summary>

NextOSP connects over TCP as the `nwos` role. Ensure the role exists
(`sudo -u postgres createuser --createdb --pwprompt nwos`), that `db_host`,
`db_user`, and `db_password` in the config match, and that `pg_hba.conf` allows
`md5`/`scram-sha-256` for `127.0.0.1`.

</details>

<details>
<summary><strong>Address already in use / port 8069 busy</strong></summary>

Another process (or a second NextOSP) holds the port. Find it with
`sudo ss -ltnp | grep 8069` and stop it, or change `http_port` in the config.

</details>

<details>
<summary><strong>Assets/CSS look broken</strong></summary>

`node-less` (and `npm`) must be installed so the server can compile assets.
Reinstall the package, then rebuild assets by upgrading the web module:
`./nwos-bin server -c nwos.conf -d nwos -u web --stop-after-init`.

</details>

<details>
<summary><strong>Permission denied writing to the data directory</strong></summary>

The `data_dir` (filestore) must be writable by the user running the server. In
production: `sudo chown -R nwos:nwos /var/lib/nwos`.

</details>
