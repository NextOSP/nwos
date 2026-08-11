# Docker Compose environment

Runs the whole stack: Postgres + NWOS web workers + a separate cron worker.

## Ports

| Port | Service | Purpose |
| ---- | ------- | ------- |
| 9600 | `web`   | HTTP — this is what Nginx Proxy Manager forwards to |
| 9601 | `web`   | Websocket / longpolling (gevent worker) |
| 9632 | `db`    | Postgres (host-exposed for convenience; remove the `ports:` block to close it) |

All three are overridable in `.env` (`NWOS_HTTP_PORT`, `NWOS_GEVENT_PORT`, `POSTGRES_HOST_PORT`).
The *container-internal* ports stay 9600/9601 and are set in `docker/nwos.conf`.

## First run — server (uses the CI-built image)

```bash
cp .env.example .env          # adjust ports/credentials if needed
$EDITOR docker/nwos.conf      # change admin_passwd

echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
docker compose pull
docker compose up -d
docker compose logs -f web
```

## First run — local dev (builds from source)

```bash
cp .env.example .env
sed -i '' 's|^NWOS_IMAGE=.*|NWOS_IMAGE=nwos:local|' .env
docker compose build
docker compose up -d
```

Then open `http://<host>:9600` and create a database from the manager.

To create the database non-interactively instead:

```bash
docker compose run --rm web server -c /etc/nwos/nwos.conf \
    -d nwos --without-demo=all -i base --stop-after-init
```

## Common operations

```bash
# install / upgrade a module
docker compose run --rm web server -c /etc/nwos/nwos.conf -d nwos -u nextbot_workspace --stop-after-init
docker compose restart web cron

# shell
docker compose run --rm web shell -c /etc/nwos/nwos.conf -d nwos

# psql
docker compose exec db psql -U nwos -d nwos

# backup / restore the filestore + db
docker compose exec db pg_dump -U nwos -Fc nwos > nwos.dump
docker run --rm -v flectra_nwos-data:/data -v "$PWD:/out" alpine tar czf /out/filestore.tgz -C /data .

# deploy the latest CI image by hand (same thing the CD job does)
docker compose pull && docker compose up -d --no-build

# rebuild locally after code changes
docker compose build && docker compose up -d
```

## Self-updating server (pull-based)

`scripts/nwos-selfupdate.sh` on a systemd timer polls GHCR and rolls out a new
image only when the digest changes. No inbound SSH, no GitHub secrets — the
server pulls rather than CI pushing.

On a change it: backs up the database → stops `web`/`cron` → runs `-u all` →
starts the stack → prunes old images. When the digest is unchanged it exits 0
immediately, so the timer stays green.

From the repository root:

```bash
sudo sh scripts/install-selfupdate.sh    # generates the unit for THIS checkout

systemctl list-timers nwos-selfupdate    # when it next runs
journalctl -u nwos-selfupdate -f         # watch a rollout
sudo systemctl start nwos-selfupdate     # force a check now
```

The installer writes `WorkingDirectory`, `NWOS_DIR`, and `User` from the actual
checkout path and owner, so it works whether you cloned to `/root/nwos`,
`/home/ubuntu/nwos`, or anywhere else. Re-run it after moving the checkout.
Do not copy `scripts/systemd/nwos-selfupdate.service` by hand — it is a template
with placeholder paths. Interval is `OnUnitActiveSec=10min` in the timer.

The script `git reset --hard`s the checkout so compose/config changes ship with
the image — **but only when the working tree is clean**. Keep server-specific
settings in the two untracked files (`.env` and `docker/nwos.local.conf`) rather
than editing tracked ones, or the update will skip the checkout refresh and warn.

## CI/CD

`.github/workflows/ci.yml` runs on push to `master`:

1. **sanity** — deps install, CLI starts, YAML/shell/README checks
2. **container** — builds and pushes `ghcr.io/nextosp/nwos:latest` and `:<sha>`
3. **deploy** — SSHes to the server, resets the checkout to the built SHA,
   `docker compose pull && up -d`, runs `-u all`, then health-checks over HTTPS.
   Skipped automatically when `DEPLOY_HOST` is unset — leave it that way if you
   use the pull-based self-update timer above, and pick one or the other rather
   than running both.

Required repository secrets:

| Secret | Value |
| ------ | ----- |
| `DEPLOY_HOST` | server IP / hostname |
| `DEPLOY_USER` | ssh user (e.g. `ubuntu`) |
| `DEPLOY_SSH_KEY` | private key whose public half is in the server's `authorized_keys` |
| `GHCR_READ_TOKEN` | GitHub PAT with `read:packages`, used by the server to pull |
| `DEPLOY_HEALTH_HOST` | public hostname the health check curls (the NPM domain) |

Server prerequisites: Docker + compose plugin installed, the repo cloned to
`~/nwos` (or set `DEPLOY_PATH`), and `.env` + `docker/nwos.conf` already
configured. Those two files are **not** in git, so they survive `git reset --hard`.

The deploy runs `-u all`, which upgrades every installed module. It is the safe
default but it is slow on a large database and it takes the site down for the
duration. Narrow it to the modules you actually changed if that matters.

## Nginx Proxy Manager

`proxy_mode = True` is already set in `docker/nwos.conf`, so NPM must send
`X-Forwarded-For` / `X-Forwarded-Proto` (it does by default).

**Details tab**

- Scheme: `http`
- Forward Hostname / IP: the Docker host IP (or `web` if NPM shares this compose network — see the `networks:` note at the bottom of `docker-compose.yml`)
- Forward Port: `9600`
- Websockets Support: **on**
- Block Common Exploits: on

**Advanced tab** — route the websocket to the gevent port and lift the upload limit:

```nginx
client_max_body_size 500m;
proxy_read_timeout 720s;
proxy_connect_timeout 720s;
proxy_send_timeout 720s;

location /websocket {
    proxy_pass http://<host-ip>:9601;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location / {
    proxy_pass http://<host-ip>:9600;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_redirect off;
}
```

Replace `<host-ip>` with the same value used in the Details tab. Getting the
`/websocket` block right is what makes NextBot's realtime streaming and Discuss
work — without it the bus falls back to polling.

## Notes

- `web` runs with `--max-cron-threads=0` and `cron` with `--workers=0 --no-http`,
  so scheduled actions never compete with HTTP workers.
- `web` and `cron` share the `nwos-data` volume (the filestore). Keep it that way.
- Worker count is `workers = 4` in `docker/nwos.conf`; the rule of thumb is
  `(2 × cores) + 1`. Adjust for your host.
- The image uses Debian's `wkhtmltopdf` (unpatched Qt), so PDF report headers and
  footers render without page-number support. Swap in a patched 0.12.6.1 build in
  the Dockerfile if you need those.
