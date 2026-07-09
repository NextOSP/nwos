# Daily Backup & Easy Restore (Standard)

Turnkey daily backup of the **whole** Flectra instance (SQL database **and** the
entire filestore / attachments) with a one-click in-app restore.

## What it does on install

- Creates a **Daily Local Backup** config for the current database (`zip` format,
  which bundles `dump.sql` + `manifest.json` + the whole `filestore/`).
- Creates a **Daily S3 Backup** config for the same database — inactive in
  practice until you fill the S3 credentials.
- Enables the daily **Scheduled Action** *Backup : Automatic Database Backup*.

Backups keep 30 days by default (`auto_remove`). Local backups are written to
`<data_dir>/backups/<dbname>/`.

## Configure

**Settings → Technical → Automatic Database Backup → Backup Configuration**
(requires developer mode). Open *Daily S3 Backup* and enter Bucket, Region,
Access Key and Secret Key to activate off-site backups. Adjust the schedule under
**Settings → Technical → Scheduled Actions**.

## Restore (in-app wizard)

**Settings → Technical → Automatic Database Backup → Restore Backup**

1. Pick the **Backup Source** (the Local or S3 config) — the most recent backup
   is preselected and the full list is shown for reference.
2. Enter **Restore As** — the name of a *new* database to create.
3. Enter the **Master Password** and click **Restore**.

The database and filestore are restored together into the new database. The
running database is never overwritten. Open the restored database from the
database selector.

## Restore (manual fallback via Database Manager)

Any `zip` produced here can also be restored with Flectra's built-in manager:

1. Download the `zip` from the destination (S3 bucket or the local backups folder).
2. Go to `/web/database/manager`, click **Restore Database**, upload the file,
   provide the master password and a new database name, then **Continue**.

## Requirements

- Database management must be enabled (default). If the server runs with
  `list_db = False`, both backup and restore are disabled by the framework.
- S3 backups require the `boto3` library: `pip install boto3`.

Setup
-----

Install this addon from a configured source checkout:

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb nwos
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i auto_database_backup_default
```

To install it in an existing database, use Apps in the web client or run:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -i auto_database_backup_default
```

After changing this addon, update it with:

```bash
./nwos-bin server --addons-path=addons,nwos/addons -d nwos -u auto_database_backup_default
```

Some addons depend on other applications or external services. Install any
missing dependencies shown by the module loader, then configure the feature from
the relevant Settings menu in the web client.

