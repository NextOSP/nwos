# NextOSP

NextOSP is an open-source ERP and CRM platform for running business applications
from one modular server. It includes apps for accounting, inventory, sales,
purchasing, projects, marketing, help desk, point of sale, websites, and more.

The platform is built around a Python server, PostgreSQL database, web client,
module system, report engine, background jobs, and HTTP/XML-RPC integration
interfaces.

## Requirements

- Python 3.10 through 3.14
- PostgreSQL 13 or newer
- A Python virtual environment for local development
- System libraries required by dependencies such as `lxml`, `Pillow`, and
  `psycopg2`

## Quick Start

From a source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i base
```

Then open the web client at:

```text
http://localhost:7073
```

If PostgreSQL requires explicit credentials, add `--db_user`, `--db_password`,
`--db_host`, and `--db_port` to the server command.

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

## License

NextOSP is distributed under the LGPL-3 license. See [LICENSE](LICENSE) for the
full license text.
