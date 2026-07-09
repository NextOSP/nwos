# Deploying NextOSP

This guide covers container, Docker Compose, and Kubernetes deployment paths for
NextOSP. The examples are intentionally plain YAML so they work as a starting
point for most environments.

## Container Image

Build the image locally:

```bash
docker build -t nextosp/nwos:local .
```

Run it against an existing PostgreSQL server:

```bash
docker run --rm -p 7073:7073 \
  -e NWOS_DB_HOST=host.docker.internal \
  -e NWOS_DB_PORT=5432 \
  -e NWOS_DB_USER=nwos \
  -v "$PWD/docker/nwos.conf:/etc/nwos/nwos.conf:ro" \
  -v nextosp-data:/var/lib/nwos \
  nextosp/nwos:local
```

The image starts `nwos-bin server -c /etc/nwos/nwos.conf` by default. Override
the command to initialize or update modules:

```bash
docker run --rm nextosp/nwos:local server -c /etc/nwos/nwos.conf -i base --stop-after-init
docker run --rm nextosp/nwos:local server -c /etc/nwos/nwos.conf -u sale --stop-after-init
```

## Docker Compose

Start PostgreSQL and NextOSP together:

```bash
docker compose up --build
```

The Compose stack runs three services:

- `db`: PostgreSQL.
- `web`: HTTP workers with cron disabled.
- `cron`: background scheduler with HTTP exposed only inside the Compose
  network.

Open:

```text
http://localhost:7073
```

Initialize the database on first run:

```bash
docker compose run --rm web server -c /etc/nwos/nwos.conf -d nwos -i base --stop-after-init
```

Install common business apps:

```bash
docker compose run --rm web server -c /etc/nwos/nwos.conf -d nwos \
  -i sale,stock,purchase,account --stop-after-init
```

Back up the database:

```bash
./scripts/backup-compose.sh
```

Restore into a fresh database:

```bash
./scripts/restore-compose.sh backups/nwos-YYYYMMDDTHHMMSSZ.dump
```

## Kubernetes

The `k8s/` directory contains a starter production layout:

- `namespace.yaml`
- `secret.yaml`
- `configmap.yaml`
- `postgres.yaml`
- `web.yaml`
- `cron.yaml`
- `backup-cronjob.yaml`
- `restore-job.yaml`
- `ingress.yaml`

Build and push an image:

```bash
docker build -t ghcr.io/nextosp/nwos:latest .
docker push ghcr.io/nextosp/nwos:latest
```

Update secrets before applying manifests:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl -n nextosp create secret generic nextosp-secret \
  --from-literal=db-user=nwos \
  --from-literal=db-password='change-me' \
  --from-literal=db-name=nwos \
  --from-literal=admin-password='change-me' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Apply the stack:

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/web.yaml
kubectl apply -f k8s/cron.yaml
kubectl apply -f k8s/backup-cronjob.yaml
kubectl apply -f k8s/ingress.yaml
```

Initialize the database:

```bash
kubectl -n nextosp exec deploy/nextosp-web -- \
  /opt/nwos/nwos-bin server -c /etc/nwos/nwos.conf -d nwos -i base --stop-after-init
```

Watch rollout status:

```bash
kubectl -n nextosp rollout status deploy/nextosp-web
kubectl -n nextosp rollout status deploy/nextosp-cron
kubectl -n nextosp get pods,svc,ingress
```

## Production Topology

Recommended production topology:

- `nextosp-web`: HTTP workers only, `--max-cron-threads=0`.
- `nextosp-cron`: scheduled/background jobs, `--workers=0 --max-cron-threads=2`.
- PostgreSQL: managed database service or a dedicated StatefulSet for smaller
  deployments.
- Filestore: persistent volume mounted at `/var/lib/nwos`.
- Ingress/load balancer: TLS termination, request size limits, and long request
  timeouts.
- Backup job: nightly PostgreSQL custom-format dump plus a separate filestore
  backup if you use local persistent volumes.

Why split web and cron:

- HTTP latency is not affected by long cron jobs.
- Cron concurrency can be controlled independently.
- Web replicas can scale horizontally while keeping exactly one cron scheduler.
- Maintenance and module upgrades are easier to run as one-off jobs.

If you run more than one web replica, the filestore must be shared by every web
and cron pod. Use a `ReadWriteMany` storage class, NFS, EFS, CephFS, or another
shared volume solution. If your cluster only provides `ReadWriteOnce`, keep web
replicas at `1` or move attachments to a shared object-storage integration.

## Worker Sizing

Start conservatively and measure memory:

| Workload | Web replicas | `workers` per web pod | Cron replicas | `max_cron_threads` |
| --- | ---: | ---: | ---: | ---: |
| Small team | 1 | 2 | 1 | 1 |
| Normal production | 2 | 4 | 1 | 2 |
| Heavy reporting/imports | 3+ | 4-8 | 1 | 2-4 |

Rules of thumb:

- Give each worker roughly 512 MiB to 1 GiB of memory, depending on installed
  apps and report volume.
- Keep cron replicas at `1` unless you have verified scheduler behavior for
  your workload.
- Raise `db_maxconn` when increasing total worker count.
- Keep `proxy_mode = True` behind ingress or a load balancer.
- Run upgrades with `--stop-after-init` in a one-off job, not in normal web pods.

Connection planning:

```text
db_maxconn >= (web_replicas * workers_per_web) + cron_threads + maintenance_jobs + margin
```

For example, two web pods with four workers each and one cron pod with two cron
threads should start around `db_maxconn = 32` or higher.

## Backup And Restore

Backups must include both PostgreSQL and the filestore.

### PostgreSQL on Docker Compose

Create a compressed custom-format database backup:

```bash
./scripts/backup-compose.sh
```

Restore:

```bash
docker compose stop web
./scripts/restore-compose.sh backups/nwos-YYYYMMDDTHHMMSSZ.dump
docker compose up -d web
```

### PostgreSQL on Kubernetes

Create the scheduled backup job:

```bash
kubectl apply -f k8s/backup-cronjob.yaml
```

Run a backup immediately:

```bash
kubectl -n nextosp create job --from=cronjob/nextosp-postgres-backup nextosp-postgres-backup-manual
kubectl -n nextosp logs job/nextosp-postgres-backup-manual
```

Restore from an existing dump on the backup volume:

1. Edit `k8s/restore-job.yaml` and set `BACKUP_FILE`.
2. Scale web and cron down:

```bash
kubectl -n nextosp scale deploy/nextosp-web --replicas=0
kubectl -n nextosp scale deploy/nextosp-cron --replicas=0
```

3. Run restore:

```bash
kubectl apply -f k8s/restore-job.yaml
kubectl -n nextosp logs job/nextosp-postgres-restore
```

4. Start the application:

```bash
kubectl -n nextosp scale deploy/nextosp-web --replicas=2
kubectl -n nextosp scale deploy/nextosp-cron --replicas=1
```

### Filestore

The filestore lives under `/var/lib/nwos`. Back it up with your storage
provider snapshot mechanism, Velero, restic, rsync, or a CSI volume snapshot.
Database and filestore backups should be taken close together to avoid missing
attachments.

## Upgrades

For a module update:

```bash
kubectl -n nextosp exec deploy/nextosp-web -- \
  /opt/nwos/nwos-bin server -c /etc/nwos/nwos.conf -d nwos -u sale,stock --stop-after-init
```

For safer production upgrades, create a one-off Job using the same image and
configuration as `nextosp-web`, then roll web and cron after it succeeds.

## Production Checklist

- Use an external managed PostgreSQL service for production when possible.
- Keep `/var/lib/nwos` on persistent storage; it stores filestore data.
- Set `proxy_mode = True` when running behind an ingress, load balancer, or
  reverse proxy.
- Increase `workers`, CPU, and memory based on traffic and installed apps.
- Store secrets in a cluster secret manager instead of committing them to Git.
- Terminate TLS at the ingress or load balancer.
- Schedule regular PostgreSQL and filestore backups.
- Keep staging and production databases separate.
- Run module updates with `--stop-after-init` during maintenance windows.
- Monitor pod restarts, request latency, database connections, disk usage, and
  backup job success.
- Test restore procedures before relying on backups.
