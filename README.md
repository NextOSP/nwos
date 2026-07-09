# NextOSP

[![CI](https://github.com/NextOSP/nwos/actions/workflows/ci.yml/badge.svg)](https://github.com/NextOSP/nwos/actions/workflows/ci.yml)

NextOSP is an open-source ERP and CRM platform for running business applications
from one modular server. It includes apps for accounting, inventory, sales,
purchasing, projects, marketing, help desk, point of sale, websites, and more.

The platform is built around a Python server, PostgreSQL database, web client,
module system, report engine, background jobs, and HTTP/XML-RPC integration
interfaces.

NextOSP is a fork of [Flectra](https://gitlab.com/flectra-hq/flectra), which is
itself a fork of [Odoo](https://github.com/odoo/odoo). See
[Credits](#credits) for details.

![All Apps dashboard](docs/readme/all-app.png)

## Highlights

### NextBot — get work done by chatting

NextBot lives in Discuss and turns plain-language requests into real business
records. Ask it to prepare a quotation and it drafts one, waits for your
confirmation (`ok`, `confirm`, or `/clear` to cancel), then creates the sales
order and links straight back to it — no form-hopping required.

![NextBot drafting and creating a quotation from chat](docs/readme/chatbot.png)

### Stock Requests — request, approve, purchase

Internal users request items for stock, office, project, or manufacturing.
Each request flows through **Draft → To Approve → Approved → Purchased**, with a
configurable self-approval threshold. Once approved, a buyer clicks *Generate
Purchase* and every line is routed through the product's own routes
(Buy / Manufacture / Transfer), feeding replenishment and RFQs automatically.

![Stock Requests list with status pipeline](docs/readme/stock-request.png)

The request form tracks the full approval and purchasing history in the chatter,
and surfaces the linked purchases and receipts right from the header.

![Stock Request detail with approval flow and chatter](docs/readme/detail.png)

## Installation Guide

### Requirements

- Python 3.10 through 3.14
- PostgreSQL 13 or newer
- A Python virtual environment for local development
- System libraries required by dependencies such as `lxml`, `Pillow`, and
  `psycopg2`
- `wkhtmltopdf` for PDF report generation
- Node.js and npm are useful when working on web assets and JavaScript tests

### 1. Clone the repository

```bash
git clone https://github.com/NextOSP/nwos.git
cd nwos
```

### 2. Install system packages

On macOS with Homebrew:

```bash
brew install python@3.10 postgresql wkhtmltopdf node
```

On Debian/Ubuntu:

```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-dev build-essential \
    libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev libjpeg-dev \
    zlib1g-dev libpq-dev postgresql wkhtmltopdf nodejs npm
```

### 3. Create a Python environment

```bash
python3.10 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

### 4. Create a PostgreSQL user and database

For local development, create a database user that can create databases:

```bash
createuser --createdb --pwprompt nwos
createdb --owner=nwos nwos
```

If you already use your operating-system PostgreSQL user, you can create only
the database:

```bash
createdb nwos
```

### 5. Create a local configuration file

Create `nwos.local.conf` for machine-specific settings:

```ini
[options]
addons_path = addons,nwos/addons
data_dir = data
db_host = localhost
db_port = 5432
db_user = nwos
db_password = change-me
db_name = nwos
http_port = 7073
logfile = logs/nwos.log
```

Do not commit local configuration files with real passwords.

### 6. Initialize the database

```bash
./nwos-bin server -c nwos.local.conf -i base --stop-after-init
```

### 7. Start the server

```bash
./nwos-bin server -c nwos.local.conf
```

Open the web client at:

```text
http://localhost:7073
```

The default master password is configured in your local config. Change it before
using a shared or public environment.

### 8. Install business apps

```bash
./nwos-bin server -c nwos.local.conf -i sale,stock,purchase,account
```

To update installed modules after pulling code changes:

```bash
./nwos-bin server -c nwos.local.conf -u sale,stock,purchase,account --stop-after-init
```

## Container Deployment

NextOSP includes a production-oriented `Dockerfile`, a local
`docker-compose.yml`, and starter Kubernetes manifests in `k8s/`.

Build the image:

```bash
docker build -t nextosp/nwos:local .
```

Run PostgreSQL and NextOSP locally with Docker Compose:

```bash
docker compose up --build
```

Initialize the Compose database:

```bash
docker compose run --rm web server -c /etc/nwos/nwos.conf -d nwos -i base --stop-after-init
```

Deploy the starter Kubernetes stack:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/web.yaml
kubectl apply -f k8s/cron.yaml
kubectl apply -f k8s/backup-cronjob.yaml
kubectl apply -f k8s/ingress.yaml
```

Before using Kubernetes in production, change secrets, image names, ingress
hostnames, storage classes, and resource sizes. See
[docs/deployment.md](docs/deployment.md) for container, Compose, Kubernetes,
backup, and production notes.

## Configuration

Most runtime options can be provided on the command line or in an INI-style
configuration file:

```ini
[options]
addons_path = addons,nwos/addons
data_dir = data
db_host = localhost
db_port = 5432
db_user = nwos
db_password = nwos
http_port = 7073
```

Start with a configuration file by passing `-c`:

```bash
./nwos-bin server -c nwos.conf
```

Do not commit production secrets or environment-specific paths.

## Troubleshooting

- `psycopg2` build errors usually mean `libpq-dev` or PostgreSQL headers are
  missing.
- `lxml` build errors usually mean `libxml2-dev` and `libxslt1-dev` are
  missing.
- If the server cannot connect to PostgreSQL, check `db_host`, `db_port`,
  `db_user`, and `db_password` in the config file.
- If port `7073` is already used, change `http_port` in the config file.
- If PDFs do not render, verify that `wkhtmltopdf` is installed and available
  on `PATH`.

## Common Development Tasks

Install or update modules in a database:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i sale,stock
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u sale,stock
```

Run with developer reload helpers:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos --dev=reload,qweb,xml
```

Create a new addon skeleton:

```bash
./nwos-bin scaffold my_module addons
```

List available commands:

```bash
./nwos-bin --help
```

## Testing

Run tests for installed modules:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos_test --test-enable
```

Run a targeted test selection:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos_test --test-tags /account
```

Both `--test-enable` and `--test-tags` imply `--stop-after-init`.

## Repository Layout

- `nwos/`: core server, ORM, services, tools, and CLI commands
- `nwos/addons/`: server-wide and core technical addons
- `addons/`: business and application addons
- `setup/`: packaging and service entry points
- `doc/`: contributor and legal documentation
- `migration/`: migration planning and support material

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines.

Security issues should be reported privately as described in
[SECURITY.md](SECURITY.md).

## Credits

NextOSP builds on the work of the open-source ERP community:

- [Odoo](https://github.com/odoo/odoo) — the original ERP/CRM platform on which
  this lineage is based.
- [Flectra](https://gitlab.com/flectra-hq/flectra) — the community fork of Odoo
  that NextOSP is derived from.

NextOSP is an independent project and is not affiliated with, sponsored by, or
endorsed by Odoo S.A. or the Flectra project. "Odoo" and "Flectra" are the
trademarks of their respective owners.

## License

NextOSP is distributed under the LGPL-3 license. See [LICENSE](LICENSE) for the
full license text.
