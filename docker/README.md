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

## First run

```bash
cp .env.example .env          # adjust ports/credentials if needed
$EDITOR docker/nwos.conf      # change admin_passwd
docker compose build
docker compose up -d
docker compose logs -f web
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

# rebuild after code changes
docker compose build && docker compose up -d
```

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
